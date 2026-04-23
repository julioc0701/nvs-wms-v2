from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from logger import get_logger
log = get_logger("tiny")
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from models import TinyOrderSync, TinyOrderItem, TinyPickingList, TinyPickingListItem, Barcode, Shortage, PickingItem, TinySeparationStatus, TinySeparationItemCache, TinySeparationHeader, TinyErpSendLog
from pydantic import BaseModel
import asyncio
import json
from services.tiny_service import TinyService
from services.sync_engine import get_sync_snapshot, run_batched_full_sync, run_window_sync, sync_order_ids
from typing import Optional, Dict, Any, List
from datetime import datetime
import os
import time

router = APIRouter()

TINY_TOKEN = os.getenv("TINY_API_TOKEN", "")

# ── Feature gate: sync de status para a API Olist/Tiny ───────────────────────
# true  = produção (chama a API Tiny e atualiza a situação da separação)
# false = local/testes (apenas loga DRY-RUN, não toca PRD)
ENABLE_OLIST_SYNC = os.getenv("ENABLE_OLIST_SYNC", "true").lower() == "true"

# Código de situação "Separado" na API do Tiny ERP v2.
# ⚠️  VERIFICAR na documentação Tiny qual é o código correto antes de ir para PRD.
# Candidatos comuns: "separado" (string) ou o código numérico correspondente.
TINY_SEPARATION_DONE_SITUACAO = os.getenv("TINY_SEPARATION_DONE_SITUACAO", "separado")

def get_service(token: Optional[str] = None):
    active_token = token or TINY_TOKEN
    if not active_token:
        raise HTTPException(status_code=400, detail="Token do Tiny ERP não configurado.")
    return TinyService(active_token)

# Memory Cache para não derrubar a API do Tiny com Rate Limits (4 computadores concorrentes)
_PEDIDOS_CACHE: Dict[str, Any] = {}
CACHE_TTL_MINUTOS = 3

IS_SHUTTING_DOWN = False

async def vacuum_last_30_days(token: str):
    await run_batched_full_sync(
        token,
        lookback_days=int(os.getenv("SYNC_FULL_LOOKBACK_DAYS", "60")),
        chunk_days=int(os.getenv("SYNC_FULL_CHUNK_DAYS", "7")),
        note="carga completa manual em blocos",
    )

async def sync_background_orders(token: str, order_ids: list):
    """Busca os detalhes ricos e atualiza espelho bruto + camada canônica."""
    if not order_ids:
        return
    await sync_order_ids(token, order_ids, sync_type="targeted")

from fastapi import Request

WEBHOOK_ENABLED = os.getenv("ENABLE_TINY_WEBHOOK", "true").lower() == "true"

@router.post("/webhook")
async def receive_tiny_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Recebe notificação de eventos do Tiny ERP (ex: inserção/alteração de pedidos).
    PAUSADO — ativar setando ENABLE_TINY_WEBHOOK=true nas env vars.
    """
    if not WEBHOOK_ENABLED:
        log.info("[WEBHOOK TINY] recebido mas PAUSADO (ENABLE_TINY_WEBHOOK=false)")
        return {"status": "paused", "message": "Webhook desativado para testes"}
    try:
        body = await request.json()
        print(f"[WEBHOOK TINY] Novo evento recebido: {body.get('tipo', 'desconhecido')}")

        dados = body.get("dados", {})
        pedido_id = dados.get("id")

        if pedido_id:
            print(f"[WEBHOOK TINY] Agendando Sincronização do Pedido ID: {pedido_id}")
            background_tasks.add_task(sync_background_orders, TINY_TOKEN, [str(pedido_id)])

        return {"status": "success", "message": "Evento processado"}
    except Exception as e:
        print(f"[WEBHOOK TINY] Erro ao ler payload: {e}")
        return {"status": "error", "message": str(e)}

@router.get("/pedidos")
async def list_pedidos(
    background_tasks: BackgroundTasks,
    pagina: int = 1, 
    token: Optional[str] = None, 
    status: Optional[str] = None,
    data_inicial: Optional[str] = None,
    data_final: Optional[str] = None,
    force_refresh: bool = False,
    db: Session = Depends(get_db)
):
    """Busca pedidos de venda da Tiny API e injeta dados ricos do Espelho Local SQLite"""
    api_token = token or TINY_TOKEN
    if not api_token:
        raise HTTPException(status_code=400, detail="TINY_API_TOKEN não configurado no .env ou enviado na requisição")
    
    cache_key = f"{pagina}_{status}_{data_inicial}_{data_final}"
    now = time.time()
    
    data = None
    if not force_refresh and cache_key in _PEDIDOS_CACHE:
        cached_data, cache_time = _PEDIDOS_CACHE[cache_key]
        if now - cache_time < (CACHE_TTL_MINUTOS * 60):
            print(f"[CACHE HIT] OlistOrders Entregue diretamente pela RAM em 5ms.")
            data = cached_data
            
    if data is None:
        if force_refresh:
            print("[CACHE BUST] Usuário forçou atualização. Ignorando cache e indo no Tiny ERP.")
            
        svc = TinyService(token=api_token)
        try:
            data = await svc.search_orders(pagina=pagina, status=status, data_inicial=data_inicial, data_final=data_final)
            _PEDIDOS_CACHE[cache_key] = (data, now)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ---- MÁGICA DA INJEÇÃO DO ESPELHO LOCAL ----
    pedidos_lista = data.get("pedidos", [])
    if not pedidos_lista:
        return data
        
    ids_to_sync = []
    
    for item in pedidos_lista:
        p_obj = item.get("pedido", {})
        p_id = p_obj.get("id")
        if not p_id:
            continue
            
        # Tenta buscar os dados ricos no nosso Banco SQLite extremamente rápido
        sync_record = db.query(TinyOrderSync).filter(TinyOrderSync.id == p_id).first()
        
        if sync_record:
            # Injeta direto no objeto que vai pro Frontend
            if sync_record.ecommerce:
                p_obj["ecommerce"] = sync_record.ecommerce
            if sync_record.marcadores_json:
                try:
                    p_obj["marcadores"] = json.loads(sync_record.marcadores_json)
                except:
                    pass
            
            # --- AUTO-MIGRAÇÃO DE ITENS (Para pedidos já baixados antes da tabela de Itens existir) ---
            # Verificamos no banco se o pedido já tem itens vinculados.
            # Se não tiver, e nós já temos o raw_data salvo, recriamos os itens instantaneamente sem usar a API.
            is_items_empty = db.query(TinyOrderItem).filter(TinyOrderItem.tiny_order_id == p_id).count() == 0
            if is_items_empty and sync_record.raw_data:
                try:
                    raw = json.loads(sync_record.raw_data)
                    itens_list = raw.get("itens", [])
                    if itens_list:
                        for item_obj in itens_list:
                            item_data = item_obj.get("item", {})
                            db.add(TinyOrderItem(
                                tiny_order_id=p_id,
                                id_produto=item_data.get("id_produto"),
                                codigo=item_data.get("codigo"),
                                descricao=item_data.get("descricao"),
                                quantidade=float(item_data.get("quantidade", 0) or 0),
                                valor_unitario=float(item_data.get("valor_unitario", 0) or 0)
                            ))
                        db.commit()
                except Exception as e:
                    db.rollback()
        else:
            # Se não tem no banco ainda, sincroniza qualquer pedido para manter o espelho fiel.
            ids_to_sync.append(p_id)
            
    if ids_to_sync:
        # Aciona o robô em background, sem travar a requisição do usuário
        print(f"[SYNC ENGINE] Disparando captura em background para {len(ids_to_sync)} pedidos sem marcadores.")
        background_tasks.add_task(sync_background_orders, api_token, ids_to_sync)

    return data

@router.get("/pedidos/{pedido_id}")
async def obter_pedido(pedido_id: str, token: Optional[str] = None):
    """Obtém detalhes de um pedido específico."""
    try:
        service = get_service(token)
        return await service.get_order_details(pedido_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/separacoes")
async def list_separacoes(
    background_tasks: BackgroundTasks,
    pagina: int = 1,
    data_inicial: Optional[str] = None,
    data_final: Optional[str] = None,
    token: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Busca separações cadastradas no Tiny ERP e injeta numero do pedido via espelho local."""
    try:
        service = get_service(token)
        data = await service.search_separations(pagina=pagina, data_inicial=data_inicial, data_final=data_final)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    separacoes = data.get("separacoes", [])
    if not separacoes:
        return data

    ids_origem = [str(s.get("idOrigemVinc")) for s in separacoes if s.get("idOrigemVinc")]
    if not ids_origem:
        return data

    # --- Camada 1: TinyOrderSync (espelho completo) ---
    synced: dict = {}
    records = db.query(TinyOrderSync).filter(TinyOrderSync.id.in_(ids_origem)).all()
    for r in records:
        if r.numero:
            synced[r.id] = r.numero

    # --- Camada 2: OrderOperational (camada canônica, populada pelo scheduler) ---
    missing = [oid for oid in ids_origem if oid not in synced]
    if missing:
        from models import OrderOperational
        op_records = db.query(OrderOperational).filter(OrderOperational.order_id.in_(missing)).all()
        for r in op_records:
            if r.numero:
                synced[r.order_id] = r.numero

    # --- Camada 3: pedidos.pesquisa.php filtrado por Faturado + período (1 chamada) ---
    still_missing = [oid for oid in ids_origem if oid not in synced]
    if still_missing:
        log.info(f"SEPARACOES: {len(still_missing)} sem numero — buscando via pesquisa Faturados")
        try:
            from datetime import datetime as _dt
            _hoje = _dt.now().strftime("%d/%m/%Y")
            _di = data_inicial or _hoje
            _df = data_final or _hoje
            faturados = await service.get_faturados_numeros(_di, _df)
            resolved = {}
            for oid in still_missing:
                if oid in faturados:
                    synced[oid] = faturados[oid]
                    resolved[oid] = faturados[oid]
            # Persiste para futuras consultas
            for oid, numero in resolved.items():
                existing = db.query(TinyOrderSync).filter(TinyOrderSync.id == oid).first()
                if existing:
                    existing.numero = numero
                else:
                    db.add(TinyOrderSync(id=oid, numero=numero, last_synced_at=datetime.utcnow()))
            if resolved:
                db.commit()
            log.info(f"SEPARACOES: {len(resolved)}/{len(still_missing)} numeros resolvidos via Faturados")
        except Exception as e:
            log.warning(f"SEPARACOES: falha na camada 3: {e}")

    # Injeta numero_pedido em cada separação
    for s in separacoes:
        origem_id = str(s.get("idOrigemVinc", ""))
        s["numero_pedido"] = synced.get(origem_id) or ""

    # ── Upsert de headers de exibição ─────────────────────────────────────────
    # Salva campos de display no DB local para que as abas em_separacao/separadas
    # possam ser servidas sem depender do filtro de data do Tiny.
    try:
        for s in separacoes:
            sep_id = str(s.get("id", ""))
            if not sep_id:
                continue
            forma_envio = s.get("formaEnvio")
            header_data = dict(
                numero=s.get("numero"),
                destinatario=s.get("destinatario"),
                numero_ec=s.get("numeroPedidoEcommerce"),
                data_emissao=s.get("dataEmissao"),
                prazo_maximo=s.get("prazo_maximo"),
                id_forma_envio=str(s.get("idFormaEnvio") or ""),
                forma_envio_descricao=forma_envio.get("descricao") if isinstance(forma_envio, dict) else None,
                numero_pedido=s.get("numero_pedido"),
                updated_at=datetime.utcnow(),
            )
            existing_h = db.query(TinySeparationHeader).filter(
                TinySeparationHeader.separation_id == sep_id
            ).first()
            if existing_h:
                for k, v in header_data.items():
                    setattr(existing_h, k, v)
            else:
                db.add(TinySeparationHeader(separation_id=sep_id, **header_data))
        db.commit()
    except Exception as e:
        db.rollback()
        log.warning(f"SEPARACOES: falha ao upsert headers: {e}")

    return data


async def _backfill_sep_headers_bg(sep_ids: List[str], token: Optional[str]):
    """Busca separacao.obter.php para cada ID sem header e persiste os campos de exibição."""
    db = SessionLocal()
    try:
        service = get_service(token)
        BATCH_SIZE = 8
        updated = 0
        for i in range(0, len(sep_ids), BATCH_SIZE):
            batch = sep_ids[i:i + BATCH_SIZE]
            tasks = [service.get_separation_details(sid) for sid in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for sid, res in zip(batch, results):
                if isinstance(res, Exception):
                    log.warning(f"BACKFILL_HEADERS sep_id={sid}: {res}")
                    continue
                sep = res.get("separacao", {})
                if not sep:
                    continue
                forma_envio = sep.get("formaEnvio")
                header_data = dict(
                    numero=sep.get("numero"),
                    destinatario=sep.get("destinatario"),
                    numero_ec=sep.get("numeroPedidoEcommerce"),
                    data_emissao=sep.get("dataEmissao"),
                    prazo_maximo=sep.get("prazo_maximo"),
                    id_forma_envio=str(sep.get("idFormaEnvio") or ""),
                    forma_envio_descricao=forma_envio.get("descricao") if isinstance(forma_envio, dict) else None,
                    updated_at=datetime.utcnow(),
                )
                existing_h = db.query(TinySeparationHeader).filter(
                    TinySeparationHeader.separation_id == str(sid)
                ).first()
                if existing_h:
                    for k, v in header_data.items():
                        setattr(existing_h, k, v)
                else:
                    db.add(TinySeparationHeader(separation_id=str(sid), **header_data))
                updated += 1
            db.commit()
            if i + BATCH_SIZE < len(sep_ids):
                await asyncio.sleep(0.3)
        log.info(f"BACKFILL_HEADERS concluído: {updated}/{len(sep_ids)} docs")
    except Exception as e:
        log.error(f"BACKFILL_HEADERS ERRO: {e}", exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


@router.get("/tracked-separacoes")
async def get_tracked_separacoes(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Documentos de separação rastreados localmente (em_separacao + concluida + enviada_erp + erro_envio_erp).
    Enriquecidos com campos de exibição do cache de headers local.
    Completamente independente de filtro de data do Tiny — retorna TUDO.
    Se houver docs sem header, dispara backfill automático em background."""
    statuses = db.query(TinySeparationStatus).filter(
        TinySeparationStatus.status.in_(["em_separacao", "concluida", "enviada_erp", "erro_envio_erp"])
    ).all()

    if not statuses:
        return {"separacoes": [], "backfill_triggered": False}

    sep_ids = [s.separation_id for s in statuses]

    headers = {
        h.separation_id: h
        for h in db.query(TinySeparationHeader).filter(
            TinySeparationHeader.separation_id.in_(sep_ids)
        ).all()
    }

    # Docs sem header ou com numero nulo → backfill automático em background
    missing_ids = [
        sid for sid in sep_ids
        if sid not in headers or not headers[sid].numero
    ]
    backfill_triggered = False
    if missing_ids and TINY_TOKEN:
        log.info(f"TRACKED_SEP: {len(missing_ids)} docs sem header — backfill em background")
        background_tasks.add_task(_backfill_sep_headers_bg, missing_ids, TINY_TOKEN)
        backfill_triggered = True

    list_ids = [s.list_id for s in statuses if s.list_id]
    lists: dict = {}
    if list_ids:
        lists = {
            l.id: l.name
            for l in db.query(TinyPickingList).filter(TinyPickingList.id.in_(list_ids)).all()
        }

    # Último log de envio ERP por doc (para badges de sucesso/erro na aba Enviadas ERP)
    erp_log_ids = [
        s.separation_id for s in statuses
        if s.status in ("enviada_erp", "erro_envio_erp")
    ]
    last_erp_logs: dict = {}
    if erp_log_ids:
        from sqlalchemy import func as sa_func
        subq = (
            db.query(
                TinyErpSendLog.separation_id,
                sa_func.max(TinyErpSendLog.sent_at).label("max_sent")
            )
            .filter(TinyErpSendLog.separation_id.in_(erp_log_ids))
            .group_by(TinyErpSendLog.separation_id)
            .subquery()
        )
        logs = (
            db.query(TinyErpSendLog)
            .join(subq, (TinyErpSendLog.separation_id == subq.c.separation_id) &
                        (TinyErpSendLog.sent_at == subq.c.max_sent))
            .all()
        )
        last_erp_logs = {l.separation_id: l for l in logs}

    result = []
    for s in statuses:
        h = headers.get(s.separation_id)
        last_log = last_erp_logs.get(s.separation_id)
        result.append({
            "id": s.separation_id,
            "numero": h.numero if h else None,
            "destinatario": h.destinatario if h else None,
            "numeroPedidoEcommerce": h.numero_ec if h else None,
            "dataEmissao": h.data_emissao if h else None,
            "prazo_maximo": h.prazo_maximo if h else None,
            "idFormaEnvio": h.id_forma_envio if h else None,
            "numero_pedido": h.numero_pedido if h else None,
            "local_status": s.status,
            "list_id": s.list_id,
            "list_name": lists.get(s.list_id) if s.list_id else None,
            "last_erp_log": {
                "status": last_log.status,
                "triggered_by": last_log.triggered_by,
                "error_message": last_log.error_message,
                "sent_at": last_log.sent_at.isoformat(),
            } if last_log else None,
        })

    return {"separacoes": result, "backfill_triggered": backfill_triggered}


@router.post("/vacuum-30-days")
async def trigger_vacuum(background_tasks: BackgroundTasks, api_token: Optional[str] = Query(None)):
    """
    Aciona o aspirador de pó para buscar todos os pedidos dos últimos 30 dias em background.
    """
    token = api_token or TINY_TOKEN
    if not token:
        raise HTTPException(status_code=400, detail="TINY_API_TOKEN não configurado no backend.")
    background_tasks.add_task(vacuum_last_30_days, token)
    return {
        "status": "ok", 
        "message": "Máquina do tempo acionada. O servidor iniciou a raspagem de 30 dias nos bastidores."
    }


@router.post("/sync/full")
async def trigger_full_sync(background_tasks: BackgroundTasks, api_token: Optional[str] = Query(None), lookback_days: int = Query(60)):
    token = api_token or TINY_TOKEN
    if not token:
        raise HTTPException(status_code=400, detail="TINY_API_TOKEN não configurado no backend.")
    background_tasks.add_task(
        run_batched_full_sync,
        token,
        lookback_days=max(1, lookback_days),
        chunk_days=max(1, int(os.getenv("SYNC_FULL_CHUNK_DAYS", "7"))),
        note="disparo manual de carga completa em blocos",
    )
    return {"status": "ok", "message": f"Carga completa agendada para {lookback_days} dias."}


@router.post("/sync/incremental")
async def trigger_incremental_sync(background_tasks: BackgroundTasks, api_token: Optional[str] = Query(None), lookback_days: int = Query(3)):
    token = api_token or TINY_TOKEN
    if not token:
        raise HTTPException(status_code=400, detail="TINY_API_TOKEN não configurado no backend.")
    background_tasks.add_task(
        run_window_sync,
        token,
        lookback_days=max(1, lookback_days),
        sync_type="incremental",
        note="disparo manual incremental",
    )
    return {"status": "ok", "message": f"Sync incremental agendado para {lookback_days} dias."}


@router.post("/sync/reconcile")
async def trigger_reconciliation_sync(background_tasks: BackgroundTasks, api_token: Optional[str] = Query(None), lookback_days: int = Query(30)):
    token = api_token or TINY_TOKEN
    if not token:
        raise HTTPException(status_code=400, detail="TINY_API_TOKEN não configurado no backend.")
    background_tasks.add_task(
        run_window_sync,
        token,
        lookback_days=max(1, lookback_days),
        sync_type="reconciliation",
        note="disparo manual de reconciliação",
    )
    return {"status": "ok", "message": f"Reconciliação agendada para {lookback_days} dias."}


@router.get("/sync/status")
async def sync_status():
    return get_sync_snapshot()


# --- PICKING LISTS (LISTAS DE SEPARAÇÃO CONSOLIDADAS) ---

CACHE_TTL_HOURS = 6

async def _fetch_and_cache(separation_ids: List[str], service: TinyService, db):
    """Busca detalhes de separações no Tiny e armazena no cache local.
    Chamado em background — não bloqueia o usuário."""
    from datetime import timedelta
    BATCH_SIZE = 12

    for i in range(0, len(separation_ids), BATCH_SIZE):
        batch = separation_ids[i:i + BATCH_SIZE]
        tasks = [service.get_separation_details(sid) for sid in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for sid, res in zip(batch, results):
            if isinstance(res, Exception):
                log.warning(f"CACHE_WARM ERRO sep_id={sid}: {res}")
                continue
            sep = res.get("separacao", {})
            itens_raw = sep.get("itens", [])
            if not itens_raw:
                continue
            # Apaga cache antigo deste doc e grava o fresco
            db.query(TinySeparationItemCache).filter(
                TinySeparationItemCache.separation_id == str(sid)
            ).delete(synchronize_session=False)
            for it in itens_raw:
                sku = it.get("codigo")
                if not sku:
                    continue
                db.add(TinySeparationItemCache(
                    separation_id=str(sid),
                    sku=sku,
                    description=it.get("descricao"),
                    quantity=float(it.get("quantidade", 0)),
                    location=it.get("localizacao") or "",
                    cached_at=datetime.utcnow()
                ))
        db.commit()

        if i + BATCH_SIZE < len(separation_ids):
            await asyncio.sleep(0.2)

    log.info(f"CACHE_WARM concluido: {len(separation_ids)} docs")


async def _fetch_and_cache_bg(separation_ids: List[str], token: Optional[str]):
    """Versão background — cria sua própria sessão de DB."""
    db = SessionLocal()
    try:
        service = get_service(token)
        await _fetch_and_cache(separation_ids, service, db)
    except Exception as e:
        log.error(f"CACHE_WARM_BG ERRO: {e}", exc_info=True)
    finally:
        db.close()


def _consolidate_from_cache(separation_ids: List[str], cached_items) -> List[dict]:
    """Consolida itens do cache por SKU, somando quantidades."""
    sku_map = {}
    for item in cached_items:
        if item.separation_id not in separation_ids:
            continue
        sku = item.sku
        if sku not in sku_map:
            sku_map[sku] = {
                "sku": sku,
                "description": item.description,
                "quantity": 0.0,
                "location": item.location or "",
                "source_ids": []
            }
        sku_map[sku]["quantity"] += item.quantity
        if item.separation_id not in sku_map[sku]["source_ids"]:
            sku_map[sku]["source_ids"].append(item.separation_id)
    result = list(sku_map.values())
    result.sort(key=lambda x: x["quantity"], reverse=True)
    return result


class PickingListRequest(BaseModel):
    name: Optional[str] = None
    separation_ids: List[str]

class PickRequest(BaseModel):
    mode: str = "unit"
    qty: Optional[float] = None

@router.post("/picking-lists")
async def create_picking_list(req: PickingListRequest, db: Session = Depends(get_db), token: Optional[str] = None):
    """Cria uma lista de separação consolidada por SKU e localização."""
    try:
        service = get_service(token)
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=CACHE_TTL_HOURS)

        # 1. Verifica cache — busca do Tiny apenas os IDs sem cache fresco
        cached = db.query(TinySeparationItemCache).filter(
            TinySeparationItemCache.separation_id.in_(req.separation_ids),
            TinySeparationItemCache.cached_at >= cutoff
        ).all()
        cached_ids = {c.separation_id for c in cached}
        missing_ids = [sid for sid in req.separation_ids if sid not in cached_ids]

        if missing_ids:
            log.info(f"CACHE_MISS {len(missing_ids)} docs — buscando no Tiny")
            await _fetch_and_cache(missing_ids, service, db)
            fresh = db.query(TinySeparationItemCache).filter(
                TinySeparationItemCache.separation_id.in_(missing_ids)
            ).all()
            cached = list(cached) + list(fresh)
        else:
            log.info(f"CACHE_HIT total — {len(req.separation_ids)} docs servidos do cache")

        items = _consolidate_from_cache(req.separation_ids, cached)

        if not items:
            raise HTTPException(status_code=400, detail="Nenhum item encontrado nos pedidos selecionados.")

        # 2. Gera nome sequencial L{N} - DD/MM/YYYY HH:MM (ou usa nome customizado se informado)
        if req.name:
            list_name = req.name
        else:
            seq = db.query(TinyPickingList).count() + 1
            now_local = datetime.now()
            list_name = f"L{seq} - {now_local.strftime('%d/%m/%Y %H:%M')}"

        # 3. Cria o mestre da lista
        new_list = TinyPickingList(
            name=list_name,
            status="pendente",
            created_at=datetime.utcnow()
        )
        db.add(new_list)
        db.flush() # Para pegar o ID inserido

        # 4. Adiciona os itens consolidados
        for it in items:
            db.add(TinyPickingListItem(
                list_id=new_list.id,
                sku=it["sku"],
                description=it["description"],
                quantity=it["quantity"],
                location=it["location"],
                source_separation_ids=",".join(it["source_ids"])
            ))
        
        # 5. Registra status local dos documentos de separação (Tiny é somente-leitura, nunca escrevemos de volta)
        for sep_id in req.separation_ids:
            existing = db.query(TinySeparationStatus).filter(TinySeparationStatus.separation_id == str(sep_id)).first()
            if existing:
                existing.status = "em_separacao"
                existing.list_id = new_list.id
            else:
                db.add(TinySeparationStatus(
                    separation_id=str(sep_id),
                    status="em_separacao",
                    list_id=new_list.id
                ))

        db.commit()
        return {"status": "success", "id": new_list.id, "name": new_list.name, "item_count": len(items)}
    except Exception as e:
        db.rollback()
        log.error(f"ERRO em create_picking_list: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/separation-statuses")
async def get_separation_statuses(db: Session = Depends(get_db)):
    """Retorna o mapa de status local dos documentos de separação.
    O Tiny é somente-leitura — este endpoint é a fonte de verdade local."""
    statuses = (
        db.query(TinySeparationStatus, TinyPickingList.name)
        .outerjoin(TinyPickingList, TinyPickingList.id == TinySeparationStatus.list_id)
        .all()
    )
    return {
        s.separation_id: {"status": s.status, "list_id": s.list_id, "list_name": name}
        for s, name in statuses
    }


class WarmCacheRequest(BaseModel):
    separation_ids: List[str]

@router.post("/separation-cache/warm")
async def warm_separation_cache(
    req: WarmCacheRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    token: Optional[str] = None
):
    """Aquece o cache de itens de separação em background.
    Chamado pelo frontend após carregar a lista — silencioso, não bloqueia."""
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(hours=CACHE_TTL_HOURS)

    # Limpa entradas expiradas
    db.query(TinySeparationItemCache).filter(
        TinySeparationItemCache.cached_at < cutoff
    ).delete(synchronize_session=False)
    db.commit()

    already = {r[0] for r in db.query(TinySeparationItemCache.separation_id).filter(
        TinySeparationItemCache.separation_id.in_(req.separation_ids),
        TinySeparationItemCache.cached_at >= cutoff
    ).distinct().all()}

    missing = [sid for sid in req.separation_ids if sid not in already]

    if missing:
        background_tasks.add_task(_fetch_and_cache_bg, missing, token)
        log.info(f"CACHE_WARM agendado: {len(missing)} docs (já cacheados: {len(already)})")
        return {"status": "warming", "to_fetch": len(missing), "cached": len(already)}

    return {"status": "ready", "cached": len(already)}


class RevertStatusRequest(BaseModel):
    separation_ids: List[str]

@router.post("/separation-statuses/revert")
async def revert_separation_statuses(req: RevertStatusRequest, db: Session = Depends(get_db)):
    """Devolve documentos para 'Aguardando Separação' localmente.
    - Se tem registro local (criado por nós): apaga o registro (volta a depender do Tiny).
    - Se não tem registro (Tiny diz situacao=4): cria um override 'aguardando' para sobrescrever o Tiny.
    Tiny é somente-leitura — nunca escrevemos de volta."""
    reverted = 0
    for sep_id in req.separation_ids:
        existing = db.query(TinySeparationStatus).filter(
            TinySeparationStatus.separation_id == str(sep_id)
        ).first()
        if existing:
            if existing.status == "em_separacao":
                # Criado por nós — apaga para cair no fallback do Tiny (situacao=1)
                db.delete(existing)
            else:
                existing.status = "aguardando"
        else:
            # Tiny diz situacao=4 mas não temos controle — override local
            db.add(TinySeparationStatus(
                separation_id=str(sep_id),
                status="aguardando",
                list_id=None,
                created_at=datetime.utcnow()
            ))
        reverted += 1
    db.commit()
    log.info(f"REVERT_STATUS {reverted} docs devolvidos para aguardando: {req.separation_ids}")
    return {"status": "success", "reverted": reverted}


class DeleteStatusRequest(BaseModel):
    separation_ids: List[str]

@router.post("/separation-statuses/delete")
async def delete_separation_statuses(req: DeleteStatusRequest, db: Session = Depends(get_db)):
    """Remove registros de status local dos documentos de separação.
    O documento some do nosso rastreamento — Tiny não é afetado."""
    deleted = 0
    for sep_id in req.separation_ids:
        existing = db.query(TinySeparationStatus).filter(
            TinySeparationStatus.separation_id == str(sep_id)
        ).first()
        if existing:
            db.delete(existing)
            deleted += 1
    db.commit()
    log.info(f"DELETE_STATUS {deleted} docs removidos: {req.separation_ids}")
    return {"status": "success", "deleted": deleted}


async def _push_separation_status_to_olist(sep_id: str):
    """Background task: empurra situação 'separado' para a API Tiny/Olist.

    LOCAL  (ENABLE_OLIST_SYNC=false): apenas loga o que SERIA feito (DRY-RUN).
    PRD    (ENABLE_OLIST_SYNC=true):  chama a API Tiny e atualiza a situação.

    Falhas são logadas mas não propagadas — o status local já foi salvo com sucesso.
    """
    if not ENABLE_OLIST_SYNC:
        log.info(
            f"[OLIST_SYNC=OFF] DRY-RUN sep_id={sep_id} "
            f"→ situacao={TINY_SEPARATION_DONE_SITUACAO} (não enviado)"
        )
        return

    if not TINY_TOKEN:
        log.warning(f"[OLIST_SYNC] TINY_API_TOKEN ausente — ignorando sep_id={sep_id}")
        return

    try:
        svc = TinyService(token=TINY_TOKEN)
        await svc.update_separation_status(sep_id, TINY_SEPARATION_DONE_SITUACAO)
        log.info(f"[OLIST_SYNC OK] sep_id={sep_id} → situacao={TINY_SEPARATION_DONE_SITUACAO}")
    except Exception as e:
        log.error(f"[OLIST_SYNC ERRO] sep_id={sep_id}: {e}", exc_info=True)
        # Não re-raise: o pick já foi salvo localmente com sucesso


def _check_and_advance_doc_statuses(list_id: int, db) -> list:
    """Verifica se algum documento da lista teve todos os seus SKUs concluídos
    (picked ou shortage) e avança o status local para 'concluida'.
    Chamado após cada pick ou registro de falta.
    Retorna lista de sep_ids recém-avançados para 'concluida' (para sync Olist).

    Cobre dois cenários de quebra:
    A) sep_id em source_separation_ids mas sem registro TinySeparationStatus → cria como 'concluida'
    B) sep_id com status 'em_separacao' no banco mas sem itens em doc_items (cache vazio na criação)
       → avança vacuously (zero itens = nada a coletar = concluído)
    """
    # Expira cache de sessão — garante valores frescos após o commit do pick
    db.expire_all()

    # Todos os itens da lista
    items = db.query(TinyPickingListItem).filter(TinyPickingListItem.list_id == list_id).all()
    if not items:
        return []

    # Monta mapa: sep_id → [items que contêm esse doc]
    from collections import defaultdict
    doc_items: dict = defaultdict(list)
    for it in items:
        if not it.source_separation_ids:
            continue
        for sep_id in it.source_separation_ids.split(","):
            sep_id = sep_id.strip()
            if sep_id:
                doc_items[sep_id].append(it)

    newly_concluded: list = []

    # ── Cenário normal + Cenário A: sep_ids que aparecem em source_separation_ids ──
    for sep_id, its in doc_items.items():
        all_done = all(
            (it.qty_picked is not None and it.qty_picked >= it.quantity - 0.001) or it.is_shortage
            for it in its
        )
        if not all_done:
            pending = [(it.sku, it.qty_picked, it.quantity) for it in its
                       if not ((it.qty_picked is not None and it.qty_picked >= it.quantity - 0.001) or it.is_shortage)]
            log.debug(f"SEP_PENDENTE sep_id={sep_id} itens_pendentes={pending}")
            continue

        record = db.query(TinySeparationStatus).filter(
            TinySeparationStatus.separation_id == sep_id
        ).first()

        if record and record.status == "em_separacao":
            # Caso normal
            record.status = "concluida"
            newly_concluded.append(sep_id)
            log.info(f"DOC_CONCLUIDO sep_id={sep_id} list_id={list_id}")
        elif not record:
            # Cenário A: sem registro → cria direto como 'concluida'
            db.add(TinySeparationStatus(
                separation_id=sep_id,
                status="concluida",
                list_id=list_id,
            ))
            newly_concluded.append(sep_id)
            log.warning(f"DOC_CONCLUIDO_SEM_REGISTRO sep_id={sep_id} list_id={list_id} — criado direto como concluida")
        # se record.status == "concluida" já → nada a fazer

    # ── Cenário B: sep_ids com em_separacao neste list_id mas sem nenhum item em doc_items ──
    # (cache estava vazio quando a lista foi criada — vacuously done)
    tracked = db.query(TinySeparationStatus).filter(
        TinySeparationStatus.list_id == list_id,
        TinySeparationStatus.status == "em_separacao",
    ).all()
    for record in tracked:
        if record.separation_id not in doc_items:
            record.status = "concluida"
            newly_concluded.append(record.separation_id)
            log.warning(f"DOC_CONCLUIDO_SEM_ITENS sep_id={record.separation_id} list_id={list_id} — sem itens em doc_items, avançado vacuamente")

    db.commit()
    return newly_concluded


@router.get("/separacao/{sep_id}")
async def get_separacao_detail(sep_id: str, token: Optional[str] = None, db: Session = Depends(get_db)):
    """Retorna detalhes completos de uma separação (lazy — chamado ao clicar no documento).
    Enriquece com progresso local de picking se existir lista associada."""
    service = get_service(token)
    data = await service.get_separation_details(sep_id)
    sep = data.get("separacao", {})

    # Enriquece com progresso local se houver lista associada
    local_status = db.query(TinySeparationStatus).filter(
        TinySeparationStatus.separation_id == str(sep_id)
    ).first()

    picking_progress = None
    if local_status and local_status.list_id:
        items = db.query(TinyPickingListItem).filter(
            TinyPickingListItem.list_id == local_status.list_id
        ).all()
        # Filtra apenas itens que vieram desta separação
        related = [it for it in items if it.source_separation_ids and str(sep_id) in it.source_separation_ids.split(",")]
        if related:
            total_qty = sum(it.quantity for it in related)
            picked_qty = sum(it.qty_picked or 0 for it in related)
            pct = round((picked_qty / total_qty * 100) if total_qty > 0 else 0)
            picking_progress = {
                "pct": pct,
                "picked_qty": picked_qty,
                "total_qty": total_qty,
                "list_name": local_status.list_name if hasattr(local_status, 'list_name') else None,
                "items": [
                    {"sku": it.sku, "qty_picked": it.qty_picked or 0, "quantity": it.quantity, "is_shortage": it.is_shortage}
                    for it in related
                ]
            }

    return {"separacao": sep, "local_status": local_status.status if local_status else None, "picking_progress": picking_progress}


@router.get("/picking-lists")
async def list_picking_lists(db: Session = Depends(get_db)):
    """Lista o histórico de listas de separação geradas."""
    lists = db.query(TinyPickingList).order_by(TinyPickingList.created_at.desc()).all()
    return lists

@router.delete("/picking-lists/{list_id}")
async def delete_picking_list(list_id: int, db: Session = Depends(get_db)):
    """Exclui uma lista de separação e reverte os documentos para 'aguardando separação'."""
    plist = db.query(TinyPickingList).filter(TinyPickingList.id == list_id).first()
    if not plist:
        raise HTTPException(status_code=404, detail="Lista não encontrada.")

    # Coleta todos os separation_ids associados aos itens desta lista
    items = db.query(TinyPickingListItem).filter(TinyPickingListItem.list_id == list_id).all()
    sep_ids: set[str] = set()
    for it in items:
        if it.source_separation_ids:
            for sid in it.source_separation_ids.split(","):
                sid = sid.strip()
                if sid:
                    sep_ids.add(sid)

    # Reverte status local: apaga registros em_separacao/concluida para este list_id
    for sep_id in sep_ids:
        record = db.query(TinySeparationStatus).filter(
            TinySeparationStatus.separation_id == sep_id
        ).first()
        if record and record.list_id == list_id:
            db.delete(record)  # Remove override → volta a depender do Tiny (aguardando)

    # Deleta itens e lista (cascade já cuida dos itens pelo relationship)
    db.delete(plist)
    db.commit()

    log.info(f"DELETE_LIST list_id={list_id} sep_ids_revertidos={sep_ids}")
    return {"status": "success", "deleted_list_id": list_id, "reverted_sep_ids": list(sep_ids)}


@router.post("/picking-lists/{list_id}/recheck-statuses")
async def recheck_list_statuses(list_id: int, db: Session = Depends(get_db)):
    """Re-executa _check_and_advance_doc_statuses manualmente com diagnóstico completo.
    Cobre Cenário A (sem registro) e Cenário B (em_separacao sem itens).
    Útil para corrigir listas concluídas que ficaram com docs presos."""
    plist = db.query(TinyPickingList).filter(TinyPickingList.id == list_id).first()
    if not plist:
        raise HTTPException(status_code=404, detail="Lista não encontrada.")

    # Snapshot antes de executar
    db.expire_all()
    items = db.query(TinyPickingListItem).filter(TinyPickingListItem.list_id == list_id).all()

    from collections import defaultdict
    doc_items: dict = defaultdict(list)
    for it in items:
        if not it.source_separation_ids:
            continue
        for sep_id in it.source_separation_ids.split(","):
            sep_id = sep_id.strip()
            if sep_id:
                doc_items[sep_id].append(it)

    # Snapshot de status antes
    all_sep_ids = set(doc_items.keys())
    tracked = db.query(TinySeparationStatus).filter(
        TinySeparationStatus.list_id == list_id
    ).all()
    for r in tracked:
        all_sep_ids.add(r.separation_id)

    status_before = {}
    for sep_id in all_sep_ids:
        r = db.query(TinySeparationStatus).filter(TinySeparationStatus.separation_id == sep_id).first()
        status_before[sep_id] = r.status if r else None

    # Executa a lógica corrigida
    newly_concluded = _check_and_advance_doc_statuses(list_id, db)

    # Monta diagnóstico
    diagnostic = []
    for sep_id in all_sep_ids:
        its = doc_items.get(sep_id, [])
        pending = [
            {"sku": it.sku, "qty_picked": it.qty_picked, "quantity": it.quantity}
            for it in its
            if not ((it.qty_picked is not None and it.qty_picked >= it.quantity - 0.001) or it.is_shortage)
        ]
        r = db.query(TinySeparationStatus).filter(TinySeparationStatus.separation_id == sep_id).first()
        diagnostic.append({
            "sep_id": sep_id,
            "total_items": len(its),
            "done_items": len(its) - len(pending),
            "pending_items": pending,
            "status_before": status_before.get(sep_id),
            "status_after": r.status if r else "concluida",
            "advanced": sep_id in newly_concluded,
            "scenario": "B_sem_itens" if not its else ("A_sem_registro" if status_before.get(sep_id) is None else "normal"),
        })

    return {
        "list_id": list_id,
        "newly_concluded": newly_concluded,
        "diagnostic": sorted(diagnostic, key=lambda x: (not x["advanced"], len(x["pending_items"]))),
    }


@router.get("/picking-lists/{list_id}")
async def get_picking_list_details(list_id: int, db: Session = Depends(get_db)):
    """Retorna os detalhes e itens de uma lista específica."""
    plist = db.query(TinyPickingList).filter(TinyPickingList.id == list_id).first()
    if not plist:
        raise HTTPException(status_code=404, detail="Lista não encontrada.")
    
    # SQLAlchemy já carrega os items por causa do relationship
    # No entanto, garantimos a ordenação por quantidade se necessário
    items = sorted(plist.items, key=lambda x: x.quantity, reverse=True)
    
    return {
        "id": plist.id,
        "name": plist.name,
        "status": plist.status,
        "created_at": plist.created_at,
        "items": items
    }

# Cache em memória: sku.upper() → url (str) ou None (sem imagem)
_product_image_cache: dict[str, str | None] = {}

@router.get("/product-image/{sku}")
async def get_product_image(sku: str, token: Optional[str] = None):
    """Retorna a URL da primeira imagem do produto no Tiny.
    Cache em memória por SKU — zero DB, zero custo extra em runtime."""
    sku_key = sku.strip().upper()

    if sku_key in _product_image_cache:
        return {"sku": sku_key, "image_url": _product_image_cache[sku_key]}

    service = get_service(token)

    try:
        # Passo 1: pesquisa pelo código/SKU
        pesquisa = await service._post("produtos.pesquisa.php", {"pesquisa": sku_key})
        produtos = pesquisa.get("produtos", [])
        produto_id = None
        for p in produtos:
            prod = p.get("produto", {})
            if str(prod.get("codigo", "")).upper() == sku_key:
                produto_id = prod.get("id")
                break
        if not produto_id and produtos:
            produto_id = produtos[0].get("produto", {}).get("id")

        if not produto_id:
            _product_image_cache[sku_key] = None
            return {"sku": sku_key, "image_url": None}

        # Passo 2: busca detalhes com anexos
        obter = await service._post("produto.obter.php", {"id": produto_id})
        produto = obter.get("produto", {})
        anexos = produto.get("anexos", [])
        image_url = anexos[0].get("anexo") if anexos else None

        _product_image_cache[sku_key] = image_url
        return {"sku": sku_key, "image_url": image_url}

    except Exception as e:
        log.warning(f"product-image/{sku_key}: {e}")
        return {"sku": sku_key, "image_url": None}


class WarmImagesRequest(BaseModel):
    skus: List[str]

@router.post("/product-images/warm")
async def warm_product_images(req: WarmImagesRequest, background_tasks: BackgroundTasks, token: Optional[str] = None):
    """Pre-aquece cache de imagens para uma lista de SKUs.
    Executa em background — retorna imediatamente."""
    missing = [s.strip().upper() for s in req.skus if s.strip().upper() not in _product_image_cache]
    if missing:
        background_tasks.add_task(_warm_images_bg, missing, token)
    return {"warming": len(missing), "already_cached": len(req.skus) - len(missing)}


async def _fetch_one_image(sku_key: str, service) -> None:
    """Busca imagem de um SKU e armazena no cache."""
    if sku_key in _product_image_cache:
        return
    try:
        pesquisa = await service._post("produtos.pesquisa.php", {"pesquisa": sku_key})
        produtos = pesquisa.get("produtos", [])
        produto_id = None
        for p in produtos:
            prod = p.get("produto", {})
            if str(prod.get("codigo", "")).upper() == sku_key:
                produto_id = prod.get("id")
                break
        if not produto_id and produtos:
            produto_id = produtos[0].get("produto", {}).get("id")
        if not produto_id:
            _product_image_cache[sku_key] = None
            return
        obter = await service._post("produto.obter.php", {"id": produto_id})
        anexos = obter.get("produto", {}).get("anexos", [])
        _product_image_cache[sku_key] = anexos[0].get("anexo") if anexos else None
    except Exception as e:
        log.warning(f"warm_images_bg/{sku_key}: {e}")
        _product_image_cache[sku_key] = None


async def _warm_images_bg(skus: List[str], token: Optional[str]):
    """Busca imagens em batches paralelos de 3 — rápido e sem estourar rate limit Tiny."""
    try:
        service = get_service(token)
    except Exception:
        return
    missing = [s for s in skus if s not in _product_image_cache]
    BATCH = 3
    for i in range(0, len(missing), BATCH):
        batch = missing[i:i + BATCH]
        await asyncio.gather(*[_fetch_one_image(sku, service) for sku in batch], return_exceptions=True)
        if i + BATCH < len(missing):
            await asyncio.sleep(0.15)  # 150ms entre batches


@router.get("/resolve-barcode/{barcode}")
async def resolve_barcode(barcode: str, focus_sku: str | None = None, db: Session = Depends(get_db)):
    """Verifica se um código de barras pertence a um SKU (via WMS).

    focus_sku: se fornecido, prioriza o vínculo com esse SKU específico.
    Permite que o mesmo barcode vinculado a múltiplos SKUs resolva corretamente
    conforme o contexto de bipagem (SKU da tela).
    """
    code = barcode.strip().upper()

    # Se focus_sku informado, checa primeiro se existe o par (barcode, focus_sku)
    if focus_sku:
        focused = db.query(Barcode).filter(
            Barcode.barcode == code,
            Barcode.sku == focus_sku.strip().upper(),
        ).first()
        if focused:
            return {"sku": focused.sku, "found": True, "source": "wms_mapping"}

    # Fallback: primeiro registro encontrado
    mapping = db.query(Barcode).filter(Barcode.barcode == code).first()
    if mapping:
        return {"sku": mapping.sku, "found": True, "source": "wms_mapping"}
    return {"sku": code, "found": False, "source": "direct"}

@router.post("/link-barcode")
async def link_barcode(request: dict, db: Session = Depends(get_db)):
    """Vincula um novo código de barras a um SKU no banco do WMS.

    Um mesmo código de barras pode ser vinculado a múltiplos SKUs diferentes.
    A verificação de duplicata usa o par (barcode, sku), não só o barcode.
    """
    barcode_val = (request.get("barcode") or "").strip().upper()
    sku_val = (request.get("sku") or "").strip().upper()

    if not barcode_val or not sku_val:
        raise HTTPException(status_code=400, detail="Barcode e SKU são obrigatórios")

    # Verifica se o par exato (barcode, sku) já existe — evita duplicata
    existing = db.query(Barcode).filter(
        Barcode.barcode == barcode_val,
        Barcode.sku == sku_val,
    ).first()
    if existing:
        return {"message": "Vínculo já existe", "sku": sku_val}

    # Permite mesmo barcode para SKUs diferentes (mesmo comportamento do picking)
    from sqlalchemy.exc import IntegrityError
    try:
        new_mapping = Barcode(barcode=barcode_val, sku=sku_val, is_primary=False)
        db.add(new_mapping)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Erro de integridade ao vincular barcode")

    return {"message": "Vínculo criado com sucesso", "sku": sku_val}

@router.post("/picking-items/{item_id}/pick")
async def register_item_pick(item_id: int, request: PickRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Registra a coleta (total ou parcial) de um item na lista de picking."""
    try:
        item = db.query(TinyPickingListItem).filter(TinyPickingListItem.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Item não encontrado")

        mode = request.mode
        qty_val = request.qty
        log.info(f"PICK id={item_id} sku={item.sku} {item.qty_picked}/{item.quantity}")

        if mode == "box":
            item.qty_picked = float(item.quantity)
        elif mode == "set" and qty_val is not None:
            item.qty_picked = float(qty_val)
        else:
            item.qty_picked = (item.qty_picked or 0) + 1
            if item.qty_picked > item.quantity:
                item.qty_picked = item.quantity

        item.picked_at = datetime.utcnow()
        item.is_shortage = False
        list_id = item.list_id
        db.commit()
        db.refresh(item)
        log.info(f"PICK OK id={item_id} {item.qty_picked}/{item.quantity}")
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"PICK ERRO item_id={item_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    
    total_items = db.query(TinyPickingListItem).filter(TinyPickingListItem.list_id == list_id).count()
    completed_items = db.query(TinyPickingListItem).filter(
        TinyPickingListItem.list_id == list_id,
        TinyPickingListItem.qty_picked >= TinyPickingListItem.quantity
    ).count()
    
    list_completed = False
    if total_items == completed_items and total_items > 0:
        master_list = db.query(TinyPickingList).filter(TinyPickingList.id == list_id).first()
        if master_list:
            master_list.status = "concluida"
            db.commit()
            list_completed = True

    try:
        concluded_ids = _check_and_advance_doc_statuses(list_id, db)
        for sep_id in (concluded_ids or []):
            background_tasks.add_task(_push_separation_status_to_olist, sep_id)
    except Exception as e:
        log.error(f"ERRO ao avançar status docs list_id={list_id}: {e}", exc_info=True)

    return {
        "status": "success",
        "item": {
            "id": item.id,
            "sku": item.sku,
            "description": item.description,
            "quantity": item.quantity,
            "qty_picked": item.qty_picked,
            "is_shortage": item.is_shortage,
            "notes": item.notes,
            "location": item.location
        },
        "list_completed": list_completed
    }


@router.post("/picking-items/{item_id}/unpick")
async def register_item_unpick(item_id: int, db: Session = Depends(get_db)):
    """Remove o registro de coleta de um item (desfaz)."""
    item = db.query(TinyPickingListItem).filter(TinyPickingListItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    
    sku = item.sku
    list_id = item.list_id

    item.qty_picked = 0.0
    item.qty_shortage = 0.0
    item.picked_at = None
    item.is_shortage = False
    item.notes = None

    # Remove registro de falta correspondente na tabela shortages
    db.query(Shortage).filter(
        Shortage.sku == sku,
        Shortage.list_id == str(list_id)
    ).delete()

    # Reverte o status da lista mestra se ela estava concluída
    master_list = db.query(TinyPickingList).filter(TinyPickingList.id == list_id).first()
    if master_list and master_list.status == "concluida":
        master_list.status = "em_andamento"

    db.commit()
    log.info(f"UNPICK id={item_id} sku={sku} — shortage removido")
    return {"status": "success", "item": {"id": item_id, "qty_picked": 0.0, "qty_shortage": 0.0, "is_shortage": False, "notes": None}}

class ShortageRequest(BaseModel):
    sku: str
    qty: float
    category: str
    list_id: str | None = None
    description: str | None = None
    operator_id: int | None = None
    notes: str | None = None # NOVO
    item_id: int | None = None # NOVO

@router.post("/picking-items/{item_id}/clear-shortage")
async def clear_item_shortage(item_id: int, db: Session = Depends(get_db)):
    """Remove a marcação de falta de um item e o registro no relatório."""
    item = db.query(TinyPickingListItem).filter(TinyPickingListItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    
    item.is_shortage = False
    
    # Busca e remove da tabela Shortage para manter consistência
    try:
        from models import Shortage
        db.query(Shortage).filter(
            Shortage.sku == item.sku,
            Shortage.list_id == str(item.list_id)
        ).delete()
    except Exception as e:
        print(f"Erro ao deletar registro de falta relacionado: {e}")

    db.commit()
    return {"status": "success", "cleared": True}

@router.post("/report-shortage")
async def report_shortage(req: ShortageRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Registra um item com estoque zerado ou parcial no relatório de faltas."""
    log.info(f"SHORTAGE sku={req.sku} qty={req.qty} list={req.list_id} item={req.item_id}")
    try:
        shortage = Shortage(
            sku=req.sku,
            quantity=req.qty,
            category=req.category,
            list_id=req.list_id,
            description=req.description,
            operator_id=req.operator_id,
            notes=req.notes
        )
        db.add(shortage)

        if req.category == "organico" and req.item_id:
            item = db.query(TinyPickingListItem).filter(TinyPickingListItem.id == req.item_id).first()
            if item:
                item.is_shortage = True
                item.qty_shortage = float(req.qty)
                item.notes = req.notes
                log.info(f"SHORTAGE OK item={req.item_id}")
                db.commit()
                try:
                    concluded_ids = _check_and_advance_doc_statuses(item.list_id, db)
                    for sep_id in (concluded_ids or []):
                        background_tasks.add_task(_push_separation_status_to_olist, sep_id)
                except Exception as ce:
                    log.error(f"ERRO ao avançar status docs (shortage) item={req.item_id}: {ce}", exc_info=True)
            else:
                db.commit()
        else:
            db.commit()

        log.info(f"SHORTAGE OK sku={req.sku}")
        return {"status": "success", "msg": "Falta registrada com sucesso"}
    except Exception as e:
        db.rollback()
        log.error(f"SHORTAGE ERRO sku={req.sku}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/shortages")
async def get_shortages(db: Session = Depends(get_db)):
    """Retorna todas as faltas registradas (tabela nova + legados)."""
    from models import Operator, Session as PickSession
    
    # 1. Busca da tabela definitiva
    new_shortages = db.query(Shortage).all()
    
    # 2. Busca legados do PickingItem (Full - Shopee/ML)
    # Precisamos do join com Session e Operator para os legados
    legacy_rows = (
        db.query(PickingItem, Operator.name)
        .join(PickSession, PickSession.id == PickingItem.session_id)
        .outerjoin(Operator, Operator.id == PickSession.operator_id)
        .filter(PickingItem.shortage_qty > 0)
        .all()
    )
    
    consolidated = []
    
    # Adiciona os novos
    for s in new_shortages:
        consolidated.append({
            "id": s.id,
            "sku": s.sku,
            "description": s.description,
            "quantity": s.quantity,
            "category": s.category,
            "list_id": s.list_id,
            "notes": s.notes,
            "operator_name": s.operator.name if s.operator else "Admin",
            "created_at": s.created_at
        })

    # Converte os legados
    for item, op_name in legacy_rows:
        consolidated.append({
            "id": f"legacy_{item.id}",
            "sku": item.sku,
            "description": item.description,
            "quantity": item.shortage_qty,
            "category": "full",
            "list_id": f"Lista {item.session_id}",
            "operator_name": op_name or "Desconhecido",
            "created_at": item.completed_at or datetime.utcnow()
        })
        
    # Ordena por data (mais recentes primeiro)
    consolidated.sort(key=lambda x: x["created_at"] if isinstance(x["created_at"], datetime) else datetime.utcnow(), reverse=True)
    
    return consolidated

# ── ERP SEND: envio de documentos separados para o Tiny ─────────────────────

class EnviarErpRequest(BaseModel):
    separation_ids: List[str]
    triggered_by: str = "manual"  # manual | auto


async def _send_single_doc_to_erp(sep_id: str, triggered_by: str, db) -> dict:
    """Envia um documento para o Tiny via separacao.alterar.situacao.php (situacao=2).
    Atualiza TinySeparationStatus e grava log independente do resultado.
    Retorna dict com {ok, status, message}."""
    if not TINY_TOKEN:
        msg = "TINY_API_TOKEN não configurado"
        log.warning(f"[ERP_SEND] {sep_id}: {msg}")
        _save_erp_log(db, sep_id, triggered_by, "error", None, msg)
        _set_erp_status(db, sep_id, "erro_envio_erp")
        db.commit()
        return {"ok": False, "status": "error", "message": msg}

    try:
        svc = TinyService(token=TINY_TOKEN)
        resp = await svc._post("separacao.alterar.situacao.php", {
            "situacao": 2,
            "idSeparacao": sep_id,
        })
        resp_json = json.dumps(resp, ensure_ascii=False) if isinstance(resp, dict) else str(resp)

        # TinyService._post já desembala o "retorno" interno — resp é o objeto direto.
        # Suporta tanto {"status":"OK"} (desembalado) quanto {"retorno":{"status":"OK"}} (embalado).
        retorno = resp.get("retorno", resp) if isinstance(resp, dict) else {}
        ok = str(retorno.get("status", "")).upper() == "OK"

        if ok:
            _set_erp_status(db, sep_id, "enviada_erp")
            _save_erp_log(db, sep_id, triggered_by, "success", resp_json, None)
            db.commit()
            log.info(f"[ERP_SEND OK] sep_id={sep_id} triggered_by={triggered_by}")
            return {"ok": True, "status": "success", "message": "Enviado com sucesso"}
        else:
            msg = f"Tiny retornou status não-OK: {resp_json[:300]}"
            _set_erp_status(db, sep_id, "erro_envio_erp")
            _save_erp_log(db, sep_id, triggered_by, "error", resp_json, msg)
            db.commit()
            log.warning(f"[ERP_SEND NOK] sep_id={sep_id}: {msg}")
            return {"ok": False, "status": "error", "message": msg}

    except Exception as e:
        msg = str(e)
        try:
            _set_erp_status(db, sep_id, "erro_envio_erp")
            _save_erp_log(db, sep_id, triggered_by, "error", None, msg)
            db.commit()
        except Exception:
            pass
        log.error(f"[ERP_SEND ERRO] sep_id={sep_id}: {msg}", exc_info=True)
        return {"ok": False, "status": "error", "message": msg}


def _set_erp_status(db, sep_id: str, new_status: str):
    existing = db.query(TinySeparationStatus).filter(
        TinySeparationStatus.separation_id == str(sep_id)
    ).first()
    if existing:
        existing.status = new_status
    else:
        db.add(TinySeparationStatus(
            separation_id=str(sep_id),
            status=new_status,
            list_id=None,
            created_at=datetime.utcnow()
        ))


def _save_erp_log(db, sep_id: str, triggered_by: str, status: str, response_json, error_message):
    db.add(TinyErpSendLog(
        separation_id=str(sep_id),
        triggered_by=triggered_by,
        status=status,
        response_json=response_json,
        error_message=error_message,
        sent_at=datetime.utcnow()
    ))


@router.post("/separation-statuses/enviar-erp")
async def enviar_docs_erp(req: EnviarErpRequest, db: Session = Depends(get_db)):
    """Envia documentos da aba 'Separadas' para o ERP Tiny (situacao=2).
    Pode ser chamado manualmente (seleção do usuário) ou pelo scheduler automático.
    Retorna resultado por documento."""
    results = {}
    for sep_id in req.separation_ids:
        results[sep_id] = await _send_single_doc_to_erp(sep_id, req.triggered_by, db)

    total = len(results)
    success = sum(1 for r in results.values() if r["ok"])
    log.info(f"[ERP_SEND BATCH] {success}/{total} enviados com sucesso (triggered_by={req.triggered_by})")
    return {
        "status": "done",
        "total": total,
        "success": success,
        "failed": total - success,
        "results": results,
    }


@router.get("/erp-send-logs/{sep_id}")
async def get_erp_send_logs(sep_id: str, db: Session = Depends(get_db)):
    """Histórico de logs de envio ERP para um documento específico."""
    logs = (
        db.query(TinyErpSendLog)
        .filter(TinyErpSendLog.separation_id == sep_id)
        .order_by(TinyErpSendLog.sent_at.desc())
        .limit(50)
        .all()
    )
    return {
        "separation_id": sep_id,
        "logs": [
            {
                "id": l.id,
                "triggered_by": l.triggered_by,
                "status": l.status,
                "error_message": l.error_message,
                "sent_at": l.sent_at.isoformat(),
            }
            for l in logs
        ],
    }


@router.post("/shortages/{shortage_id}/delete")
async def delete_shortage(shortage_id: int, db: Session = Depends(get_db)):
    """Remove um registro da tabela de faltas."""
    item = db.query(Shortage).filter(Shortage.id == shortage_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    
    db.delete(item)
    db.commit()
    return {"status": "ok"}
