"""
Endpoint WebSocket para agentes Zebra locais.

Rota  : GET /ws/zebra-agent/{machine_id}  (upgrade para WebSocket)
Status: GET /api/zebra/agent-status        (lista máquinas conectadas)

Protocolo de mensagens (JSON):
─────────────────────────────────────────────────────────────────────
  Agente → Servidor  │  {"type":"hello","machine_id":"...","hostname":"...",
                     │   "printer":"...","all_printers":[...],"agent_version":"..."}
                     │
  Servidor → Agente  │  {"type":"connected","machine_id":"...","server_time":"..."}
                     │
  Servidor → Agente  │  {"type":"print_job","id":N,"sku":"...","zpl_content":"..."}
                     │
  Agente → Servidor  │  {"type":"print_result","job_id":N,
                     │   "status":"ok"|"error","printer":"...","message":"..."}
                     │
  Agente → Servidor  │  {"type":"ping"}
  Servidor → Agente  │  {"type":"pong"}
                     │
  Servidor → Agente  │  {"type":"fix_spooler"}      (comando remoto)
  Agente → Servidor  │  {"type":"fix_spooler_result","status":"ok"|"error",...}
                     │
  Servidor → Agente  │  {"type":"refresh_printer"}   (redetecta impressora)
  Agente → Servidor  │  {"type":"printer_info","printer":"...","all_printers":[...]}
─────────────────────────────────────────────────────────────────────
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from database import SessionLocal
from models import PickingItem, PrintJob
from services.zebra_connection import zebra_manager

log = logging.getLogger("zebra-ws")
router = APIRouter(tags=["zebra-ws"])


# ────────────────────────────────────────────────────────────────────────────
# WebSocket principal
# ────────────────────────────────────────────────────────────────────────────

@router.websocket("/ws/zebra-agent/{machine_id}")
async def zebra_agent_endpoint(websocket: WebSocket, machine_id: str) -> None:
    """
    Aceita a conexão do agente, registra no manager e entra no loop de
    mensagens. Desregistra ao desconectar.
    """
    await websocket.accept()
    zebra_manager.register(machine_id, websocket)

    try:
        while True:
            msg = await websocket.receive_json()
            await _dispatch(websocket, machine_id, msg)

    except WebSocketDisconnect:
        log.info(f"[WS] Agente desconectado (normal): {machine_id}")
    except Exception as exc:
        log.error(f"[WS] Erro na sessão '{machine_id}': {exc}")
    finally:
        zebra_manager.unregister(machine_id)


# ────────────────────────────────────────────────────────────────────────────
# Dispatcher de mensagens
# ────────────────────────────────────────────────────────────────────────────

async def _dispatch(ws: WebSocket, machine_id: str, msg: dict) -> None:
    msg_type = msg.get("type", "")

    if msg_type == "hello":
        log.info(
            f"[WS] Hello de '{machine_id}': "
            f"hostname={msg.get('hostname')} "
            f"printer={msg.get('printer')} "
            f"v={msg.get('agent_version')}"
        )
        await ws.send_json({
            "type":        "connected",
            "machine_id":  machine_id,
            "server_time": datetime.now(timezone.utc).isoformat(),
        })

    elif msg_type == "print_result":
        await _handle_print_result(msg)

    elif msg_type == "printer_info":
        log.info(
            f"[WS] Impressora de '{machine_id}': "
            f"{msg.get('printer')} | todas={msg.get('all_printers')}"
        )

    elif msg_type == "fix_spooler_result":
        status = msg.get("status", "?")
        log.info(f"[WS] fix_spooler resultado de '{machine_id}': {status} — {msg.get('message', '')}")

    elif msg_type == "ping":
        await ws.send_json({"type": "pong"})

    else:
        log.debug(f"[WS] Mensagem desconhecida de '{machine_id}': {msg_type}")


# ────────────────────────────────────────────────────────────────────────────
# Handler de resultado de impressão
# ────────────────────────────────────────────────────────────────────────────

async def _handle_print_result(msg: dict) -> None:
    """
    Recebe {"type":"print_result","job_id":N,"status":"ok"|"error",...}
    e atualiza o banco de dados (PrintJob + PickingItem.labels_printed).
    """
    job_id    = msg.get("job_id")
    ok        = msg.get("status") == "ok"
    printer   = msg.get("printer") or ""
    error_msg = msg.get("message") or ""

    if not job_id:
        log.warning(f"[WS] print_result sem job_id: {msg}")
        return

    db = SessionLocal()
    try:
        job: PrintJob | None = db.query(PrintJob).filter(PrintJob.id == job_id).first()
        if not job:
            log.warning(f"[WS] Job {job_id} não encontrado no DB")
            return

        if ok:
            job.status      = "PRINTED"
            job.printer_name = printer
            job.printed_at  = datetime.utcnow()

            # Marca PickingItem como impresso
            item: PickingItem | None = db.query(PickingItem).filter(
                PickingItem.session_id == job.session_id,
                PickingItem.sku        == job.sku,
            ).first()
            if item:
                item.labels_printed = True

            log.info(f"[WS] Job {job_id} → PRINTED via '{printer}'")
        else:
            job.status    = "ERROR"
            job.error_msg = error_msg
            log.error(f"[WS] Job {job_id} → ERROR: {error_msg}")

        db.commit()

    except Exception as exc:
        log.error(f"[WS] Erro ao atualizar job {job_id}: {exc}")
        db.rollback()
    finally:
        db.close()


# ────────────────────────────────────────────────────────────────────────────
# Endpoint REST: status dos agentes conectados
# ────────────────────────────────────────────────────────────────────────────

@router.get("/api/zebra/agent-status", tags=["zebra-ws"])
def agent_status():
    """
    Lista as máquinas com agente Zebra conectado no momento.
    Usado pelo frontend (Supervisor) para checar se há agente online.
    """
    machines = zebra_manager.connected_machines()
    return {
        "connected":   machines,
        "total":       len(machines),
        "has_agent":   bool(machines),
    }


@router.post("/api/zebra/fix-spooler", tags=["zebra-ws"])
async def fix_spooler_via_ws(machine_id: str | None = None):
    """
    Envia comando fix_spooler para o agente conectado via WebSocket.
    Retorna imediatamente — o resultado chega pelo canal WS (log do agente).
    """
    if machine_id and machine_id in zebra_manager._connections:
        targets = [(machine_id, zebra_manager._connections[machine_id])]
    else:
        targets = list(zebra_manager._connections.items())

    if not targets:
        from fastapi import HTTPException
        raise HTTPException(503, "Nenhum agente conectado.")

    mid, ws = targets[0]
    try:
        await ws.send_json({"type": "fix_spooler"})
        log.info(f"[WS] fix_spooler enviado para '{mid}'")
        return {"ok": True, "machine_id": mid}
    except Exception as exc:
        zebra_manager.unregister(mid)
        from fastapi import HTTPException
        raise HTTPException(503, f"Falha ao enviar comando: {exc}")
