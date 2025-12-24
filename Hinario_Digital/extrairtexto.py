import os
import re
import pytesseract
from PIL import Image, ImageEnhance, ImageDraw, ImageFilter

# ===================== CONFIGURAÇÃO =====================
NUMERO = 1
PASTA_IMAGENS = "musicos_images"
PASTA_TEXTOS = "musicos_textos_corrigidos"
IDIOMA_OCR = 'fra'

pytesseract.pytesseract.tesseract_cmd = r"C:\Users\psoares\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
# =======================================================

def melhorar_imagem_para_ocr(img_crop):
    """Filtros para limpar pauta musical e realçar texto"""
    img = img_crop.convert('L')
    fator_aumento = 3
    w, h = img.size
    img = img.resize((w * fator_aumento, h * fator_aumento), Image.Resampling.LANCZOS)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    limiar = 160 
    img = img.point(lambda p: 0 if p < limiar else 255)
    img = img.filter(ImageFilter.SHARPEN)
    return img

def limpar_linha_hino(texto):
    """Remove lixo específico de partituras (hifens de sílabas, autores, etc)"""
    # 1. Remove hifens usados para separar sílabas (ex: "Maî - tre" -> "Maître")
    # A regex procura hifens cercados por espaços e os remove
    #texto = re.sub(r'\s+-\s+', '', texto)
    #texto = re.sub(r'-\s+', '', texto) # Hifen no final de palavra quebrada

    # 1. REMOVE LIXO ESPECÍFICO (Seu pedido)
    # Remove a string exata "LU d" (ignorando maiúsculas/minúsculas)
    texto = re.sub(r'(?i)LU\s*d', '', texto)

    # --- NOVO: Remove "r Fr" (case insensitive) ---
    texto = re.sub(r'(?i)r\s*Fr', '', texto)
    
    # 2. Remove caracteres indesejados
    sujeira = r'[|/\\—~=<>«»♪♫♭♯♮]'
    texto = re.sub(sujeira, '', texto)
    
    # O Tesseract costuma ler o undertie como underscore.
    texto = texto.replace("‿", "~")

    # 3. Corrige pontuação francesa (espaço antes de pontuação)
    texto = re.sub(r'\s+([.,!?;:])', r'\1', texto)
    
    # 4. Remove números soltos no inicio que não sejam o índice
    # Ex: "1. 1 Christ" -> "Christ"
    texto = re.sub(r'^\d+\.\s*\d+\s+', '', texto)
    
    return texto.strip()

def validar_linha(linha):
    """Retorna True se a linha parece ser parte da letra, False se for lixo"""
    # Ignora linhas muito curtas
    if len(linha) < 4: return False
    
    # Ignora linhas que parecem ser apenas autores ou compasso
    # Ex: "Leila Naylor", "( 56 - 66)"
    #if re.search(r'\d+\s*-\s*\d+', linha): return False # Intervalo de números
    #if re.match(r'^[A-Z\s\.]+$', linha): return False # Só maiúsculas (frequentemente cabeçalho)
    
    return True

def extrair_hino_definitivo():
    print("--- INICIANDO PROCESSAMENTO (LIMPEZA AVANÇADA) ---")
    
    base = os.path.dirname(os.path.abspath(__file__))
    nomes_possiveis = [f"{NUMERO}.PNG", f"{NUMERO}.png", f"{NUMERO}.jpg"]
    img_path = None
    for nome in nomes_possiveis:
        teste = os.path.join(base, PASTA_IMAGENS, nome)
        if os.path.exists(teste):
            img_path = teste
            break
    
    if not img_path: return

    debug_path = os.path.join(base, f"debug_final_hino_{NUMERO:03d}.png")
    out_path = os.path.join(base, PASTA_TEXTOS, f"hino_{NUMERO:03d}.txt")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    try: img = Image.open(img_path)
    except: return

    # COORDENADAS
    regioes = [
        (366, 191, 1197, 288),   # 0: Título
        (421, 345, 1187, 446),   # 1: Bloco 1
        (428, 678, 1188, 775),   # 2: Bloco 2
        (427, 1007, 1187, 1101), # 3: Bloco 3
        (430, 1330, 1192, 1430), # 4: Bloco 4
    ]

    todas_linhas = []
    debug = img.copy()
    draw = ImageDraw.Draw(debug)
    config_tesseract = f'--psm 6 --oem 3 --dpi 300'

    # === PARTE 1: TOPO (Título) ===
    print("Processando Título...")
    area0 = img.crop(regioes[0])
    area0 = melhorar_imagem_para_ocr(area0)
    texto0 = pytesseract.image_to_string(area0, lang=IDIOMA_OCR, config=config_tesseract)
    
    # Lógica específica para limpar título
    linhas_topo = [l.strip() for l in texto0.split('\n') if len(l) > 5]
    titulo_texto = "TITULO DESCONHECIDO"
    
    for l in linhas_topo:
        # Pega a primeira linha que parece texto real (evita nomes de autores)
        l_limpa = limpar_linha_hino(l)
        if len(l_limpa) > 5 and not re.search(r'\d', l_limpa):
            titulo_texto = l_limpa
            break
            
    titulo = f"{NUMERO}. {titulo_texto}"
    print(f"  > Título: {titulo}")
    draw.rectangle(regioes[0], outline="magenta", width=5)

    # === PARTE 2: BLOCOS (Letra) ===
    cores = ["red", "lime", "blue", "yellow"]
    
    # Dicionário para agrupar as frases por estrofe
    # estrofes[1] = "Frase 1 bloco 1", "Frase 1 bloco 2"...
    estrofes = {1: [], 2: [], 3: [], 4: [], 5: []}

    for k in range(1, 5):
        print(f"Processando Bloco {k}...")
        left, top, right, bottom = regioes[k]
        draw.rectangle([(left, top), (right, bottom)], outline=cores[(k-1)%4], width=5)

        area = img.crop((left, top, right, bottom))
        area = melhorar_imagem_para_ocr(area)
        
        texto = pytesseract.image_to_string(area, lang=IDIOMA_OCR, config=config_tesseract)
        
        # Filtra linhas brutas do OCR
        linhas_raw = [l.strip() for l in texto.split('\n') if len(l.strip()) > 0]
        
        # Contador local para saber qual estrofe é (1ª linha = estrofe 1, etc)
        idx_estrofe = 1
        
        for linha_crua in linhas_raw:
            # Limpa a linha
            linha_limpa = limpar_linha_hino(linha_crua)
            
            # Valida se é texto útil
            if validar_linha(linha_limpa):
                # Remove numeração inicial que o OCR pegou (ex: "1. Christ")
                linha_limpa = re.sub(r'^\d+[\.,]\s*', '', linha_limpa)
                
                # Adiciona à estrofe correspondente
                if idx_estrofe <= 5:
                    estrofes[idx_estrofe].append(linha_limpa)
                    print(f"    [Estrofe {idx_estrofe}]: {linha_limpa}")
                    idx_estrofe += 1

    # Salva Debug
    debug.save(debug_path)
    
    # Monta Texto Final
    resultado = [titulo, ""]
    
    for i in range(1, 6):
        if estrofes[i]:
            # Junta todas as partes da estrofe em uma linha só
            texto_completo = " ".join(estrofes[i])
            resultado.append(f"{i}. {texto_completo}")

    texto_final = "\n".join(resultado).strip()

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(texto_final)

    print("\n" + "="*50)
    print(texto_final)
    print("="*50)
    print(f"Salvo em: {out_path}")

if __name__ == "__main__":
    extrair_hino_definitivo()