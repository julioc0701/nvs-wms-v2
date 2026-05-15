# Reverter doc no Tiny ao desfazer bip / reportar shortage após envio

**Data:** 2026-05-15
**Status:** Aprovado (aguardando review do usuário)

## Problema

Quando o operador conclui o picking de um doc na lista, o doc é enviado automaticamente ao Tiny como `situacao=2` (separado). O status local vira `enviada_erp`.

Se depois disso o operador percebe que bipou errado, ele:

1. Desfaz o bip (`unpick`) → SKU volta a "disponível"
2. Abre o SKU e reporta sem estoque (`report-shortage`)

Hoje nada acontece no Tiny — o doc continua como `situacao=2` (separado) lá, mesmo que no NVS o operador tenha desfeito tudo. Divergência silenciosa.

Causa raiz: `_check_and_advance_doc_statuses` em [backend/routers/tiny.py](../../../backend/routers/tiny.py) trata `enviada_erp` e `erro_envio_erp` como imutáveis. Não reavalia. Sem reavaliação, sem revert no Tiny.

## Objetivo

Quando o estado de coleta de um item muda após o doc ter sido enviado ao Tiny, reavaliar o doc e — se o resultado já não couber em "separado" — reverter automaticamente no Tiny (`situacao=1` = aguardando) e atualizar o status local pro novo valor (`em_separacao` ou `sem_estoque`).

Falha de comunicação com o Tiny exibe toast vermelho ao operador; status local muda mesmo assim.

## Decisões de produto

| Pergunta | Resposta |
|---|---|
| Comportamento ao desfazer bip de doc enviado | Automático e silencioso (sem confirmação) |
| Status local após revert | Recalculado: `em_separacao` ou `sem_estoque` (depende dos itens) |
| Tratamento de falha de comunicação com Tiny | Toast visual; status local muda mesmo assim |
| Debounce | Sim, 2 segundos por sep_id |

## Triggers

Toda ação que muda o estado de coleta:

- `register_item_unpick` (`POST /picking-items/{id}/unpick`)
- `report_shortage` (`POST /report-shortage`)
- `clear_item_shortage` (`POST /picking-items/{id}/clear-shortage`)
- `register_item_pick` (`POST /picking-items/{id}/pick`)

Cada um chama `_check_and_advance_doc_statuses(list_id, db)`. Hoje `report_shortage`, `pick` e (com mudança recente) `clear-shortage` já chamam. `unpick` **não** chama — vai passar a chamar.

## Mudança em `_check_and_advance_doc_statuses`

Hoje: `IMMUTABLE = {"enviada_erp", "erro_envio_erp"}` — pula sem reavaliar.

Novo comportamento:

```
target = recalcula como hoje (em_separacao | sem_estoque | concluida)

if record.status in {"enviada_erp", "erro_envio_erp"}:
    if target == "concluida":
        continue   # já está como separado no Tiny, nada a fazer
    else:
        # precisa reverter no Tiny
        record.status = target
        agenda_revert_debounced(sep_id)  # background, com debounce de 2s
```

Para os outros status (em_separacao, concluida, sem_estoque), comportamento atual (bidirecional) é mantido.

## Função nova: `_revert_separation_status_to_olist`

```
async def _revert_separation_status_to_olist(sep_id: str):
    try:
        svc = TinyService(TINY_TOKEN)
        resp = await svc._post("separacao.alterar.situacao.php", {
            "id": sep_id, "situacao": 1
        })
        ok = resp.get("status") == "OK"
        log(TinyErpSendLog, triggered_by="revert",
            status="success" if ok else "error",
            response_json=resp, error_message=... if not ok else None)
    except Exception as e:
        log(TinyErpSendLog, triggered_by="revert", status="error",
            error_message=str(e))
```

## Debounce (2 segundos por sep_id)

Estrutura em memória do processo:

```python
_REVERT_PENDING: Dict[str, asyncio.Task] = {}

def agenda_revert_debounced(sep_id: str):
    if sep_id in _REVERT_PENDING:
        _REVERT_PENDING[sep_id].cancel()
    _REVERT_PENDING[sep_id] = asyncio.create_task(_revert_after_delay(sep_id, 2.0))

async def _revert_after_delay(sep_id: str, delay: float):
    try:
        await asyncio.sleep(delay)
        await _revert_separation_status_to_olist(sep_id)
    except asyncio.CancelledError:
        pass
    finally:
        _REVERT_PENDING.pop(sep_id, None)
```

Se o operador oscila bip/unpick rápido, o último estado em 2s sem mudança é o que vai pro Tiny. Reduz risco de rate-limit e estado fora de ordem.

## Endpoint `/separation-statuses/revert` (já existe)

Hoje apaga registro local. Vai passar a chamar `_revert_separation_status_to_olist(sep_id)` também (sem debounce — é ação manual explícita). Mantém o botão "reverter pra aguardando" funcional para qualquer aba.

## Exposição ao front

`/tracked-separacoes` passa a retornar, por doc, o último log `triggered_by="revert"`:

```json
{
  "id": "...",
  "local_status": "sem_estoque",
  "last_revert_log": {
    "status": "error",
    "error_message": "Tiny rejeitou: ...",
    "sent_at": "..."
  }
}
```

Front em `SeparacaoOlist.jsx`:

- Mantém `last_seen_revert_log_ts` por doc em `localStorage`.
- A cada fetch, se algum doc tem `last_revert_log.status === "error"` e `sent_at > last_seen`, dispara toast vermelho `"Falha ao reverter doc {numero} no Tiny — verifique manualmente"`.
- Atualiza `last_seen`.

## Arquivos afetados

| Arquivo | Mudança |
|---|---|
| `backend/routers/tiny.py` | `_check_and_advance_doc_statuses` libera transições a partir de `enviada_erp`/`erro_envio_erp`; nova fn `_revert_separation_status_to_olist` + debounce; `register_item_unpick` passa a chamar `_check_and_advance`; endpoint `revert` aciona Tiny |
| `backend/routers/tiny.py` | `/tracked-separacoes` retorna `last_revert_log` |
| `frontend/src/pages/SeparacaoOlist.jsx` | Toast vermelho quando `last_revert_log.status === "error"` em log não visto antes |

## Riscos

1. **Tiny pode rejeitar `situacao=1`.** Endpoint `separacao.alterar.situacao.php` é documentado para alterar situação, mas não temos confirmação empírica de que aceita reverter de 2 para 1. Mitigação: testar manualmente com 1 sep_id em ambiente real antes de habilitar.
2. **Concorrência.** Dois operadores simultâneos no mesmo doc — última ação vence. Risco operacional baixo dado o fluxo.
3. **Debounce em memória.** Reinício do processo descarta tasks pendentes — se houver mudança nos últimos 2s antes de restart, o revert não acontece. Aceitável: operador percebe pelo status local divergente do Tiny (raro).

## Fora de escopo

- UI de "log de reverts" — só toast, sem tela dedicada.
- Retry automático de revert que falhou — operador vê toast, age manual ou re-aciona via botão "reverter pra aguardando".
- Auditoria por operador (quem desfez o quê) — log já guarda `sent_at`, suficiente.
