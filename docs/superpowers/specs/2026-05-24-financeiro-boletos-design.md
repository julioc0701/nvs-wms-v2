# Financeiro — Registro de Boletos a Pagar (MVP)

**Data:** 2026-05-24
**Status:** Design aprovado, aguardando plano de implementação
**Referência conceitual:** SAP Concur / ExpenseIt (captura mobile sem fricção → painel desktop)

---

## 1. Objetivo

Permitir que operadores registrem boletos recebidos para pagamento via leitura de código de barras no celular, com painel desktop centralizado para visualização e controle pelo Master.

**Filosofia:** começar com o mínimo viável (captura + lista). Aprovação, agendamento, integração bancária e roles específicas ficam para fases futuras.

---

## 2. Escopo do MVP

### Inclui
- Scanner mobile estilo app de banco (câmera contínua → para sozinha ao detectar)
- Parser FEBRABAN local (banco, valor, vencimento) — sem chamadas externas
- Tela de confirmação com pré-preenchimento + edição rápida
- Foto opcional do boleto anexada ao registro
- Aprendizado de beneficiário por campo livre (mapping banco + identificador → razão social)
- Painel desktop com lista, filtros, drawer de detalhe e marcação "pago"
- Visibilidade do painel restrita ao operador Master

### NÃO inclui (fases futuras)
- Workflow de aprovação multi-nível
- Agendamento de pagamento / integração com banco / OFX
- OCR da foto do boleto para extração de razão social
- Recorrência (boleto mensal idêntico)
- Roles granulares além de Master
- Export contábil
- Notificações push de vencimento próximo
- Boletos de arrecadação (começam com `8`) — fora do MVP, fluxo idêntico mas parser diferente

---

## 3. Arquitetura

Segue o padrão atual do projeto: FastAPI + SQLite no backend, React + Vite no frontend (mesma SPA, rotas dedicadas para mobile e desktop).

```
┌──────────────────┐                    ┌──────────────────┐
│ Mobile (PWA)     │                    │ Desktop NVS      │
│ /financeiro/scan │                    │ /financeiro      │
│ — câmera ZXing   │                    │ — lista + drawer │
└────────┬─────────┘                    └────────┬─────────┘
         │ POST /scan                            │ GET /, PATCH, etc.
         ▼                                       ▼
         ┌────────────────────────────────────────────┐
         │ FastAPI /api/financeiro                    │
         │ — parser FEBRABAN puro                     │
         │ — match beneficiário (banco + campo livre) │
         │ — CRUD boletos                             │
         └────────────────┬───────────────────────────┘
                          ▼
                  SQLite (warehouse_v3_local.db)
                  — boletos, boleto_beneficiarios
```

---

## 4. Modelo de Dados

### Tabela `boletos`
| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK | |
| `codigo_barras` | TEXT (44) | Numérico, validado por DV FEBRABAN |
| `linha_digitavel` | TEXT (47) | Derivada do código, armazenada para exibição |
| `banco_emissor` | TEXT (3) | Primeiros 3 dígitos do código |
| `valor` | REAL | Em reais, 2 casas decimais |
| `vencimento` | DATE | Calculado do fator vencimento (base 1997-10-07) |
| `beneficiario_id` | INTEGER FK NULL | Resolvido por aprendizado |
| `beneficiario_texto` | TEXT NULL | Fallback quando não houve match |
| `observacao` | TEXT NULL | Campo livre do usuário |
| `foto_path` | TEXT NULL | Caminho relativo da foto anexada |
| `status` | TEXT | `registrado` \| `pago` (MVP só dois estados) |
| `capturado_por` | INTEGER FK operators.id | |
| `capturado_em` | DATETIME | |
| `pago_em` | DATETIME NULL | Setado ao marcar pago |
| `pago_por` | INTEGER FK operators.id NULL | |

### Tabela `boleto_beneficiarios`
| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK | |
| `razao_social` | TEXT | Como digitada pela primeira vez |
| `banco` | TEXT (3) | Banco que emite os boletos dessa empresa |
| `campo_livre_prefix` | TEXT | Primeiros 6 dígitos do campo livre — chave de match |
| `criado_em` | DATETIME | |
| `criado_por` | INTEGER FK operators.id | |

Index único composto: `(banco, campo_livre_prefix)` para evitar duplicatas.

**Migração:** seguir padrão atual do projeto — adicionar criação de tabelas e `CREATE INDEX IF NOT EXISTS` inline em `database.py → init_db()`.

---

## 5. Parser FEBRABAN

Módulo puro `backend/services/boleto_parser.py`, sem dependências externas. Função única:

```
parse_boleto(codigo_ou_linha: str) -> BoletoParsed
```

Aceita tanto código de barras (44 dígitos) quanto linha digitável (47 dígitos com formatação). Normaliza removendo espaços/pontos.

Retorna dataclass com:
- `codigo_barras: str` (44 díg)
- `linha_digitavel: str` (47 díg)
- `banco: str` (3 díg)
- `valor: Decimal`
- `vencimento: date`
- `campo_livre: str` (25 díg)
- `dv_ok: bool`

Erros: `BoletoInvalidoError` para DV inválido, formato incorreto, ou boleto de arrecadação (primeiro díg = 8 — explicitamente não suportado no MVP).

**Validação DV:** módulo 11 padrão FEBRABAN, conforme especificação.

---

## 6. Rotas da API (`/api/financeiro`)

| Método | Rota | Função |
|---|---|---|
| `POST` | `/boletos/scan` | Recebe `{codigo_ou_linha, foto_base64?}`. Parseia, tenta match beneficiário, retorna `{boleto_parsed, beneficiario_sugerido?}` (sem salvar ainda) |
| `POST` | `/boletos` | Salva boleto definitivo. Recebe `{codigo_barras, beneficiario_id? OR beneficiario_texto, observacao?, foto_base64?}`. Se `beneficiario_texto` veio e o match estava vazio, cria novo `boleto_beneficiarios` |
| `GET` | `/boletos` | Lista com filtros: `status`, `vencimento_de`, `vencimento_ate`, `beneficiario_id`, `valor_min`, `valor_max`. Ordena por vencimento ASC por padrão |
| `GET` | `/boletos/{id}` | Detalhe completo |
| `PATCH` | `/boletos/{id}` | Edita `beneficiario_id`, `beneficiario_texto`, `observacao` |
| `POST` | `/boletos/{id}/pagar` | Marca como pago. Seta `pago_em`, `pago_por`, `status='pago'` |
| `POST` | `/boletos/{id}/reabrir` | Reverte para `registrado` |
| `DELETE` | `/boletos/{id}` | Remove registro (e foto se existir). Master only |
| `GET` | `/beneficiarios` | Lista para autocomplete (busca por `q` na razão social) |
| `GET` | `/foto/{boleto_id}` | Stream da foto (se existe) |

**Autenticação:** segue padrão atual (operador logado via PIN). Painel desktop (`GET /boletos`, `PATCH`, `DELETE`, etc.) restrito ao operador cujo `name = 'Master'` no MVP. Checado no frontend (rota privada) e no backend (middleware simples que lê o operador atual da sessão). Rota mobile `POST /boletos/scan` e `POST /boletos` aberta a qualquer operador autenticado.

**Upload de foto:** base64 no payload JSON, salva em `/data/boletos/{boleto_id}.jpg` (volume Railway). Limite 2MB pré-compressão no cliente.

---

## 7. Frontend Mobile

### Rota `/financeiro/scan`

**Lib de leitura:** `@zxing/browser` (suporta Code 128 / Interleaved 2 of 5, formato dos boletos brasileiros). Alternativa avaliada: `quagga2` — descartada por menor manutenção.

**Estados da tela:**

1. **Permissão**: solicita acesso à câmera. Se negado, mostra fallback "digitar linha digitável manualmente".
2. **Scanning**: viewport fullscreen da câmera com overlay de mira centralizado. Decodificador roda contínuo (~10fps).
3. **Detecção**: ao reconhecer código com DV válido → beep + vibração → para câmera → POST `/scan` → transição para tela de confirmação.
4. **Confirmação**: card com banco (logo + nome), valor (R$ formatado), vencimento (dd/mm/aaaa + badge "vence em X dias"), campo Empresa (autocomplete `/beneficiarios?q=`), campo Observação, botão "Anexar foto" (abre câmera de novo, foto única), botão **Salvar** primário.
5. **Pós-salvar**: toast "Boleto registrado" → volta para Scanning automático após 2s (permite scan em sequência) ou botão "Voltar".

**Detalhes:**
- Detector ignora códigos repetidos consecutivos (debounce por código_barras) para evitar duplo-disparo.
- Câmera traseira preferida (`facingMode: 'environment'`).
- Tela toda otimizada para retrato; bloqueia rotação.
- PWA-friendly: funciona em Safari iOS + Chrome Android. Sem app nativo.

### Acesso
- Link no menu lateral mobile do Login / Home (visível a qualquer operador autenticado).
- Operadores não-Master não veem o painel desktop, mas conseguem escanear.

---

## 8. Frontend Desktop

### Rota `/financeiro` (Master only)

**Layout:**
- Cabeçalho: filtros inline (status, faixa de vencimento, empresa autocomplete, faixa de valor) + botão "Limpar filtros" + contador "X boletos · R$ Y total"
- Tabela principal (estilo das outras telas NVS):

| Coluna | Notas |
|---|---|
| Empresa | Razão social ou texto livre |
| Valor | Direita, formatado R$ |
| Vencimento | dd/mm/aaaa + badge urgência (vencido = vermelho, ≤3 dias = laranja, ≤7 dias = amarelo) |
| Banco | Código + nome curto (237 = Bradesco, etc. — lookup local) |
| Capturado por | Nome do operador |
| Capturado em | dd/mm hh:mm |
| Status | Badge `registrado` / `pago` |
| Ações | Olho (abre drawer) + ✓ (marcar pago direto) |

**Drawer de detalhe** (abre à direita ao clicar na linha):
- Todos os campos
- Foto (se existe) com lightbox ao clicar
- Linha digitável formatada com botão "copiar"
- Histórico mínimo: capturado em / pago em
- Botões: **Editar** (empresa, obs), **Marcar como pago** / **Reabrir**, **Excluir** (confirmação)

**Sem audit log no MVP.** Edições e mudanças de status não geram trilha. Se a necessidade aparecer, vira `boleto_eventos` em fase futura.

### Acesso
- Item "Financeiro" no menu lateral do desktop, visível só para operador Master.

---

## 9. Fluxo de Match de Beneficiário

```
scan → parse_boleto(codigo)
       ↓
       (banco, campo_livre[0:6])
       ↓
       SELECT * FROM boleto_beneficiarios WHERE banco=? AND campo_livre_prefix=?
       ↓
       Achou? → retorna beneficiario_id sugerido (pré-preenche campo Empresa)
       Não achou? → campo Empresa vem vazio, usuário digita
       ↓
       No POST /boletos:
         - se veio beneficiario_id → linka
         - se veio beneficiario_texto e não havia match → cria boleto_beneficiarios novo + linka
         - se veio só texto e havia match → ignora o match, usa o texto (usuário escolheu sobrescrever)
```

**Garantia:** segundo scan do mesmo boleto recorrente pré-preenche empresa automaticamente.

---

## 10. Tratamento de Erros

| Cenário | Comportamento |
|---|---|
| DV inválido no scan | Câmera continua rodando, toast discreto "Código inválido" — não bloqueia tentativas |
| Boleto duplicado (mesmo código já existe) | POST `/boletos` retorna 409 + payload `{boleto_existente: {id, capturado_em, capturado_por}}`. Mobile mostra modal "Este boleto já foi registrado em DD/MM por Fulano. Abrir registro existente?" |
| Boleto de arrecadação (díg 1 = 8) | Parser lança erro, mobile mostra "Tipo de boleto não suportado no momento" |
| Câmera negada | Fallback: input texto para linha digitável (47 díg formatada ou colada) |
| Foto > 2MB | Cliente comprime via canvas antes do upload; se ainda exceder, mostra erro |
| Backend offline | Mobile mantém botão Salvar habilitado mas falha → toast "Sem conexão, tente novamente". Sem fila offline no MVP |

---

## 11. Testes

Seguindo a disciplina TDD do projeto:

- **Parser FEBRABAN** (`boleto_parser.py`): unit tests cobrindo
  - Códigos válidos de bancos diferentes (Itaú 341, Bradesco 237, Santander 033, BB 001, Caixa 104)
  - Linha digitável com e sem formatação
  - DV inválido
  - Boleto de arrecadação (deve lançar erro)
  - Vencimento em datas-limite (fator 0000, fator máximo)
  - Valor zero / valor máximo
- **Match de beneficiário**: integração com SQLite em memória, asserções sobre criação automática
- **Rotas**: smoke tests dos endpoints principais (scan, salvar, listar, pagar)
- **Frontend**: sem testes automatizados no MVP (segue padrão atual do projeto, validação manual via preview)

---

## 12. Riscos e Mitigações

| Risco | Mitigação |
|---|---|
| Leitura de barcode em câmera de celular ruim | ZXing tem performance aceitável; fallback de digitação manual sempre disponível |
| Foto pesa banda em conexão de obra/galpão | Compressão client-side para ~200KB antes do upload |
| Volume Railway não persiste fotos | Confirmar que `/data` está montado como volume (já está, pelo `DATABASE_URL`) |
| Match errado de beneficiário (dois clientes diferentes do mesmo banco com prefixo igual) | Usuário pode sobrescrever digitando outro nome; sistema NÃO recria automaticamente, vira responsabilidade manual |
| Boleto registrado e perdido (sem marcação de pago) | Painel desktop já resolve via filtro vencimento + badge urgência |

---

## 13. Próximos Passos (pós-MVP)

Não fazem parte deste design, listados apenas para contexto:

- Roles específicas (Financeiro, Aprovador) substituindo "só Master"
- Workflow de aprovação (rascunho → submetido → aprovado → pago)
- OCR da foto para extração automática de razão social (Groq vision já disponível no projeto via `GROQ_API_KEY`)
- Suporte a boletos de arrecadação (díg 1 = 8)
- Agendamento + integração com OFX / API bancária para baixa automática
- Notificação de vencimento próximo (push web ou email)
- Recorrência (detectar boleto mensal repetido, gerar lembrete)
- Exportação para contábil (CSV / planilha mensal)

---

## 14. Open Questions

Nenhuma. Todas as decisões foram resolvidas durante o brainstorming:
- Beneficiário: aprendizado por campo livre + autocomplete (resposta consolidada Q1)
- Foto: opcional, anexada na confirmação (resposta Q2 = B)
- Visibilidade: painel desktop só Master; mobile aberto a qualquer operador (resposta Q3)
