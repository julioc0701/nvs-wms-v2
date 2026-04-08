import io
import re
import math
import logging
import pdfplumber

logger = logging.getLogger(__name__)

def parse_picking_pdf(pdf_bytes: bytes) -> list[dict]:
    items = []
    
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages):
            words = page.extract_words()
            
            lines = []
            current_line = []
            last_top = None
            
            words = sorted(words, key=lambda w: (w['top'], w['x0']))
            
            for w in words:
                if last_top is None or abs(w['top'] - last_top) > 4:
                    if current_line:
                        lines.append(current_line)
                    current_line = []
                    last_top = w['top']
                current_line.append(w)
            if current_line:
                lines.append(current_line)
                
            current_item = None
            
            for line in lines:
                text_start = " ".join([w['text'] for w in line[:3]]).lower()
                if "shopee picking list" in text_start or "informação" in text_start or "notas total" in text_start:
                    continue
                if "vendedor" in text_start or "amarzém" in text_start or "nnoo.." in text_start or "no." in text_start:
                    continue

                col_left = [w for w in line if w['x0'] < 190]
                left_text = " ".join([w['text'] for w in col_left])
                
                # Check if this line contains a shopee ID part 1 (e.g. 123456789_1)
                is_new_item = False
                match_id = re.search(r'(\d{8,}_\d+)', left_text)
                if match_id:
                    is_new_item = True
                    
                col_seller = [w for w in line if 30 < w['x0'] < 110]
                col_shopee_id = [w for w in line if 110 <= w['x0'] < 190]
                col_desc = [w for w in line if 190 <= w['x0'] < 450]
                col_qty = [w for w in line if w['x0'] > 500 and re.match(r'^\d+$', w['text'].strip())]

                if is_new_item:
                    if current_item:
                        items.append(current_item)
                    
                    seller_sku = "".join([w['text'] for w in col_seller])
                    shopee_id = "".join([w['text'] for w in col_shopee_id])
                    
                    # If they merged due to pdfplumber lack of space
                    if not shopee_id and match_id:
                        full_str = seller_sku
                        idx = full_str.find(match_id.group(1))
                        if idx != -1:
                            seller_sku = full_str[:idx]
                            shopee_id = full_str[idx:]

                    desc = " ".join([w['text'] for w in col_desc])
                    
                    qty = 0
                    if col_qty:
                        try:
                            # if multiple, we join them as they might be 2 and 8
                            qty_str = "".join([w['text'] for w in col_qty])
                            qty = int(qty_str)
                        except ValueError:
                            pass
                            
                    current_item = {
                        "sku": seller_sku,
                        "ml_code": shopee_id,
                        "description": desc,
                        "qty_required": qty,
                        "ean": None
                    }
                elif current_item:
                    # Continuation
                    if col_seller:
                        current_item["sku"] += "".join([w['text'] for w in col_seller])
                    if col_shopee_id:
                        current_item["ml_code"] += "".join([w['text'] for w in col_shopee_id])
                    if col_desc:
                        current_item["description"] += " " + " ".join([w['text'] for w in col_desc])
                    
                    if col_qty:
                        qty_str = "".join([w['text'] for w in col_qty])
                        if current_item["qty_required"] == 0:
                            try:
                                current_item["qty_required"] = int(qty_str)
                            except ValueError:
                                pass
                        elif current_item["qty_required"] > 0 and len(str(current_item["qty_required"])) == 1 and len(qty_str) == 1:
                            # Handling the split quantity like '2' and '8' => 28
                            current_item["qty_required"] = int(str(current_item["qty_required"]) + qty_str)
                            
            if current_item:
                items.append(current_item)
                
    valid_items = []
    for it in items:
        # If it's pure noise
        if not it["sku"] and not it['ml_code']:
            continue
        
        # Sku might have picked up some 'VAR' or something that wasn't joined
        if not re.search(r'\w', it["sku"]): 
            continue
            
        it["description"] = it["description"].strip()
        it["ml_code"] = it["ml_code"].replace(" ", "").strip()
        valid_items.append(it)
        
    return valid_items
