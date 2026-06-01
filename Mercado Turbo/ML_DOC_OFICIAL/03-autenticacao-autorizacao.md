# 03 — Autenticação e Autorização (OAuth 2.0)

Fonte: `/pt_br/autenticacao-e-autorizacao` (atualizada 29/12/2025). Destilado.

## Fluxo (Authorization Code, server-side) — o que usamos
1. Redireciona p/ `https://auth.mercadolivre.com.br/authorization?response_type=code&client_id=...&redirect_uri=...&state=...` (+`code_challenge`/`code_challenge_method` se PKCE).
2. Usuário autoriza → volta em `redirect_uri?code=...&state=...`.
3. **POST** `https://api.mercadolibre.com/oauth/token` com `grant_type=authorization_code`, `client_id`, `client_secret`, `code`, `redirect_uri` (+`code_verifier` se PKCE).
4. Resposta: `access_token`, `expires_in: 21600` (6h), `scope`, `user_id`, `refresh_token`.
- Header em toda chamada: `Authorization: Bearer <access_token>`.
- **Grant tem que ser feito pela conta ADMIN/dona.** Operador/colaborador → erro `invalid_operator_user_id`.
- `redirect_uri` tem que bater **exato** (sem partes variáveis). P/ passar dados use `state` (ML NÃO valida o state — nós validamos).

## Refresh token (confirma nosso client.py)
- `grant_type=refresh_token` → novo `access_token` (6h) + **novo `refresh_token`**.
- **Uso único e rotativo**: só o **último** refresh gerado vale; só funciona pelo **client_id** associado; vira inválido após uso.
- Expira em **6 meses**. Renovar access token **só quando expirar**.
- Eventos que invalidam o access token antes das 6h: troca de senha, atualização do Client Secret, revogação pelo usuário, **ou 4 meses sem nenhuma chamada**.

## Códigos de erro OAuth — IMPORTANTE p/ diagnóstico
- `invalid_client` — client_id/secret inválidos.
- `invalid_grant` (400) — code/refresh inválido, expirado, **já usado**, fluxo errado, de outro client, redirect_uri não bate, ou seller com dados pendentes. (= o "token morto" que tivemos.)
- `invalid_scope`, `invalid_request`, `unsupported_grant_type`.
- **`forbidden` (403)** — token de outro usuário, **OU IP BLOQUEADO**, OU faltam scopes.
- **`local_rate_limited` (429)** — excesso de requisições; **bloqueio temporário**; "volte a tentar em alguns segundos".
- `unauthorized_client` — app sem grant/scope com o usuário.
- `unauthorized_application` — app bloqueado.

## ⭐ Achado-chave pro debate IP vs cota
A doc separa claramente:
- **Bloqueio de IP = 403 forbidden** (não 429).
- **429 = `local_rate_limited`** = rate-limit/cota temporário.

**Nós tomamos 429, não 403** → logo **NÃO é bloqueio de IP**; é **rate-limit/cota**. Isso **confirma** a virada de diagnóstico da war room (cota por Client ID + endpoint, não "castigo de IP"). Se algum dia virar **403**, aí sim olhar IP/scope/token.
