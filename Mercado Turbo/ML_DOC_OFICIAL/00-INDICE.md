# Referência Oficial Mercado Livre — destilada (projeto financeiro_ml)

Notas destiladas (em palavras próprias, não cópia verbatim) da doc oficial em
`developers.mercadolivre.com.br/pt_br/`. Fonte canônica do projeto pra arquitetura.
Lida via navegador logado (WebFetch é bloqueado pelo portal).

**Escopo:** só as seções relevantes ao nosso sistema (auth, IPs, rate limit, orders,
envios, notificações/webhook, partner). Trilhas de imóveis/autos/serviços/Ads ignoradas.

## Índice
- [01 — Criar aplicação / DevCenter](01-criar-aplicacao.md) ✅
- [02 — Permissões funcionais (escopos)](02-permissoes-funcionais.md) ✅
- [03 — Autenticação e Autorização (OAuth)](03-autenticacao-autorizacao.md) ✅ *(achado: 403=IP/scope, 429=rate)*
- [04 — Gerenciar IPs de um aplicativo](04-gerenciar-ips.md) ✅ *(lista branca opt-in, só parceiro)*
- [05 — Considerações de design](05-consideracoes-design.md) ✅
- [07 — Notificações / Webhooks](07-notificacoes-webhook.md) ✅ *(spec completa SaaS)*
- [08 — Developer Partner Program](08-developer-partner-program.md) ✅ *(GMV USD 2,5M/mês — fora de alcance)*
- 06 — Erro 403 — *a fazer*
- 09 — Orders (pedidos) — *a fazer (relevante p/ cálculo)*
- 10 — Envios / Custos de envio (ME2) — *a fazer (relevante p/ frete)*
- 11 — Pagamentos / Feedback de venda — *a fazer*
- FAQ — Rate limit / Erro 429 — *já estudada na war room (ver project_war_room_429)*

## Achados que mudam o diagnóstico (até agora)
1. **429 ≠ bloqueio de IP.** Doc OAuth: IP bloqueado = **403**; 429 = `local_rate_limited` (rate/cota). Nós tomamos 429 → **é cota, não IP**. Reforça virada da war room.
2. **DPP/parceria ≠ aumento de cota garantido.** Requer USD 2,5M/mês GMV (BR) + assessment + iniciativas; e a lista de benefícios **nem cita** aumento de RPM. A "cura definitiva via parceria" está **enfraquecida**.
3. **Webhook ganha peso** como única alavanca estrutural que **não depende de aprovação do ML**.

Última atualização desta referência: 2026-05-30.
