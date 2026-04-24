# NVS Zebra Agent - Guia de Operacao

Este diretorio agora separa dois mundos:

- Desenvolvimento: sua maquina, com Python/Node, usada para editar e compilar.
- Operacao: maquinas do armazem, sem Python/Node, rodando apenas `.exe` + `.bat`.

## Arquivo certo para cada caso

### Na sua maquina de desenvolvimento

Use:

```bat
iniciar_agente.bat
```

Esse modo roda `agent.py` com Python e serve para testar alteracoes no codigo.

Para gerar o pacote fechado da operacao, use:

```bat
build_operacao.bat
```

Ele gera:

```text
print-agent\release\
  ZebraAgent-WP.exe
  iniciar_operacao.bat
  README_OPERACAO.md
```

### Na maquina da operacao

Copie a pasta `release` para algo como:

```text
C:\NVS-ZebraAgent
```

Depois rode:

```bat
iniciar_operacao.bat
```

A maquina da operacao nao precisa ter Python, Node, pip, npm ou pyinstaller.

## Regra obrigatoria: MACHINE_ID unico

Cada maquina precisa ter um `MACHINE_ID` diferente dentro do `iniciar_operacao.bat`.

Exemplo:

```bat
MAQUINA_1
MAQUINA_2
MAQUINA_3
MAQUINA_4
```

Se duas maquinas usam o mesmo `MACHINE_ID`, uma conexao derruba/substitui a outra no backend. Isso pode causar parada de impressao, reentrega de jobs e comportamento intermitente.

## Arquivos legados ou de desenvolvimento

Evite usar estes arquivos na operacao:

- `iniciar_producao.bat`: script antigo, ainda tenta escolher executavel de lugares diferentes.
- `ZEBRA_INDUSTRIAL_V2.exe`: versao antiga.
- `dist\ZebraAgent-WP.exe`: artefato antigo de build.
- `agent_test.py`: teste antigo HTTP/local, nao e o fluxo WebSocket atual.
- `test_connection.py` e `test_prod_workflow.py`: diagnosticos antigos com URLs antigas.

## Fluxo recomendado

1. Alterar/testar `agent.py` na maquina de desenvolvimento.
2. Rodar `build_operacao.bat`.
3. Copiar `print-agent\release` para cada maquina.
4. Editar `MACHINE_ID` em cada maquina.
5. Rodar `iniciar_operacao.bat`.
6. No sistema, conferir se `/api/zebra/agent-status` mostra as maquinas esperadas.

## Observacao importante sobre falhas atuais

O agente atual ainda pode misturar fisicamente etiquetas quando um SKU gera muitos blocos ZPL e outro job entra na fila do Windows no meio. A proxima correcao tecnica recomendada e tornar cada job um documento RAW unico no spooler e adicionar ownership de job no backend.
