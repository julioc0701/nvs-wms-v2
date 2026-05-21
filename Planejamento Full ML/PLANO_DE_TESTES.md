# Plano de Testes - Planejamento Full ML

## Objetivo

Validar que a NVS consegue disparar um agente local para criar planos Full no Mercado Livre e registrar o resultado.

## Ambientes

### Local Mac

Usado para o piloto inicial.

- NVS local.
- Agente local.
- Playwright/Chromium.
- Sessao Mercado Livre salva localmente.

### Railway

Usado para validar o modelo real de painel.

- NVS hospedada.
- Agente local conectado ao Railway.
- Resultado registrado no banco da NVS.

### Windows futuro

Usado depois do piloto Mac.

- Agente instalado como servico ou tarefa de inicializacao.
- Sessao ML local.
- Conexao com NVS Railway.

## Casos de teste

### T01 - Login inicial

Objetivo: criar sessao Mercado Livre propria do agente.

Passos:

1. Rodar comando de login.
2. Abrir Chromium do agente.
3. Fazer login no ML.
4. Salvar sessao.
5. Fechar navegador.
6. Rodar check de sessao.

Esperado:

- Acesso ao ML sem novo login.
- Sessao salva fora do Chrome pessoal.

### T02 - Acesso ao Planejamento Full

Objetivo: confirmar acesso a tela certa.

Passos:

1. Abrir URL filtrada do planejamento.
2. Esperar tabela carregar.
3. Ler quantidade de resultados.

Esperado:

- Pagina carrega.
- Filtros aparecem.
- Campos de unidades aparecem.

### T03 - Preenchimento da primeira pagina

Objetivo: preencher unidades na primeira pagina.

Passos:

1. Usar valor fixo `200`.
2. Preencher todos os campos da primeira pagina.
3. Disparar eventos de input/change.
4. Aguardar recalculo do ML.

Esperado:

- Campos mostram `200`.
- Total do ML atualiza.
- Botao `Continuar` fica habilitado.

### T04 - Modal de produto estrela

Objetivo: garantir regra fixa do modal.

Passos:

1. Clicar `Continuar`.
2. Se aparecer modal de produto estrela, clicar `Continuar com meu plano atual`.

Esperado:

- Agente nunca clica em `Conferir produto estrela`.
- Fluxo segue com o plano atual.

### T05 - Criacao do plano

Objetivo: confirmar criacao do plano no ML.

Passos:

1. Concluir fluxo.
2. Aguardar pagina de plano/envios.
3. Capturar ID do plano pela URL.
4. Capturar IDs dos envios.
5. Capturar unidades e produtos por envio.

Esperado:

- URL no formato `/shipping/plans/{plan_id}/inbounds`.
- Pelo menos um envio gerado.
- Totais capturados.

### T06 - Registro na NVS

Objetivo: salvar resultado no painel.

Passos:

1. Agente envia resultado para a NVS.
2. NVS grava historico.
3. Abrir tela `Planejamento Full`.

Esperado:

- Envios aparecem como `created`.
- Exibe uma linha por envio ML.
- Cada envio mostra plano pai, produtos, unidades e grupo.

Status em 2026-05-20:

- Registro de plano criado validado nas execucoes reais anteriores.
- Registro por tarefa automatizada validado em simulacao.
- A tarefa `simulate` retornou para a NVS com status `simulated`, total de unidades, produtos e lista de itens calculados.

Status em 2026-05-21:

- Registro por envio validado.
- Plano pai `68116007` gerou dois registros na NVS:
  - envio `68116009`, 3 produtos, 186 unidades;
  - envio `68116010`, 9 produtos, 459 unidades.

### T06B - Disparo NVS para agente local

Objetivo: validar que o painel da NVS consegue criar uma tarefa para o agente local.

Passos:

1. Abrir `Supervisao Full > Planejamento Full`.
2. Conferir o painel `Agente Full ML`.
3. Selecionar estrategia `Formula: vendas + percentual`.
4. Usar `% extra = 20` e `minimo = 0`.
5. Clicar `Simular sem salvar`.
6. Rodar o agente local com `npm run ml:agent-once`.
7. Conferir a tarefa em `Tarefas recentes`.

Esperado:

- NVS cria tarefa `pending`.
- Agente transforma a tarefa em `running`.
- Agente executa o preenchimento no Mercado Livre.
- NVS recebe status final `simulated` ou `created`.
- Em simulacao, nenhum plano e salvo no Mercado Livre.

Status em 2026-05-20:

- Validado pela API local.
- Tarefa criada na NVS e consumida pelo agente.
- Resultado retornou com 12 produtos e 643 unidades.

Status em 2026-05-21:

- Validado end-to-end pelo botao da tela.
- Agente continuo pegou a tarefa automaticamente.
- Nao foi necessario rodar `agent-once` manualmente.

### T07 - Sessao expirada

Objetivo: tratar necessidade de login.

Passos:

1. Invalidar ou remover sessao local.
2. Rodar agente.

Esperado:

- Agente nao tenta concluir fluxo sem login.
- NVS registra `precisa_login`.

### T08 - Agente offline

Objetivo: mostrar status correto.

Passos:

1. Parar agente.
2. Clicar `Executar agora` na NVS.

Esperado:

- NVS registra tarefa pendente ou falha por agente offline.
- Usuario entende que precisa ligar/iniciar o agente.

### T09 - Execucao headless

Objetivo: garantir execucao transparente.

Passos:

1. Rodar agente em modo invisivel.
2. Disparar execucao pela NVS.
3. Usar a maquina normalmente durante o teste.

Esperado:

- Nenhuma janela interfere no usuario.
- Plano e registrado.
- Logs/screenshot ficam disponiveis para auditoria.

### T11 - Paginacao do Planejamento Full

Objetivo: garantir que o agente percorre todas as paginas antes de simular ou salvar.

Passos:

1. Usar a URL com filtros amplos e ordenacao por GMV.
2. Clicar `Simular` na NVS.
3. Aguardar o agente finalizar.
4. Conferir o log da tarefa.

Esperado:

- `pagesProcessed` maior que 1 quando o ML exibir paginacao.
- `pageResults` lista cada pagina processada.
- `filledFields` soma os campos preenchidos em todas as paginas.
- Nenhum clique em `Continuar` deve ocorrer na simulacao.
- Trace deve mostrar navegacao entre paginas.

## Evidencias por execucao

Cada execucao deve gerar:

- ID da tarefa NVS.
- Data/hora inicio.
- Data/hora fim.
- Status final.
- Plano ML.
- Envios ML.
- Total de unidades.
- Total de produtos.
- Mensagem de erro, se houver.
- Screenshot opcional em erro.

### T10 - Tela operacional sem excesso visual

Objetivo: garantir que a tela priorize envios e mantenha controles secundarios compactos.

Passos:

1. Abrir `Supervisao Full > Planejamento Full`.
2. Conferir os cards superiores.
3. Conferir a lista de envios.
4. Alternar filtro de data.
5. Expandir e recolher tarefas pelo botao `+`.

Esperado:

- Cards com contorno visivel.
- Linhas de envio alternadas com fundo azul suave.
- Sem rolagem horizontal para ver data, envio, grupo, produtos, unidades e origem.
- Painel do agente compacto.
- Tarefas recolhidas por padrao e expansivas quando necessario.

## Regras fixas ja decididas

- Escopo inicial: primeira pagina.
- Modal de estrela: sempre `Continuar com meu plano atual`.
- Chrome pessoal do usuario nao deve ser usado.
- Sessao do agente deve ser separada.
- Segredos e cookies nao devem ir para logs nem git.
- Primeira onda: execucao manual, sem agendamento.
- Historico operacional: uma linha por envio ML.
- Plano pai fica preservado no payload para auditoria.
- Regra atual para resultados negativos: preencher `0`, sem minimo artificial.

## Proximos marcos

1. Refinar tela operacional do Planejamento Full.
2. Preparar empacotamento do agente para Windows/Mac.
3. Conectar o agente local ao Railway com token seguro.
4. Criar fluxo de renovacao de login quando a sessao ML expirar.
5. Avaliar agendamento somente depois da primeira onda manual estabilizada.
