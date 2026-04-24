"""
Endpoint WebSocket para agentes Zebra locais.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from database import SessionLocal
from models import PickingItem, PrintJob
from services.zebra_connection import zebra_manager

log = logging.getLogger("zebra-ws")
router = APIRouter(tags=["zebra-ws"])


@router.websocket("/ws/zebra-agent/{machine_id}")
async def zebra_agent_endpoint(websocket: WebSocket, machine_id: str) -> None:
    await websocket.accept()
    zebra_manager.register(machine_id, websocket)

    try:
        while True:
            msg = await websocket.receive_json()
            await _dispatch(websocket, machine_id, msg)
    except WebSocketDisconnect:
        log.info("[WS] Agente desconectado: %s", machine_id)
    except Exception as exc:
        log.error("[WS] Erro na sessao '%s': %s", machine_id, exc)
    finally:
        zebra_manager.unregister(machine_id)


async def _dispatch(ws: WebSocket, machine_id: str, msg: dict) -> None:
    msg_type = msg.get("type", "")

    if msg_type == "hello":
        zebra_manager.update_meta(machine_id, msg)
        log.info(
            "[WS] Hello de '%s': hostname=%s printer=%s v=%s",
            machine_id,
            msg.get("hostname"),
            msg.get("printer"),
            msg.get("agent_version"),
        )
        await ws.send_json({
            "type": "connected",
            "machine_id": machine_id,
            "server_time": datetime.now(timezone.utc).isoformat(),
        })

    elif msg_type == "print_result":
        await _handle_print_result(machine_id, msg)
        zebra_manager.release_job(machine_id, msg.get("job_id"))

    elif msg_type == "printer_info":
        zebra_manager.update_meta(machine_id, msg)
        log.info("[WS] Impressora de '%s': %s", machine_id, msg.get("printer"))

    elif msg_type == "fix_spooler_result":
        zebra_manager.touch(machine_id)
        log.info(
            "[WS] fix_spooler resultado de '%s': %s - %s",
            machine_id,
            msg.get("status", "?"),
            msg.get("message", ""),
        )

    elif msg_type == "ping":
        zebra_manager.touch(machine_id)
        await ws.send_json({"type": "pong"})

    else:
        log.debug("[WS] Mensagem desconhecida de '%s': %s", machine_id, msg_type)


async def _handle_print_result(machine_id: str, msg: dict) -> None:
    job_id = msg.get("job_id")
    ok = msg.get("status") == "ok"
    printer = msg.get("printer") or ""
    error_msg = msg.get("message") or ""
    job_token = msg.get("job_token")
    agent_version = msg.get("agent_version") or ""

    if not job_id:
        log.warning("[WS] print_result sem job_id: %s", msg)
        return

    db = SessionLocal()
    try:
        job: PrintJob | None = db.query(PrintJob).filter(PrintJob.id == job_id).first()
        if not job:
            log.warning("[WS] Job %s nao encontrado no DB", job_id)
            return

        if job.claimed_by and job.claimed_by != machine_id:
            log.warning(
                "[WS] Resultado ignorado: job %s pertence a '%s', mas veio de '%s'",
                job_id,
                job.claimed_by,
                machine_id,
            )
            return

        if job.job_token and job_token != job.job_token:
            log.warning("[WS] Resultado ignorado: token invalido para job %s", job_id)
            return

        job.agent_version = agent_version or job.agent_version
        if ok:
            job.status = "PRINTED"
            job.printer_name = printer
            job.printed_at = datetime.utcnow()
            job.error_msg = None

            item: PickingItem | None = db.query(PickingItem).filter(
                PickingItem.session_id == job.session_id,
                PickingItem.sku == job.sku,
            ).first()
            if item:
                item.labels_printed = True

            log.info("[WS] Job %s -> PRINTED via '%s' em '%s'", job_id, printer, machine_id)
        else:
            job.status = "ERROR"
            job.error_msg = error_msg
            log.error("[WS] Job %s -> ERROR em '%s': %s", job_id, machine_id, error_msg)

        db.commit()
    except Exception as exc:
        log.error("[WS] Erro ao atualizar job %s: %s", job_id, exc)
        db.rollback()
    finally:
        db.close()


@router.get("/api/zebra/agent-status", tags=["zebra-ws"])
def agent_status():
    machines = zebra_manager.connected_machines()
    return {
        "connected": machines,
        "machines": zebra_manager.status_snapshot(),
        "total": len(machines),
        "has_agent": bool(machines),
    }


@router.post("/api/zebra/fix-spooler", tags=["zebra-ws"])
async def fix_spooler_via_ws(machine_id: str | None = None):
    if machine_id:
        conn = zebra_manager._connections.get(machine_id)
        targets = [(machine_id, conn.ws)] if conn and not conn.busy else []
    else:
        targets = [
            (mid, conn.ws)
            for mid, conn in zebra_manager._connections.items()
            if not conn.busy
        ]

    if not targets:
        raise HTTPException(503, "Nenhum agente livre para limpar spooler.")

    mid, ws = targets[0]
    try:
        await ws.send_json({"type": "fix_spooler"})
        log.info("[WS] fix_spooler enviado para '%s'", mid)
        return {"ok": True, "machine_id": mid}
    except Exception as exc:
        zebra_manager.unregister(mid)
        raise HTTPException(503, f"Falha ao enviar comando: {exc}") from exc
