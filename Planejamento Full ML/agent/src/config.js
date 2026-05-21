import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import dotenv from 'dotenv';
import { agentRoot } from './paths.js';

const localEnvPath = resolve(agentRoot, '.env.local');
if (existsSync(localEnvPath)) {
  dotenv.config({ path: localEnvPath });
}

export const config = {
  nvsApiUrl: process.env.NVS_API_URL || 'http://127.0.0.1:8001',
  agentId: process.env.AGENT_ID || 'mac-local-julio',
  agentToken: process.env.AGENT_TOKEN || '',
  mlPlanningUrl:
    process.env.ML_PLANNING_URL ||
    'https://www.mercadolivre.com.br/anuncios/lista/shipment_planning/plans?page=1&filters=WITHOUT_STOCK%7CWITH_MEDIUM_STOCK%7CWITH_CRITICAL_STOCK%7CWITH_ENOUGH_STOCK%7CWITH_LOW_STOCK&sorts=gmv_l30d_full_desc',
  headless: String(process.env.ML_HEADLESS || 'true').toLowerCase() !== 'false',
};
