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

- Plano aparece como `created`.
- Exibe plano ML, total de unidades, produtos e observacoes.

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

## Regras fixas ja decididas

- Escopo inicial: primeira pagina.
- Modal de estrela: sempre `Continuar com meu plano atual`.
- Chrome pessoal do usuario nao deve ser usado.
- Sessao do agente deve ser separada.
- Segredos e cookies nao devem ir para logs nem git.

## Proximos marcos

1. Criar esqueleto do agente Mac.
2. Validar login/sessao propria.
3. Rodar primeiro `run-once` sem NVS.
4. Criar fila de tarefas na NVS.
5. Conectar agente a NVS local.
6. Rodar execucao headless.
7. Preparar adaptacao Windows.
