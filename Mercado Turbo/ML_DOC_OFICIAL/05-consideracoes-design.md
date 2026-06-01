# 05 — Considerações de design (convenções da API)

Fonte: `/pt_br/consideracoes-de-design` (atualizada 30/12/2025). Destilado.

- **JSON** padrão. **JSONP** (param `callback`) sempre responde **200** (status/headers/body no corpo) — tratar 30x/40x/50x no body.
- **Formato de erro:** `{ "message": "...", "error": "machine_code", "status": 4xx, "cause": [] }`.
- **Redução de resposta:** param **`attributes=campo1,campo2`** → traz só esses campos (em respostas de coleção). Útil p/ encurtar payload do `/orders/search`. (Obs: payload não conta no rate-limit, mas reduz processamento.)
- **OPTIONS** num recurso → devolve auto-documentação (métodos, atributos).
- **Paginação:** `offset`/`limit`, default **offset=0, limit=50**; `paging.total` traz o total. Confirma nosso `limit=50`. (Teto de offset ~1000 é o motivo do scan — ver [[ref-429-faq]].)
