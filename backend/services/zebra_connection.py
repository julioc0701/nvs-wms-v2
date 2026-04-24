"""
Gerenciador de conexoes WebSocket dos agentes Zebra.

Ele mantem ownership em memoria para evitar que um agente receba dois jobs
simultaneos e para permitir auditoria de qual maquina recebeu cada push.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

from fastapi import WebSocket

log = logging.getLogger("zebra-ws")


@dataclass
class ZebraConnection:
    ws: WebSocket
    last_seen_at: datetime
    hostname: str | None = None
    printer: str | None = None
    agent_version: str | None = None
    busy: bool = False
    current_job_id: int | None = None


class ZebraConnectionManager:
    def __init__(self) -> None:
        self._connections: Dict[str, ZebraConnection] = {}
        self._lock = asyncio.Lock()

    def register(self, machine_id: str, ws: WebSocket) -> None:
        if machine_id in self._connections:
            log.warning("[ZebraWS] Substituindo conexao existente: %s", machine_id)
        self._connections[machine_id] = ZebraConnection(
            ws=ws,
            last_seen_at=datetime.utcnow(),
        )
        log.info("[ZebraWS] Agente registrado: %s | total=%s", machine_id, len(self._connections))

    def unregister(self, machine_id: str) -> None:
        self._connections.pop(machine_id, None)
        log.info("[ZebraWS] Agente desconectado: %s | total=%s", machine_id, len(self._connections))

    def update_meta(self, machine_id: str, payload: dict) -> None:
        conn = self._connections.get(machine_id)
        if not conn:
            return
        conn.hostname = payload.get("hostname") or conn.hostname
        conn.printer = payload.get("printer") or conn.printer
        conn.agent_version = payload.get("agent_version") or conn.agent_version
        conn.last_seen_at = datetime.utcnow()

    def touch(self, machine_id: str) -> None:
        conn = self._connections.get(machine_id)
        if conn:
            conn.last_seen_at = datetime.utcnow()

    def release_job(self, machine_id: str, job_id: int | None = None) -> None:
        conn = self._connections.get(machine_id)
        if not conn:
            return
        if job_id is None or conn.current_job_id == job_id or str(conn.current_job_id) == str(job_id):
            conn.busy = False
            conn.current_job_id = None
            conn.last_seen_at = datetime.utcnow()

    async def push_job(self, payload: dict, machine_id: Optional[str] = None) -> str | None:
        async with self._lock:
            if machine_id:
                conn = self._connections.get(machine_id)
                targets = [(machine_id, conn)] if conn else []
            else:
                targets = list(self._connections.items())

            for mid, conn in targets:
                if not conn or conn.busy:
                    continue
                try:
                    conn.busy = True
                    conn.current_job_id = payload.get("id")
                    conn.last_seen_at = datetime.utcnow()
                    await conn.ws.send_json({"type": "print_job", **payload})
                    log.info("[ZebraWS] Job %s -> push para '%s'", payload.get("id"), mid)
                    return mid
                except Exception as exc:
                    log.warning("[ZebraWS] Falha ao push para '%s': %s", mid, exc)
                    self.unregister(mid)

            return None

    def connected_machines(self) -> list[str]:
        return list(self._connections.keys())

    def status_snapshot(self) -> list[dict]:
        return [
            {
                "machine_id": machine_id,
                "hostname": conn.hostname,
                "printer": conn.printer,
                "agent_version": conn.agent_version,
                "busy": conn.busy,
                "current_job_id": conn.current_job_id,
                "last_seen_at": conn.last_seen_at.isoformat() if conn.last_seen_at else None,
            }
            for machine_id, conn in self._connections.items()
        ]

    @property
    def has_connections(self) -> bool:
        return bool(self._connections)


zebra_manager = ZebraConnectionManager()
