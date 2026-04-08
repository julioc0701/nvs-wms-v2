const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const envFile = path.join(root, '.env.code');
const env = {};

if (fs.existsSync(envFile)) {
  const lines = fs.readFileSync(envFile, 'utf8').split(/\r?\n/);
  for (const line of lines) {
    if (!line || line.trim().startsWith('#') || !line.includes('=')) continue;
    const [k, ...rest] = line.split('=');
    env[k.trim()] = rest.join('=').trim();
  }
}

const frontPort = env.VITE_PORT || '5174';
const backPort = env.FASTAPI_PORT || '8001';

async function check(url) {
  try {
    const res = await fetch(url);
    return { ok: res.ok, status: res.status };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

async function run() {
  const back = await check(`http://127.0.0.1:${backPort}/api/health`);
  const front = await check(`http://127.0.0.1:${frontPort}`);

  const result = {
    timestamp: new Date().toISOString(),
    frontend: { url: `http://127.0.0.1:${frontPort}`, ...front },
    backend: { url: `http://127.0.0.1:${backPort}/api/health`, ...back },
  };

  const out = path.join(root, 'audit_nvs_wms_completo', '11_healthcheck_isolado.json');
  fs.mkdirSync(path.dirname(out), { recursive: true });
  fs.writeFileSync(out, JSON.stringify(result, null, 2), 'utf8');

  console.log(JSON.stringify(result, null, 2));
  process.exit(back.ok && front.ok ? 0 : 1);
}

run();
