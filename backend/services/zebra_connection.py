"""
ZebraConnectionManager — Singleton para conexões WebSocket dos agentes Zebra.

Importado por:
  routers/zebra_ws.py  → registra / desregistra conexões
  routers/print_jobs.py → push de jobs para agentes conectados
"""

import logging
from typing import Dict, Optional

from fastapi import WebSocket

log = logging.getLogger("zebra-ws")


class ZebraConnectionManager:
    """
    Mantém dict {machine_id → WebSocket} das conexões ativas.
    Thread-safe para asyncio (FastAPI roda em event loop único).
    """

    def __init__(self) -> None:
        self._connections: Dict[str, WebSocket] = {}

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    def register(self, machine_id: str, ws: WebSocket) -> None:
        if machine_id in self._connections:
            log.warning(f"[ZebraWS] Substituindo conexão existente: {machine_id}")
        self._connections[machine_id] = ws
        log.info(
            f"[ZebraWS] Agente registrado: {machine_id} "
            f"| total={len(self._connections)}"
        )

    def unregister(self, machine_id: str) -> None:
        self._connections.pop(machine_id, None)
        log.info(
            f"[ZebraWS] Agente desconectado: {machine_id} "
            f"| total={len(self._connections)}"
        )

    # ------------------------------------------------------------------
    # Push de jobs
    # ------------------------------------------------------------------

    async def push_job(
        self,
        payload: dict,
        machine_id: Optional[str] = None,
    ) -> bool:
        """
        Envia um job para o agente via WebSocket.

        - machine_id fornecido: tenta a máquina específica.
        - machine_id=None     : tenta qualquer agente disponível (primeiro).

        Retorna True se o envio foi bem-sucedido, False caso nenhum
        agente esteja conectado ou todos falharem.
        """
        if machine_id and machine_id in self._connections:
            targets = [(machine_id, self._connections[machine_id])]
        else:
            targets = list(self._connections.items())

        for mid, ws in targets:
            try:
                await ws.send_json({"type": "print_job", **payload})
                log.info(f"[ZebraWS] Job {payload.get('id')} → push para '{mid}'")
                return True
            except Exception as exc:
                log.warning(f"[ZebraWS] Falha ao push para '{mid}': {exc}")
                self.unregister(mid)

        return False

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def connected_machines(self) -> list[str]:
        return list(self._connections.keys())

    @property
    def has_connections(self) -> bool:
        return bool(self._connections)


# Singleton — importado diretamente pelos routers
zebra_manager = ZebraConnectionManager()
