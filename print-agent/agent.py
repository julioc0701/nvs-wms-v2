"""
Agente Local de Impressão Zebra — NVS v3.0 (WebSocket)
=======================================================
Conecta ao backend Railway via WebSocket OUTBOUND.
Recebe print jobs por push, imprime, confirma resultado pelo mesmo canal.

Sem HTTP server local. Sem polling REST.

Protocolo de mensagens (JSON):
  → hello          : identifica a máquina ao conectar
  ← connected      : ACK do servidor
  ← print_job      : job a imprimir {"id":N,"sku":"...","zpl_content":"..."}
  → print_result   : resultado {"job_id":N,"status":"ok"|"error","printer":"...","message":"..."}
  → ping / ← pong  : heartbeat a cada 30s
  ← fix_spooler    : comando remoto para limpar fila Windows
  → fix_spooler_result
  ← refresh_printer: redetecta impressora
  → printer_info
"""

import asyncio
import json
import logging
import os
import platform
import re
import socket
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor

try:
    import websockets
    import websockets.exceptions
except ImportError:
    print("\n  [ERRO] Dependência 'websockets' não encontrada.")
    print("  Execute:  pip install websockets>=12.0\n")
    sys.exit(1)

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="  %(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("zebra-agent")

# ── Configuração ───────────────────────────────────────────────────────────
AGENT_VERSION  = "3.0"
PRINTER_NAME   = os.getenv("PRINTER_NAME", "")
MACHINE_ID     = os.getenv("MACHINE_ID", socket.gethostname())
BACKEND_URL    = os.getenv("BACKEND_URL", "http://localhost:8003/api").strip()
RECONNECT_BASE = float(os.getenv("RECONNECT_BASE", "1"))   # segundos
RECONNECT_MAX  = float(os.getenv("RECONNECT_MAX", "60"))   # teto do backoff


def _build_ws_url(backend_url: str, machine_id: str) -> str:
    """
    Deriva a URL WebSocket a partir de BACKEND_URL.
    http://localhost:8003/api  →  ws://localhost:8003/ws/zebra-agent/MAQUINA_1
    https://app.railway.app/api → wss://app.railway.app/ws/zebra-agent/MAQUINA_1
    """
    base = re.sub(r"/api/?$", "", backend_url.rstrip("/"))
    ws_base = base.replace("https://", "wss://").replace("http://", "ws://")
    return f"{ws_base}/ws/zebra-agent/{machine_id}"


# BACKEND_WS_URL substitui o auto-derivado se definido explicitamente no env
WS_URL = os.getenv("BACKEND_WS_URL") or _build_ws_url(BACKEND_URL, MACHINE_ID)

PRINTER_LOCK         = threading.Lock()
PRINTER_LOCK_TIMEOUT = 30  # segundos

# ThreadPoolExecutor dedicado para operações de impressão bloqueantes (win32print)
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="zebra-print")

# ── Cache de Impressoras ───────────────────────────────────────────────────
_cached_printer: str | None = None
_cached_all_printers: list[str] = []


def _detect_printers() -> tuple[str | None, list[str]]:
    if platform.system() != "Windows":
        return None, []
    try:
        import win32print
        raw = win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        )
        all_names = [entry[2] for entry in raw if entry[2]]
    except Exception:
        all_names = []

    zebra = PRINTER_NAME or None
    if not zebra:
        for name in all_names:
            if re.search(r"Zebra|ZD|ZDesigner", name, re.IGNORECASE):
                zebra = name
                break
    return zebra, all_names


def refresh_printer_cache() -> None:
    global _cached_printer, _cached_all_printers
    _cached_printer, _cached_all_printers = _detect_printers()


# ── Envio ZPL (inalterado da v2.0) ────────────────────────────────────────

def _split_zpl(zpl: str) -> list[bytes]:
    """Extrai blocos ^XA...^XZ completos do ZPL (case-insensitive)."""
    blocks = re.findall(r"(\^XA.*?\^XZ)", zpl, re.IGNORECASE | re.DOTALL)
    if blocks:
        return [b.encode("utf-8") for b in blocks]
    stripped = zpl.strip()
    return [stripped.encode("utf-8")] if stripped else []


def _send_via_win32print(blocks: list[bytes], printer_name: str) -> str:
    import win32print
    payload = b"\n".join(blocks)
    hp = win32print.OpenPrinter(printer_name)
    doc_started = False
    try:
        win32print.StartDocPrinter(hp, 1, ("NVS-WMS PrintJob", None, "RAW"))
        doc_started = True
        win32print.StartPagePrinter(hp)
        written = win32print.WritePrinter(hp, payload)
        if written != len(payload):
            raise RuntimeError(
                f"Erro no Spooler: escreveu {written}/{len(payload)} bytes"
            )
        win32print.EndPagePrinter(hp)
        win32print.EndDocPrinter(hp)
        doc_started = False
        return "win32print"
    except Exception:
        if doc_started:
            try:
                win32print.AbortDocPrinter(hp)
            except Exception:
                pass
        raise
    finally:
        win32print.ClosePrinter(hp)


def _send_via_copy(blocks: list[bytes], printer_name: str) -> str:
    unc = f"\\\\localhost\\{printer_name}"
    payload = b"\n".join(blocks)
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".zpl", delete=False) as tmp:
        tmp.write(payload)
        tmp_path = tmp.name
    try:
        res = subprocess.run(
            ["cmd", "/c", "copy", "/B", tmp_path, unc],
            capture_output=True, text=True, timeout=30,
        )
        if res.returncode != 0:
            raise RuntimeError(f"Falha copy /B: {res.stderr or res.stdout}")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
    return "copy/B"


def do_print(zpl: str, printer_name: str | None = None) -> dict:
    name = printer_name or _cached_printer
    if not name:
        refresh_printer_cache()
        name = _cached_printer
    if not name:
        return {"status": "error", "message": "Zebra nao encontrada."}

    if not PRINTER_LOCK.acquire(timeout=PRINTER_LOCK_TIMEOUT):
        return {"status": "error", "message": f"Impressora ocupada (timeout {PRINTER_LOCK_TIMEOUT}s)."}

    try:
        blocks = _split_zpl(zpl)
        if not blocks:
            return {"status": "error", "message": "ZPL vazio ou invalido."}

        log.info(f"  Enviando {len(blocks)} etiqueta(s) para '{name}'...")
        try:
            method = _send_via_win32print(blocks, name)
        except (ImportError, Exception):
            method = _send_via_copy(blocks, name)

        return {"status": "ok", "printer": name, "method": method, "count": len(blocks)}
    except Exception as e:
        log.error(f"Falha na impressao: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        PRINTER_LOCK.release()


def fix_spooler() -> dict:
    if platform.system() != "Windows":
        return {"status": "error", "message": "Apenas Windows suportado."}

    log.info("Iniciando limpeza forçada do spooler (solicitado via servidor)...")
    try:
        subprocess.run(["net", "stop", "spooler", "/y"], capture_output=True, timeout=15)
        subprocess.run(
            ["taskkill", "/F", "/IM", "spoolsv.exe", "/T"], capture_output=True, timeout=10
        )
        spool_path = os.path.join(
            os.environ.get("SystemRoot", "C:\\Windows"), "System32", "Spool", "Printers"
        )
        if os.path.exists(spool_path):
            import shutil
            for filename in os.listdir(spool_path):
                file_path = os.path.join(spool_path, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    log.warning(f"Nao foi possivel deletar {filename}: {e}")

        subprocess.run(["net", "start", "spooler"], capture_output=True, timeout=15)
        ps_cmd = (
            "Get-Printer | Where-Object {$_.JobCount -gt 0 -or $_.PrinterStatus -eq 'Offline'}"
            " | Set-Printer -IsOffline $false"
        )
        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, timeout=15)

        refresh_printer_cache()
        log.info("Limpeza do spooler concluída com sucesso.")
        return {"status": "ok", "message": "Spooler reiniciado e fila limpa com sucesso."}
    except Exception as e:
        log.error(f"Erro ao limpar spooler: {e}")
        return {"status": "error", "message": str(e)}


# ── WebSocket Client ───────────────────────────────────────────────────────

async def _do_print_async(zpl: str) -> dict:
    """Executa do_print() na thread pool para não bloquear o event loop asyncio."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, do_print, zpl)


async def _do_fix_spooler_async() -> dict:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, fix_spooler)


async def _heartbeat(ws) -> None:
    """Envia ping JSON a cada 30s para manter a conexão Railway viva."""
    while True:
        await asyncio.sleep(30)
        try:
            await ws.send(json.dumps({"type": "ping"}))
        except Exception:
            return  # conexão já caiu — encerra task


async def _handle_message(ws, raw: str) -> None:
    try:
        msg = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        log.warning(f"Mensagem inválida recebida: {str(raw)[:80]}")
        return

    msg_type = msg.get("type", "")

    if msg_type == "connected":
        log.info("Servidor confirmou conexão. Aguardando jobs...")

    elif msg_type == "print_job":
        job_id = msg.get("id") or msg.get("job_id")
        sku    = msg.get("sku", "?")
        zpl    = msg.get("zpl_content", "")
        job_token = msg.get("job_token")

        log.info(f"JOB {job_id} [{sku}] recebido → imprimindo...")
        result = await _do_print_async(zpl)

        await ws.send(json.dumps({
            "type":    "print_result",
            "job_id":  job_id,
            "job_token": job_token,
            "status":  result["status"],
            "printer": result.get("printer", _cached_printer or ""),
            "message": result.get("message", ""),
            "agent_version": AGENT_VERSION,
        }))

        if result["status"] == "ok":
            log.info(
                f"JOB {job_id} [{sku}] → OK  "
                f"({result.get('count', 1)} etiqueta(s) via {result.get('method', '?')})"
            )
        else:
            log.error(f"JOB {job_id} [{sku}] → ERRO: {result.get('message')}")

    elif msg_type == "fix_spooler":
        log.info("Comando fix_spooler recebido do servidor...")
        result = await _do_fix_spooler_async()
        await ws.send(json.dumps({"type": "fix_spooler_result", **result}))

    elif msg_type == "refresh_printer":
        refresh_printer_cache()
        log.info(f"Cache de impressora atualizado: {_cached_printer or 'NENHUMA'}")
        await ws.send(json.dumps({
            "type":         "printer_info",
            "printer":      _cached_printer,
            "all_printers": _cached_all_printers,
        }))

    elif msg_type == "pong":
        pass  # heartbeat reply — sem ação

    else:
        log.debug(f"Mensagem desconhecida: {msg_type}")


async def _run_session(ws) -> None:
    """
    Gerencia uma sessão WebSocket completa:
    1. Envia hello com identificação da máquina.
    2. Inicia heartbeat em background.
    3. Loop de mensagens até desconexão.
    """
    await ws.send(json.dumps({
        "type":          "hello",
        "machine_id":    MACHINE_ID,
        "hostname":      socket.gethostname(),
        "printer":       _cached_printer or "NENHUMA",
        "all_printers":  _cached_all_printers,
        "agent_version": AGENT_VERSION,
    }))

    heartbeat_task = asyncio.create_task(_heartbeat(ws))
    try:
        async for raw in ws:
            await _handle_message(ws, raw)
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass


async def agent_main() -> None:
    """Loop principal com reconexão automática e backoff exponencial."""
    delay = RECONNECT_BASE
    log.info(f"Agente iniciando | Machine: {MACHINE_ID} | WS: {WS_URL}")

    while True:
        try:
            async with websockets.connect(
                WS_URL,
                ping_interval=None,  # heartbeat próprio via ping JSON
                close_timeout=5,
                open_timeout=15,
            ) as ws:
                log.info("Conectado ao backend.")
                delay = RECONNECT_BASE  # reset backoff ao conectar com sucesso
                await _run_session(ws)

        except websockets.exceptions.ConnectionClosedOK:
            log.info("Conexão encerrada pelo servidor. Reconectando...")

        except websockets.exceptions.ConnectionClosedError as exc:
            log.warning(f"Conexão fechada com erro (code={exc.code}). Reconectando em {delay:.0f}s...")

        except (OSError, ConnectionRefusedError) as exc:
            log.warning(f"Backend indisponível: {exc}. Tentando em {delay:.0f}s...")

        except Exception as exc:
            log.error(f"Erro inesperado [{type(exc).__name__}]: {exc}. Tentando em {delay:.0f}s...")

        await asyncio.sleep(delay)
        delay = min(delay * 2, RECONNECT_MAX)


# ── Startup ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print(f"  Agente Zebra NVS v{AGENT_VERSION} — WebSocket Edition")
    print(f"  Machine ID  : {MACHINE_ID}")
    print(f"  Backend WS  : {WS_URL}")
    print("=" * 60)

    refresh_printer_cache()
    log.info(f"Impressora: {_cached_printer or '[!] NAO DETECTADA'}")

    try:
        asyncio.run(agent_main())
    except KeyboardInterrupt:
        print("\n  Agente encerrado.")
        _executor.shutdown(wait=False)
        sys.exit(0)
