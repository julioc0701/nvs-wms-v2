"""
Shopee Picking List PDF parser — resiliente a bug Skia/Chromium double-layer.

Pipeline:
  fitz (dedup spans internamente) → parse line-by-line → validate total

TODO: Substituir por scraping autenticado do Seller Center via Playwright
      (tabela HTML do painel não tem o bug, pula PDF inteiro).
      Reusar stack do projeto Olist Phase 2.

TODO: Verificar com RM da Shopee endpoint Open API v2 get_inbound_shipment_detail
      (não existe publicamente hoje, pode liberar pra parceiros enterprise).
"""
import io
import re
import logging
from pathlib import Path
from typing import List, Tuple

import fitz
import pdfplumber

from ._schema import SKU, ParseResult, PickingListIntegrityError
from ._dedupe_text import dedupe_pdfplumber_page, fix_broken_digits

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regexes
# ---------------------------------------------------------------------------
_SKU_ID_RE = re.compile(r"\d{8,}_\d+")
_SECONDARY_ID_RE = re.compile(r"^\d{8,}$")
_ASN_ID_RE = re.compile(r"INBRFSP\d+")
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}")
_DIGITS_ONLY_RE = re.compile(r"^\d+$")

# ---------------------------------------------------------------------------
# Lines to skip in the vendor-collection outer loop
# ---------------------------------------------------------------------------
_SKIP_EXACT = frozenset({
    "No.", "SKU do", "vendedor", "Shopee SKU ID", "Nome do Produto",
    "Variação", "Amarzém", "Qnt.", "Aprovada",
    "Notas", "Total",
    "Informação de Inbound", "Shopee Picking List - Shopee Fulfillment",
    "Data de Inbound", "ID de Envio (ASN ID)", "Informações de SKU",
    "ASN ID)",
})
_SKIP_STARTSWITH = (
    "No. SKU",           # fitz may join "No. SKU do" on one line
    "Shopee SKU ID",     # fitz may join with "Nome do Produto"
    "SKU do\n",
    "Instruções:",
    "nós gentilmente",
    "pelos consumidores",
    "Método de Entrega",
    "usuário poderá inserir",
    "solicitaremos",
)


def _is_skip_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped in _SKIP_EXACT:
        return True
    if any(stripped.startswith(p) for p in _SKIP_STARTSWITH):
        return True
    if _ASN_ID_RE.match(stripped):
        return True
    if _DATETIME_RE.match(stripped):
        return True
    # 5-digit standalone = total footer (11820, etc.)
    if re.match(r"^\d{5}$", stripped):
        return True
    return False


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def _extract_metadata(full_text: str) -> dict:
    asn_id = ""
    m = _ASN_ID_RE.search(full_text)
    if m:
        asn_id = m.group(0)

    data_inbound = ""
    # Pattern: "2026-05-06 06:00 (GMT-03)" — use search without ^ anchor
    m = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}[^\n]*", full_text)
    if m:
        data_inbound = m.group(0).strip()

    metodo = ""
    m = re.search(r"Método de Entrega\s+(\S+)", full_text)
    if m:
        metodo = m.group(1)

    # Total: look for "Total\n<number>" pattern in footer (appears on every page)
    total_declarado = 0
    m = re.search(r"\bTotal\s*\n\s*(\d{4,6})\b", full_text)
    if m:
        total_declarado = int(m.group(1))

    return {
        "asn_id": asn_id,
        "data_inbound": data_inbound,
        "metodo_entrega": metodo,
        "total_declarado": total_declarado,
    }


# ---------------------------------------------------------------------------
# Qty extraction from block tail
# ---------------------------------------------------------------------------

def _extract_qty_from_tail(lines: List[str]) -> Tuple[int, List[str]]:
    """
    Extract quantity from the end of a block.
    Handles:
      - direct number: ["...", "240"] → 240
      - split single digits: ["...", "2", "0", "0"] → 200  (Skia bug pages)
    Returns (qty, remaining_lines).
    """
    if not lines:
        return 0, lines

    tail: List[str] = []
    for line in reversed(lines):
        if _DIGITS_ONLY_RE.match(line):
            tail.insert(0, line)
        else:
            break

    if not tail:
        return 0, lines

    # All single digits → split qty (Skia bug case: 1,0,0 = 100)
    if all(len(t) == 1 for t in tail):
        try:
            qty = int("".join(tail))
            return qty, lines[: len(lines) - len(tail)]
        except ValueError:
            pass

    # Last token is the actual qty (others may be SKU armazem suffix like "50" in EMB150)
    try:
        qty = int(tail[-1])
        remaining_tail = tail[:-1]
        return qty, lines[: len(lines) - len(tail)] + remaining_tail
    except (ValueError, IndexError):
        return 0, lines


# ---------------------------------------------------------------------------
# Block parser
# ---------------------------------------------------------------------------

def _parse_block(vendor_parts: List[str], anchor_line: str, block_lines: List[str]) -> SKU | None:
    """
    Parse one SKU item from its component lines.
    vendor_parts: lines collected before the anchor (the vendor name, possibly multiline)
    anchor_line:  the line containing the SKU ID pattern (may have vendor prefix before it)
    block_lines:  lines after anchor_line until next anchor
    """
    m = _SKU_ID_RE.search(anchor_line)
    if not m:
        return None

    # Vendor prefix on same line as ID (e.g. "VISCAMVISION 26141745660_2")
    vendor_prefix = anchor_line[: m.start()].strip()
    all_vendor_parts = [p.strip() for p in vendor_parts if p.strip()]
    if vendor_prefix:
        all_vendor_parts.append(vendor_prefix)

    # Join without spaces: handles "VFW3GTCRIST\nAL" → "VFW3GTCRISTAL"
    sku_vendedor = "".join(all_vendor_parts)

    id_p1 = m.group(0)

    remaining = [l.strip() for l in block_lines if l.strip()]

    # SKU ID part 2: next pure 8+ digit line
    id_p2 = ""
    if remaining and _SECONDARY_ID_RE.match(remaining[0]):
        id_p2 = remaining[0]
        remaining = remaining[1:]

    shopee_sku_id = id_p1 + id_p2

    # Nome produto: lines until "Item" keyword
    nome_parts: List[str] = []
    while remaining and not re.match(r"^Item\b", remaining[0], re.IGNORECASE):
        nome_parts.append(remaining[0])
        remaining = remaining[1:]

    nome = " ".join(nome_parts)

    # Qty from tail, armazem from rest
    qty, armazem_lines = _extract_qty_from_tail(remaining)
    sku_armazem = " ".join(armazem_lines)

    if not sku_vendedor and not shopee_sku_id:
        return None

    return SKU(
        sku_vendedor=sku_vendedor,
        shopee_sku_id=shopee_sku_id,
        nome_produto=nome,
        variacao="",
        sku_armazem=sku_armazem,
        qnt_aprovada=qty,
    )


# ---------------------------------------------------------------------------
# Page line extractor — state machine with look-ahead
# ---------------------------------------------------------------------------

def _peek_next(lines: List[str], start: int) -> str:
    """Return next non-empty stripped line from start index, or ''."""
    for i in range(start, len(lines)):
        s = lines[i].strip()
        if s:
            return s
    return ""


def _parse_page_lines(lines: List[str]) -> List[SKU]:
    """
    State machine parser. States:
      VENDOR → ID2 → NOME → ARMAZEM → QTY → (back to VENDOR)
    Transition anchor: lines matching _SKU_ID_RE (Shopee SKU ID pattern).
    """
    S_VENDOR = 0
    S_ID2 = 1
    S_NOME = 2
    S_ARMAZEM = 3
    S_QTY = 4

    skus: List[SKU] = []
    state = S_VENDOR

    vendor_parts: List[str] = []
    id_p1 = ""
    id_p2 = ""
    nome_parts: List[str] = []
    armazem_parts: List[str] = []
    qty_parts: List[str] = []
    seen_gtin = False

    def _flush() -> None:
        """
        Save current item if valid, then reset item buffers.
        vendor_parts is only reset when an item was actually saved —
        otherwise it contains the vendor accumulation for the UPCOMING item.
        """
        nonlocal vendor_parts, id_p1, id_p2, nome_parts, armazem_parts, qty_parts, seen_gtin

        if id_p1:
            sku_vendedor = "".join(vendor_parts)
            shopee_sku_id = id_p1 + id_p2
            nome = " ".join(nome_parts)
            sku_armazem = " ".join(armazem_parts)

            # Qty logic: all single-digit parts → split qty (Skia bug); else last token
            if qty_parts:
                if all(len(q) == 1 for q in qty_parts):
                    qty = int("".join(qty_parts))
                else:
                    qty = int(qty_parts[-1])
            else:
                qty = 0

            if sku_vendedor:
                skus.append(SKU(
                    sku_vendedor=sku_vendedor,
                    shopee_sku_id=shopee_sku_id,
                    nome_produto=nome,
                    variacao="",
                    sku_armazem=sku_armazem,
                    qnt_aprovada=qty,
                ))

            # Reset ALL buffers including vendor_parts (vendor was consumed)
            vendor_parts = []
            id_p1 = id_p2 = ""
            nome_parts = []
            armazem_parts = []
            qty_parts = []
            seen_gtin = False
        else:
            # No item in progress — only reset non-vendor buffers.
            # vendor_parts stays: it has the upcoming item's vendor accumulated so far.
            id_p2 = ""
            nome_parts = []
            armazem_parts = []
            qty_parts = []
            seen_gtin = False

    def _start_item(anchor_line: str) -> None:
        """Start a new item from a line containing the SKU ID anchor."""
        nonlocal id_p1, state
        m = _SKU_ID_RE.search(anchor_line)
        if not m:
            return
        prefix = anchor_line[: m.start()].strip()
        if prefix:
            vendor_parts.append(prefix)
        id_p1 = m.group(0)
        state = S_ID2

    idx = 0
    while idx < len(lines):
        raw = lines[idx]
        line = raw.strip()
        idx += 1
        if not line:
            continue

        # --- VENDOR: collecting lines before the first SKU ID anchor ---
        if state == S_VENDOR:
            if _SKU_ID_RE.search(line):
                _flush()
                _start_item(line)
            elif not _is_skip_line(line):
                vendor_parts.append(line)

        # --- ID2: expecting the secondary Shopee SKU ID (8+ digits) ---
        elif state == S_ID2:
            if _SKU_ID_RE.search(line):
                # Immediate next anchor — no id_p2, no content
                _flush()
                _start_item(line)
            elif _SECONDARY_ID_RE.match(line):
                id_p2 = line
                state = S_NOME
            else:
                # No secondary ID — treat this line as first nome or armazem
                state = S_NOME
                if re.match(r"^Item\b", line, re.IGNORECASE):
                    armazem_parts.append(line)
                    state = S_ARMAZEM
                else:
                    nome_parts.append(line)

        # --- NOME: product name lines until "Item without GTIN" ---
        elif state == S_NOME:
            if _SKU_ID_RE.search(line):
                _flush()
                _start_item(line)
            elif re.match(r"^Item\b", line, re.IGNORECASE):
                armazem_parts.append(line)
                state = S_ARMAZEM
            elif _SECONDARY_ID_RE.match(line):
                # 8+ pure digits in nome position = actual GTIN in SKU Armazem column
                # (item has a real barcode instead of "Item without GTIN")
                armazem_parts.append(line)
                seen_gtin = True
                state = S_ARMAZEM
            else:
                nome_parts.append(line)

        # --- ARMAZEM: "Item without GTIN..." block ---
        elif state == S_ARMAZEM:
            if _SKU_ID_RE.search(line):
                _flush()
                _start_item(line)
            elif "GTIN" in line:
                armazem_parts.append(line)
                seen_gtin = True
            elif seen_gtin and _DIGITS_ONLY_RE.match(line):
                qty_parts.append(line)
                state = S_QTY
            elif _is_skip_line(line):
                # Header repetition mid-page (pages 4, 6) — end this block
                _flush()
                state = S_VENDOR
            else:
                armazem_parts.append(line)

        # --- QTY: collecting quantity digits ---
        elif state == S_QTY:
            if _SKU_ID_RE.search(line):
                _flush()
                _start_item(line)
            elif _DIGITS_ONLY_RE.match(line):
                # Look-ahead: distinguish numeric vendor SKUs from quantities.
                # Numeric vendors (588, 576, 502…) appear directly before a "bare" anchor
                # (an anchor line with no vendor text prefix on the same line).
                # When the next anchor has an INLINE vendor ("PROESC15014 40119788067_2"),
                # the current digit is a quantity, not a vendor.
                nxt = _peek_next(lines, idx)
                if nxt and _SKU_ID_RE.search(nxt):
                    m_nxt = _SKU_ID_RE.search(nxt)
                    nxt_vendor_prefix = nxt[: m_nxt.start()].strip()
                    if not nxt_vendor_prefix:
                        # Bare anchor — current digit is a numeric vendor SKU
                        _flush()
                        state = S_VENDOR
                        vendor_parts.append(line)
                    else:
                        # Anchor has inline vendor — current digit is a quantity
                        qty_parts.append(line)
                else:
                    qty_parts.append(line)
            else:
                # Non-digit → end of item; this line is start of next vendor
                _flush()
                state = S_VENDOR
                if _SKU_ID_RE.search(line):
                    _start_item(line)
                elif not _is_skip_line(line):
                    vendor_parts.append(line)

    _flush()
    return skus


# ---------------------------------------------------------------------------
# Buggy page detection (observability)
# ---------------------------------------------------------------------------

def _detect_buggy_pages(pdf_path: str) -> List[int]:
    """Check pdfplumber WITHOUT dedupe_chars for the Skia double-layer signature."""
    buggy: List[int] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                tables = page.extract_tables() or []
                for table in tables:
                    for row in table:
                        if row and any("NNoo" in str(cell) for cell in row if cell):
                            buggy.append(i + 1)
                            break
    except Exception:
        pass
    return buggy


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def parse_picking_list(pdf_path: str) -> ParseResult:
    """
    Parse a Shopee Picking List PDF.
    Returns ParseResult. Raises PickingListIntegrityError if totals diverge.
    """
    pdf_path = str(pdf_path)
    doc = fitz.open(pdf_path)

    all_page_lines: List[str] = []
    first_page_text = ""

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")

        if page_num == 0:
            first_page_text = text

        lines = text.splitlines()
        all_page_lines.extend(lines)

    doc.close()

    # --- Metadata ---
    meta = _extract_metadata(first_page_text)

    # --- Detect buggy pages for observability ---
    buggy_pages = _detect_buggy_pages(pdf_path)
    for pg in buggy_pages:
        logger.info(f"Página {pg}: Skia double-layer detectado — dedupe aplicado via fitz")

    # --- Parse all items ---
    skus = _parse_page_lines(all_page_lines)

    # --- Validate ---
    total_calculado = sum(s.qnt_aprovada for s in skus)
    total_declarado = meta["total_declarado"]

    result = ParseResult(
        asn_id=meta["asn_id"],
        data_inbound=meta["data_inbound"],
        metodo_entrega=meta["metodo_entrega"],
        skus=skus,
        total_declarado=total_declarado,
        total_calculado=total_calculado,
        paginas_com_dedupe=buggy_pages,
    )

    if total_calculado != total_declarado:
        raise PickingListIntegrityError(total_calculado, total_declarado)

    return result


# ---------------------------------------------------------------------------
# Compatibility wrapper (contrato com parser_factory.py)
# ---------------------------------------------------------------------------

def parse_picking_pdf(pdf_bytes: bytes) -> List[dict]:
    """
    Adapter: recebe bytes (como o parser_factory passa), salva temp, parseia.
    Retorna list[dict] compatível com o schema existente do WMS.
    """
    import tempfile, os

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        result = parse_picking_list(tmp_path)
    finally:
        os.unlink(tmp_path)

    return [
        {
            "sku": s.sku_vendedor,
            "ml_code": s.shopee_sku_id,
            "description": s.nome_produto,
            "qty_required": s.qnt_aprovada,
            "ean": None,
        }
        for s in result.skus
    ]
