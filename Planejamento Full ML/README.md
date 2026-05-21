# Planejamento Full ML

Este diretorio centraliza o desenho do novo modulo de Planejamento Full do Mercado Livre para o NVS.

Objetivo do modulo:

- Permitir disparo manual pelo painel da NVS.
- Acionar um agente local conectado a NVS.
- Executar o fluxo no Mercado Livre com navegador automatizado.
- Registrar no painel o resultado gerado por envio: envio ML, plano pai, unidades, produtos, status e logs.

## Decisao da primeira onda

A primeira entrega nao tera agendamento. O escopo funcional e:

1. usuario acessa a NVS;
2. usuario clica em `Executar e salvar`;
3. agente local ja online recebe a tarefa;
4. agente cria o planejamento no Mercado Livre;
5. NVS registra uma linha por envio criado.

Agendamento diario e instalador definitivo ficam para fases posteriores.

## Decisao de arquitetura

A criacao real do plano acontece sempre no ambiente do Mercado Livre. A NVS nao substitui o Mercado Livre; ela vira o painel de controle, programacao e auditoria.

Como a API publica do Mercado Livre nao oferece hoje uma operacao oficial para criar o planejamento Full, o MVP usara um agente local com Playwright/Chromium autenticado em uma sessao do Mercado Livre.

## Componentes

```text
NVS no Railway
  - cadastra regras
  - dispara execucao manual
  - mostra agente online/offline
  - registra historico e resultado

Agente Full ML local
  - roda na maquina executora
  - mantem conexao com a NVS
  - recebe comandos
  - abre navegador invisivel
  - acessa Mercado Livre com sessao salva
  - cria o planejamento
  - devolve resultado para a NVS
```

## Regra ja validada no teste real

Quando o Mercado Livre exibir o modal:

```text
Inclua 1 produto estrela no seu plano e impulsione suas vendas
```

O agente deve clicar sempre em:

```text
Continuar com meu plano atual
```

Nao deve clicar em `Conferir produto estrela`.

## Regra de calculo validada

Estrategia atual:

```text
ceil(vendas_full_ultimos_30_dias * 1.20) - aptas_e_a_caminho
```

Quando o resultado for zero ou negativo, aplicar `0`. O processo decidiu nao forcar minimo artificial para itens negativos.

URL filtrada usada pelo agente:

```text
https://www.mercadolivre.com.br/anuncios/lista/shipment_planning/plans?page=1&filters=WITHOUT_STOCK%7CWITH_MEDIUM_STOCK%7CWITH_CRITICAL_STOCK%7CWITH_ENOUGH_STOCK%7CWITH_LOW_STOCK&sorts=gmv_l30d_full_desc
```

Filtros atuais:

- sem estoque;
- estoque medio;
- estoque critico;
- estoque suficiente;
- estoque baixo.

Ordenacao atual:

- `gmv_l30d_full_desc`, maior GMV Full dos ultimos 30 dias primeiro.

## Teste real validado

Data: 2026-05-20

Fluxo testado:

- Pagina filtrada do Planejamento Full ML.
- Primeira pagina apenas.
- Preenchimento de `200` unidades por campo.
- Clique em `Continuar`.
- Modal de produto estrela tratado com `Continuar com meu plano atual`.
- Plano criado com sucesso no Mercado Livre.

Resultado observado:

- Plano ML: `68106790`
- Envio `68106791`: 800 unidades, 4 produtos grandes e extragrandes.
- Envio `68106792`: 2.000 unidades, 10 produtos pequenos e medios.
- Total aceito pelo Mercado Livre: 2.800 unidades, 14 produtos.
- Observacao: 18 campos foram preenchidos, mas itens classificados como excedente nao entraram no total final aceito pelo ML.

## Piloto do agente local Mac

Data: 2026-05-20

Resultado:

- Agente local criado em `agent/`.
- Chromium separado do Chrome pessoal validado.
- Login manual realizado uma vez pelo Playwright.
- Sessao salva localmente em `agent/storage/ml-session.json`.
- Checagem headless validada com sucesso.
- Pagina filtrada acessada pelo agente: 18 resultados encontrados.

Artefatos locais:

- Log em `agent/logs/`.
- Screenshot em `agent/screenshots/`.
- Trace Playwright em `agent/traces/`.

Esses artefatos sao locais e nao devem ser versionados.

## Estado atual validado

Data: 2026-05-21

Fluxo end-to-end validado:

- NVS local com botao `Executar e salvar`.
- Agente continuo rodando com `npm run ml:agent`.
- Agente detecta a tarefa automaticamente por polling.
- Agente preenche a primeira pagina filtrada.
- Agente percorre as paginas disponiveis do Planejamento Full antes de concluir.
- Agente salva o planejamento no Mercado Livre.
- Agente espera a pagina de envios carregar.
- Agente captura plano pai e envios filhos.
- NVS grava uma linha por envio.

## Paginacao do planejamento

Com os filtros novos, o Mercado Livre pode exibir varias paginas de produtos.

O agente deve:

1. preencher a pagina atual;
2. registrar no log quantos campos foram preenchidos naquela pagina;
3. clicar em `Proximo` quando houver proxima pagina habilitada;
4. repetir ate nao existir proxima pagina;
5. somente depois disso simular ou clicar em `Continuar`.

O resultado da execucao grava:

- `pagesProcessed`;
- `pageResults`;
- `filledFields` total;
- `appliedRows` com pagina e indice do item.

Antes de usar em modo real com multiplas paginas, validar primeiro com `Simular`.

Ultimo teste confirmado:

- Plano pai ML: `68116007`
- Envio `68116009`: 186 unidades, 3 produtos, grupo grandes e extragrandes.
- Envio `68116010`: 459 unidades, 9 produtos, grupo pequenos e medios.
- Total do planejamento: 645 unidades, 12 produtos.

## Tela operacional na NVS

A tela `Supervisao Full > Planejamento Full` ficou definida para a primeira onda com foco operacional:

- historico principal em nivel de envio;
- uma linha por envio, alternando fundos azuis suaves para facilitar leitura;
- cards superiores com contorno mais forte para resumo de envios, produtos e unidades;
- filtro de periodo com data inicial e data final ao lado do botao `Atualizar`;
- painel `Agente Full ML` compacto na lateral;
- tarefas recentes recolhidas por padrao, com botao `+` para expandir logs quando necessario.

As tarefas/logs existem para auditoria e suporte, mas nao devem competir visualmente com a lista de envios.

Comandos principais:

```bash
npm run ml:login
npm run ml:check-session
npm run ml:agent
npm run ml:agent-once
```

## Documentos

- [ARQUITETURA_AGENTE_LOCAL.md](ARQUITETURA_AGENTE_LOCAL.md)
- [RUNBOOK_MAC_PILOTO.md](RUNBOOK_MAC_PILOTO.md)
- [PLANO_DE_TESTES.md](PLANO_DE_TESTES.md)
