import { app, BrowserWindow, ipcMain, shell } from 'electron';
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const isPackaged = app.isPackaged;
const agentRoot = isPackaged
  ? path.join(process.resourcesPath, 'agent')
  : path.resolve(__dirname, '..', '..', 'agent');

const settingsPath = () => path.join(app.getPath('userData'), 'settings.json');
const defaultSettings = {
  nvsApiUrl: 'http://localhost:8003',
  agentId: 'mac-local-julio',
  headless: true,
  trace: true,
};

let mainWindow = null;
let agentProcess = null;
let loginProcess = null;

function send(channel, payload) {
  mainWindow?.webContents.send(channel, payload);
}

async function readSettings() {
  try {
    const raw = await readFile(settingsPath(), 'utf8');
    return { ...defaultSettings, ...JSON.parse(raw) };
  } catch {
    return defaultSettings;
  }
}

async function saveSettings(settings) {
  const next = { ...defaultSettings, ...settings };
  await mkdir(path.dirname(settingsPath()), { recursive: true });
  await writeFile(settingsPath(), `${JSON.stringify(next, null, 2)}\n`, 'utf8');
  return next;
}

async function syncAgentEnv(settings) {
  const envPath = path.join(agentRoot, '.env.local');
  const lines = [
    `NVS_API_URL=${settings.nvsApiUrl}`,
    `AGENT_ID=${settings.agentId}`,
    `ML_HEADLESS=${settings.headless ? 'true' : 'false'}`,
    `ML_TRACE=${settings.trace ? 'true' : 'false'}`,
  ];
  await writeFile(envPath, `${lines.join('\n')}\n`, 'utf8');
}

function agentEnv(settings) {
  return {
    ...process.env,
    ELECTRON_RUN_AS_NODE: '1',
    NVS_API_URL: settings.nvsApiUrl,
    AGENT_ID: settings.agentId,
    ML_HEADLESS: settings.headless ? 'true' : 'false',
    ML_TRACE: settings.trace ? 'true' : 'false',
  };
}

function spawnAgentScript(scriptName, settings, { keepAlive = false } = {}) {
  const child = spawn(process.execPath, [`src/${scriptName}`], {
    cwd: agentRoot,
    env: agentEnv(settings),
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  child.stdout.on('data', data => send('agent-log', String(data)));
  child.stderr.on('data', data => send('agent-log', String(data)));
  child.on('exit', code => {
    if (keepAlive) agentProcess = null;
    send('agent-process', { running: Boolean(agentProcess), code });
  });

  return child;
}

async function fetchAgentStatus(settings) {
  const response = await fetch(`${settings.nvsApiUrl}/api/ml-full-plans/automation/status`);
  if (!response.ok) {
    throw new Error(`NVS respondeu HTTP ${response.status}`);
  }
  return response.json();
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 880,
    height: 680,
    minWidth: 780,
    minHeight: 560,
    title: 'NVS Full Agent',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  await mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
}

ipcMain.handle('settings:get', async () => {
  const settings = await readSettings();
  return {
    settings,
    agentRoot,
    sessionExists: existsSync(path.join(agentRoot, 'storage', 'ml-session.json')),
    agentRunning: Boolean(agentProcess),
  };
});

ipcMain.handle('settings:save', async (_event, settings) => {
  const saved = await saveSettings(settings);
  await syncAgentEnv(saved);
  return saved;
});

ipcMain.handle('agent:login', async (_event, settings) => {
  const saved = await saveSettings(settings);
  await syncAgentEnv(saved);
  if (loginProcess) return { ok: true, alreadyRunning: true };
  loginProcess = spawnAgentScript('login.js', saved);
  loginProcess.on('exit', () => {
    loginProcess = null;
    send('agent-login', {
      running: false,
      sessionExists: existsSync(path.join(agentRoot, 'storage', 'ml-session.json')),
    });
  });
  send('agent-login', { running: true });
  return { ok: true };
});

ipcMain.handle('agent:finish-login', async () => {
  if (!loginProcess) return { ok: false, message: 'Nenhum login em andamento.' };
  loginProcess.stdin.write('\n');
  return { ok: true };
});

ipcMain.handle('agent:check-session', async (_event, settings) => {
  const saved = await saveSettings(settings);
  await syncAgentEnv(saved);
  spawnAgentScript('check-session.js', saved);
  return { ok: true };
});

ipcMain.handle('agent:start', async (_event, settings) => {
  if (agentProcess) return { ok: true, alreadyRunning: true };
  const saved = await saveSettings(settings);
  await syncAgentEnv(saved);
  agentProcess = spawnAgentScript('agent.js', saved, { keepAlive: true });
  send('agent-process', { running: true });
  return { ok: true };
});

ipcMain.handle('agent:stop', async () => {
  if (agentProcess) {
    agentProcess.kill();
    agentProcess = null;
  }
  send('agent-process', { running: false });
  return { ok: true };
});

ipcMain.handle('agent:open-folder', async () => {
  await shell.openPath(agentRoot);
  return { ok: true };
});

ipcMain.handle('agent:nvs-status', async (_event, settings) => {
  const saved = await saveSettings(settings);
  return fetchAgentStatus(saved);
});

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (agentProcess) agentProcess.kill();
  if (loginProcess) loginProcess.kill();
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
