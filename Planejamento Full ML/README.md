# Planejamento Full ML

Este diretorio centraliza o desenho do novo modulo de Planejamento Full do Mercado Livre para o NVS.

Objetivo do modulo:

- Programar execucoes de planejamento Full pela NVS.
- Permitir disparo manual pelo painel.
- Acionar um agente local conectado a NVS.
- Executar o fluxo no Mercado Livre com navegador automatizado.
- Registrar no painel o resultado gerado: plano ML, envios, unidades, produtos, status e logs.

## Decisao de arquitetura

A criacao real do plano acontece sempre no ambiente do Mercado Livre. A NVS nao substitui o Mercado Livre; ela vira o painel de controle, programacao e auditoria.

Como a API publica do Mercado Livre nao oferece hoje uma operacao oficial para criar o planejamento Full, o MVP usara um agente local com Playwright/Chromium autenticado em uma sessao do Mercado Livre.

## Componentes

```text
NVS no Railway
  - cadastra regras
  - agenda execucoes
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

Esses artefatos sao locais e nao devem ser versionados.

## Documentos

- [ARQUITETURA_AGENTE_LOCAL.md](ARQUITETURA_AGENTE_LOCAL.md)
- [RUNBOOK_MAC_PILOTO.md](RUNBOOK_MAC_PILOTO.md)
- [PLANO_DE_TESTES.md](PLANO_DE_TESTES.md)
