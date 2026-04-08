"""
Barcode master data management.
Allows importing EAN→SKU mapping from an Excel file, and CRUD via API.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel
from typing import Optional, List
from database import get_db
from models import Barcode, PickingItem
from io import BytesIO
import openpyxl

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────

class CreateProductBody(BaseModel):
    sku: str
    description: Optional[str] = None
    barcodes: List[str] = []

class UpdateProductBody(BaseModel):
    description: Optional[str] = None

class AddBarcodeBody(BaseModel):
    barcode: str


# ── Import ────────────────────────────────────────────────────────────────────

@router.post("/import-excel", status_code=200)
async def import_excel(
    file: UploadFile = File(...),
    db: DBSession = Depends(get_db),
):
    """
    Imports EAN barcodes from an Excel file.
    Expected columns: SKU (A) | Descrição (B, opcional) | EAN1 (C) | EAN2 (D, opcional) | EAN3 (E, opcional)
    Fallback: se o arquivo tiver apenas 2 colunas (SKU, EAN), a coluna B é o EAN.
    """
    content = await file.read()
    wb = openpyxl.load_workbook(BytesIO(content), read_only=True, data_only=True)
    ws = wb.active

    # Wipe existing data — full replace on every import
    deleted = db.query(Barcode).delete()
    db.commit()

    existing: set[str] = set()
    added = 0
    skipped = 0

    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or not row[0]:
            continue
        sku = str(row[0]).strip()
        if not sku:
            continue

        # Column B (index 1) = Descrição (salva no SKU-alias para uso no Master Data)
        # Columns C, D, E (indices 2, 3, 4) = EANs (one per column, all linked to same SKU)
        # Fallback: if file has only 2 columns (SKU, EAN), column B is the EAN
        if len(row) <= 2:
            description = None
            ean_cols = [1]
        else:
            raw_desc = row[1]
            description = str(raw_desc).strip() if raw_desc and str(raw_desc).strip().lower() not in ("none", "n/a", "") else None
            ean_cols = range(2, min(len(row), 5))  # C, D, E

        ean_list = []
        for col_idx in ean_cols:
            val = row[col_idx] if col_idx < len(row) else None
            if val:
                s = str(val).strip()
                if s and s.lower() not in ("none", "n/a", ""):
                    ean_list.append(s)

        if not ean_list:
            skipped += 1
            continue

        # Ensure SKU-alias entry exists (barcode == sku, used internally)
        if sku not in existing:
            db.add(Barcode(barcode=sku, sku=sku, is_primary=False, description=description))
            existing.add(sku)

        for ean in ean_list:
            # Check if this EXACT ean-sku pair already exists to avoid redundant rows
            # No longer skipping if EAN belongs to another SKU, only if it's the SAME SKU
            already_added = (ean, sku) in existing
            if already_added:
                skipped += 1
                continue
            
            ean_is_real = ean != sku
            db.add(Barcode(barcode=ean, sku=sku, is_primary=ean_is_real))
            # No longer skipping if EAN belongs to another SKU
            if ean_is_real:
                added += 1
            else:
                skipped += 1

    db.commit()
    return {"added": added, "skipped": skipped, "deleted": deleted}


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.post("/product", status_code=201)
def create_product(body: CreateProductBody, db: DBSession = Depends(get_db)):
    """Cria um novo produto manualmente (sem upload de arquivo)."""
    sku = body.sku.strip()
    if not sku:
        raise HTTPException(400, "SKU obrigatório")
    existing = db.query(Barcode).filter(Barcode.sku == sku).first()
    if existing:
        raise HTTPException(409, f"SKU '{sku}' já existe")

    db.add(Barcode(barcode=sku, sku=sku, is_primary=False, description=body.description))

    for raw in body.barcodes:
        b = raw.strip()
        if not b or b == sku:
            continue
        # No longer checking if barcode already belongs to another SKU
        db.add(Barcode(barcode=b, sku=sku, is_primary=True))

    db.commit()
    return {"status": "ok", "sku": sku}


@router.put("/{sku}")
def update_product(sku: str, body: UpdateProductBody, db: DBSession = Depends(get_db)):
    """Atualiza a descrição de um produto."""
    alias = db.query(Barcode).filter(Barcode.barcode == sku, Barcode.sku == sku).first()
    if not alias:
        # Produto existe mas sem alias — cria
        if not db.query(Barcode).filter(Barcode.sku == sku).first():
            raise HTTPException(404, f"SKU '{sku}' não encontrado")
        alias = Barcode(barcode=sku, sku=sku, is_primary=False, description=body.description)
        db.add(alias)
    else:
        alias.description = body.description
    db.commit()
    return {"status": "ok"}


@router.delete("/{sku}")
def delete_product(sku: str, db: DBSession = Depends(get_db)):
    """Remove um produto e todos os seus códigos de barras do Master Data."""
    deleted = db.query(Barcode).filter(Barcode.sku == sku).delete()
    if deleted == 0:
        raise HTTPException(404, f"SKU '{sku}' não encontrado")
    db.commit()
    return {"status": "ok", "deleted": deleted}


@router.post("/{sku}/barcode", status_code=201)
def add_barcode_to_sku(sku: str, body: AddBarcodeBody, db: DBSession = Depends(get_db)):
    """Adiciona um novo código de barras a um SKU existente."""
    if not db.query(Barcode).filter(Barcode.sku == sku).first():
        raise HTTPException(404, f"SKU '{sku}' não encontrado")
    barcode = body.barcode.strip()
    if not barcode:
        raise HTTPException(400, "Código de barras obrigatório")
        # No longer checking if barcode already belongs to another SKU
        pass
    db.add(Barcode(barcode=barcode, sku=sku, is_primary=True))
    db.commit()
    return {"status": "ok"}


@router.delete("/{sku}/barcode/{barcode}")
def remove_barcode_from_sku(sku: str, barcode: str, db: DBSession = Depends(get_db)):
    """Remove um código de barras de um SKU (não remove o SKU-alias)."""
    bc = db.query(Barcode).filter(
        Barcode.barcode == barcode,
        Barcode.sku == sku,
        Barcode.barcode != Barcode.sku,
    ).first()
    if not bc:
        raise HTTPException(404, "Código não encontrado")
    db.delete(bc)
    db.commit()
    return {"status": "ok"}


# ── Resolve / List ────────────────────────────────────────────────────────────

@router.get("/resolve")
def resolve_barcode(barcode: str = Query(...), db: DBSession = Depends(get_db)):
    rows = db.query(Barcode).filter(Barcode.barcode == barcode).all()
    if not rows:
        raise HTTPException(404, "Código de barras não encontrado")
    
    skus = list(set(r.sku for r in rows))
    return {
        "barcode": barcode, 
        "sku": skus[0], # Legacy support
        "skus": skus
    }


@router.get("/")
def list_barcodes(
    db: DBSession = Depends(get_db),
    search: str = Query(default="", description="Filtrar por SKU ou código de barras"),
    limit: int = Query(default=200, le=2000),
):
    # Show all barcodes — including those where barcode == sku (learned ones)
    from sqlalchemy import true
    base = true()

    if search:
        like = f"%{search}%"
        matching_skus = (
            db.query(Barcode.sku)
            .filter(base, (Barcode.sku.ilike(like)) | (Barcode.barcode.ilike(like)))
            .distinct()
            .subquery()
        )
        rows = (
            db.query(Barcode)
            .filter(base, Barcode.sku.in_(matching_skus))
            .order_by(Barcode.sku, Barcode.is_primary.desc())
            .all()
        )
        total = len({b.sku for b in rows})
    else:
        total = (
            db.query(Barcode.sku)
            .filter(base, Barcode.is_primary == True)
            .distinct()
            .count()
        )
        top_skus = (
            db.query(Barcode.sku)
            .filter(base, Barcode.is_primary == True)
            .distinct()
            .order_by(Barcode.sku)
            .limit(limit)
            .subquery()
        )
        rows = (
            db.query(Barcode)
            .filter(base, Barcode.sku.in_(top_skus))
            .order_by(Barcode.sku, Barcode.is_primary.desc())
            .all()
        )

    # Group by SKU
    grouped: dict[str, dict] = {}
    for b in rows:
        if b.sku not in grouped:
            grouped[b.sku] = {"sku": b.sku, "description": None, "barcodes": []}
        grouped[b.sku]["barcodes"].append({
            "barcode": b.barcode,
            "is_primary": b.is_primary,
            "learned": b.added_by is not None,
        })

    if grouped:
        # 1) Descrição do SKU-alias (Master Data manual ou Excel com descrição)
        alias_rows = (
            db.query(Barcode.sku, Barcode.description)
            .filter(Barcode.barcode == Barcode.sku, Barcode.sku.in_(grouped.keys()), Barcode.description.isnot(None))
            .all()
        )
        for sku, desc in alias_rows:
            grouped[sku]["description"] = desc

        # 2) Fallback: descrição da última sessão de picking
        desc_rows = (
            db.query(PickingItem.sku, PickingItem.description)
            .filter(
                PickingItem.sku.in_(grouped.keys()),
                PickingItem.description.isnot(None),
            )
            .distinct(PickingItem.sku)
            .all()
        )
        for sku, desc in desc_rows:
            if grouped[sku]["description"] is None:
                grouped[sku]["description"] = desc

    return {
        "total": total,
        "results": len(grouped),
        "items": list(grouped.values()),
    }
