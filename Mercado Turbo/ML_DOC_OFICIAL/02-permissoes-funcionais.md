# 02 — Permissões funcionais (escopos)

Fonte: `/pt_br/permissoes-funcionais` (atualizada 21/11/2025). Destilado.

## Escopos (concedidos pelo usuário no Grant)
- **Somente leitura** = GET. **Leitura e escrita** = PUT/POST/DELETE.

## Grupos de permissão funcional (habilitados por app)
- **Usuários (default)** — sempre ativo. Recurso `users`.
- **Publicação e sincronização** — `items`, `pictures`, `prices`.
- **Comunicação pré e pós-venda** — `questions`, `messages`, `claims`, `returns`.
- **Publicidade** — `advertising`.
- **Métricas do negócio** — `trends`, `highlights`, `visits`.
- **Vendas e envios** — `orders`, `shipments`, `claims`, `returns`. ← **É A NOSSA** (robô lê orders + shipments).
- **Promoções, cupons e descontos** — `offers`, `deals`.
- **Faturamento** — `invoices`, `billing`. ← possível requisito p/ detalhe de **tarifa/reembolso**.

## Erro 403 por falta de permissão
```
{"code":"PA_UNAUTHORIZED_RESULT_FROM_POLICIES","blocked_by":"PolicyAgent",
 "message":"At least one policy returned UNAUTHORIZED.","status":403}
```
Solução: nas configs do app, **habilitar a permissão funcional** correspondente (ativar leitura/escrita).

## Implicações pro nosso projeto
- Robô precisa de **"Vendas e envios"** (orders, shipments). Já funciona → temos.
- **Pista financeira:** `tarifa_refund` (hardcoded 0 no nosso `calc.py`) é dado de **faturamento/billing** → pode exigir a permissão **"Faturamento"** + endpoint de billing. Verificar na trilha do bug de margem.
- Se algum GET retornar **403 PolicyAgent**, não é 429 nem token — é **permissão funcional faltando** no app.
