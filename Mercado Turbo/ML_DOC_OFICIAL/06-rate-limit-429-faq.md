# 06 — FAQ Rate limit / Erro 429

Fonte: `/pt_br/rate-limit-erro-429` (atualizada 05/05/2026). Destilado (6 Q&A).

- **429 = excesso de requisições em curto período.** Cura recomendada: **backoff exponencial + jitter**, **distribuir** (evitar picos), **consolidar/reduzir chamadas**, consumir `scroll` dentro do TTL, **não fazer retries massivos**, batching prudente, **evitar concorrência extrema**.
- **Multiget:** muitas APIs não suportam multiget amplo (ex: items/visits = 1 product_id por consulta) → batching + intervalos + limitar RPM.
- **⭐ Por IP, Client ID ou usuário?** *"O controle principal é aplicado **POR CLIENT ID (aplicação)** na maioria dos casos e **POR ENDPOINT**; o tamanho do payload NÃO conta. Recomenda distribuir o consumo e **solicitar aumento de cota** pra volume legítimo pelos canais correspondentes."* → **NÃO menciona IP.** Limite é por app+endpoint.
- **scroll_id:** expira (TTL); consumo repetido ou scroll aberto demais → 429. Consumir dentro do TTL, reduzir concorrência, backoff+jitter.
- **Não misturar `scroll_id` com `offset/limit`** na mesma requisição (causa erro). Escolher scroll OU offset por endpoint.
- **Aumento de RPM:** contatar **Integrações Comerciais com evidência de uso**; enquanto isso, otimizar (batching, consolidação).

## Cruzamento com a doc de OAuth ([[03-autenticacao-autorizacao]])
- **429 `local_rate_limited`** = rate/cota (temporário, "volte em alguns segundos").
- **403 forbidden** = token de outro usuário / **IP bloqueado** / falta scope. → bloqueio de IP é **403**, não 429.

## Conclusão (alinhada com [[08-developer-partner-program]])
Solução = **otimizar (feito)** + **reduzir chamadas na raiz (webhook)**. "Aumento de cota via parceria" é canal comercial separado, incerto pra app pequeno (DPP exige USD 2,5M/mês GMV).
