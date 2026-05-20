# Runbook - Piloto Mac do Agente Full ML

## Objetivo

Validar na maquina Mac um agente local capaz de:

- autenticar uma sessao propria no Mercado Livre;
- abrir o Planejamento Full sem usar o Chrome pessoal;
- executar em modo invisivel;
- receber comando da NVS;
- criar plano;
- devolver resultado para a NVS.

## Fase 1 - Prova de acesso

Meta: provar que o agente consegue acessar o Mercado Livre com uma sessao propria.

Passos:

1. Criar esqueleto do agente local.
2. Instalar Playwright/Chromium.
3. Rodar comando `login`.
4. Abrir Chromium visivel.
5. Fazer login manual no Mercado Livre.
6. Salvar `storageState` local.
7. Rodar comando `check-session`.
8. Confirmar que o agente abre a pagina de planejamento sem pedir login.

Resultado esperado:

- Sessao ML salva.
- Acesso ao Planejamento Full confirmado.
- Print ou log salvo localmente.

Status em 2026-05-20:

- Concluido.
- `npm run ml:login` abriu Chromium separado e salvou a sessao.
- `npm run ml:check-session` validou acesso headless.
- Resultado encontrado: 18 resultados na pagina filtrada.

## Fase 2 - Execucao assistida local

Meta: repetir o teste real sem usar o Chrome pessoal.

Escopo inicial:

- Primeira pagina apenas.
- Filtros:
  - `WITH_CRITICAL_STOCK`
  - `WITH_LOW_STOCK`
  - `WITHOUT_STOCK`
- Valor fixo de teste: `200`.
- Modal de produto estrela: sempre `Continuar com meu plano atual`.

Passos:

1. Abrir pagina filtrada.
2. Esperar tabela carregar.
3. Preencher `200` nos campos da primeira pagina.
4. Validar total exibido pelo ML.
5. Clicar `Continuar`.
6. Se aparecer modal de estrela, clicar `Continuar com meu plano atual`.
7. Capturar URL do plano.
8. Capturar envios gerados.
9. Salvar log local.

Resultado esperado:

- Plano criado.
- IDs dos envios capturados.
- Total de unidades e produtos capturados.

Status parcial em 2026-05-20:

- Teste agendado localmente com `sleep 60 && npm run ml:run-once`.
- Agente abriu a pagina filtrada em Chromium separado.
- Agente tratou os modais/onboarding iniciais do Mercado Livre.
- Agente preencheu 18 campos com `200`.
- Mercado Livre recalculou: 2.400 unidades, 12 produtos.
- Botao `Continuar` ficou visivel.
- O agente nao clicou em `Continuar` neste teste.

Status salvo em 2026-05-20:

- Execucao autorizada com `ML_SAVE_PLAN=true npm run ml:run-once`.
- Agente preencheu 18 campos com `200`.
- Mercado Livre aceitou 2.400 unidades em 12 produtos.
- Plano ML criado: `68109358`.
- Envio `68109360`: 600 unidades, 3 produtos grandes e extragrandes.
- Envio `68109361`: 1.800 unidades, 9 produtos pequenos e medios.
- Registro salvo na NVS local com status `created`.

Status da regra de calculo em 2026-05-20:

- Regra implementada no agente com `ML_UNITS_STRATEGY=formula`.
- Formula: `ceil(vendas_30_dias * 1.20) - aptas_e_a_caminho`.
- Quando o resultado e zero ou negativo, o agente aplica `1` unidade.
- Teste geral rodado sem salvar no Mercado Livre.
- Agente preencheu 18 campos usando a formula.
- Exemplo validado no primeiro item `YVJQ10171`: vendas 94, aptas/a caminho 37, alvo 113, valor aplicado 76.
- Total recalculado pelo Mercado Livre: 636 unidades, 6 produtos.
- Botao `Continuar` ficou visivel.
- O agente nao clicou em `Continuar` neste teste da regra.

Status salvo com minimo 1 em 2026-05-20:

- Execucao autorizada com `ML_UNITS_STRATEGY=formula ML_SAVE_PLAN=true npm run ml:run-once`.
- Agente preencheu 18 campos.
- Mercado Livre aceitou 643 unidades em 12 produtos.
- Plano ML criado: `68112585`.
- Envio `68112586`: 185 unidades, 3 produtos grandes e extragrandes.
- Envio `68112587`: 458 unidades, 9 produtos pequenos e medios.
- Registro salvo na NVS local com status `created`.

## Fase 3 - Integracao com NVS local

Meta: NVS local cria tarefa e agente executa.

Passos:

1. Criar tabela/fila de tarefas de automacao.
2. Criar endpoint para `Executar agora`.
3. Criar endpoint para agente buscar tarefas pendentes.
4. Criar endpoint para agente registrar resultado.
5. Agente roda em loop local consultando a NVS.
6. Clicar no botao da NVS.
7. Confirmar execucao e historico.

Resultado esperado:

- Botao na NVS dispara tarefa.
- Agente local executa.
- NVS registra sucesso/erro.

## Fase 4 - Execucao transparente

Meta: executar sem abrir janela visivel.

Passos:

1. Rodar agente em `headless`.
2. Repetir fluxo completo.
3. Salvar screenshot em pontos-chave somente para auditoria.
4. Confirmar que o usuario nao e interrompido.

Resultado esperado:

- Execucao invisivel.
- Sem interferir no Chrome pessoal.
- Logs suficientes para auditoria.

## Fase 5 - Agente em segundo plano

Meta: simular comportamento de produto.

Passos:

1. Criar comando `agent start`.
2. Manter agente consultando NVS.
3. Mostrar heartbeat/check-in no painel.
4. Testar maquina online/offline.
5. Testar erro de sessao expirada.

Resultado esperado:

- NVS mostra agente online.
- Tarefa manual executa.
- Falhas aparecem de forma clara.

## Comandos esperados do agente

Nomes sugeridos para o MVP:

```bash
npm run ml:login
npm run ml:check-session
npm run ml:run-once
npm run ml:agent
```

## Arquivos locais esperados

```text
Planejamento Full ML/
  agent/
    .env.local
    storage/ml-session.json
    logs/
    screenshots/
```

Esses arquivos locais nao devem ser versionados:

- `.env.local`
- `storage/ml-session.json`
- `logs/`
- `screenshots/`

## Criterios de sucesso do piloto Mac

- Agente acessa ML sem usar o Chrome pessoal.
- Agente executa primeira pagina filtrada.
- Agente trata o modal de produto estrela corretamente.
- Agente captura IDs do plano/envios.
- NVS registra o resultado.
- Execucao headless nao atrapalha o usuario.

## Pontos que bloqueiam automacao

- Mercado Livre pedir captcha.
- Mercado Livre pedir 2FA.
- Sessao expirada.
- Mudanca de layout da pagina.
- Erro interno do ML.
- Produto com regra que impede envio.

Nesses casos, o agente deve parar e registrar status claro na NVS.
