import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { launchBrowser, newMlContext } from './browser.js';
import { config } from './config.js';
import { ensureAgentDirs, timestampSlug, writeJson } from './fs-utils.js';
import { getPlanningSummary, waitForPlanningPage } from './ml-page.js';
import { logsDir, screenshotsDir, sessionPath } from './paths.js';

await ensureAgentDirs();

if (!existsSync(sessionPath)) {
  console.error('Sessao nao encontrada. Rode primeiro: npm run ml:login');
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
  const summary = await getPlanningSummary(page);
  const screenshotPath = resolve(screenshotsDir, `check-session-${slug}.png`);
  await page.screenshot({ path: screenshotPath, fullPage: true });

  const result = {
    status,
    ok: status === 'planning',
    startedAt: startedAt.toISOString(),
    finishedAt: new Date().toISOString(),
    screenshotPath,
    ...summary,
  };

  await writeJson(resolve(logsDir, `check-session-${slug}.json`), result);

  if (!result.ok) {
    console.error('Sessao nao validada. Status:', status);
    console.error('URL atual:', summary.url);
    process.exitCode = 2;
  } else {
    console.log('Sessao validada com sucesso.');
    console.log(`Pagina: ${summary.url}`);
    console.log(`Resultados: ${summary.resultText || 'nao identificado'}`);
    console.log(`Inputs encontrados: ${summary.inputCount}`);
    console.log(`Screenshot: ${screenshotPath}`);
  }
} catch (error) {
  const errorResult = {
    status: 'error',
    ok: false,
    startedAt: startedAt.toISOString(),
    finishedAt: new Date().toISOString(),
    message: error.message,
    stack: error.stack,
  };
  await writeJson(resolve(logsDir, `check-session-error-${slug}.json`), errorResult);
  console.error('Erro ao validar sessao:', error.message);
  process.exitCode = 1;
} finally {
  await browser.close();
}
