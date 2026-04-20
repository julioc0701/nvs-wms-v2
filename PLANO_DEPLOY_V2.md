# Plano de Deploy — warehouse-picker v2.0

> Status: **AGUARDANDO VALIDAÇÃO FINAL**
> Última atualização: 2026-04-17
> Pré-requisito: testes locais aprovados antes de executar qualquer etapa

---

## Contexto

| | v1.0 (produção atual) | v2.0 (migrar para) |
|---|---|---|
| **Banco** | `warehouse_v2.db` | `warehouse_v3_local.db` |
| **Tabelas** | 9 | 20+ (todo v1 + Tiny ERP + AI + sync) |
| **Integração** | Nenhuma | Tiny ERP (Olist) completo |
| **AI** | Nenhum | NVS (Groq + Llama 3.3 70B) |
| **Deploy** | `publicar_producao.bat` → `nvs-production` | Idêntico |
| **ZebraAgent** | 4 máquinas apontando para URL v1 | Atualizar após go-live v2 |

---

## Pré-requisitos — confirmar antes de começar

- [ ] `TINY_API_TOKEN` disponível
- [ ] `GROQ_API_KEY` disponível
- [ ] `DOWNLOAD_SECRET` configurado na v1 (necessário para baixar o banco)
- [ ] Repositório git do v2 tem remote próprio no GitHub (diferente do v1)
- [ ] Acesso ao painel do Railway
- [ ] Testes locais aprovados

---

## Etapa 1 — Criar novo projeto no Railway
**Tempo estimado: 15 min | Risco: Zero (não toca v1)**

1. Acessar `railway.app` → New Project → Deploy from GitHub repo
2. Selecionar repositório da v2
3. Configurar branch de deploy: `nvs-production`
4. Configurar variáveis de ambiente:

```
DATABASE_URL                 = /data/warehouse_v3_local.db
TINY_API_TOKEN               = <seu token>
GROQ_API_KEY                 = <sua chave>
DOWNLOAD_SECRET              = <senha para download do DB>
ENABLE_LOCAL_SYNC_SCHEDULER  = true
```

5. **Não fazer deploy ainda** — só configurar o projeto

---

## Etapa 2 — Baixar e preparar banco de produção v1
**Tempo estimado: 10 min | Risco: Zero (só leitura)**

1. Baixar banco atual da v1:
```
GET https://<url-v1>/api/admin/download-db?secret=<DOWNLOAD_SECRET>
```

2. Salvar o arquivo como `warehouse_v3_local.db` na raiz do projeto v2

3. Rodar backend v2 localmente apontando para esse banco:
```bash
cd backend
python main.py
```

4. Confirmar que os dados aparecem: operadores, barcodes, sessões
5. O `init_db()` do v2 cria automaticamente as tabelas novas (Tiny, AI, sync) sem apagar dados existentes

---

## Etapa 3 — Primeiro deploy v2 (paralelo, sem desligar v1)
**Tempo estimado: 20 min | Risco: Baixo**

1. Com `warehouse_v3_local.db` atualizado na raiz do v2, executar:
```
publicar_producao.bat
```

2. Railway sobe v2 em nova URL (ex: `warehouse-v2-production.railway.app`)
3. Verificar health check:
```
GET https://<url-v2>/api/health
```

4. Validar manualmente:
   - [ ] Login de operador funciona
   - [ ] Abertura de sessão funciona
   - [ ] Bipagem de SKU funciona
   - [ ] Tela Tiny ERP carrega separações
   - [ ] Chat NVS responde
   - [ ] Impressão (apontar 1 ZebraAgent para v2 em teste)

> **V1 continua rodando normalmente. Nenhum operador afetado.**

---

## Etapa 4 — Atualizar ZebraAgent nas 4 máquinas
**Tempo estimado: 30 min | Risco: Médio (janela de 2-5 min por máquina)**

> Fazer máquina por máquina. Não trocar todas ao mesmo tempo.

Em cada máquina:
1. Fechar o ZebraAgent atual
2. Editar configuração (`.env` ou arquivo de config do agente):
```
BACKEND_URL = https://<nova-url-v2>.railway.app
```
3. Reiniciar o ZebraAgent
4. Confirmar que está recebendo jobs de impressão da v2
5. Repetir para as próximas 3 máquinas

---

## Etapa 5 — Desativar v1 (não deletar)
**Tempo estimado: 5 min**

1. No Railway, **pausar** o serviço v1 (não deletar)
2. Manter pausado por **mínimo 7 dias** como garantia
3. Após 7 dias sem incidentes → pode deletar com segurança

---

## Plano de Rollback

> Tempo de execução: **menos de 5 minutos**

Se algo der errado após a Etapa 4:

```
1. Reativar serviço v1 no Railway (botão "Resume")
2. Em cada máquina: trocar BACKEND_URL de volta para URL v1
3. Reiniciar ZebraAgent nas 4 máquinas
```

O banco v1 nunca foi tocado — todos os dados estão intactos.

---

## Fluxo visual

```
HOJE:
  [v1 Railway - ativo] ←── 4x ZebraAgent

ETAPA 3 (paralelo):
  [v1 Railway - ativo] ←── 4x ZebraAgent (ainda na v1)
  [v2 Railway - ativo] ← testando em paralelo

ETAPA 4 (switch):
  [v1 Railway - pausado (standby 7 dias)]
  [v2 Railway - ativo] ←── 4x ZebraAgent (migrados)

APÓS 7 DIAS:
  [v2 Railway - ativo] ←── 4x ZebraAgent
```

---

## Observações importantes

- O `publicar_producao.bat` da v2 é idêntico ao da v1 — mesmo fluxo, nenhuma mudança necessária
- O banco v1 **nunca é alterado** em nenhum momento deste plano
- As tabelas novas do v2 (Tiny, AI, sync) são criadas automaticamente pelo `init_db()` no primeiro boot
- `FORCE_SEED` deve estar `false` (ou ausente) em produção v2 para não sobrescrever dados migrados
