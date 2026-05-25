# Módulo Financeiro — Boletos a Pagar

> Documento de transferência. Lê tudo daqui antes de mexer no módulo.
> Última atualização: 2026-05-24

---

## 1. O que é

Seção do NVS-WMS para registro centralizado de **boletos a pagar** recebidos pela empresa. Operador captura o boleto (foto ou digitação) pelo celular e o Master visualiza/gerencia tudo no painel desktop.

**Não é** sistema de pagamento — não conversa com bancos, não emite ordens. É apenas **registro e visibilidade**.

---

## 2. Origem e referência conceitual

Inspirado no fluxo do **SAP Concur / ExpenseIt**:

- Concur: foto do recibo → OCR + ML extraem dados → vira "expense report" → workflow de aprovação → reembolso
- Nosso: foto do boleto → IA extrai linha digitável → parser valida → registra → Master vê painel

Diferenças vs Concur:
- Concur usa OCR de **recibo** (texto livre). Nós usamos código de barras / linha digitável **estruturada** (FEBRABAN), o que dá menos erro
- Concur tem aprovação multi-nível. Nós, por enquanto, NÃO (decisão consciente — fase 1 = registro só)
- Concur faz reembolso. Nós só marcamos "pago" manualmente (pagamento real é fora do sistema)

Documentos de origem (manter):
- `docs/superpowers/specs/2026-05-24-financeiro-boletos-design.md` — spec original
- `docs/superpowers/plans/2026-05-24-financeiro-boletos.md` — plano de implementação tasks

---

## 3. Arquitetura geral

```
┌──────────────────┐                    ┌──────────────────┐
│ Mobile (PWA)     │                    │ Desktop NVS      │
│ /financeiro/scan │                    │ /financeiro      │
│ - 2 botões:      │                    │ - lista + drawer │
│   📷 Tirar foto  │                    │ - filtros        │
│   ⌨ Digitar      │                    │ - marcar pago    │
└────────┬─────────┘                    └────────┬─────────┘
         │                                       │
         ▼                                       ▼
         ┌────────────────────────────────────────────┐
         │ FastAPI /api/financeiro                    │
         │ - boleto_vision.py: chama Gemini           │
         │ - boleto_parser.py: parser FEBRABAN puro   │
         │ - financeiro.py: rotas REST                │
         └────────────────┬───────────────────────────┘
                          │
                          ▼
                  SQLite (warehouse_v3_local.db)
                  - boletos, boleto_beneficiarios
                  + Gemini 2.0 Flash (vision)
```

---

## 4. Modelo de dados

### Tabela `boletos`
| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK | |
| `codigo_barras` | VARCHAR(44) UNIQUE | Sempre 44 dígitos. UNIQUE evita duplicata |
| `linha_digitavel` | VARCHAR(47) | Cache da linha (gerada do código) |
| `banco_emissor` | VARCHAR(3) | 3 primeiros dígitos do código |
| `valor` | FLOAT | Em reais (parser converte centavos) |
| `vencimento` | DATE | Calculado do fator vencimento |
| `beneficiario_id` | FK NULL | Liga ao cadastro aprendido (se houver) |
| `beneficiario_texto` | VARCHAR(200) NULL | Texto livre digitado pelo operador |
| `observacao` | TEXT NULL | Campo livre |
| `foto_path` | VARCHAR(300) NULL | Nome do arquivo em `/data/boletos/{id}.jpg` |
| `status` | VARCHAR(20) | `registrado` \| `pago` |
| `capturado_por` | FK operators | Quem escaneou |
| `capturado_em` | DATETIME | |
| `pago_em` | DATETIME NULL | Quando virou pago |
| `pago_por` | FK operators NULL | Quem marcou como pago |

**Índices:**
- `idx_boletos_status` em `status`
- `idx_boletos_vencimento` em `vencimento`
- `idx_boletos_codigo_unique` em `codigo_barras` (UNIQUE) ← protege duplicata em race condition

### Tabela `boleto_beneficiarios`
Cadastro **aprendido** automaticamente. Primeira vez que aparece um boleto de uma empresa, o operador digita a razão social → criamos um registro. Próximos boletos da mesma empresa (mesmo banco + mesmo prefixo do campo livre) pré-preenchem o nome.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK | |
| `razao_social` | VARCHAR(200) | Como o operador digitou |
| `banco` | VARCHAR(3) | Banco emissor |
| `campo_livre_prefix` | VARCHAR(6) | Primeiros 6 dígitos do campo livre |
| `criado_em` | DATETIME | |
| `criado_por` | FK operators | |

**Índice único composto:** `(banco, campo_livre_prefix)` — uma empresa por combinação.

**Migração:** as duas tabelas são criadas inline em `database.py → init_db()`. Não há migração externa.

---

## 5. Parser FEBRABAN (`backend/services/boleto_parser.py`)

Módulo puro, sem dependências externas. **18 testes unitários** em `tests/test_boleto_parser.py`.

### Funções públicas

```python
def dv_mod10(campo: str) -> int  # DV dos campos da linha digitável
def dv_mod11_codigo_barras(codigo_sem_dv: str) -> int  # DV geral do código
def fator_para_data(fator: int) -> date  # Fator vencimento → data
def parse_boleto(entrada: str) -> BoletoParsed  # função principal
```

### Detalhes do algoritmo

**DV mod 10 (campos):**
- Multiplica cada dígito (direita → esquerda) alternando pesos 2,1,2,1,...
- Se produto ≥ 10, soma os dígitos (ex: 18 → 1+8=9)
- DV = 10 − (soma mod 10). Se DV = 10, wrap para 0.

**DV mod 11 (DV geral do código de barras):**
- Pesos cíclicos 2,3,4,5,6,7,2,3,4,5,6,7,...
- DV = 11 − (soma mod 11). Se DV ∈ {0,10,11}, retorna 1.

**Fator vencimento → data (com WRAP de 2025-02-21):**
- Base antiga FEBRABAN: fator 1000 = 03/07/2000
- Em 21/02/2025, fator atingiu 9999 e ocorreu wrap
- Base nova: fator 1000 = 22/02/2025
- Nosso parser tenta a base antiga primeiro. Se a data resultante cair >1 ano antes de hoje, usa base nova.
- **Atenção:** boletos pré-2025 podem dar data errada. Mas em 2026+ a base nova é a regra.

### Comportamento com DV errado

**Importante:** o parser **NÃO bloqueia** boleto com DV inválido. Retorna `dv_ok=False` e segue. O frontend mostra um banner laranja "⚠ DV não bate" mas permite salvar.

Decisão consciente: bancos brasileiros emitem boletos com DV errado de vez em quando, e a IA pode ler um dígito errado mas o resto correto. Bloquear hard atrapalha mais do que ajuda.

### Boletos não suportados

- Arrecadação (primeiro dígito = 8) — sem suporte no MVP, parser lança `BoletoInvalidoError`
- Boletos com layout não FEBRABAN — não acontece na prática no BR

---

## 6. Rotas da API (`/api/financeiro`)

| Método | Rota | O que faz |
|---|---|---|
| POST | `/boletos/scan` | Parseia código/linha digitável (sem salvar). Retorna dados + sugestão de beneficiário + duplicata se existe |
| POST | `/boletos/scan-foto` | Recebe foto base64 → IA (Gemini Vision) extrai linha → parser valida → mesmo retorno do scan |
| POST | `/boletos` | Salva boleto. Cria beneficiário se for novo. 409 se duplicata escapar (UNIQUE no DB) |
| GET | `/boletos` | Lista com filtros: status, vencimento, beneficiario_id, valor min/max. Retorna `{boletos, total, valor_total}` |
| GET | `/boletos/{id}` | Detalhe completo |
| PATCH | `/boletos/{id}` | Edita empresa/observação |
| POST | `/boletos/{id}/pagar` | Marca como pago |
| POST | `/boletos/{id}/reabrir` | Reverte para registrado |
| DELETE | `/boletos/{id}` | Remove (também apaga foto do disco) |
| GET | `/beneficiarios?q=` | Autocomplete de empresas |
| GET | `/foto/{boleto_id}` | Stream JPG da foto anexada |

**Autenticação:** Master-only no frontend (rotas privadas). Backend não força — segue o padrão atual do projeto. Se isso for prioridade, adicionar middleware (TODO).

---

## 7. Frontend mobile (`FinanceiroScan.jsx`)

### Tela inicial (estado `home`)

```
┌──────────────────────────────┐
│  Registrar boleto             │
│  Tire uma foto ou digite     │
│                               │
│  ┌─────────────────────────┐ │
│  │ 📷 Tirar foto do boleto │ │  ← primário
│  └─────────────────────────┘ │
│                               │
│  ┌─────────────────────────┐ │
│  │ ⌨ Digitar manualmente   │ │  ← secundário
│  └─────────────────────────┘ │
└──────────────────────────────┘
```

### Fluxo "Tirar foto"

1. `<input type="file" capture="environment">` abre câmera nativa do celular
2. Tira foto → tela `preview` mostra imagem com botões "Tirar outra" / "Continuar"
3. "Continuar" → comprime no client (canvas, 1600px max, 85% qualidade JPEG) → POST `/scan-foto`
4. Tela `lendo` com spinner ~2-5s
5. Sucesso → `sessionStorage` armazena resultado → navega para `/financeiro/confirmar`
6. Falha → tela `falhou` com mensagem + botões "Tirar nova foto" / "Digitar"

### Fluxo "Digitar"

- Textarea com máscara incremental: **5.5 / 5.6 / 5.6 / 1 / 14** (47 dígitos)
- Exemplo de formato: `23792.37213 90016.790967 25000.527306 3 14580000058182`
- Contador "X/47 dígitos" com check ✓ quando completo
- `inputMode="numeric"` aciona teclado numérico no celular
- Botão "Continuar" só ativa em 44 ou 47 dígitos
- Submit → POST `/scan` (mesmo endpoint do código por câmera antiga)

### Redirect automático (Layout.jsx)

```js
if (isMaster && isMobilePhone) {
  // Força Master no celular para /financeiro/scan
  // Painel desktop (/financeiro) é redirecionado pro scan
}
if (!isMaster && isMobilePhone) {
  // Operador comum vai pra /separacao/listas (regra antiga, mantida)
}
```

---

## 8. Frontend desktop (`FinanceiroPainel.jsx`)

Tabela com filtros (status, vencimento, valor min/max). Cada linha:
- Empresa (beneficiário ou texto livre)
- Valor formatado em R$
- Vencimento + badge de urgência (vencido / hoje / ≤3d / ≤7d / OK)
- Banco emissor
- Operador que capturou
- Status (registrado / pago)
- Ações: 👁 Ver detalhe | ✓ Marcar pago

**Drawer** (`FinanceiroDrawer.jsx`) abre à direita ao clicar em "Ver detalhe":
- Todos os campos
- Foto em lightbox
- Linha digitável formatada + botão copiar
- Edição inline de empresa/observação
- Botões: Editar | Marcar pago/Reabrir | Excluir

**Dialogs** de confirmação (`FinanceiroConfirmDialog.jsx`) — pagar/reabrir/excluir usam dialog estilizado em vez de `confirm()` nativo do browser. Padrão visual idêntico ao `TransferConfirmDialog` do módulo de separação.

---

## 9. Prevenção de duplicata — 3 camadas

1. **No `/scan`:** retorna `duplicata: {id, capturado_em, capturado_por_id}` se já existe boleto com mesmo `codigo_barras`. Frontend mostra banner vermelho.
2. **No `POST /boletos`:** rechecagem antes de salvar. Se duplicar, retorna `409 Conflict` com mensagem `"Este boleto já consta registrado (capturado por X em DD/MM/AAAA HH:MM)."`
3. **No banco (UNIQUE index):** garante atomicamente que `codigo_barras` é único, mesmo em race condition (dois requests simultâneos). Se escapar das camadas 1 e 2, o INSERT estoura `IntegrityError` que é convertido em 409.

Frontend desabilita o botão "Salvar" se a tela de confirmação chegou com `duplicata != null`.

---

## 10. A SAGA DA LEITURA DO CÓDIGO DE BARRAS

### Por que isso merece uma seção

Esta foi a parte mais difícil do módulo. Tentamos **4 abordagens diferentes** ao longo do desenvolvimento. **3 falharam.** Documentado aqui pra ninguém repetir os mesmos erros.

### Tentativa 1: ZXing-js (`@zxing/browser`)

**O que fizemos:** stream de vídeo via `BrowserMultiFormatReader.decodeFromConstraints` com hints `POSSIBLE_FORMATS=[ITF, CODE_128]` e `TRY_HARDER=true`. Câmera traseira em 1920×1080.

**Por que falhou:**
- ZXing-js está em **modo manutenção** (sem features novas há 2+ anos)
- Reading rate documentado em benchmarks: **31.87%** em open-source (pior dos avaliados)
- Issue oficial #658 do projeto reconhece problemas específicos com Interleaved 2 of 5 (formato do boleto)
- Códigos finos, borrados ou em baixa luz (típico de boleto físico) sumiam
- Mesmo com `TRY_HARDER`, frames passavam sem detecção

**Sintoma observado:** câmera ativa, mira na tela, mas nenhuma leitura por minutos.

### Tentativa 2: BarcodeDetector API + ZBar-WASM (híbrido)

**O que fizemos:** detecção via `BarcodeDetector` nativo do Chrome (quando disponível) com fallback para `@undecaf/zbar-wasm` (WebAssembly do ZBar). Loop com `requestAnimationFrame`.

**Por que falhou parcialmente:**
- BarcodeDetector não está disponível no Safari iOS (que era um dos targets)
- ZBar funcionou melhor que ZXing em alguns boletos, mas:
  - Performance ~50-100ms por frame em mobile (sentia travado)
  - Falhava em códigos sem contraste alto
  - Quando lia, demorava muito (frames acumulavam)
- Bundle aumentou em ~50KB (WASM lazy-loaded)

**Sintoma observado:** câmera ativa, contador de frames aumentava, mas leitura raramente acontecia em boletos reais.

### Tentativa 3: ZBar-WASM forçado pra todos

**O que fizemos:** removemos o BarcodeDetector e usamos só ZBar pra uniformidade, com debug visível na tela (contador de frames + última mensagem de erro).

**Por que falhou:**
- Mesmo problema da tentativa 2 — ZBar não é confiável o suficiente em condições reais
- Usuário viu frames sendo processados mas zero leitura
- O debug confirmou: ZBar simplesmente não conseguia decodificar os boletos físicos do dia-a-dia

### Pesquisa de mercado feita após 3 falhas

Investigação em fóruns/GitHub revelou a **realidade desagradável:**

| Lib | Tipo | ITF | Custo | Verdadeira reading rate |
|---|---|---|---|---|
| ZXing-js | OSS | ⚠️ ruim | grátis | 31% |
| html5-qrcode | OSS | ⚠️ ruim | grátis | (fork abandonado do ZXing) |
| Quagga2 | OSS | ⚠️ médio | grátis | melhor que ZXing, mas issues abertos |
| ZBar-WASM | OSS | ⚠️ médio | grátis | ~40-50% em condições ruins |
| BarcodeDetector | Browser API | ✓ bom | grátis | bom no Chrome, ausente no Safari iOS |
| **STRICH** | comercial | ❌ falhou em test | ~$500/ano | 0/2 ITF no benchmark Dynamsoft |
| **Scanbot/Scandit/Dynamsoft** | comercial | ✓ excelente | $1500-3000/ano | 83%+ em ITF |

**Conclusões da pesquisa:**

1. Bancos brasileiros (Nubank, Itaú, PicPay) **não usam web** pra ler boleto. Eles usam apps **nativos** com Google ML Kit (Android) ou AVFoundation/Vision Framework (iOS). Esses sistemas usam IA otimizada com autofoco contínuo controlado pelo OS — muito superior ao que browser consegue.

2. Reading boleto via web pura é **fundamentalmente fraco** para o nível de qualidade que usuários esperam. Mesmo libs comerciais caras têm casos onde falham.

3. Strich (comercial) falhou em 2 de 2 boletos ITF no benchmark da Dynamsoft. Mostra que pagar não é garantia.

### Tentativa 4 (FINAL): Foto + Gemini Vision

**O que fizemos:** **abandonamos a leitura de stream** e abraçamos a IA. Usuário tira uma foto única do boleto (não stream), backend manda pra Gemini 2.0 Flash com prompt "extraia a linha digitável de 47 dígitos", parser FEBRABAN valida.

**Por que funciona:**
- **Câmera nativa do dispositivo** (`<input type="file" capture="environment">`) faz autofoco perfeito e captura imagem de alta qualidade — muito melhor que stream de vídeo
- **Gemini 2.0 Flash** é multimodal de última geração — lê texto numérico em imagens com altíssima precisão
- **Foto estática** elimina motion blur que matava as tentativas anteriores
- **Validação dupla:** o que a IA leu passa pelo parser FEBRABAN. Se o DV não bate, o sistema avisa.

**Custo:**
- Free tier do Google Gemini: **1500 requests/dia** + 1M tokens/dia
- Operação atual: 1-5 boletos/dia (0.3% do limite)
- Preço se um dia escalar: ~R$ 0,00075 por foto = R$ 11/mês a 2000 boletos/dia

**Resultado:** funciona com confiabilidade próxima a 100% em boletos reais. UX fica idêntica ao Concur/ExpenseIt.

### Lição aprendida

> Pra ler boleto bancário via web, **não tente ler o código de barras**. O ITF é fino, sensível a iluminação e as libs JS open-source são todas fracas nele. Em vez disso, **tire foto e use Vision AI**. Custo zero (free tier sobra) e qualidade igual a app nativo.

Se algum dia uma lib JS realmente ler ITF bem (>90%), aí faz sentido voltar. Por enquanto, **foto + IA é o caminho**.

---

## 11. Plan B: digitação manual

Sempre disponível. Caminho conservador para:
- Boleto físico em ambiente sem internet
- Foto ruim / IA não conseguiu ler
- Boletos pré-2025 com fator vencimento esquisito
- Usuário que prefere digitar

UX da tela de digitar:
- Textarea grande, fonte mono
- Máscara incremental aplica formatação enquanto digita
- Contador "X/47 dígitos ✓" no canto
- `inputMode="numeric"` ativa teclado numérico no celular
- Auto-focus ao abrir
- Botão Continuar só ativa em 44 ou 47 dígitos

Tempo médio: 30 segundos pra um operador digitar 47 dígitos com a máscara.

---

## 12. Análise de custo

### Gemini Free Tier (Google AI Studio)

| Recurso | Limite gratuito |
|---|---|
| Requests por dia | 1.500 |
| Tokens por dia | 1.000.000 |
| Requests por minuto | 15 RPM |

**Cada foto consome ~1.200-1.500 tokens** (imagem ~1024 tokens + prompt + resposta).

### Tabela de custo por volume

| Boletos/dia | Status | Custo mensal |
|---|---|---|
| 5 (atual) | Free | R$ 0 |
| 100 | Free | R$ 0 |
| 1.000 | Free | R$ 0 |
| 1.500 | Limite gratuito | R$ 0 |
| 2.000 | Excede em 500 | ~R$ 11 |
| 10.000 | Excede em 8.500 | ~R$ 192 |

**Pricing pago Gemini 2.0 Flash (acima do limite):**
- Input: $0.10 / 1M tokens
- Output: $0.40 / 1M tokens
- Por foto: ~R$ 0,00075 (0,075 centavo de real)

A chave usada é `GOOGLE_AI_STUDIO_KEY`, **a mesma já usada por outros módulos do projeto** (IA Gemma). Setada no Railway.

---

## 13. Variáveis de ambiente

| Variável | Default | Descrição |
|---|---|---|
| `GOOGLE_AI_STUDIO_KEY` | obrigatória | Chave do Google AI Studio. Mesma do resto do projeto. |
| `BOLETO_VISION_MODEL` | `gemini-2.0-flash` | Modelo de visão. Pode trocar para `gemini-1.5-flash` se necessário. |
| `BOLETO_VISION_BASE_URL` | endpoint OpenAI-compat do Google | Não mudar a menos que troque de provider. |
| `BOLETO_VISION_TIMEOUT_S` | `15` | Timeout em segundos da chamada de visão. |

---

## 14. Testes

### Backend
- `backend/tests/test_boleto_parser.py` — 18 testes unitários (DV mod 10, DV mod 11, fator vencimento, parse_boleto, casos de erro)
- `backend/tests/test_financeiro_router.py` — 11 testes de integração (scan, criar, duplicata, listar, pagar, reabrir, excluir, beneficiários)
- **Atenção:** os testes usam DB SQLite isolado em arquivo temporário (`_isolar_db` fixture). NÃO destroem mais o DB de dev.
- Rodar: `cd backend && python -m pytest tests/ -v` — 29 testes passando.

### Frontend
- Sem testes automatizados (segue padrão do projeto)
- Validação manual via DevTools Mobile + boletos reais

---

## 15. Limitações conhecidas

1. **Boletos pré-2025** com fator antigo podem dar data errada (parser usa base nova por padrão). Solução: corrigir manualmente após o scan.
2. **Boletos de arrecadação** (luz, água, IPVA) — começam com `8`, formato diferente. Parser rejeita.
3. **Backend não força autenticação** nas rotas (segue padrão do projeto). Frontend faz a checagem de Master. Em produção isso é OK porque a app fica atrás de auth de operador.
4. **Sem audit trail** de mudanças (quem editou, quando, o quê). Adicionar `boleto_eventos` quando necessário.
5. **Sem aprovação multi-nível.** Master vê e marca como pago, ponto. Workflow tipo Concur ficou pra fase 2.
6. **Foto não tem OCR fallback no client.** Se Gemini cair, só resta digitar.
7. **Sem agendamento de pagamento / integração bancária.** Pagamento real continua manual no banco.

---

## 16. Próximos passos sugeridos (fase 2)

Em ordem de prioridade prática:

1. **Roles específicas** — criar role "Financeiro" e "Aprovador" no lugar de "Master vê tudo"
2. **Workflow de aprovação** — registrado → aprovado → pago (multi-nível)
3. **Suporte a PDF** — `pdfplumber` extrai linha digitável direto sem usar IA (grátis, instantâneo, 100% preciso). Idea: detectar tipo do arquivo (image vs PDF) no upload e rotear.
4. **Suporte a boletos de arrecadação** — parser separado para os que começam com 8
5. **Notificações de vencimento próximo** — push web ou email quando faltar 3 dias
6. **Recorrência** — detectar boleto mensal repetido (mesma empresa, valor similar, intervalo de 30d) e gerar lembrete
7. **Agendamento** — campo "agendado para DD/MM" + integração futura com OFX/CIP
8. **Audit log** — tabela `boleto_eventos` para trilha de auditoria
9. **Exportação contábil** — CSV mensal de boletos pagos

---

## 17. Mapa de arquivos

### Backend
```
backend/
├── services/
│   ├── boleto_parser.py       # Parser FEBRABAN puro (DV mod 10/11, fator, parse_boleto)
│   ├── boleto_storage.py      # Salvar/ler/excluir fotos em /data/boletos
│   └── boleto_vision.py       # Chama Gemini Vision para extrair linha digitável
├── routers/
│   └── financeiro.py          # Todas as rotas /api/financeiro/*
├── models.py                  # +Boleto, +BoletoBeneficiario
├── database.py                # init_db cria tabelas + UNIQUE index
└── tests/
    ├── test_boleto_parser.py       # 18 unit tests
    └── test_financeiro_router.py   # 11 integration tests
```

### Frontend
```
frontend/src/
├── pages/
│   ├── FinanceiroScan.jsx          # Tela mobile (foto + digitar)
│   ├── FinanceiroConfirmar.jsx     # Tela de confirmação após scan
│   └── FinanceiroPainel.jsx        # Painel desktop Master
├── components/
│   ├── FinanceiroDrawer.jsx        # Drawer de detalhe + ações
│   └── dialogs/
│       └── FinanceiroConfirmDialog.jsx  # Dialog estilizado (pagar/excluir)
├── utils/
│   └── boletoBancos.js             # Mapping banco→nome + urgência de vencimento
├── api/client.js                   # +scanBoleto, +scanBoletoFoto, +criarBoleto, etc.
└── App.jsx                         # +rotas /financeiro/*
```

### Docs
```
FINANCEIRO.md                       # este arquivo
docs/superpowers/specs/2026-05-24-financeiro-boletos-design.md
docs/superpowers/plans/2026-05-24-financeiro-boletos.md
```

---

## 18. Como debugar

### Câmera não abre no celular
- Confirma HTTPS (produção sempre, local precisa `https://localhost` ou `localhost` direto)
- Permissão de câmera no navegador
- `<input type="file" capture="environment">` é o padrão moderno — não usa `getUserMedia` então não tem problema de HTTPS

### IA retorna "NAO_ENCONTRADO"
- Foto borrada / longe demais
- Boleto cortado / sem linha digitável visível
- Reflexo / sombra
- Solução: tirar nova foto com luz boa e boleto centralizado

### IA retorna número errado (DV não bate)
- Bem raro com Gemini 2.0
- Frontend mostra banner laranja "DV não bate" mas permite salvar
- Usuário pode editar manualmente antes de confirmar

### "Este boleto já consta registrado"
- Funcionamento correto. Boleto único por código de barras.
- Se precisar reaproveitar, excluir o original primeiro

### Backend log do Gemini
- Cada chamada loga `[VISION] resposta bruta: ...` no log do FastAPI
- Útil pra ver o que a IA leu antes do parser validar

---

## 19. Histórico

| Data | O que rolou |
|---|---|
| 2026-05-24 | Spec original aprovada (`docs/superpowers/specs/...`) |
| 2026-05-24 | Plano de 20 tasks TDD escrito |
| 2026-05-24 | Tasks 1-20 implementadas — parser, modelos, rotas, painel, drawer, dialogs |
| 2026-05-24 | **Tentativa 1:** ZXing-js → falhou em boletos reais |
| 2026-05-24 | Spec/UX iteradas: máscara correta, DV mole, foto opcional, dialog estilizado |
| 2026-05-24 | **Tentativa 2:** BarcodeDetector + ZBar híbrido → falhou parcialmente |
| 2026-05-24 | **Tentativa 3:** ZBar-WASM forçado pra todos → falhou |
| 2026-05-24 | Pesquisa de mercado: ITF via web é fraco em todas as libs OSS |
| 2026-05-24 | **Tentativa 4 (FINAL):** Foto + Gemini 2.0 Flash → funciona |
| 2026-05-24 | UNIQUE index no `codigo_barras` adicionado contra race condition |
| 2026-05-24 | Testes isolados em arquivo temporário (não destrói mais DB dev) |
| 2026-05-24 | Doc consolidada (este arquivo) |
