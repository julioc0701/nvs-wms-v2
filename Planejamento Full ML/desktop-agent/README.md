# NVS Full Agent Desktop

Aplicativo desktop do agente local do Planejamento Full ML.

Ele nao substitui o motor do agente. Ele e a embalagem operacional para uma maquina de usuario:

- configura a URL da NVS;
- configura o ID da maquina/agente;
- abre o Chromium separado para login no Mercado Livre;
- salva a sessao local do Mercado Livre;
- inicia e para o agente em segundo plano;
- exibe logs basicos para suporte.

## Estrutura

```text
desktop-agent/
  src/main.js              processo principal Electron
  src/preload.js           ponte segura entre tela e processo principal
  src/renderer/            tela local do operador/suporte

../agent/
  src/agent.js             motor continuo que consulta a NVS
  src/run-once.js          fluxo real no Mercado Livre
  storage/                 sessao local do Mercado Livre, ignorada pelo git
  logs/ screenshots/       auditoria local, ignorada pelo git
```

## Como testar no Mac em modo desenvolvimento

Na pasta `Planejamento Full ML/desktop-agent`:

```bash
npm run prepare:agent
npm install
npm run dev
```

Fluxo esperado:

1. informar a URL da NVS;
2. informar o ID do agente;
3. clicar em `Salvar`;
4. clicar em `Conectar Mercado Livre`;
5. fazer login no Chromium aberto;
6. voltar para o app e clicar em `Salvar sessao`;
7. clicar em `Validar sessao`;
8. clicar em `Iniciar agente`;
9. disparar `Executar e salvar` dentro da NVS.

## Como gerar pacote local

Ainda na pasta `desktop-agent`:

```bash
npm run pack
```

Para instalador Windows:

```bash
npm run dist:win
```

Observacao: o ideal e gerar o `.exe` em uma maquina Windows ou em um pipeline preparado para build Windows. O usuario final nao deve precisar instalar Node, Python ou Playwright manualmente; isso deve ir empacotado no instalador.

## O que deve ir para a maquina Windows

Para teste de PRD com usuario sem ferramentas de desenvolvimento, o melhor caminho e entregar o instalador gerado em `dist/`, nao a pasta fonte.

Se for compartilhar a pasta fonte para um teste tecnico, a maquina ainda precisara de Node/npm para rodar `npm install` e `npm run dev`. Isso serve para desenvolvimento, mas nao e o formato final do usuario.

## Pontos de atencao para o instalador final

- incluir o motor `../agent` como recurso do app;
- incluir `node_modules` do agente, especialmente Playwright;
- garantir que o Chromium do Playwright esteja disponivel no Windows;
- guardar `settings.json` e a sessao ML no perfil local do usuario;
- nunca versionar ou enviar `storage/ml-session.json`;
- futuramente, iniciar junto com o Windows ou registrar como servico/tarefa.
