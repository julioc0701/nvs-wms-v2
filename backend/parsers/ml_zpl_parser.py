"""
Parse a ZPL label file from Mercado Livre into per-SKU label blocks.
Each ^XA...^XZ block is one printable sheet (may contain 2 labels side by side).
Extracts SKU and ML barcode code from each block.
"""
import re


def parse_zpl_file(content: str) -> list[dict]:
    """
    Returns list of dicts: [{sku, ml_code, label_index, zpl_content}]
    Groups and indexes labels by SKU.
    """
    blocks = re.findall(r"\^XA.*?\^XZ", content, re.DOTALL | re.IGNORECASE)
    labels = []
    sku_counts: dict[str, int] = {}

    for block in blocks:
        block = block.strip()
        sku = _extract_sku(block)
        ml_code = _extract_ml_code(block)
        if not sku:
            sku = ml_code or "UNKNOWN"

        sku_counts[sku] = sku_counts.get(sku, 0) + 1
        labels.append({
            "sku": sku,
            "ml_code": ml_code,
            "label_index": sku_counts[sku],
            "zpl_content": block,
        })

    return labels


def get_ml_barcodes(content: str) -> list[dict]:
    """
    Returns [{sku, ml_code}] for registering ML codes as scannable barcodes.
    Deduplicates — one entry per SKU.
    """
    seen: set[str] = set()
    result = []
    for lbl in parse_zpl_file(content):
        if lbl["sku"] not in seen and lbl["ml_code"]:
            seen.add(lbl["sku"])
            result.append({"sku": lbl["sku"], "ml_code": lbl["ml_code"]})
    return result


def _extract_sku(block: str) -> str | None:
    # ML ZPL format: ^FDSKU: DISCTRASBROS\n^FS
    match = re.search(r"SKU:\s*([A-Z0-9_\-]+)", block, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _extract_ml_code(block: str) -> str | None:
    # ML barcode field: ^BCN,54,N,N^FD{ML_CODE}^FS
    match = re.search(r"\^BCN,\d+,N,N\^FD(\S+?)\^FS", block)
    if match:
        return match.group(1).strip()
    return None
