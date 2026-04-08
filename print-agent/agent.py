"""
# Agente Local de Impressão Zebra — NVS v2.0
====================================================
Este script atua como um servidor HTTP local para receber ZPL e enviar para a Zebra via USB.
Também realiza polling de jobs pendentes no backend (Railway).

Versão 2.0: Resiliência Industrial
- Gerenciamento de Spooler com AbortDocPrinter em caso de erro.
- Conexão persistente por lote de etiquetas (abre/fecha porta uma única vez).
- Lock com timeout para evitar deadlocks permanentes.
- Separação inteligente de blocos ZPL (Regex ^XA...^XZ).
- Logging profissional e tratamento robusto de erros de rede.
"""

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
import time
import urllib.request
import urllib.error

# Configuração de Logging
logging.basicConfig(
    level=logging.INFO,
    format="  %(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("zebra-agent")

# Constantes e Configurações
AGENT_VERSION   = "2.0"
AGENT_PORT      = int(os.getenv("PRINT_AGENT_PORT", "9100"))
PRINTER_NAME    = os.getenv("PRINTER_NAME", "")   # vazio = auto-deteccao
ENABLE_POLLING  = os.getenv("ENABLE_POLLING", "0").strip() == "1"
BACKEND_URL     = os.getenv("BACKEND_URL", "http://localhost:8001/api").strip()
POLL_INTERVAL   = int(os.getenv("POLL_INTERVAL", "5"))

PRINTER_LOCK         = threading.Lock()
PRINTER_LOCK_TIMEOUT = 30  # segundos

def _load_allowed_origins() -> set[str]:
    raw = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5174,http://localhost:5175,http://127.0.0.1:5174,http://127.0.0.1:5175",
    )
    return {origin.strip() for origin in raw.split(",") if origin.strip()}


ALLOWED_ORIGINS = _load_allowed_origins()

from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

# ---------------------------------------------------------------------------
# Cache e Detecção de Impressoras
# ---------------------------------------------------------------------------
_cached_printer: str | None = None
_cached_all_printers: list[str] = []

def _detect_printers() -> tuple[str | None, list[str]]:
    if platform.system() != "Windows":
        return None, []
    try:
        import win32print
        raw = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
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

# ---------------------------------------------------------------------------
# Gestão de Porta e Processo
# ---------------------------------------------------------------------------
def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0

def _is_our_agent(port: int) -> bool:
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/status")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            return data.get("agent") == "warehouse-picker-zebra"
    except Exception:
        return False

def _kill_process_on_port(port: int) -> bool:
    try:
        result = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, timeout=8)
        pattern = re.compile(rf"[\s:]0*{port}\s.*?LISTENING\s+(\d+)", re.IGNORECASE)
        for line in result.stdout.splitlines():
            m = pattern.search(line)
            if m:
                pid = m.group(1)
                if pid != "0":
                    subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True, timeout=5)
                    time.sleep(1)
                    return not _port_in_use(port)
    except Exception:
        pass
    return False

def _check_startup_port() -> None:
    if not _port_in_use(AGENT_PORT):
        return
    if _is_our_agent(AGENT_PORT):
        print(f"\n  [INFO] O agente ja esta rodando na porta {AGENT_PORT}.\n")
        sys.exit(0)
    print(f"\n  [!] Porta {AGENT_PORT} ocupada. Tentando liberar...\n")
    if not _kill_process_on_port(AGENT_PORT):
        print(f"  ERRO: Nao foi possivel liberar a porta {AGENT_PORT}.")
        sys.exit(1)

# ---------------------------------------------------------------------------
# Lógica de Envio ZPL (Refatorada v2.0)
# ---------------------------------------------------------------------------
def _split_zpl(zpl: str) -> list[bytes]:
    """Extrai blocos ^XA...^XZ completos do ZPL (case-insensitive)."""
    blocks = re.findall(r"(\^XA.*?\^XZ)", zpl, re.IGNORECASE | re.DOTALL)
    if blocks:
        return [b.encode("utf-8") for b in blocks]
    stripped = zpl.strip()
    return [stripped.encode("utf-8")] if stripped else []

def _send_via_win32print(blocks: list[bytes], printer_name: str) -> str:
    import win32print
    hp = win32print.OpenPrinter(printer_name)
    try:
        for i, zpl_bytes in enumerate(blocks):
            doc_started = False
            try:
                win32print.StartDocPrinter(hp, 1, (f"Etiqueta {i+1}", None, "RAW"))
                doc_started = True
                win32print.StartPagePrinter(hp)
                written = win32print.WritePrinter(hp, zpl_bytes)
                if written != len(zpl_bytes):
                    raise RuntimeError(f"Erro no Spooler: escreveu {written}/{len(zpl_bytes)} bytes")
                win32print.EndPagePrinter(hp)
                win32print.EndDocPrinter(hp)
                doc_started = False
            except Exception:
                if doc_started:
                    try: win32print.AbortDocPrinter(hp)
                    except: pass
                raise
            if len(blocks) > 1 and i < len(blocks) - 1:
                time.sleep(0.05)
        return "win32print"
    finally:
        win32print.ClosePrinter(hp)

def _send_via_copy(blocks: list[bytes], printer_name: str) -> str:
    unc = f"\\\\localhost\\{printer_name}"
    for i, zpl_bytes in enumerate(blocks):
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".zpl", delete=False) as tmp:
            tmp.write(zpl_bytes)
            tmp_path = tmp.name
        try:
            res = subprocess.run(["cmd", "/c", "copy", "/B", tmp_path, unc], capture_output=True, text=True, timeout=15)
            if res.returncode != 0:
                raise RuntimeError(f"Falha copy /B: {res.stderr or res.stdout}")
        finally:
            if os.path.exists(tmp_path): os.unlink(tmp_path)
        if len(blocks) > 1 and i < len(blocks) - 1:
            time.sleep(0.05)
    return "copy/B"

def do_print(zpl: str, printer_name: str | None = None) -> dict:
    name = printer_name or _cached_printer
    if not name:
        refresh_printer_cache()
        name = _cached_printer
    if not name:
        return {"status": "error", "message": "Zebra nao encontrada."}

    # Lock com Timeout para evitar travamentos infinitos
    if not PRINTER_LOCK.acquire(timeout=PRINTER_LOCK_TIMEOUT):
        return {"status": "error", "message": f"Impressora ocupada (timeout {PRINTER_LOCK_TIMEOUT}s)."}

    try:
        blocks = _split_zpl(zpl)
        if not blocks:
            return {"status": "error", "message": "ZPL vazio ou invalido."}

        log.info(f"Enviando {len(blocks)} etiquetas para '{name}'...")
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
    
    log.info("Iniciando limpeza forçada do spooler (solicitado via API)...")
    try:
        # 1. Para spooler (forçado)
        subprocess.run(["net", "stop", "spooler", "/y"], capture_output=True, timeout=15)
        subprocess.run(["taskkill", "/F", "/IM", "spoolsv.exe", "/T"], capture_output=True, timeout=10)
        
        # 2. Limpa arquivos temporários
        spool_path = os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32', 'Spool', 'Printers')
        if os.path.exists(spool_path):
            import shutil
            for filename in os.listdir(spool_path):
                file_path = os.path.join(spool_path, filename)
                try:
                    if os.path.isfile(file_path): os.unlink(file_path)
                    elif os.path.isdir(file_path): shutil.rmtree(file_path)
                except Exception as e:
                    log.warning(f"Nao foi possivel deletar {filename}: {e}")
        
        # 3. Reinicia o serviço
        subprocess.run(["net", "start", "spooler"], capture_output=True, timeout=15)
        
        # 4. Tenta colocar impressoras ONLINE via PowerShell
        ps_cmd = "Get-Printer | Where-Object {$_.JobCount -gt 0 -or $_.PrinterStatus -eq 'Offline'} | Set-Printer -IsOffline $false"
        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, timeout=15)
        
        refresh_printer_cache()
        log.info("Limpeza do spooler concluída com sucesso.")
        return {"status": "ok", "message": "Spooler reiniciado e fila limpa com sucesso."}
    except Exception as e:
        log.error(f"Erro ao limpar spooler: {e}")
        return {"status": "error", "message": str(e)}

# ---------------------------------------------------------------------------
# Servidor HTTP
# ---------------------------------------------------------------------------
class PrintHandler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        try: self.wfile.write(body)
        except: pass

    def _cors_headers(self):
        origin = self.headers.get("Origin", "")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path == "/status":
            self._send_json(200, {"status": "ok", "agent": "warehouse-picker-zebra", "version": AGENT_VERSION, "printer": _cached_printer})
        elif self.path == "/refresh":
            refresh_printer_cache()
            self._send_json(200, {"status": "ok", "printer": _cached_printer})
        elif self.path == "/fix-spooler":
            res = fix_spooler()
            self._send_json(200 if res["status"] == "ok" else 500, res)
        elif self.path == "/health":
            self._send_json(200, {"status": "ok", "version": AGENT_VERSION})
        elif self.path == "/test":
            res = do_print("^XA^FO50,50^A0N,50,50^FDTeste NVS v2.0^FS^XZ")
            self._send_json(200 if res["status"] == "ok" else 500, res)
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/print":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            zpl = raw.decode("utf-8", errors="replace").strip()
            if "application/json" in self.headers.get("Content-Type", ""):
                try: zpl = json.loads(raw).get("zpl", "").strip()
                except: pass
            if not zpl:
                self._send_json(400, {"status": "error", "message": "ZPL vazio"})
                return
            res = do_print(zpl)
            self._send_json(200 if res["status"] == "ok" else 500, res)
        else:
            self._send_json(404, {"error": "not found"})

    def log_message(self, fmt, *args): pass

# ---------------------------------------------------------------------------
# Polling Loop e Backend
# ---------------------------------------------------------------------------
def _backend_request(method: str, path: str, body: dict | None = None):
    url = f"{BACKEND_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))

def _safe_patch(job_id: int, body: dict):
    try: _backend_request("PATCH", f"/print-jobs/{job_id}", body)
    except Exception as e: log.warning(f"Nao foi possivel atualizar status do job {job_id}: {e}")

def _process_job(job: dict):
    job_id = job["id"]
    sku = job.get("sku", "?")
    try:
        # Reserva
        _backend_request("PATCH", f"/print-jobs/{job_id}", {"status": "PRINTING"})
        # Download
        full_job = _backend_request("GET", f"/print-jobs/{job_id}")
        zpl = full_job.get("zpl_content", "")
        if not zpl:
            _safe_patch(job_id, {"status": "ERROR", "error_msg": "ZPL vazio"})
            return
        
        log.info(f"JOB {job_id} [{sku}] — Iniciando impressao...")
        res = do_print(zpl)
        
        if res["status"] == "ok":
            _safe_patch(job_id, {"status": "PRINTED", "printer_name": res.get("printer")})
            log.info(f"JOB {job_id} — OK")
        else:
            _safe_patch(job_id, {"status": "ERROR", "error_msg": res.get("message")})
    except urllib.error.HTTPError as e:
        if e.code != 400: log.error(f"Erro HTTP no Job {job_id}: {e}")
    except Exception as e:
        log.error(f"Erro ao processar Job {job_id}: {e}")
        _safe_patch(job_id, {"status": "PENDING", "error_msg": "Falha no download/processamento"})

def _polling_loop():
    log.info(f"Polling ativo ({POLL_INTERVAL}s) -> {BACKEND_URL}")
    while True:
        try:
            jobs = _backend_request("GET", "/print-jobs/pending")
            for job in jobs: _process_job(job)
        except Exception as e:
            log.debug(f"Falha de polling: {e}")
            time.sleep(10)
        time.sleep(POLL_INTERVAL)

# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print(f"  Agente Zebra NVS v{AGENT_VERSION} — Industrial Edition")
    print("=" * 60)
    _check_startup_port()
    refresh_printer_cache()
    log.info(f"Impressora: {_cached_printer or '[!] NAO DETECTADA'}")
    
    if ENABLE_POLLING:
        threading.Thread(target=_polling_loop, daemon=True).start()

    server = ThreadingHTTPServer(("127.0.0.1", AGENT_PORT), PrintHandler)
    try: server.serve_forever()
    except: sys.exit(0)
