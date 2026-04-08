def generate_shopee_labels(items_data: list[dict]) -> list[dict]:
    """
    Generate ZPL labels locally for Shopee using the parsed items list.
    Because Shopee doesn't natively send us a TXT label roll, we synthesize it.
    """
    labels = []
    for item in items_data:
        qty = item.get("qty_required", 1)
        desc = item.get("description", "")
        seller_sku = item.get("sku", "")
        shopee_id = item.get("ml_code", "")
        
        for i in range(qty):
            # Clean string and safely break lines
            desc_clean = desc.replace('^', '')
            max_len = 40
            line1 = desc_clean[:max_len]
            line2 = desc_clean[max_len:max_len*2]
            line3 = desc_clean[max_len*2:max_len*3]
                
            zpl = "^XA\n"
            zpl += "^PW800\n" # Assuming a default standard width to prevent cutoff
            zpl += "^CI28\n"  # Unicode support
            
            # Title / Desc
            zpl += f"^FO20,20^A0N,25,25^FD{line1}^FS\n"
            if line2:
                zpl += f"^FO20,50^A0N,25,25^FD{line2}^FS\n"
            if line3:
                zpl += f"^FO20,80^A0N,25,25^FD{line3}^FS\n"
            
            # Barcode graphic containing Shopee SKU ID
            # Code-128 (supports alphanumeric and underscores)
            zpl += f"^BY3,2,60\n"
            zpl += f"^FO20,120^BCN,60,N,N,N\n"
            zpl += f"^FD{shopee_id}^FS\n"
            
            # Required Info Fields
            zpl += f"^FO20,200^A0N,25,25^FDwhs skuid: {shopee_id}^FS\n"
            zpl += f"^FO20,230^A0N,25,25^FDbarcode: {shopee_id}^FS\n"
            zpl += f"^FO20,260^A0N,30,30^FDseller sku: {seller_sku}^FS\n"
            
            zpl += "^XZ"
            
            labels.append({
                "sku": seller_sku,
                "label_index": i + 1,
                "zpl_content": zpl
            })
            
    return labels
