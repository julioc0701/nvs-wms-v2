"""Geração automática de listas de separação Tiny (seg-sex 06:00 BR).

Fluxo:
1. Verifica se já rodou hoje (via AutoSeparationState)
2. Para cada marketplace ('ml', 'shopee'): busca docs aguardando + cria lista
3. Skip silencioso quando marketplace sem docs
4. Retry 1x em falha; se 2ª falha → state.last_status='failed_visible'
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta, time as dtime
from typing import Optional

from sqlalchemy.orm import Session as DBSession

from database import SessionLocal
from models import (
    AutoSeparationState,
    TinyPickingList,
    TinyPickingListItem,
    TinySeparationStatus,
    TinySeparationItemCache,
)
from services.tiny_service import TinyService

log = logging.getLogger(__name__)

# Marketplace → idFormaEnvio (do código Tiny existente)
MARKETPLACE_FORMAS = {
    "ml": "735794407",       # Mercado Envios
    "shopee": "735725326",   # Shopee
}


def _get_state(db: DBSession) -> AutoSeparationState:
    """Pega o singleton AutoSeparationState (id=1). Garantido existir pela migration."""
    state = db.query(AutoSeparationState).filter(AutoSeparationState.id == 1).first()
    if not state:
        # Defensivo — migration deveria ter inserido. Cria aqui se faltou.
        state = AutoSeparationState(id=1, last_status="never_ran", consecutive_failures=0)
        db.add(state)
        db.flush()
    return state


def _already_ran_today(state: AutoSeparationState) -> bool:
    """Verifica se já rodou hoje (mesma data calendário em BR)."""
    if not state.last_run_at:
        return False
    # Para simplicidade, compara data UTC (job roda 06:00 BR = 09:00 UTC).
    # Diferença de dia entre BR e UTC só ocorre entre 21:00-23:59 BR — fora do horário do job.
    return state.last_run_at.date() == datetime.utcnow().date()


async def _fetch_docs_for_marketplace(
    service: TinyService,
    marketplace: str,
    data_inicial: str,
    data_final: str,
    db: DBSession,
) -> list[dict]:
    """Busca docs aguardando separação no Tiny para um marketplace.
    Retorna lista de docs FILTRADOS — exclui docs já em em_separacao local."""
    forma_id = MARKETPLACE_FORMAS.get(marketplace)
    if not forma_id:
        log.warning(f"[AUTO_SEP] Marketplace desconhecido: {marketplace}")
        return []

    resp = await service.search_separations(
        pagina=1,
        data_inicial=data_inicial,
        data_final=data_final,
    )
    all_docs = resp.get("separacoes", [])
    # Filtra por marketplace via idFormaEnvio
    marketplace_docs = [
        s.get("separacao") or s
        for s in all_docs
        if str((s.get("separacao") or s).get("idFormaEnvio") or "") == forma_id
    ]
    if not marketplace_docs:
        return []

    # Filtra docs que já estão em em_separacao localmente
    sep_ids = [str(d.get("id")) for d in marketplace_docs if d.get("id")]
    if not sep_ids:
        return []
    em_sep = db.query(TinySeparationStatus.separation_id).filter(
        TinySeparationStatus.separation_id.in_(sep_ids),
        TinySeparationStatus.status.in_(("em_separacao", "concluida", "enviada_erp", "erro_envio_erp"))
    ).all()
    em_sep_set = {row[0] for row in em_sep}
    return [d for d in marketplace_docs if str(d.get("id")) not in em_sep_set]


async def _create_list_for_marketplace(
    service: TinyService,
    marketplace: str,
    docs: list[dict],
    db: DBSession,
) -> dict:
    """Cria TinyPickingList consolidada para um marketplace.
    Retorna dict com info da lista criada."""
    # 1. Garante que itens estão em cache (warm + fetch)
    sep_ids = [str(d.get("id")) for d in docs if d.get("id")]
    cached = db.query(TinySeparationItemCache).filter(
        TinySeparationItemCache.separation_id.in_(sep_ids)
    ).all()
    cached_ids = {c.separation_id for c in cached}
    missing_ids = [sid for sid in sep_ids if sid not in cached_ids]
    if missing_ids:
        # Fetch e cacheia — usa helper interno do tiny router
        from routers.tiny import _fetch_and_cache
        await _fetch_and_cache(missing_ids, service, db)
        cached = db.query(TinySeparationItemCache).filter(
            TinySeparationItemCache.separation_id.in_(sep_ids)
        ).all()

    # 2. Consolida itens
    from routers.tiny import _consolidate_from_cache
    items = _consolidate_from_cache(sep_ids, cached)
    if not items:
        log.info(f"[AUTO_SEP] {marketplace}: 0 itens consolidados, skip")
        return {"marketplace": marketplace, "list_id": None, "docs": 0}

    # 3. Gera nome com sufixo " - Aut"
    seq = db.query(TinyPickingList).count() + 1
    now_local = datetime.now()
    list_name = f"L{seq} - {now_local.strftime('%d/%m/%Y %H:%M')} - Aut"

    # 4. Cria mestre da lista (source='auto')
    new_list = TinyPickingList(
        name=list_name,
        status="pendente",
        source="auto",
        created_at=datetime.utcnow()
    )
    db.add(new_list)
    db.flush()

    # 5. Adiciona itens
    for it in items:
        db.add(TinyPickingListItem(
            list_id=new_list.id,
            sku=it["sku"],
            description=it["description"],
            quantity=it["quantity"],
            location=it["location"],
            source_separation_ids=",".join(it["source_ids"])
        ))

    # 6. Marca docs como em_separacao
    for sep_id in sep_ids:
        existing = db.query(TinySeparationStatus).filter(
            TinySeparationStatus.separation_id == str(sep_id)
        ).first()
        if existing:
            existing.status = "em_separacao"
            existing.list_id = new_list.id
        else:
            db.add(TinySeparationStatus(
                separation_id=str(sep_id),
                status="em_separacao",
                list_id=new_list.id
            ))

    return {
        "marketplace": marketplace,
        "list_id": new_list.id,
        "list_name": new_list.name,
        "docs": len(sep_ids),
        "items": len(items),
    }


async def executar_job(token: str, force: bool = False) -> dict:
    """Executa o job completo:
    - Verifica idempotência (já rodou hoje?)
    - Para cada marketplace busca docs e cria listas
    - Atualiza state (success / failed_visible / no_docs)

    force=True ignora 'já rodou hoje' — usado pelo endpoint run-now.

    Retorna dict com sumário da execução.
    """
    db = SessionLocal()
    summary = {"status": "unknown", "lists": [], "errors": []}
    try:
        state = _get_state(db)

        if not force and _already_ran_today(state):
            log.info("[AUTO_SEP] Já rodou hoje (skip — não força)")
            return {"status": "skipped_already_ran", "lists": []}

        # Calcula janela: hoje - 6 dias (= 7 dias incluindo hoje)
        today = datetime.now()
        data_final = today.strftime("%d/%m/%Y")
        data_inicial = (today - timedelta(days=6)).strftime("%d/%m/%Y")
        log.info(f"[AUTO_SEP] Iniciando — janela {data_inicial} a {data_final}")

        service = TinyService(token=token)
        any_success = False
        any_failure = False
        summary_parts = []

        for marketplace in ("ml", "shopee"):
            try:
                docs = await _fetch_docs_for_marketplace(
                    service, marketplace, data_inicial, data_final, db
                )
                if not docs:
                    log.info(f"[AUTO_SEP] {marketplace}: 0 docs aguardando — skip silencioso")
                    summary_parts.append(f"{marketplace}=0")
                    any_success = True  # Sem docs não é falha
                    continue

                result = await _create_list_for_marketplace(service, marketplace, docs, db)
                db.commit()  # commit por marketplace (atômico)
                summary["lists"].append(result)
                summary_parts.append(f"{marketplace}={result['docs']}")
                any_success = True
                log.info(f"[AUTO_SEP] {marketplace}: lista {result['list_name']} criada com {result['docs']} docs")

            except Exception as exc:
                db.rollback()
                msg = f"{marketplace}: {exc}"
                log.exception(f"[AUTO_SEP] Falha em {marketplace}")
                summary["errors"].append(msg)
                summary_parts.append(f"{marketplace}=fail")
                any_failure = True

        # Atualiza state com base no resultado
        state = _get_state(db)
        state.last_run_at = datetime.utcnow()
        state.last_summary = " ".join(summary_parts)
        if any_failure and not any_success:
            state.consecutive_failures += 1
            state.last_error_msg = "; ".join(summary["errors"])[:500]
            if state.consecutive_failures >= 2:
                state.last_status = "failed_visible"
                summary["status"] = "failed_visible"
            else:
                state.last_status = "success"  # falha única não é "visible" ainda
                summary["status"] = "failed_single"
        else:
            # Pelo menos 1 marketplace OK (ou skip silencioso). Reset failures.
            state.consecutive_failures = 0
            state.last_error_msg = None
            if not summary["lists"]:
                state.last_status = "no_docs"
                summary["status"] = "no_docs"
            else:
                state.last_status = "success"
                summary["status"] = "success"
        db.commit()
        return summary
    except Exception as outer:
        log.exception(f"[AUTO_SEP] Falha geral: {outer}")
        try:
            state = _get_state(db)
            state.consecutive_failures += 1
            state.last_error_msg = str(outer)[:500]
            if state.consecutive_failures >= 2:
                state.last_status = "failed_visible"
            db.commit()
        except Exception:
            pass
        return {"status": "error", "error": str(outer)}
    finally:
        db.close()


def should_run_now() -> bool:
    """Retorna True se for hora de rodar o job:
    - Dia da semana = seg(0) a sex(4)
    - Horário (BR) entre 06:00 e 06:30 (janela de 30min)
    - Não considera idempotência aqui (essa parte é checada dentro de executar_job)

    Nota: 'horário BR' é assumido = America/Sao_Paulo (UTC-3, sem DST hoje).
    Como Railway roda em UTC, comparamos: BR 06:00 = UTC 09:00.
    """
    now_utc = datetime.utcnow()
    # BR = UTC - 3 (sem horário de verão atualmente)
    now_br = now_utc - timedelta(hours=3)

    # Seg = 0, Sex = 4
    if now_br.weekday() > 4:
        return False

    # Janela 06:00 - 06:30 BR
    if now_br.hour != 6:
        return False
    if now_br.minute >= 30:
        return False

    return True
