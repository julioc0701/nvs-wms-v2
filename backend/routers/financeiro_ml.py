"""Rotas REST do Resumo Financeiro Mercado Livre.
Permissão: somente Master.
"""
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


# ============ Schemas ============

class FilterParams(BaseModel):
    data_inicio: date
    data_fim: date
    sku: str | None = None
    mlb: str | None = None
    status: Literal["aprovado", "cancelado", "todos"] = "todos"
    modalidade: Literal["premium", "classico", "gratis", "todos"] = "todos"
    tipo_frete: Literal["me1", "me2", "sem_me", "full", "flex", "outro", "todos"] = "todos"
    custo_imposto: Literal["sem_custo", "sem_imposto", "sem_custo_imposto", "todos"] = "todos"
    considerar_frete_comprador: bool = False
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)


class SkuPayload(BaseModel):
    custo_unit: Decimal
    imposto_pct: Decimal


# ============ Rotas ============

@router.get("/health")
async def health():
    """Verifica que o módulo está vivo e que ml_tokens tem token."""
    from database import SessionLocal
    from models import MLTokens
    with SessionLocal() as session:
        token = session.query(MLTokens).first()
        return {
            "ok": True,
            "ml_configured": token is not None,
            "user_id": token.user_id if token else None,
        }
