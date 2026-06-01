# 10 — Relatórios de Faturamento (billing) — testado live

Fonte: `/pt_br/relatorios-de-faturamento` + testes locais reais (seller 221832146, 2026-06-01). Destilado.

## Permissão (destravada hoje)
- Exige o escopo **`urn:ml:mktp:invoices`** = permissão funcional **"Faturamento"** no app. Sem ela: **403 PolicyAgent**.
- Ligar no DevCenter + **RE-AUTORIZAR** (token novo). Token antigo não pega a permissão (escopo congela no grant).
- App local 8806 já re-autorizado com invoices (✓ testado).

## Endpoints (caminho certo = `monthly`)
1. **Períodos:** `GET /billing/integration/monthly/periods?group={ML|MP}&document_type={BILL|CREDIT_NOTE}` → últimos 12 meses, cada um com `key` (ex: `2026-05-01`). ✓ 200 testado.
2. **Documentos:** `GET /billing/integration/periods/key/{KEY}/documents?group=ML&document_type=BILL` → faturas do período, cada uma com `id`, `amount`, **`count_details`** (nº de linhas, ex: 31874). ✓ 200.
3. **Resumo:** `GET /billing/integration/periods/key/{KEY}/summary/details?group=ML&document_type=BILL` → ✓ 200, MAS é **AGREGADO por tipo de encargo** do período inteiro: "Cargo por Mercado Envios" (total), "Cargo por venda" (total), bonificações/estornos. **NÃO é por pedido.**
- `/details` e `/documents/{id}/details` → 404 (rota não existe nesses paths).

## ⚠️ Achado crítico pro nosso caso
- **O resumo de billing dá TOTAIS do período, não frete POR PEDIDO.** Pra margem por pedido (o que o painel mostra), o resumo não resolve sozinho.
- As **linhas por pedido** (`count_details` = milhares) devem estar num **relatório de conciliação (XLSX/CSV) baixável** (a doc cita "relatório de conciliação em formato XLSX e CSV" na seção de erros) OU em **"Relatórios de Pagamentos"** — **AINDA NÃO CONFIRMADO** o endpoint que traz por-pedido.
- Billing TAMBÉM tem **429 por IP** (doc: "Bloqueio preventivo por quantidade limitada de requests por IP. Evite chamadas repetitivas"). Mas billing = ~poucas chamadas/período → não tripa.

## Implicação pro redesenho
- **Caminho A (billing por pedido):** só fecha SE o relatório de conciliação (XLSX/CSV) ou Relatórios de Pagamentos trouxer **frete por order_id** em lote. **A confirmar** (próximo passo de pesquisa).
- **Caminho B (seguro):** manter `/shipments/{id}/costs` por pedido (frete vendedor = `senders[].cost`, ver [[09-frete-e-faturamento]]) mas **espalhado no tempo, sem rajada** + circuit-breaker duro. Funciona já, sem depender do relatório.
