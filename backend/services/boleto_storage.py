"""Persistência de fotos de boletos no disco (volume Railway /data ou local)."""
import base64
import os
from database import DATABASE_URL


def _boletos_dir() -> str:
    """Retorna o diretório onde as fotos de boletos vivem.

    Em produção (DATABASE_URL contém /data/) usa /data/boletos. Em dev, usa ./data/boletos
    relativo ao diretório do backend. Garante criação do diretório.
    """
    if "/data/" in DATABASE_URL:
        base = "/data/boletos"
    else:
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "boletos"))
    os.makedirs(base, exist_ok=True)
    return base


def salvar_foto_base64(boleto_id: int, foto_b64: str) -> str:
    """Decodifica base64 e salva como JPG. Retorna o NOME do arquivo (não o path inteiro)."""
    if foto_b64.startswith("data:"):
        foto_b64 = foto_b64.split(",", 1)[1]
    raw = base64.b64decode(foto_b64)
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError(f"Foto excede limite de 4MB pós-base64 ({len(raw)} bytes)")
    nome = f"{boleto_id}.jpg"
    caminho = os.path.join(_boletos_dir(), nome)
    with open(caminho, "wb") as f:
        f.write(raw)
    return nome


def caminho_foto(nome_arquivo: str) -> str | None:
    """Retorna caminho absoluto da foto se existir, ou None."""
    caminho = os.path.join(_boletos_dir(), nome_arquivo)
    return caminho if os.path.exists(caminho) else None


def excluir_foto(nome_arquivo: str) -> None:
    """Remove a foto do disco. Silencioso se não existir."""
    caminho = os.path.join(_boletos_dir(), nome_arquivo)
    if os.path.exists(caminho):
        os.remove(caminho)
