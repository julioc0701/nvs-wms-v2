const form = document.querySelector('#settings-form');
const nvsApiUrl = document.querySelector('#nvs-api-url');
const agentId = document.querySelector('#agent-id');
const headless = document.querySelector('#headless');
const trace = document.querySelector('#trace');
const log = document.querySelector('#log');
const statusDot = document.querySelector('#status-dot');
const agentStatus = document.querySelector('#agent-status');
const sessionStatus = document.querySelector('#session-status');

const buttons = {
  login: document.querySelector('#login'),
  finishLogin: document.querySelector('#finish-login'),
  checkSession: document.querySelector('#check-session'),
  openFolder: document.querySelector('#open-folder'),
  start: document.querySelector('#start'),
  stop: document.querySelector('#stop'),
  nvsStatus: document.querySelector('#nvs-status'),
  clearLog: document.querySelector('#clear-log'),
};

let settings = {
  nvsApiUrl: 'http://localhost:8003',
  agentId: 'windows-full-01',
  headless: true,
  trace: true,
};

function currentSettings() {
  return {
    nvsApiUrl: nvsApiUrl.value.trim(),
    agentId: agentId.value.trim(),
    headless: headless.checked,
    trace: trace.checked,
  };
}

function hydrate(next) {
  settings = { ...settings, ...next };
  nvsApiUrl.value = settings.nvsApiUrl || '';
  agentId.value = settings.agentId || '';
  headless.checked = Boolean(settings.headless);
  trace.checked = Boolean(settings.trace);
}

function appendLog(line) {
  const text = String(line || '').trimEnd();
  if (!text) return;
  log.textContent += `${text}\n`;
  log.scrollTop = log.scrollHeight;
}

function setStatus(label, online = false) {
  agentStatus.textContent = label;
  statusDot.classList.toggle('online', online);
  statusDot.classList.toggle('offline', !online);
}

async function runAction(label, action) {
  try {
    appendLog(`> ${label}`);
    const result = await action();
    if (result?.message) appendLog(result.message);
    return result;
  } catch (error) {
    appendLog(`[erro] ${error.message}`);
    setStatus('Erro', false);
    return null;
  }
}

form.addEventListener('submit', event => {
  event.preventDefault();
  runAction('salvando configuracao', async () => {
    const saved = await window.nvsAgent.saveSettings(currentSettings());
    hydrate(saved);
    appendLog('Configuracao salva.');
  });
});

buttons.login.addEventListener('click', () => {
  runAction('abrindo login Mercado Livre', async () => {
    await window.nvsAgent.login(currentSettings());
    sessionStatus.textContent = 'Login em andamento';
    appendLog('Faça login no Chromium aberto. Depois clique em "Salvar sessao".');
  });
});

buttons.finishLogin.addEventListener('click', () => {
  runAction('salvando sessao Mercado Livre', async () => {
    const result = await window.nvsAgent.finishLogin();
    if (!result?.ok) appendLog(result?.message || 'Login nao estava em andamento.');
  });
});

buttons.checkSession.addEventListener('click', () => {
  runAction('validando sessao Mercado Livre', async () => {
    sessionStatus.textContent = 'Validando...';
    await window.nvsAgent.checkSession(currentSettings());
  });
});

buttons.openFolder.addEventListener('click', () => {
  runAction('abrindo pasta do agente', () => window.nvsAgent.openFolder());
});

buttons.start.addEventListener('click', () => {
  runAction('iniciando agente', async () => {
    await window.nvsAgent.start(currentSettings());
    setStatus('Online', true);
  });
});

buttons.stop.addEventListener('click', () => {
  runAction('parando agente', async () => {
    await window.nvsAgent.stop();
    setStatus('Parado', false);
  });
});

buttons.nvsStatus.addEventListener('click', () => {
  runAction('consultando status NVS', async () => {
    const status = await window.nvsAgent.nvsStatus(currentSettings());
    const state = status?.agent?.status || status?.status || 'status recebido';
    appendLog(JSON.stringify(status, null, 2));
    setStatus(state === 'online' ? 'Online' : state, state === 'online');
  });
});

buttons.clearLog.addEventListener('click', () => {
  log.textContent = '';
});

window.nvsAgent.onLog(line => {
  appendLog(line);
  if (String(line).includes('Sessao validada com sucesso')) {
    sessionStatus.textContent = 'Sessão validada';
  }
});

window.nvsAgent.onProcess(state => {
  setStatus(state.running ? 'Online' : 'Parado', state.running);
  if (typeof state.code === 'number') appendLog(`Processo finalizado com codigo ${state.code}.`);
});

window.nvsAgent.onLogin(state => {
  if (state.running) {
    sessionStatus.textContent = 'Login em andamento';
    return;
  }
  sessionStatus.textContent = state.sessionExists ? 'Sessão salva' : 'Sessão não encontrada';
});

const initial = await window.nvsAgent.getSettings();
hydrate(initial.settings);
setStatus(initial.agentRunning ? 'Online' : 'Parado', initial.agentRunning);
sessionStatus.textContent = initial.sessionExists ? 'Sessão local encontrada' : 'Sessão não encontrada';
appendLog(`Agente: ${initial.agentRoot}`);
