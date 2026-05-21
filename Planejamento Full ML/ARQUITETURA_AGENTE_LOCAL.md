# Arquitetura - Agente Local Full ML

## Objetivo

Criar um agente local que execute o Planejamento Full do Mercado Livre a partir de comandos criados na NVS.

A experiencia desejada para a primeira onda:

1. Entrar na NVS.
2. Clicar em `Executar e salvar`.
3. A NVS aciona o agente local.
4. O agente executa o fluxo no Mercado Livre.
5. A NVS registra o resultado.

Agendamento fica fora da primeira onda. O foco inicial e o botao manual com agente online.

## Premissas

- A NVS esta hospedada no Railway.
- O Mercado Livre exige uma sessao web autenticada.
- A API publica do Mercado Livre nao cobre a criacao do planejamento Full.
- O agente precisa rodar em uma maquina executora com acesso ao Mercado Livre.
- O agente nao deve depender do Chrome pessoal do usuario.
- O agente deve usar um perfil/sessao propria.

## Modelo recomendado para MVP

```text
NVS Railway
  |
  | WebSocket ou polling curto
  v
Agente Local Full ML
  |
  | Playwright/Chromium headless
  v
Mercado Livre
```

## Gatilho

O gatilho funcional fica na NVS:

- primeira onda: botao manual `Executar e salvar`;
- fase futura: agenda configurada no painel.

Tecnicamente, para a NVS conseguir acionar uma maquina local, o agente precisa estar rodando e conectado a NVS.

Existem dois modos possiveis:

### Modo 1 - WebSocket

O agente abre uma conexao persistente com a NVS.

Vantagens:

- Execucao quase imediata.
- Painel consegue mostrar `online`/`offline`.
- Bom para botao manual.

Riscos:

- Precisa cuidar de reconexao.
- Railway precisa expor endpoint WebSocket estavel.

### Modo 2 - Polling

O agente consulta a NVS a cada poucos segundos ou minutos.

Vantagens:

- Mais simples para MVP.
- Menos sensivel a queda de conexao.
- Facil de debugar.

Riscos:

- Execucao manual nao e instantanea, depende do intervalo.
- Menos elegante para status em tempo real.

Recomendacao:

- Comecar com polling curto no piloto local.
- Para a primeira onda, manter apenas execucao manual; sem programacao diaria.
- Evoluir para WebSocket quando o fluxo estiver estavel.

## Estado do agente

A NVS deve saber:

- `offline`: agente nao se comunica ha algum tempo.
- `online`: agente esta conectado ou fez check-in recente.
- `executando`: agente recebeu uma tarefa e esta trabalhando.
- `precisa_login`: sessao Mercado Livre expirou ou pediu verificacao.
- `erro`: falha tecnica ou bloqueio do Mercado Livre.

## Sessao Mercado Livre

O agente usa uma sessao separada do navegador pessoal.

Fluxo:

1. Primeira configuracao abre Chromium visivel.
2. Usuario faz login no Mercado Livre.
3. Agente salva o estado da sessao em arquivo local seguro.
4. Execucoes futuras rodam em modo invisivel.

Quando a sessao expirar:

- agente nao tenta resolver 2FA/captcha sozinho;
- marca tarefa como `precisa_login`;
- NVS orienta renovar a sessao.

## Fluxo de execucao

```text
1. NVS cria tarefa pending
2. Agente identifica tarefa
3. Agente marca tarefa running
4. Agente abre Planejamento Full ML
5. Aplica filtros configurados
6. Para cada pagina:
     calcula unidades
     preenche campos
     registra contadores da pagina
     clica Proximo se existir
7. Quando terminar as paginas:
     se simulacao, para sem salvar
     se execucao real, clica Continuar
8. Se aparecer modal de produto estrela:
     clicar Continuar com meu plano atual
9. Captura plano ML e envios gerados
10. Envia resultado para NVS
11. NVS registra historico
```

## Dados minimos da tarefa

```json
{
  "id": "task-id",
  "type": "ml_full_planning",
  "status": "pending",
  "filters": [
    "WITHOUT_STOCK",
    "WITH_MEDIUM_STOCK",
    "WITH_CRITICAL_STOCK",
    "WITH_ENOUGH_STOCK",
    "WITH_LOW_STOCK"
  ],
  "sort": "gmv_l30d_full_desc",
  "scope": "first_page",
  "run_mode": "simulate",
  "units_strategy": "formula",
  "fixed_units": null,
  "percentage": 20,
  "min_units": 0,
  "agent_id": "mac-local-julio"
}
```

Modos suportados no piloto:

- `run_mode = simulate`: preenche a tela e devolve o resultado sem clicar em `Continuar`.
- `run_mode = save`: preenche, clica em `Continuar`, trata o modal de estrela e registra o plano criado.
- `units_strategy = fixed`: usa a mesma quantidade em todos os itens.
- `units_strategy = formula`: usa `ceil(vendas_30_dias * (1 + percentage / 100)) - aptas_e_a_caminho`; se o resultado for negativo, aplica `min_units`.
- Primeira onda: `min_units = 0`, sem minimo artificial para contas negativas.

## Dados minimos do resultado

```json
{
  "status": "created",
  "ml_plan_id": "68116007",
  "inbounds": [
    {
      "id": "68116009",
      "units": 186,
      "products": 3,
      "group": "grandes e extragrandes"
    },
    {
      "id": "68116010",
      "units": 459,
      "products": 9,
      "group": "pequenos e medios"
    }
  ],
  "total_units": 645,
  "products_count": 12,
  "filled_fields": 18
}
```

## Registro no historico

A NVS deve registrar o resultado no nivel de envio, nao no nivel do plano pai.

Exemplo esperado:

```text
Envio 68116009 | Plano pai 68116007 | 3 produtos | 186 unidades
Envio 68116010 | Plano pai 68116007 | 9 produtos | 459 unidades
```

O plano pai continua salvo no payload para auditoria, mas a tela operacional exibe uma linha por envio, igual ao Mercado Livre.

## UI da primeira onda

Prioridade da tela:

1. mostrar envios criados;
2. permitir filtro rapido por periodo;
3. exibir status do agente;
4. permitir executar/simular;
5. manter logs de tarefas acessiveis, mas recolhidos.

Decisoes visuais:

- cards de resumo com borda mais evidente;
- linhas de envio em blocos alternados com fundos azuis suaves;
- sem barra horizontal para ver informacoes basicas;
- painel do agente mais compacto que a area de historico;
- tarefas recentes recolhidas com `+` para expandir.

## Status do MVP local em 2026-05-20

Implementado:

- tabelas de fila de tarefas e estado do agente na NVS local;
- endpoints para criar tarefa, consultar status, buscar proxima tarefa e concluir tarefa;
- painel `Agente Full ML` dentro de `Supervisao Full > Planejamento Full`;
- comando local `npm run ml:agent-once`;
- comando local continuo `npm run ml:agent`;
- retorno de resultado do agente para a NVS;
- criacao automatica de historico por envio quando o Mercado Livre retorna um plano criado;
- geracao local de screenshot e trace Playwright por execucao.

Validado:

- agente acessa a sessao propria do Mercado Livre;
- agente executa em Chromium separado do Chrome pessoal;
- regra de formula com percentual e minimo;
- tarefa de simulacao criada pela NVS e finalizada pelo agente.
- tarefa real criada pelo botao da NVS e executada automaticamente pelo agente continuo;
- captura de dois envios filhos e registro separado no painel.

## Seguranca

- Nao salvar senha do Mercado Livre em texto puro.
- Nao enviar cookies do ML para logs.
- Nao registrar `.env`, tokens ou storage state no git.
- Usar token proprio do agente para falar com a NVS.
- Permitir revogar agente na NVS.

## Caminho para Windows

Depois do piloto no Mac, o mesmo agente pode virar um instalador Windows:

- Node.js + Playwright no MVP.
- Windows Service ou Agendador de Tarefas para iniciar com o Windows.
- Pasta local de configuracao com token e sessao.
- Logs locais e envio de status para NVS.

O conceito e o mesmo de um agente de impressao: instalado uma vez, roda em segundo plano e recebe comandos do sistema central.
