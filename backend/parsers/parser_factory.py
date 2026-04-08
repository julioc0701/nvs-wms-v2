from parsers.ml_pdf_parser import parse_picking_pdf as ml_parse_pdf
from parsers.ml_zpl_parser import parse_zpl_file as ml_parse_zpl, get_ml_barcodes

from parsers.shopee_pdf_parser import parse_picking_pdf as shopee_parse_pdf
# from parsers.shopee_zpl_parser import parse_zpl_file as shopee_parse_zpl

def parse_picking_pdf_factory(marketplace: str, pdf_bytes: bytes) -> list[dict]:
    """
    Routes the PDF parsing to the specific marketplace implementation.
    """
    if marketplace == "shopee":
        return shopee_parse_pdf(pdf_bytes)
    else:
        # Default is Mercado Livre
        return ml_parse_pdf(pdf_bytes)


def parse_labels_factory(marketplace: str, txt_content: str) -> list[dict]:
    """
    Routes the label (TXT/ZPL/CSV) parsing to the specific marketplace implementation.
    """
    if not txt_content.strip():
        return []
        
    if marketplace == "shopee":
        # Shopee labels are generated on-the-fly from picking list, 
        # but if a file is provided we treat it as empty or custom ZPL.
        return []
    else:
        # Default is Mercado Livre
        return ml_parse_zpl(txt_content)


def get_barcodes_factory(marketplace: str, txt_content: str) -> list[dict]:
    """
    Extracts barcodes and SKU associations from the label file.
    """
    if not txt_content.strip():
        return []

    if marketplace == "shopee":
        return [] # TODO: Implement Shopee barcode extraction if needed
    else:
        return get_ml_barcodes(txt_content)
