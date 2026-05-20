import { mkdir, writeFile } from 'node:fs/promises';
import { logsDir, screenshotsDir, storageDir } from './paths.js';

export async function ensureAgentDirs() {
  await Promise.all([
    mkdir(storageDir, { recursive: true }),
    mkdir(logsDir, { recursive: true }),
    mkdir(screenshotsDir, { recursive: true }),
  ]);
}

export function timestampSlug(date = new Date()) {
  return date.toISOString().replace(/[:.]/g, '-');
}

export async function writeJson(path, data) {
  await writeFile(path, `${JSON.stringify(data, null, 2)}\n`, 'utf8');
}
