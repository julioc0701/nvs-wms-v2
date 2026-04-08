import textwrap

def generate_shopee_paired_zpl(item: dict, is_single: bool = False) -> str:
    """
    Gera blocos ZPL para Shopee em colunas duplas (2-up) otimizadas para etiquetas 
    de 80x25mm (duas de 40x25mm lado a lado).
    Layout: Side-by-side (QR na esquerda, texto na direita).
    """
    product_name = item.get("product_name", "").replace('^', '')
    seller_sku = item.get("seller_sku", "")
    barcode = item.get("barcode", "")
    whs_skuid = item.get("whs_skuid", "")
    
    # Wrap name to fit in half-label
    name_line = textwrap.wrap(product_name, width=28)[0] if product_name else ""
    
    # Adicionamos comandos de reset de estado (PW, LL, LH, LS) para garantir o alinhamento
    zpl = "^XA\n^PW640\n^LL200\n^LH0,0\n^LS0\n^CI28\n"
    
    # ── COLUNA 1 (Esquerda) ──
    # Nome no topo
    zpl += f"^FO10,5^A0N,18,18^FD{name_line}^FS\n"
    # QR Code na esquerda
    zpl += f"^FO10,32^BQN,2,2^FDQA,{barcode}^FS\n"
    # Textos na direita do QR Code (X=95)
    zpl += f"^FO95,35^A0N,12,10^FDSKU: {seller_sku}^FS\n"
    zpl += f"^FO95,53^A0N,12,10^FDEAN: {barcode}^FS\n"
    zpl += f"^FO95,71^A0N,12,10^FDWHS: {whs_skuid}^FS\n"
    
    # ── COLUNA 2 (Direita) ── - Offset aumentado para 350 para centralizar no rolo
    if not is_single:
        zpl += f"^FO350,5^A0N,18,18^FD{name_line}^FS\n"
        zpl += f"^FO350,32^BQN,2,2^FDQA,{barcode}^FS\n"
        zpl += f"^FO435,35^A0N,12,10^FDSKU: {seller_sku}^FS\n"
        zpl += f"^FO435,53^A0N,12,10^FDEAN: {barcode}^FS\n"
        zpl += f"^FO435,71^A0N,12,10^FDWHS: {whs_skuid}^FS\n"
        
    zpl += "^XZ"
    return zpl
