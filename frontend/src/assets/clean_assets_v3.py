from PIL import Image, ImageDraw
import numpy as np
import os

ASSETS_DIR = os.path.dirname(os.path.abspath(__file__))

def final_aggressive_cleaning(input_path, output_path, tolerance=200):
    if not os.path.exists(input_path):
        print(f"Arquivo não encontrado: {input_path}")
        return
    
    img = Image.open(input_path).convert("RGBA")
    data = np.array(img)
    width, height = img.size
    
    # 1. Identificar fundo por Flood Fill agressivo
    # Criar uma imagem "mascara"
    mask = Image.new("L", (width, height), 255) # Tudo branco (logo)
    
    # Inundar de preto (0) a partir dos cantos na máscara se for "quase branco"
    r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]
    
    # Condição de "cor de fundo" aproximada (tolerância maior para tirar brancos sujos)
    def is_bg(x, y):
        pr, pg, pb = data[y, x, 0], data[y, x, 1], data[y, x, 2]
        # Se for cinza muito claro ou branco
        return pr > tolerance and pg > tolerance and pb > tolerance
    
    # Pontos de semente (incluindo margens para garantir)
    seeds = [(0,0), (width-1, 0), (0, height-1), (width-1, height-1), 
             (width//2, 0), (width//2, height-1), (0, height//2), (width-1, height//2)]
    
    # Vamos usar uma abordagem de máscara direta
    # Para ser ultra agressivo e seguro: tudo que estiver conectado aos cantos e for clarinho -> Alpha 0
    # Como o Pillow floodfill não tem tolerância por pixel, vamos simular:
    from collections import deque
    q = deque([s for s in seeds if is_bg(s[0], s[1])])
    visited = set(q)
    
    while q:
        x, y = q.popleft()
        data[y, x, 3] = 0 # Torna Transparente
        
        # Vizinhos
        for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in visited:
                if is_bg(nx, ny):
                    visited.add((nx, ny))
                    q.append((nx, ny))

    # 2. Salvar o resultado final
    clean_img = Image.fromarray(data)
    
    # 3. AUTO-CROP
    bbox = clean_img.getbbox()
    if bbox:
        clean_img = clean_img.crop(bbox)
        print(f"Aggressive Crop: {bbox}")
        
    clean_img.save(output_path)
    print(f"Limpeza AGRESSIVA concluída: {output_path}")

if __name__ == "__main__":
    # Limpar com tolerância maior de 200
    final_aggressive_cleaning(os.path.join(ASSETS_DIR, "logo-novaes.png"), os.path.join(ASSETS_DIR, "logo-novaes-v3.png"), tolerance=200)
    
    # Reprocessar ML e Shopee com a mesma lógica agressiva
    final_aggressive_cleaning(os.path.join(ASSETS_DIR, "ml-logo-raw.png"), os.path.join(ASSETS_DIR, "ml-logo-v3.png"), tolerance=220)
    final_aggressive_cleaning(os.path.join(ASSETS_DIR, "shopee-logo-raw.png"), os.path.join(ASSETS_DIR, "shopee-logo-v3.png"), tolerance=220)
