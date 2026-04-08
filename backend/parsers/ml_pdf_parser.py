"""
Parse Mercado Livre picking list PDFs into structured item data.
Uses pdfplumber table extraction tuned for the ML Inbound PDF format.
"""
import re
import pdfplumber
from io import BytesIO


def parse_picking_pdf(content: bytes) -> list[dict]:
    """
    Returns a list of dicts: [{sku, ml_code, description, qty_required, ean}]
    """
    with pdfplumber.open(BytesIO(content)) as pdf:
        items = _extract_ml_table(pdf)
        if not items:
            items = _fallback_text(pdf)
    return items


def _extract_ml_table(pdf) -> list[dict]:
    """
    Handles the ML Inbound PDF table format:
      Column 0 (PRODUTO):  'Código ML: X Código universal: Y SKU:\\nSKU_VALUE\\nDescription'
      Column 1 (UNIDADES): '100' or '1,000'
    """
    items = []
    seen_skus: set[str] = set()

    for page in pdf.pages:
        for table in page.extract_tables() or []:
            for row in table:
                if not row or not row[0]:
                    continue
                produto = str(row[0])
                unidades = str(row[1]) if len(row) > 1 and row[1] else ""

                # Must contain 'Código ML:' to be a product row
                if "digo ML:" not in produto:
                    continue

                sku = _extract_sku(produto)
                if not sku:
                    continue

                qty = _parse_qty(unidades)
                if not qty:
                    continue

                ean = _extract_ean(produto)
                ml_code = _extract_ml_code(produto)
                description = _extract_description(produto, sku)

                # Deduplicate: same SKU can appear on multiple pages
                if sku in seen_skus:
                    # Sum quantities for duplicate SKUs
                    for item in items:
                        if item["sku"] == sku:
                            item["qty_required"] += qty
                            break
                else:
                    seen_skus.add(sku)
                    items.append({
                        "sku": sku,
                        "ml_code": ml_code,
                        "description": description,
                        "qty_required": qty,
                        "ean": ean,
                    })

    return items


def _extract_sku(produto: str) -> str | None:
    # Pattern: 'SKU:\nSKU_VALUE' or 'SKU: SKU_VALUE'
    match = re.search(r"SKU:\s*\n?(\S+)", produto)
    return match.group(1) if match else None


def _extract_ml_code(produto: str) -> str | None:
    # Pattern: 'Código ML: CIGQ85538' (the 'C' and accent may be mangled by PDF)
    match = re.search(r"digo\s+ML:\s*([A-Z0-9]+)", produto, re.IGNORECASE)
    return match.group(1) if match else None


def _extract_ean(produto: str) -> str | None:
    # Pattern: 'Código universal:\n1234567890123' or inline
    match = re.search(r"niversal:\s*\n?(\d{8,14})", produto)
    return match.group(1) if match else None


def _extract_description(produto: str, sku: str) -> str:
    lines = produto.split("\n")
    # Find the line containing the SKU value, then take following lines as description
    for i, line in enumerate(lines):
        if sku in line:
            desc_parts = [l.strip() for l in lines[i + 1:] if l.strip()]
            return " ".join(desc_parts)[:200]
    return ""


def _parse_qty(value: str) -> int | None:
    try:
        return int(re.sub(r"[^\d]", "", value.strip()))
    except (ValueError, AttributeError):
        return None


def _fallback_text(pdf) -> list[dict]:
    """Last-resort text-based extraction."""
    full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    items = []
    seen = set()
    pattern = re.compile(
        r"SKU:\s*\n?([A-Z0-9_\-]{3,30}).*?(\d{1,5})\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    for m in pattern.finditer(full_text):
        sku, qty = m.group(1), int(m.group(2))
        if sku not in seen:
            seen.add(sku)
            items.append({"sku": sku, "description": "", "qty_required": qty, "ean": None})
    return items
