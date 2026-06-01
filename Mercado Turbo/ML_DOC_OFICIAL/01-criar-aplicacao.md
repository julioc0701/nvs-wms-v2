# 01 — Criar aplicação no Mercado Livre (DevCenter)

Fonte: `/pt_br/crie-uma-aplicacao-no-mercado-livre` (atualizada 29/12/2025). Destilado.

## Criação
- App criado no **DevCenter** ("Minhas aplicações"). Gera **Client_Id** + **Secret_Key** (usados na auth).
- Conta deve ser a **dona** da solução; recomendado **pessoa jurídica** (evita problema de transferência depois).
- **BR (e AR/MX/CL): só é permitido criar 1 aplicação** por titular validado, e os dados têm que bater com os da conta. ⚠️ Relevante pro nosso debate: se BR limita a 1 app, a "troca de Client ID" entre 27/05 e 30/05 provavelmente foi recriação/edição do mesmo app, não 2 apps simultâneos.

## Informações básicas
- Nome (único), Nome curto (gera URL do app), Descrição (≤150 char, aparece na tela de autorização), Logo.
- **Redirect URLs**: têm que ser **HTTPS** e preenchidas com a **raiz do domínio**. (Bate com nosso `ML_REDIRECT_URI`.)
- **PKCE**: opcional, recomendado (anti code-injection / CSRF).
- **Device Grant**: fluxo onde o app usa só as próprias credenciais p/ acessar recursos próprios (não em nome de usuário); chamadas recorrentes até o usuário concluir a permissão.

## Escopos
- **Leitura** = métodos GET. **Escrita** = PUT/POST/DELETE. **offline** = recebe refresh_token p/ agir com usuário offline.
- 3 tipos de app: só-leitura; online leitura/escrita (token expira, precisa renovar); **offline leitura/escrita** (tem refresh_token) ← é o nosso caso.

## Tópicos de notificação (webhook) — config no app
- Marca-se os tópicos desejados + preenche **"URL de retorno de notificações"** (rota pública que recebe os webhooks).
- Tópicos principais: **Orders, Messages, Items, Catalog, Shipments, Promotions**.
- ML faz POST nessa rota a cada novidade nos tópicos marcados. ← É aqui que o **webhook `orders_v2`** se configura, no nível do app.

## Client Secret — renovação
- "Renove agora": gera chave nova, **expira a antiga na hora** → usuários novos tomam erro durante a transição.
- "Programar renovação" (recomendado): agenda expiração (até 7 dias), mantém **2 secrets válidos** na janela → dá tempo de trocar nos ambientes. ⚠️ Boa prática p/ não derrubar o robô ao rotacionar secret.

## Gestão / permissões
- Lista de usuários que autorizaram o app: Novo (<24h), Inativo (sem uso >3 meses / <3 meses), Ativo.
- **Excluir app é irreversível.**

## Implicações pro nosso projeto
- Confirma: nosso app é "offline read/write" (refresh_token). Redirect HTTPS raiz. OK.
- **Webhook se liga aqui** (tópicos + URL de retorno) — pré-requisito do caminho SaaS.
- BR = 1 app só → atenção ao gerir Client ID/Secret (rotação programada, não "renove agora").
