# Geração Automática de Listas de Separação (seg-sex 06:00)

**Data:** 2026-05-18
**Status:** Aprovado (aguardando review do usuário)

## Problema

Hoje a geração da lista de separação dos docs vindos do Tiny ERP é 100% manual:

1. Master abre painel Separação
2. Escolhe data (últimos 7 dias)
3. Backend chama Tiny: docs com `situacao=1` (Aguardando Separação)
4. Master seleciona docs → clica "Gerar Lista"
5. Listas ficam disponíveis pros operadores

Esse fluxo precisa ser feito todo dia de manhã antes da operação começar — consome tempo da Master e atrasa o início do trabalho dos operadores.

## Objetivo

Automatizar a geração das listas de separação **seg-sex às 06:00 (horário BR)** pra que quando o operador chegar (07:00+), as listas já estejam prontas pra bipar.

O processo deve ser **transparente** — roda no servidor Railway sem depender de máquina/navegador do usuário.

## Decisões de produto

| # | Pergunta | Resposta |
|---|---|---|
| 1 | Quando o job roda? | Seg-sex às 06:00 (BR), fixo no código |
| 2 | Janela de busca de docs | Últimos 7 dias com `situacao=1` |
| 3 | Output | 2 listas separadas (1 ML + 1 Shopee) |
| 4 | Marketplace sem docs | Skip silencioso (não cria lista vazia) |
| 5 | Falha do job | Retry 1x após 5min; se ambas falharem → banner sutil em SeparacaoOlist |
| 6 | Nome da lista | `L{N} - DD/MM/YYYY HH:MM - Aut` (auto) / `... - Man` (manual) |
| 7 | Identificação operador | Sufixo " - Aut" / " - Man" visível |
| 8 | Desabilitar via painel | Não. Controle via env var existente (`ENABLE_LOCAL_SYNC_SCHEDULER`) |

## Arquitetura

Componentes criados/modificados:

| Componente | Tipo | Responsabilidade |
|---|---|---|
| `backend/services/auto_separation.py` | **Novo** | Lógica do job: busca docs Tiny + gera listas |
| `backend/services/sync_engine.py` | Modificado | Adicionar `auto_separation_loop` (chama o módulo acima às 06:00 seg-sex) |
| `backend/models.py` | Modificado | Adicionar coluna `source` em `TinyPickingList` ('auto' \| 'manual'); criar tabela `auto_separation_state` |
| `backend/database.py` | Modificado | Migration: nova coluna `source` + nova tabela `auto_separation_state` |
| `backend/routers/tiny.py` | Modificado | Endpoints `GET /tiny/auto-separation/status` e `POST /tiny/auto-separation/run-now` |
| `backend/routers/tiny.py` (criar lista manual) | Modificado | Setar `source='manual'` ao criar via fluxo manual existente |
| `frontend/src/api/client.js` | Modificado | Novos métodos `getAutoSeparationStatus`, `runAutoSeparationNow`, `dismissAutoBanner` |
| `frontend/src/pages/SeparacaoOlist.jsx` | Modificado | Banner sutil quando job falhou 2x consecutivas |
| `frontend/src/pages/PickingListsHistory.jsx` | Modificado | Exibir sufixo "Aut/Man" no nome da lista (vem do nome no DB) |

## Fluxo de dados

```
06:00 BR (seg-sex)
   │
   ▼
[ Scheduler dispara auto_separation_loop ]
   │
   ▼
[ Verifica auto_separation_state ]
   ├─ last_run_at é hoje? → ABORTA (evita duplicar se backend reiniciar)
   └─ Não rodou hoje → PROSSEGUE
   │
   ▼
[ Calcula janela: hoje - 7 dias até hoje ]
   │
   ▼
[ Loop sobre marketplaces: ['ml', 'shopee'] ]
   │
   ├─── PARA CADA marketplace:
   │      │
   │      ▼
   │   [ Chama Tiny API: GET separacoes (situacao=1, com filtro de marketplace) ]
   │      │
   │      ├─ ERRO API → registra falha, prossegue p/ próximo marketplace
   │      └─ OK → recebe lista de docs
   │      │
   │      ▼
   │   [ Filtra docs já em em_separacao localmente (tiny_separation_statuses) ]
   │      │
   │      ├─ 0 docs restantes → skip silencioso
   │      └─ N docs → prossegue
   │      │
   │      ▼
   │   [ Cria TinyPickingList com source='auto' ]
   │   [ Nome: L{N} - DD/MM/YYYY HH:MM - Aut ]
   │   [ Marca docs como em_separacao em tiny_separation_statuses ]
   │
   ▼ (fim do loop)
   │
[ Atualiza auto_separation_state ]
   │
   ▼
[ Loga: "AUTO_SEPARATION: ml=N docs, shopee=N docs criados" ]
```

## Tratamento de erros

```
[ Tentativa 1 ] → falha
   │
   ▼
[ Aguarda 5min ]
   │
   ▼
[ Tentativa 2 (retry) ] → falha
   │
   ▼
[ state.consecutive_failures += 1 ]
   │
   ├─ == 1: silencioso (1ª falha do dia)
   └─ >= 2: state.last_status = 'failed_visible'
        │
        ▼
   [ Frontend pega via GET /tiny/auto-separation/status ]
        │
        ▼
   [ Banner sutil em SeparacaoOlist no topo ]
   "⚠️ Geração automática falhou hoje (HH:MM). Gere manualmente."
```

**Reset do contador**: próxima execução com sucesso zera `consecutive_failures` e remove o banner.

**Dismiss manual**: usuário pode clicar X no banner pra dispensar (estado local frontend, não persiste).

## Modelos de dados

### Nova coluna em `TinyPickingList`

```python
source: Mapped[str] = mapped_column(String(20), default="manual")  # manual | auto
```

Migration:
```sql
ALTER TABLE tiny_picking_lists ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'manual';
```

### Nova tabela `auto_separation_state`

```python
class AutoSeparationState(Base):
    __tablename__ = "auto_separation_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str] = mapped_column(String(30), default="never_ran")
    # 'never_ran' | 'success' | 'failed_visible' | 'no_docs'
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    last_error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ex: "ml=30 shopee=12" ou "ml=ok shopee=fail (timeout)"
```

Singleton (1 linha só). A migration garante que existe uma linha inicial com `id=1, last_status='never_ran', consecutive_failures=0` (usando `INSERT OR IGNORE`). Toda lógica do job atualiza essa linha por `id=1`.

## Endpoints novos

### `GET /api/tiny/auto-separation/status`

Retorna estado atual do job. Usado pelo banner do frontend.

**Response:**
```json
{
  "last_run_at": "2026-05-18T06:00:32",
  "last_status": "failed_visible",
  "consecutive_failures": 2,
  "last_error_msg": "Tiny API timeout after 60s",
  "last_summary": "ml=fail shopee=fail",
  "show_banner": true
}
```

### `POST /api/tiny/auto-separation/run-now`

Roda o job imediatamente, mesmo fora do horário. Acesso interno (sem role check específico nessa versão — segue o auth padrão da API). Útil pra teste e recuperação manual.

**Response:**
```json
{
  "status": "success",
  "ml_list_id": 123,
  "ml_docs": 30,
  "shopee_list_id": 124,
  "shopee_docs": 12,
  "duration_ms": 1430
}
```

## Frontend UI

### Banner em `SeparacaoOlist.jsx`

Aparece quando `getAutoSeparationStatus().show_banner === true`:

```
┌────────────────────────────────────────────────────────┐
│ ⚠️  Geração automática falhou hoje (06:00).            │
│     Gere manualmente abaixo ou aguarde retry.       [X]│
└────────────────────────────────────────────────────────┘
```

- Cor: amarelo/laranja claro (não vermelho — não é erro crítico)
- Posição: topo do conteúdo, abaixo do header
- Dismissable: botão X esconde via state local

### Sufixo "Aut/Man" nas listas

Em `PickingListsHistory.jsx`, o nome da lista já vem com o sufixo do backend (`L1 - 18/05/2026 06:00 - Aut`). Sem mudança visual além do nome — o sufixo já carrega a informação.

## Testes

### Endpoint manual `run-now` para QA

Permite rodar o job em qualquer horário pra teste:

```bash
curl -X POST https://<railway-host>/api/tiny/auto-separation/run-now
```

### Testes automatizados (`tests/test_auto_separation.py`)

| Teste | Cenário |
|---|---|
| `test_job_creates_two_lists` | Mock Tiny com docs ML+Shopee → 2 listas criadas |
| `test_skip_empty_marketplace` | Mock retorna 0 docs Shopee → só ML |
| `test_no_docs_at_all` | 0 docs em tudo → status='no_docs', 0 listas |
| `test_retry_on_failure` | 1ª falha, 2ª OK → 1 sucesso |
| `test_double_failure_marks_visible` | Ambas falham → state.last_status='failed_visible' |
| `test_already_ran_today` | Idempotente — segunda chamada no mesmo dia não duplica |
| `test_naming_with_aut_suffix` | Lista criada tem sufixo " - Aut" |
| `test_manual_list_has_man_suffix` | Lista criada via fluxo manual tem " - Man" |
| `test_dismiss_banner_via_success_run` | Run com sucesso reseta `consecutive_failures` |

## Plano de rollout

**Fase 1 — Deploy + teste manual** (zero risco)
- Deploy via `publicar_producao.bat`
- Job agendado fica em standby; testa via `POST /run-now`
- Verifica criação correta de listas + sufixo "Aut"

**Fase 2 — Habilitar automático em horário real** (1 semana)
- Loop ativo, 06:00 seg-sex
- Monitora logs do Railway diariamente
- Confirma listas corretas chegando

**Fase 3 — Operação normal**
- Job roda autônomo
- Master só intervém quando banner aparece

## Riscos e mitigações

| Risco | Mitigação |
|---|---|
| API Tiny instável às 06:00 | Retry 1x + banner sutil. Master pode gerar manualmente |
| Backend reiniciar 06:30 (após o cron) | `auto_separation_state` rastreia se já rodou hoje |
| Duplicação de docs (job + manual) | Filtro `tiny_separation_statuses` já remove docs em uso |
| Job criar lista vazia | Skip silencioso se 0 docs |
| Timezone errado | Usa `pytz.timezone('America/Sao_Paulo')` explicitamente |
| Holidays nacionais | Não tratado nessa versão. Job roda mesmo em feriado. Master pode arquivar lista se não houver operação |

## Fora do escopo

- Notificação externa (telegram/email): não nessa versão. Banner em tela cobre 95% dos casos
- Configuração via UI (horário/dias): controlado em código por enquanto
- Calendário de feriados BR: pode ser adicionado depois se demanda surgir
- Múltiplos slots de geração no mesmo dia (ex: 06:00 + 14:00): pode evoluir no futuro
