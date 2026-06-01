# 07 — Notificações / Webhooks

Fonte: `/pt_br/produto-receba-notificacoes` (atualizada 23/04/2026). Destilado. **A cura de fundo (SaaS + reduz polling).**

## Como funciona
- Configura no DevCenter (no app): **Callback URL** pública (recebe **HTTP POST**) + **tópicos** desejados. Notificações em **UTC**.
- ML faz POST na callback a cada novidade nos tópicos. App responde **200** → confirma. Senão, re-tenta.

## Tópicos relevantes pra nós
- **`orders_v2`** (recomendado): notifica **criação E alterações** de vendas confirmadas. Payload:
  ```json
  {"resource":"/orders/2195160686","user_id":...,"topic":"orders_v2","application_id":...,"attempts":1,"sent":"...","received":"..."}
  ```
  → fazer **GET `/orders/{id}`** pra pegar os detalhes.
- **`shipments`**: criação/alterações dos envios.
- **`payments`**: pagamento criado ou status mudou → GET `/collections/{id}`.
- (orders feedback, items, questions, claims/post_purchase, etc. — não usamos agora.)

## Regras operacionais CRÍTICAS (viram requisito de arquitetura)
- **Responder HTTP 200 em até 500 ms** do recebimento. Senão o tópico é **desativado por fallback** → notificações do período **não** ficam no my_feeds e tem que **re-inscrever**.
- **Usar FILAS:** confirmar 200 **na hora** e só **depois** consultar o recurso (async). Evita re-tentativas e duplicidade. ← **Nosso desenho atual (asyncio.Queue + worker único) já encaixa: endpoint dá 200 e enfileira `{resource}`; worker faz o GET + enrich + upsert.**
- Re-tentativas por **1 hora**; depois disso, descartada.
- **Sempre** escutar e **depois fazer GET no recurso** pra confirmar a mudança (mudança pode vir de outras fontes: front, Seller Central, outro app).

## missed_feeds (recuperar perdidas)
- `GET /missed_feeds?app_id=$APP_ID` → notificações que após a 8ª tentativa (1h) não receberam 200 = "perdidas".
- ⚠️ **Só guarda perdidas de até 2 DIAS atrás.** Depois, somem → tem que armazenar.
- Filtro por tópico; default 10, usa limit/offset.

## IPs de origem das notificações do ML (pra liberar no firewall)
`54.88.218.97`, `18.215.140.160`, `18.213.114.129`, `18.206.34.84`.

## Implicações pro nosso projeto (arquitetura)
- **Webhook NÃO elimina o enriquecimento** (cada `orders_v2` ainda exige GET /orders/{id} + shipment/costs/discounts). MAS **elimina o polling de busca** (`/orders/search` repetido) e **espalha a carga no tempo** → ataca a raiz do 429 (menos picos, near-real-time).
- **Encaixa no nosso CQRS:** endpoint público `POST /webhook` → responde 200 → enfileira na `asyncio.Queue` → worker (já existe) processa. Pouca obra nova.
- **Precisa de poll de RECONCILIAÇÃO curto** (1-3 dias) + sweep de `missed_feeds` (janela 2 dias) pra cobrir perdidas. Não é "webhook OU poll" — é **webhook + poll leve de reconciliação**.
- Pré-requisito: callback URL pública sempre-on (Railway entrega) + **dedup** (idempotência por order_id — nosso upsert já é idempotente) + responder rápido.
- Ver [[ref-429-faq]] (webhook não dá "cota grátis", mas espalha carga) e [[01-criar-aplicacao]] (tópicos/callback se configuram no app).
