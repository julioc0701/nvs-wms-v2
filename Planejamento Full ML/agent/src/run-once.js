import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { launchBrowser, newMlContext } from './browser.js';
import { config } from './config.js';
import { ensureAgentDirs, timestampSlug, writeJson } from './fs-utils.js';
import { getPlanningSummary, waitForPlanningPage } from './ml-page.js';
import { logsDir, screenshotsDir, sessionPath } from './paths.js';

const units = Number(process.env.ML_TEST_UNITS || 200);
const shouldSavePlan = String(process.env.ML_SAVE_PLAN || 'false').toLowerCase() === 'true';
const unitsStrategy = process.env.ML_UNITS_STRATEGY || 'fixed';

function parseMlNumber(value) {
  if (!value) return null;
  return Number(String(value).replace(/\./g, '').replace(',', '.'));
}

function parseProductCalculations(pageText) {
  return pageText
    .split(/(?=Código ML:)/)
    .slice(1)
    .map(chunk => {
      const beforeInput = chunk.split(/\nunidades/i)[0] || chunk;
      const unitMatchesBeforeInput = [...beforeInput.matchAll(/(\d[\d.]*)\s+un\./g)];
      const code = chunk.match(/Código ML:\s*([A-Z0-9]+)/)?.[1] || null;
      const lines = chunk
        .split('\n')
        .map(line => line.trim())
        .filter(Boolean);
      const title = lines.find((line, index) => index > 4 && /^Venda por/i.test(lines[index + 1] || '')) || null;
      const sales = parseMlNumber(unitMatchesBeforeInput[0]?.[1]);
      const readyAndInbound = parseMlNumber(
        chunk.match(/(\d[\d.]*)\s+un\.\s*\nAptas\s+/)?.[1] || unitMatchesBeforeInput[1]?.[1],
      );
      const targetWithPercent = sales == null ? null : Math.ceil(sales * 1.2);
      const rawUnits =
        targetWithPercent == null || readyAndInbound == null ? null : targetWithPercent - readyAndInbound;
      const appliedUnits = rawUnits == null ? null : Math.max(1, rawUnits);

      return {
        code,
        title,
        salesLast30Days: sales,
        readyAndInbound,
        targetWithPercent,
        rawUnits,
        appliedUnits,
      };
    });
}

await ensureAgentDirs();

if (!existsSync(sessionPath)) {
  console.error('Sessao nao encontrada. Rode primeiro: npm run ml:login');
  process.exit(1);
}

if (unitsStrategy !== 'fixed' && unitsStrategy !== 'formula') {
  console.error('ML_UNITS_STRATEGY precisa ser fixed ou formula.');
  process.exit(1);
}

if (unitsStrategy === 'fixed' && (!Number.isInteger(units) || units <= 0)) {
  console.error('ML_TEST_UNITS precisa ser um numero inteiro positivo.');
  process.exit(1);
}

const browser = await launchBrowser({ headless: config.headless });
const context = await newMlContext(browser);
const page = await context.newPage();
const startedAt = new Date();
const slug = timestampSlug(startedAt);

try {
  await page.goto(config.mlPlanningUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });

  const status = await waitForPlanningPage(page);
  if (status !== 'planning') {
    throw new Error(`Pagina de planejamento nao carregou. Status: ${status}. URL: ${page.url()}`);
  }

  await page.waitForTimeout(1500);

  await page.keyboard.press('Escape').catch(() => {});
  await page.locator('.andes-modal__close-button').first().click({ timeout: 3000 }).catch(() => {});
  await page
    .locator('button[aria-label*="fechar" i], button[aria-label*="close" i]')
    .first()
    .click({ timeout: 3000 })
    .catch(() => {});
  await page
    .getByRole('button', { name: /Cerrar|Fechar o assistente/i })
    .first()
    .click({ timeout: 3000 })
    .catch(() => {});
  await page.waitForTimeout(3000);

  for (let step = 0; step < 5; step += 1) {
    const onboardingButton = page
      .getByRole('button', { name: /Próximo|Siguiente|Finalizar|Entendi|Concluir|Fechar/i })
      .first();
    const visible = await onboardingButton.isVisible().catch(() => false);
    if (!visible) break;
    await onboardingButton.click();
    await page.waitForTimeout(700);
  }

  await page.locator('text=/Código ML:/i').first().waitFor({ timeout: 15000 });

  const productCalculations = parseProductCalculations(await page.evaluate(() => document.body.innerText));
  const productCodes = page.locator('text=/Código ML:/i');
  const productCount = await productCodes.count();
  let filledFields = 0;
  const appliedRows = [];

  for (let index = 0; index < productCount; index += 1) {
    const code = productCodes.nth(index);
    await code.scrollIntoViewIfNeeded();
    await page.waitForTimeout(120);

    const box = await code.boundingBox();
    if (!box) continue;

    const x = Math.min(box.x + 520, 760);
    const y = Math.min(Math.max(box.y + 34, 120), 630);
    const calculatedUnits =
      unitsStrategy === 'formula' ? productCalculations[index]?.appliedUnits : units;

    if (!Number.isInteger(calculatedUnits) || calculatedUnits < 0) {
      appliedRows.push({
        index,
        skipped: true,
        reason: 'calculo_indisponivel',
        calculation: productCalculations[index] || null,
      });
      continue;
    }

    await page.mouse.click(x, y);
    await page.waitForTimeout(80);
    await page.keyboard.press('Meta+A').catch(() => {});
    await page.keyboard.type(String(calculatedUnits), { delay: 10 });
    await page.keyboard.press('Tab').catch(() => {});
    filledFields += 1;
    appliedRows.push({
      index,
      value: calculatedUnits,
      calculation: productCalculations[index] || null,
    });
    await page.waitForTimeout(120);
  }

  const fillResult = {
    filledFields,
    values: [],
  };

  await page.waitForTimeout(3500);

  const summary = await getPlanningSummary(page);
  const totalText = await page
    .locator('text=/Total\\s+\\d/i')
    .first()
    .textContent({ timeout: 5000 })
    .catch(() => null);
  const continueVisible = await page
    .getByRole('button', { name: /^Continuar$/i })
    .isVisible()
    .catch(() => false);
  let saveResult = null;

  if (shouldSavePlan) {
    await page.getByRole('button', { name: /^Continuar$/i }).click({ timeout: 15000 });
    await page.waitForTimeout(1500);

    const keepCurrentPlanButton = page.getByRole('button', { name: /Continuar com meu plano atual/i });
    if (await keepCurrentPlanButton.isVisible().catch(() => false)) {
      await keepCurrentPlanButton.click();
    }

    await page.waitForURL(/\/shipping\/plans\/\d+\/inbounds/i, { timeout: 60000 });
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);

    const planMatch = page.url().match(/\/shipping\/plans\/(\d+)\/inbounds/i);
    const inboundRows = await page.evaluate(() => {
      const text = document.body.innerText;
      const ids = [...text.matchAll(/Envio\s+#(\d+)/g)].map(match => match[1]);
      const unitMatches = [...text.matchAll(/(\d[\d.]*)\s+unidades\s+(\d+)\s+produtos?([^\n]*)/gi)];
      return ids.map((id, index) => ({
        id,
        unitsText: unitMatches[index]?.[1] || null,
        productsText: unitMatches[index]?.[2] || null,
        group: unitMatches[index]?.[3]?.trim() || null,
      }));
    });

    saveResult = {
      status: 'created',
      mlPlanId: planMatch?.[1] || null,
      url: page.url(),
      inbounds: inboundRows,
    };
  }

  const screenshotPath = resolve(
    screenshotsDir,
    shouldSavePlan ? `run-once-saved-${slug}.png` : `run-once-fill-${slug}.png`,
  );
  await page.screenshot({ path: screenshotPath, fullPage: true });

  const result = {
    status: shouldSavePlan ? 'created' : 'filled_only',
    ok: fillResult.filledFields > 0,
    action: shouldSavePlan ? 'fill_and_save_plan' : 'fill_first_page_without_continue',
    units,
    unitsStrategy,
    formula: unitsStrategy === 'formula' ? 'ceil(vendas_30_dias * 1.20) - aptas_e_a_caminho' : null,
    startedAt: startedAt.toISOString(),
    finishedAt: new Date().toISOString(),
    filledFields: fillResult.filledFields,
    appliedRows,
    allValuesMatch: fillResult.values.every(value => value === String(units)),
    totalText,
    continueVisible,
    saveResult,
    screenshotPath,
    ...summary,
  };

  await writeJson(
    resolve(logsDir, shouldSavePlan ? `run-once-saved-${slug}.json` : `run-once-fill-${slug}.json`),
    result,
  );

  if (!result.ok) {
    console.error('Nenhum campo foi preenchido.');
    process.exitCode = 2;
  } else {
    console.log('Teste executado com sucesso.');
    console.log(`Campos preenchidos: ${result.filledFields}`);
    console.log(`Estrategia: ${unitsStrategy}`);
    console.log(`Valor aplicado: ${unitsStrategy === 'fixed' ? units : 'formula por linha'}`);
    console.log(`Total lido: ${totalText || 'nao identificado'}`);
    console.log(`Botao Continuar visivel: ${continueVisible ? 'sim' : 'nao'}`);
    if (saveResult) {
      console.log(`Plano ML criado: ${saveResult.mlPlanId || 'nao identificado'}`);
      console.log(`Envios: ${saveResult.inbounds.map(inbound => inbound.id).join(', ') || 'nao identificados'}`);
    }
    console.log(`Screenshot: ${screenshotPath}`);
    console.log(shouldSavePlan ? 'Fluxo salvo no Mercado Livre.' : 'Nenhum clique em Continuar foi realizado.');
  }
} catch (error) {
  const screenshotPath = resolve(
    screenshotsDir,
    shouldSavePlan ? `run-once-saved-error-${slug}.png` : `run-once-fill-error-${slug}.png`,
  );
  await page.screenshot({ path: screenshotPath, fullPage: true }).catch(() => {});
  await writeJson(resolve(logsDir, shouldSavePlan ? `run-once-saved-error-${slug}.json` : `run-once-fill-error-${slug}.json`), {
    status: 'error',
    ok: false,
    action: shouldSavePlan ? 'fill_and_save_plan' : 'fill_first_page_without_continue',
    units,
    startedAt: startedAt.toISOString(),
    finishedAt: new Date().toISOString(),
    message: error.message,
    stack: error.stack,
    screenshotPath,
  });
  console.error('Erro no teste:', error.message);
  process.exitCode = 1;
} finally {
  await browser.close();
}
