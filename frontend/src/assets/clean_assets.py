from PIL import Image
import numpy as np
import os

def process_image(input_path, output_path, tolerance=240):
    if not os.path.exists(input_path):
        print(f"Arquivo não encontrado: {input_path}")
        return
    
    img = Image.open(input_path).convert("RGBA")
    data = np.array(img)
    
    # 1. Remover fundo branco/quase branco
    r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]
    white_mask = (r > tolerance) & (g > tolerance) & (b > tolerance)
    data[white_mask, 3] = 0 # Torna Transparente
    
    clean_img = Image.fromarray(data)
    
    # 2. AUTO-CROP
    bbox = clean_img.getbbox()
    if bbox:
        clean_img = clean_img.crop(bbox)
        print(f"Cropped {input_path} -> {bbox}")
    
    clean_img.save(output_path)
    print(f"Processamento concluído: {output_path}")

if __name__ == "__main__":
    assets_dir = r"C:\Users\julio\OneDrive\Documentos\Antigra\warehouse-picker v2\frontend\src\assets"
    
    # ML
    process_image(os.path.join(assets_dir, "ml-logo-raw.png"), os.path.join(assets_dir, "ml-logo.png"))
    
    # Shopee
    process_image(os.path.join(assets_dir, "shopee-logo-raw.png"), os.path.join(assets_dir, "shopee-logo.png"))
    
    # NOVAES
    process_image(os.path.join(assets_dir, "logo-novaes.png"), os.path.join(assets_dir, "logo-novaes-clean.png"), tolerance=250)
