"""
# Agente de Teste — NVS
====================================
Substituto do agent.py para testar SEM impressora física.

Em vez de imprimir, salva cada ZPL recebido em:
  print-agent/test_output/label_YYYYMMDD_HHMMSS_NNN.txt

E exibe o conteúdo resumido no terminal.

Como usar:
    python agent_test.py

Depois, faça a bipagem normalmente no sistema.
Quando um item for concluído, o ZPL será salvo aqui e você pode
verificar se o conteúdo está correto antes de testar na impressora real.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from pathlib import Path
import json
import os
import sys

# Force UTF-8 output so Windows terminal does not choke on special chars
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AGENT_PORT = int(os.getenv("PRINT_AGENT_PORT", "6543"))
OUTPUT_DIR = Path(__file__).parent / "test_output"
OUTPUT_DIR.mkdir(exist_ok=True)

_counter = 0   # label counter per session


def save_zpl(zpl: str) -> Path:
    global _counter
    _counter += 1
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = OUTPUT_DIR / f"label_{ts}_{_counter:03d}.txt"
    filename.write_text(zpl, encoding="utf-8")
    return filename


def summarize_zpl(zpl: str) -> str:
    """Extract a few key fields from ZPL for quick visual check."""
    import re
    lines = []

    # Try to find SKU field
    sku_match = re.search(r"SKU[:\s]+([A-Z0-9_\-]+)", zpl, re.IGNORECASE)
    if sku_match:
        lines.append(f"  SKU        : {sku_match.group(1)}")

    # Count ^XA blocks (each = 1 label sheet)
    blocks = len(re.findall(r"\^XA", zpl, re.IGNORECASE))
    lines.append(f"  ^XA blocos : {blocks}")

    # ZPL size
    lines.append(f"  Tamanho    : {len(zpl):,} bytes")

    return "\n".join(lines) if lines else "  (ZPL sem campos reconhecíveis)"


class MockPrintHandler(BaseHTTPRequestHandler):

    def _send_json(self, code: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/status":
            self._send_json(200, {
                "status": "ok",
                "version": "TEST",
                "printer": "MODO TESTE — sem impressora física",
                "printer_found": True,   # trick frontend into thinking agent is ready
                "all_printers": ["MODO TESTE — salva em test_output/"],
            })
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/print":
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length))
            except json.JSONDecodeError:
                self._send_json(400, {"status": "error", "message": "JSON inválido"})
                return

            zpl = body.get("zpl", "").strip()
            if not zpl:
                self._send_json(400, {"status": "error", "message": "ZPL vazio"})
                return

            path = save_zpl(zpl)

            print()
            print("-" * 55)
            print(f"  [OK] ZPL recebido — {datetime.now().strftime('%H:%M:%S')}")
            print(summarize_zpl(zpl))
            print(f"  Arquivo    : {path.name}")
            print("-" * 55)

            self._send_json(200, {"status": "ok", "printer": "TEST (arquivo salvo)"})
        else:
            self._send_json(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        pass   # silencia logs HTTP repetitivos


if __name__ == "__main__":
    print("=" * 55)
    print("  [TESTE] Agente de Impressao — NVS")
    print("=" * 55)
    print(f"  URL         : http://localhost:{AGENT_PORT}")
    print(f"  Saida ZPL   : {OUTPUT_DIR}/")
    print()
    print("  Faca a bipagem no sistema.")
    print("  Cada ZPL recebido sera salvo em test_output/")
    print("  Pressione Ctrl+C para parar.")
    print("=" * 55)

    server = HTTPServer(("localhost", AGENT_PORT), MockPrintHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n  Agente encerrado. {_counter} etiqueta(s) salva(s) em {OUTPUT_DIR}/".encode("utf-8", errors="replace").decode())
        sys.exit(0)
