import { launchBrowser, newMlContext } from './browser.js';
import { config } from './config.js';
import { ensureAgentDirs } from './fs-utils.js';
import { sessionPath } from './paths.js';

await ensureAgentDirs();

console.log('Abrindo Chromium separado para login do Mercado Livre...');
console.log('Faca o login manualmente. Quando a pagina de planejamento carregar, volte aqui e pressione Enter.');

const browser = await launchBrowser({ headless: false });
const context = await newMlContext(browser, { useSession: false });
const page = await context.newPage();

await page.goto(config.mlPlanningUrl, { waitUntil: 'domcontentloaded' });

process.stdin.setEncoding('utf8');
process.stdin.resume();
process.stdin.once('data', async () => {
  await context.storageState({ path: sessionPath });
  await browser.close();
  console.log(`Sessao salva em: ${sessionPath}`);
  process.exit(0);
});
