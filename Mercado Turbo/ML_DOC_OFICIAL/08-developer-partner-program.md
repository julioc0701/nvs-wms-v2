# 08 — Developer Partner Program (DPP)

Fonte: `/pt_br/developer-partner-program` (atualizada 03/03/2026). Destilado.

## ⚠️ Reality check (derruba a suposição "parceria = mais cota")
A war room (e eu) assumimos que a **parceria NVS TECH** seria o caminho pra **aumentar cota/RPM**. A doc do DPP **NÃO confirma isso**:
- Os **requisitos** do DPP são altíssimos pra nós:
  - **GMV mínimo — Brasil: USD 2.500.000/mês** (faturamento em USD dos sellers ativos que usam tua solução, últimos 3 meses). Nossa loja faz ~R$1,6M/mês ≈ ~USD 320k → **~8x abaixo**. E é pra **vários sellers** usando a solução (é programa pra fornecedor de software SaaS), não 1 loja.
  - **Assessment de Segurança ≥65%.**
  - **Iniciativas certificadas** guiadas por um Integration Expert, com prazos por medalha (Silver/Gold/Platinum), até 4 iniciativas/trimestre via JIRA.
- **A lista de BENEFÍCIOS do DPP NÃO menciona aumento de rate-limit/cota.** Os benefícios são: medalha, suporte IX, visibilidade na Central de Parceiros, SLA de suporte (2d/1d/3h), Slack, contratação direta, regionalização, eventos. **Nada de "mais RPM".**

## Conclusão honesta
- **DPP não é caminho de curto prazo** pra 1 loja (exige USD 2,5M/mês GMV + assessment + iniciativas + IX — é programa de SaaS estabelecido).
- **"Parceria → mais cota" é suposição não confirmada pela doc.** O aumento de cota aparece SÓ na FAQ do 429 (P3/P6) como *"contatar Integrações Comerciais com evidência de uso"* — um canal **comercial separado** do DPP, e **sem garantia** de que um app pequeno de 1 loja recebe bump.
- Medalhas: mantêm-se pela velocidade de entrega de iniciativas; atraso → quarentena amarela (40d) → vermelha (40d) → downgrade/perda.

## Implicação pro plano
- **Não contar com o DPP/parceria como cura do 429 a curto prazo.** Era a "perna 2 definitiva" da war room — **enfraquecida**.
- Caminhos que sobram pra 1 loja: (a) robô o mais leve possível (feito) + caber na cota default; (b) **webhook** (corta chamadas na raiz, NÃO depende de aprovação de parceria — ver [[07-notificacoes-webhook]]); (c) tentar o canal de Integrações Comerciais por evidência de uso (incerto).
- Webhook ganha peso: é a única alavanca estrutural que **não depende de aprovação do ML**.
