# Plano de Deploy — warehouse-picker v2.0

> Status: **PRONTO PARA DEPLOY**
> Última atualização: 2026-04-23

---

## Contexto

| | v1.0 (produção anterior) | v2.0 (atual) |
|---|---|---|
| **Banco** | `warehouse_v2.db` | `warehouse_v3_local.db` |
| **Tabelas** | 9 | 20+ (todo v1 + Tiny ERP + AI + sync + ERP logs) |
| **Integração** | Nenhuma | Tiny ERP (Olist) completo |
| **Separação** | Manual Excel | Fluxo completo: aguardando → em separação → separadas → enviadas ERP |
| **Scheduler** | Nenhum | Sync pedidos + ERP auto-send (5 min) |
| **Deploy** | `publicar_producao.bat` → `nvs-production` | Idêntico |

---

## Pré-requisitos — confirmar antes de começar

- [ ] `TINY_API_TOKEN` disponível
- [ ] `GROQ_API_KEY` disponível (NVS AI)
- [ ] Repositório git do v2 tem remote próprio no GitHub
- [ ] Acesso ao painel do Railway
- [ ] Testes locais aprovados (especialmente fluxo de envio ERP)

---

## Etapa 1 — Criar novo projeto no Railway
**Tempo estimado: 15 min | Risco: Zero**

1. Acessar `railway.app` → New Project → Deploy from GitHub repo
2. Selecionar repositório da v2
3. Configurar branch de deploy: `nvs-production`
4. Configurar **todas** as variáveis de ambiente:

```
DATABASE_URL                 = sqlite:////data/warehouse_v3_local.db
TINY_API_TOKEN               = <seu token Tiny>
GROQ_API_KEY                 = <sua chave Groq>
ENABLE_LOCAL_SYNC_SCHEDULER  = true
ENABLE_OLIST_SYNC            = true
ENABLE_TINY_WEBHOOK          = true
ERP_SYNC_INTERVAL_SECONDS    = 300
FORCE_SEED                   = false
```

> **ATENÇÃO**: `FORCE_SEED=false` obrigatório em produção. Se `true`, sobrescreve o banco com o seed do repo e apaga dados reais.

5. Adicionar volume persistente em `/data`
6. **Não fazer deploy ainda** — só configurar

---

## Etapa 2 — Preparar banco de produção
**Tempo estimado: 10 min | Risco: Zero (só leitura)**

1. Garantir que `warehouse_v3_local.db` na raiz do projeto está atualizado com dados reais de operadores e barcodes

2. Rodar backend v2 localmente para validar migrações:
```bash
cd backend
uvicorn main:app --reload --port 8001
```

3. Confirmar no log de startup que todas as tabelas foram criadas/migradas:
```
--- DATABASE MIGRATION: tiny_erp_send_logs table verified/created ---
--- DATABASE MIGRATION: Picking Lists tables verified/created ---
--- DATA VERIFICATION ---
--- Total Operators: X ---
--- Total Barcodes: X ---
```

---

## Etapa 3 — Primeiro deploy (paralelo, v1 continua ativa)
**Tempo estimado: 20 min | Risco: Baixo**

1. Executar:
```
publicar_producao.bat
```

2. Railway sobe v2 em nova URL
3. Verificar health check:
```
GET https://<url-v2>/api/health
```

4. Validar manualmente:
   - [ ] Login de operador funciona (PIN)
   - [ ] Tela Separação carrega abas locais (em separação + separadas)
   - [ ] Busca de "aguardando" funciona ao selecionar período e clicar Aplicar
   - [ ] Gerar lista de picking funciona
   - [ ] Picking de item (bipe) funciona
   - [ ] Botão "Enviar para ERP" envia e move para aba "Enviadas ERP"
   - [ ] Scheduler ERP auto-send aparece no log (`[ERP_AUTO] Loop iniciado`)
   - [ ] Mobile: abre em `/separacao/listas`, navegação funciona

---

## Etapa 4 — Atualizar ZebraAgent nas 4 máquinas
**Tempo estimado: 30 min | Risco: Médio**

> Fazer máquina por máquina.

Em cada máquina:
1. Fechar o ZebraAgent atual
2. Editar `.env` do agente:
```
BACKEND_URL = https://<nova-url-v2>.railway.app/api
```
3. Reiniciar o ZebraAgent
4. Confirmar que está recebendo jobs de impressão

---

## Etapa 5 — Desativar v1
**Tempo estimado: 5 min**

1. No Railway, **pausar** (não deletar) o serviço v1
2. Manter pausado por mínimo 7 dias
3. Após 7 dias sem incidentes → pode deletar

---

## Plano de Rollback

> Tempo de execução: **menos de 5 minutos**

```
1. Reativar serviço v1 no Railway (botão "Resume")
2. Em cada máquina: trocar BACKEND_URL de volta para URL v1
3. Reiniciar ZebraAgent nas 4 máquinas
```

---

## Checklist de Funcionalidades para Validar em PRD

### Separação Tiny
- [ ] Aba "Aguardando" carrega ao aplicar filtro de data
- [ ] Gerar lista cria `tiny_picking_lists` e move docs para "Em Separação"
- [ ] Picking de itens atualiza `qty_picked` corretamente
- [ ] Conclusão de doc move para "Separadas" automaticamente
- [ ] Botão "Enviar para ERP" envia `situacao=2` e move para "Enviadas ERP"
- [ ] Badge ✅/❌ correto na aba "Enviadas ERP"
- [ ] Histórico de logs no drawer mostra tentativas passadas
- [ ] Job automático a cada 5 min envia docs `concluida` pendentes

### Mobile
- [ ] Operador não-Master é redirecionado para `/separacao/listas`
- [ ] Cards mobile aparecem na lista de itens
- [ ] Auto-seleção do primeiro item ao abrir lista
- [ ] Botão "Próximo →" avança para próximo item
- [ ] Auto-avanço após concluir item

### WMS Core
- [ ] Login PIN funciona
- [ ] Bipagem em sessão Full/Orgânico funciona
- [ ] Relatório de faltas registra corretamente

---

## Observações

- O `publicar_producao.bat` da v2 é idêntico ao da v1 — mesmo fluxo
- O banco v1 nunca é alterado em nenhum momento deste plano
- As novas tabelas (Tiny, ERP logs, sync) são criadas automaticamente pelo `init_db()` no primeiro boot
- `ENABLE_LOCAL_SYNC_SCHEDULER=true` ativa TANTO o sync de pedidos quanto o ERP auto-send
