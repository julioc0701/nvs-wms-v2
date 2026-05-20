import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

export const agentRoot = resolve(__dirname, '..');
export const storageDir = resolve(agentRoot, 'storage');
export const logsDir = resolve(agentRoot, 'logs');
export const screenshotsDir = resolve(agentRoot, 'screenshots');
export const sessionPath = resolve(storageDir, 'ml-session.json');
