import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { launchBrowser, newMlContext } from './browser.js';
import { config } from './config.js';
import { ensureAgentDirs, timestampSlug, writeJson } from './fs-utils.js';
import { getPlanningSummary, waitForPlanningPage } from './ml-page.js';
import { logsDir, screenshotsDir, sessionPath, tracesDir } from './paths.js';

const units = Number(process.env.ML_TEST_UNITS || 200);
const shouldSavePlan = String(process.env.ML_SAVE_PLAN || 'false').toLowerCase() === 'true';
const unitsStrategy = process.env.ML_UNITS_STRATEGY || 'fixed';
const taskId = process.env.NVS_TASK_ID || null;
const formulaPercentage = Number(process.env.ML_FORMULA_PERCENTAGE || 20);
const formulaMinUnits = Number(process.env.ML_FORMULA_MIN_UNITS || 0);
const traceEnabled = String(process.env.ML_TRACE || 'false').toLowerCase() === 'true';

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
      const targetWithPercent = sales == null ? null : Math.ceil(sales * (1 + formulaPercentage / 100));
      const rawUnits =
        targetWithPercent == null || readyAndInbound == null ? null : targetWithPercent - readyAndInbound;
      const appliedUnits = rawUnits == null ? null : Math.max(formulaMinUnits, rawUnits);

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

async function extractInboundRows(page) {
  return page.evaluate(() => {
    const text = document.body.innerText;
    const ids = [
      ...new Set([
        ...[...text.matchAll(/Envio\s+#(\d+)/gi)].map(match => match[1]),
        ...[...text.matchAll(/#(\d{6,})/g)].map(match => match[1]),
      ]),
    ];
    const unitMatches = [...text.matchAll(/(\d[\d.]*)\s+unidades\s+(\d+)\s+produtos?([^\n]*)/gi)];
    return ids.map((id, index) => ({
      id,
      unitsText: unitMatches[index]?.[1] || null,
      productsText: unitMatches[index]?.[2] || null,
      group: unitMatches[index]?.[3]?.trim() || null,
    }));
  });
}

async function waitForInboundRows(page, timeoutMs = 90000) {
  const deadline = Date.now() + timeoutMs;
  let rows = [];

  while (Date.now() < deadline) {
    await page.waitForLoadState('domcontentloaded').catch(() => {});
    rows = await extractInboundRows(page).catch(() => []);
    if (rows.length > 0) return rows;

    const stillLoading = await page
      .getByText(/aguarde|pode levar alguns segundos|prepara/i)
      .first()
      .isVisible()
      .catch(() => false);

    await page.waitForTimeout(stillLoading ? 3000 : 1500);
  }

  return rows;
}

async function getCurrentPageNumber(page) {
  return page.evaluate(() => {
    const candidates = [...document.querySelectorAll('button, a, [aria-current], [aria-selected]')];
    const active = candidates.find(element => {
      const text = element.textContent?.trim();
      const ariaCurrent = element.getAttribute('aria-current');
      const ariaSelected = element.getAttribute('aria-selected');
      const className = String(element.className || '');
      return /^\d+$/.test(text || '')
        && (ariaCurrent === 'page' || ariaSelected === 'true' || /selected|current|active/i.test(className));
    });
    return Number(active?.textContent?.trim() || 0) || null;
  }).catch(() => null);
}

async function fillCurrentPlanningPage(page, pageNumber) {
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
        page: pageNumber,
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
      page: pageNumber,
      index,
      value: calculatedUnits,
      calculation: productCalculations[index] || null,
    });
    await page.waitForTimeout(120);
  }

  return {
    page: pageNumber,
    productCount,
    filledFields,
    appliedRows,
    url: page.url(),
  };
}

async function goToNextPlanningPage(page) {
  const nextButton = page.getByRole('button', { name: /Próximo|Siguiente|Next/i }).first();
  const nextLink = page.getByRole('link', { name: /Próximo|Siguiente|Next/i }).first();

  for (const control of [nextButton, nextLink]) {
    const visible = await control.isVisible().catch(() => false);
    if (!visible) continue;
    const disabled = await control.evaluate(element => {
      const ariaDisabled = element.getAttribute('aria-disabled');
      return ariaDisabled === 'true' || element.disabled || element.classList.contains('andes-pagination__button--disabled');
    }).catch(() => false);
    if (disabled) continue;

    const beforeUrl = page.url();
    await control.scrollIntoViewIfNeeded().catch(() => {});
    await control.click({ timeout: 10000 });
    await page.waitForLoadState('domcontentloaded').catch(() => {});
    await page.waitForFunction(
      previous => location.href !== previous || document.body.innerText.includes('Código ML:'),
      beforeUrl,
      { timeout: 15000 },
    ).catch(() => {});
    await page.waitForTimeout(2000);
    return true;
  }

  return false;
}

async function fillAllPlanningPages(page) {
  const pageResults = [];
  const appliedRows = [];
  const seenPages = new Set();
  let filledFields = 0;

  for (let loop = 0; loop < 20; loop += 1) {
    const currentPageNumber = await getCurrentPageNumber(page) || pageResults.length + 1;
    const pageKey = `${currentPageNumber}:${page.url()}`;
    if (seenPages.has(pageKey)) break;
    seenPages.add(pageKey);

    const result = await fillCurrentPlanningPage(page, currentPageNumber);
    pageResults.push({
      page: result.page,
      productCount: result.productCount,
      filledFields: result.filledFields,
      url: result.url,
    });
    appliedRows.push(...result.appliedRows);
    filledFields += result.filledFields;

    const moved = await goToNextPlanningPage(page);
    if (!moved) break;
  }

  return {
    filledFields,
    values: [],
    appliedRows,
    pageResults,
    pagesProcessed: pageResults.length,
  };
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
const tracePath = traceEnabled
  ? resolve(tracesDir, shouldSavePlan ? `run-once-saved-${slug}.zip` : `run-once-fill-${slug}.zip`)
  : null;

if (traceEnabled) {
  await context.tracing.start({ screenshots: true, snapshots: true, sources: true });
}

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

  const fillResult = await fillAllPlanningPages(page);

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
    const inboundRows = await waitForInboundRows(page);

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
    action: shouldSavePlan ? 'fill_all_pages_and_save_plan' : 'fill_all_pages_without_continue',
    units,
    unitsStrategy,
    formula: unitsStrategy === 'formula' ? `ceil(vendas_30_dias * ${1 + formulaPercentage / 100}) - aptas_e_a_caminho` : null,
    formulaPercentage,
    formulaMinUnits,
    startedAt: startedAt.toISOString(),
    finishedAt: new Date().toISOString(),
    filledFields: fillResult.filledFields,
    appliedRows: fillResult.appliedRows,
    pagesProcessed: fillResult.pagesProcessed,
    pageResults: fillResult.pageResults,
    allValuesMatch: fillResult.values.every(value => value === String(units)),
    totalText,
    continueVisible,
    saveResult,
    screenshotPath,
    tracePath,
    ...summary,
  };

  await writeJson(
    resolve(logsDir, shouldSavePlan ? `run-once-saved-${slug}.json` : `run-once-fill-${slug}.json`),
    result,
  );

  if (taskId) {
    const inboundIds = saveResult?.inbounds?.map(inbound => inbound.id).filter(Boolean) || [];
    const notes = saveResult
      ? `Plano criado pelo agente local. Envios: ${inboundIds.length ? inboundIds.join(', ') : 'nao identificados'}. Total aceito pelo ML: ${totalText || 'nao identificado'}.`
      : `Simulacao concluida pelo agente local. Total calculado pelo ML: ${totalText || 'nao identificado'}.`;
    await fetch(`${config.nvsApiUrl}/api/ml-full-plans/agent/tasks/${taskId}/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        status: saveResult ? 'created' : 'simulated',
        ml_plan_id: saveResult?.mlPlanId || null,
        products_count: Number(totalText?.match(/\((\d+)\s+produtos?\)/i)?.[1] || 0),
        total_units: Number((totalText?.match(/Total\s+([\d.]+)\s+un/i)?.[1] || '0').replace(/\./g, '')),
        notes,
        result,
      }),
    }).catch(() => {});
  }

  if (!result.ok) {
    console.error('Nenhum campo foi preenchido.');
    process.exitCode = 2;
  } else {
    console.log('Teste executado com sucesso.');
    console.log(`Campos preenchidos: ${result.filledFields}`);
    console.log(`Paginas processadas: ${result.pagesProcessed}`);
    for (const pageResult of result.pageResults) {
      console.log(`Pagina ${pageResult.page}: ${pageResult.filledFields}/${pageResult.productCount} campos preenchidos`);
    }
    console.log(`Estrategia: ${unitsStrategy}`);
    console.log(`Valor aplicado: ${unitsStrategy === 'fixed' ? units : 'formula por linha'}`);
    console.log(`Total lido: ${totalText || 'nao identificado'}`);
    console.log(`Botao Continuar visivel: ${continueVisible ? 'sim' : 'nao'}`);
    if (saveResult) {
      console.log(`Plano ML criado: ${saveResult.mlPlanId || 'nao identificado'}`);
      console.log(`Envios: ${saveResult.inbounds.map(inbound => inbound.id).join(', ') || 'nao identificados'}`);
    }
    console.log(`Screenshot: ${screenshotPath}`);
    if (tracePath) console.log(`Trace: ${tracePath}`);
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
    action: shouldSavePlan ? 'fill_all_pages_and_save_plan' : 'fill_all_pages_without_continue',
    units,
    startedAt: startedAt.toISOString(),
    finishedAt: new Date().toISOString(),
    message: error.message,
    stack: error.stack,
    screenshotPath,
    tracePath,
  });
  if (taskId) {
    await fetch(`${config.nvsApiUrl}/api/ml-full-plans/agent/tasks/${taskId}/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        status: 'failed',
        error_message: error.message,
        result: { screenshotPath, tracePath, stack: error.stack },
      }),
    }).catch(() => {});
  }
  console.error('Erro no teste:', error.message);
  process.exitCode = 1;
} finally {
  if (traceEnabled && tracePath) {
    await context.tracing.stop({ path: tracePath }).catch(error => {
      console.error('Erro ao salvar trace:', error.message);
    });
  }
  await browser.close();
}
