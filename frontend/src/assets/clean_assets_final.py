from PIL import Image, ImageDraw
import numpy as np
import os

def mask_background_color(input_path, output_path, seed_points=[(0,0), (0,-1), (-1,0), (-1,-1)]):
    if not os.path.exists(input_path):
        print(f"Arquivo não encontrado: {input_path}")
        return
    
    # 1. Abrir a imagem e garantir que está em RGBA
    img = Image.open(input_path).convert("RGBA")
    width, height = img.size
    
    # 2. Vamos tratar cada canto como um ponto de partida para o fundo "branco"
    # Convertemos seed points negativos para coordenadas reais
    real_seeds = []
    for x, y in seed_points:
        rx = x if x >= 0 else width + x
        ry = y if y >= 0 else height + y
        real_seeds.append((rx, ry))
    
    # 3. Criar uma máscara de fundo usando Flood Fill (tolerância alta para brancos/cinzas claros)
    # Pillow não tem floodfill com tolerância nativo na UI, então vamos usar uma técnica:
    # Converter para escala de cinza e aplicar limite para criar uma máscara de fundo "perfeita"
    
    data = np.array(img)
    # Máscara binária de pixels "quase brancos"
    # Qualquer coisa com R, G, B > 230
    white_mask = (data[:,:,0] > 230) & (data[:,:,1] > 230) & (data[:,:,2] > 230)
    
    # Como queremos apenas o fundo conectado aos cantos, vamos usar flood fill na máscara
    flood_mask = Image.fromarray((white_mask * 255).astype(np.uint8))
    
    # Inundar de preto (0) a partir dos cantos na máscara branca (255)
    # Os pontos pretos serão o fundo que vamos remover
    target_mask = Image.new("L", (width, height), 255) # Tudo branco inicialmente
    draw = ImageDraw.Draw(target_mask)
    
    # Vamos usar a biblioteca para inundar os pontos pretos (fundo)
    for sx, sy in real_seeds:
        # Se o pixel original for quase branco, inundamos
        if white_mask[sy, sx]:
           ImageDraw.floodfill(target_mask, xy=(sx, sy), value=0, thresh=0)
    
    # Agora target_mask tem 0 (preto) onde é fundo CONECTADO e 255 (branco) onde é logo
    final_alpha = np.array(target_mask)
    
    # Aplicar a transparência (0) onde a máscara for 0
    # E vamos dar uma suavizada na borda (anti-aliasing)
    # Para simplificar: apenas zeramos o alpha onde for fundo.
    
    # Para ser mais robusto, qualquer pixel na borda do logo que tenha contraste alto 
    # com branco deve ser matizado ou zerado.
    
    new_data = data.copy()
    new_data[:,:,3] = np.where(final_alpha == 0, 0, new_data[:,:,3])
    
    # Salvar o PNG final limpo
    clean_img = Image.fromarray(new_data)
    
    # 4. AUTO-CROP
    bbox = clean_img.getbbox()
    if bbox:
        clean_img = clean_img.crop(bbox)
        print(f"Cropped Final: {bbox}")
        
    clean_img.save(output_path)
    print(f"Processamento de TRANSPARÊNCIA concluído: {output_path}")

if __name__ == "__main__":
    assets_dir = r"C:\Users\julio\OneDrive\Documentos\Antigra\warehouse-picker v2\frontend\src\assets"
    
    # Limpar o logo principal (NVS)
    # Aumentando o número de seed points para cobrir as bordas
    seeds = [(0,0), (10, 10), (2000, 10), (10, 2000), (2000, 2000)]
    mask_background_color(os.path.join(assets_dir, "logo-novaes.png"), os.path.join(assets_dir, "logo-novaes-clean.png"))
    
    # Reprocessar ML e Shopee para garantir que o contorno branco sumiu
    mask_background_color(os.path.join(assets_dir, "ml-logo-raw.png"), os.path.join(assets_dir, "ml-logo.png"))
    mask_background_color(os.path.join(assets_dir, "shopee-logo-raw.png"), os.path.join(assets_dir, "shopee-logo.png"))
