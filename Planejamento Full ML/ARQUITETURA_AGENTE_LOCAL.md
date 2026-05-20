# Arquitetura - Agente Local Full ML

## Objetivo

Criar um agente local que execute o Planejamento Full do Mercado Livre a partir de comandos criados na NVS.

A experiencia desejada para o usuario:

1. Entrar na NVS.
2. Programar um horario ou clicar em `Executar agora`.
3. A NVS aciona o agente local.
4. O agente executa o fluxo no Mercado Livre.
5. A NVS registra o resultado.

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

- botao manual `Executar agora`;
- agenda configurada no painel.

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
6. Calcula unidades
7. Preenche campos
8. Clica Continuar
9. Se aparecer modal de produto estrela:
     clicar Continuar com meu plano atual
10. Captura plano ML e envios gerados
11. Envia resultado para NVS
12. NVS registra historico
```

## Dados minimos da tarefa

```json
{
  "id": "task-id",
  "type": "ml_full_planning",
  "status": "pending",
  "filters": [
    "WITH_CRITICAL_STOCK",
    "WITH_LOW_STOCK",
    "WITHOUT_STOCK"
  ],
  "scope": "first_page",
  "units_strategy": {
    "type": "fixed",
    "value": 200
  }
}
```

## Dados minimos do resultado

```json
{
  "status": "created",
  "ml_plan_id": "68106790",
  "inbounds": [
    {
      "id": "68106791",
      "units": 800,
      "products": 4,
      "group": "large_and_extra_large"
    },
    {
      "id": "68106792",
      "units": 2000,
      "products": 10,
      "group": "small_and_medium"
    }
  ],
  "total_units": 2800,
  "products_count": 14,
  "filled_fields": 18,
  "ignored_or_exceeded_items": 4
}
```

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
