from PIL import Image
import numpy as np
import os

ASSETS_DIR = os.path.dirname(os.path.abspath(__file__))

def clean_logo(input_path, output_path):
    # Abrir a imagem
    img = Image.open(input_path).convert("RGBA")
    data = np.array(img)
    
    # Identificar as cores do checkerboard (estimativa comum em imagens assim)
    # Branco (255, 255, 255) e um cinza clarinho (usualmente em torno de 204-206)
    
    # Vamos pegar os canais R, G, B
    r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]
    
    # Máscara para as partes brancas do fundo (que queremos manter brancas mas "limpas")
    # E para os quadradinhos cinza que queremos branquear.
    
    # O checkerboard costuma ter cores bem específicas: (255, 255, 255) e (204, 204, 204) ou similar
    # Vamos tratar como fundo tudo que for CINZA CLARO que não tenha detalhe em volta (opcional)
    # Mas uma abordagem simples: qualquer pixel que seja EXATAMENTE o cinza do fundo vira branco.
    
    # Primeiro vamos descobrir as cores mais comuns próximas de branco
    # Para simplificar, vamos remover o tom de cinza do "fundo pontilhado"
    
    gray_threshold = 200 # A maioria dos checkerboards usa cinza claro (204, 204, 204)
    white_threshold = 250
    
    # Mudando para branco os tons de cinza do fundo
    # Se R, G, B forem quase iguais (cinza) e estiverem na faixa do checkerboard
    is_checker_gray = (r > 200) & (r < 210) & (g > 200) & (g < 210) & (b > 200) & (b < 210)
    
    # Aplicar: onde for o cinza do fundo, torna BRANCO (255, 255, 255, 255)
    data[is_checker_gray] = [255, 255, 255, 255]
    
    # Agora vamos tentar tornar a parte branca do fundo em TRANSPARENTE?
    # O usuário pediu "sem esse fundo". Transparente é o ideal se o container for cinza ou degradê.
    # Se for fundo branco, basta tirar o pontilhado cinza.
    
    # Se o usuário quer apenas tirar o pontilhado, deixar tudo branco já ajuda muito.
    # Mas vamos tentar tornar o fundo TRANSPARENTE para o design glassmorphism ficar top.
    
    # Máscara para tudo que é BRANCO (255, 255, 255)
    is_white = (data[:,:,0] == 255) & (data[:,:,1] == 255) & (data[:,:,2] == 255)
    
    # Torna transparente os pixels brancos (pássivel de erro se o logo tiver áreas puramente brancas)
    # Como o logo tem relevo metálico, o branco absoluto é raro no logo, costuma ser reflexo.
    # Mas para garantir, vamos manter o fundo branco limpíssimo por enquanto se não der pra garantir transparência.
    
    new_img = Image.fromarray(data)
    new_img.save(output_path)
    print(f"Limpeza concluída! Resultado salvo em {output_path}")

if __name__ == "__main__":
    path = os.path.join(ASSETS_DIR, "logo-novaes.png")
    out = os.path.join(ASSETS_DIR, "logo-novaes-clean.png")
    clean_logo(path, out)
