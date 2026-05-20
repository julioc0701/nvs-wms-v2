# Agente Full ML

Agente local do Planejamento Full Mercado Livre.

Neste primeiro MVP, ele faz apenas:

- login inicial em um Chromium separado do Chrome pessoal;
- armazenamento de sessao local;
- checagem de acesso a pagina do Planejamento Full.

Ele ainda nao cria plano automaticamente pelo comando padrao. O comando `ml:run-once` esta bloqueado ate recebermos autorizacao explicita para o proximo teste real.

## Setup

```bash
cd "Planejamento Full ML/agent"
npm install
cp .env.example .env.local
npm run ml:login
npm run ml:check-session
```

## Arquivos sensiveis

Nao versionar:

- `.env.local`
- `storage/ml-session.json`
- `logs/`
- `screenshots/`

## Comandos

### `npm run ml:login`

Abre Chromium visivel para login manual no Mercado Livre e salva a sessao em:

```text
storage/ml-session.json
```

### `npm run ml:check-session`

Abre Chromium usando a sessao salva e valida se a pagina do Planejamento Full carrega.

### `npm run ml:run-once`

Executa um teste controlado. Por padrao, preenche a primeira pagina e nao clica em `Continuar`.

Valor fixo:

```bash
npm run ml:run-once
```

Formula por linha:

```bash
ML_UNITS_STRATEGY=formula npm run ml:run-once
```

Formula aplicada:

```text
ceil(vendas_30_dias * 1.20) - aptas_e_a_caminho
```

Quando o resultado for zero ou negativo, o agente aplica `1` unidade.

Para salvar de verdade no Mercado Livre, e necessario habilitar explicitamente:

```bash
ML_UNITS_STRATEGY=formula ML_SAVE_PLAN=true npm run ml:run-once
```
