from PIL import Image
import numpy as np
import os

def process_logo_final(input_path, output_path):
    if not os.path.exists(input_path):
        print(f"Arquivo não encontrado: {input_path}")
        return
    
    # 1. Abrir e converter para RGBA
    img = Image.open(input_path).convert("RGBA")
    data = np.array(img)
    
    # 2. Remover fundo branco com alta tolerância
    r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]
    white_mask = (r > 230) & (g > 230) & (b > 230)
    data[white_mask, 3] = 0 # Torna Transparente
    
    # Criar nova imagem com transparência
    clean_img = Image.fromarray(data)
    
    # 3. AUTO-CROP: Remover bordas transparentes vazias
    # Getbbox retorna o bounding box dos dados não-zero (considerando o canal alpha)
    bbox = clean_img.getbbox()
    if bbox:
        clean_img = clean_img.crop(bbox)
        print(f"Imagem croppada para: {bbox}")
    
    # 4. Salvar resultado final
    clean_img.save(output_path)
    print(f"Processamento concluído: {output_path}")

if __name__ == "__main__":
    assets_dir = r"C:\Users\julio\OneDrive\Documentos\Antigra\warehouse-picker v2\frontend\src\assets"
    
    # ML
    process_logo_final(os.path.join(assets_dir, "ml-logo-raw.png"), os.path.join(assets_dir, "ml-logo.png"))
    
    # Shopee
    process_logo_final(os.path.join(assets_dir, "shopee-logo-raw.png"), os.path.join(assets_dir, "shopee-logo.png"))
