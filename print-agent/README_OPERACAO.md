# NVS Zebra Agent - Guia de Operacao

Este diretorio separa dois usos:

- Desenvolvimento: sua maquina, com Python/Node, usada para editar, testar e compilar.
- Operacao: maquinas do armazem, sem Python/Node, rodando apenas `.exe` + `.bat`.

## Qual arquivo usar

Na sua maquina de desenvolvimento, use:

```bat
iniciar_agente.bat
```

Para gerar um pacote fechado para operacao, use:

```bat
build_operacao.bat
```

Ele monta:

```text
print-agent\release\
  ZebraAgent-WP.exe
  iniciar_operacao.bat
  README_OPERACAO.md
```

Na maquina da operacao, copie a pasta `release` para algo como:

```text
C:\NVS-ZebraAgent
```

Depois rode:

```bat
iniciar_operacao.bat
```

A maquina da operacao nao precisa ter Python, Node, pip, npm ou pyinstaller.

## MACHINE_ID unico

Cada maquina precisa ter um `MACHINE_ID` diferente dentro do `iniciar_operacao.bat`.

Exemplos:

```text
MAQUINA_1
MAQUINA_2
MAQUINA_3
MAQUINA_4
```

Se duas maquinas usam o mesmo `MACHINE_ID`, uma conexao substitui a outra no backend. Isso pode causar parada de impressao, reentrega de jobs e comportamento intermitente.

## Correcoes de confiabilidade incluidas

- O agente envia o ZPL inteiro do job como um unico documento RAW para o spooler do Windows.
- O backend registra qual maquina recebeu o job (`claimed_by`) e quando iniciou (`claimed_at`/`started_at`).
- Cada envio recebe `job_token`; o backend ignora resultado vindo de maquina/token errado.
- O status dos agentes mostra maquina, impressora, versao, ocupacao e job atual.
- O comando remoto de limpar spooler nao e enviado para agente ocupado.

Esses pontos atacam o problema de mistura de SKUs no meio da impressao e melhoram a auditoria quando houver falha rara.

## Arquivos antigos

Evite usar arquivos antigos ou de teste na operacao. O caminho recomendado e sempre:

```text
release\iniciar_operacao.bat
```

Depois de qualquer alteracao no `agent.py`, gere novamente o pacote com `build_operacao.bat` antes de copiar para as maquinas.
