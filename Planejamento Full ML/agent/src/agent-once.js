import { spawn } from 'node:child_process';
import { config } from './config.js';
import { agentRoot } from './paths.js';

const agentId = config.agentId || 'mac-local-julio';

async function main() {
  await fetch(`${config.nvsApiUrl}/api/ml-full-plans/agent/heartbeat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ agent_id: agentId, status: 'online', message: 'agent-once iniciando' }),
  }).catch(() => {});

  const response = await fetch(`${config.nvsApiUrl}/api/ml-full-plans/agent/next-task?agent_id=${encodeURIComponent(agentId)}`);
  if (!response.ok) {
    throw new Error(`Erro ao buscar tarefa: HTTP ${response.status}`);
  }
  const task = await response.json();
  if (!task || task.task === null) {
    console.log('Nenhuma tarefa pendente.');
    return;
  }

  console.log(`Executando tarefa #${task.id} (${task.run_mode})...`);

  const env = {
    ...process.env,
    NVS_TASK_ID: String(task.id),
    ML_UNITS_STRATEGY: task.units_strategy || 'formula',
    ML_SAVE_PLAN: task.run_mode === 'save' ? 'true' : 'false',
    ML_FORMULA_PERCENTAGE: String(task.percentage ?? 20),
    ML_FORMULA_MIN_UNITS: String(task.min_units ?? 0),
    ML_TRACE: process.env.ML_TRACE || 'true',
  };

  if (task.units_strategy === 'fixed') {
    env.ML_TEST_UNITS = String(task.fixed_units || 200);
  }

  await new Promise((resolve, reject) => {
    const child = spawn(process.execPath, ['src/run-once.js'], {
      cwd: agentRoot,
      env,
      stdio: 'inherit',
    });
    child.on('exit', code => {
      if (code === 0) resolve();
      else reject(new Error(`run-once terminou com codigo ${code}`));
    });
  });
}

main().catch(error => {
  console.error(error.message);
  process.exit(1);
});
