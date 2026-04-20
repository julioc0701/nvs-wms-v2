import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "app.log")

fmt = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
file_handler.setFormatter(fmt)

console_handler = logging.StreamHandler()
console_handler.setFormatter(fmt)

root = logging.getLogger()
root.setLevel(logging.INFO)

# Evita duplicar handlers se o módulo for reimportado (uvicorn reload)
if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
    root.addHandler(file_handler)
if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler) for h in root.handlers):
    root.addHandler(console_handler)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
