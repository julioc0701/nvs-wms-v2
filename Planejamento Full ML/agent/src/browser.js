import { existsSync } from 'node:fs';
import { chromium } from 'playwright';
import { sessionPath } from './paths.js';

export async function launchBrowser({ headless }) {
  return chromium.launch({
    headless,
    args: ['--disable-blink-features=AutomationControlled'],
  });
}

export async function newMlContext(browser, options = {}) {
  const contextOptions = {
    viewport: { width: 1366, height: 768 },
    locale: 'pt-BR',
    timezoneId: 'America/Sao_Paulo',
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
  };

  if (options.useSession !== false && existsSync(sessionPath)) {
    contextOptions.storageState = sessionPath;
  }

  return browser.newContext(contextOptions);
}
