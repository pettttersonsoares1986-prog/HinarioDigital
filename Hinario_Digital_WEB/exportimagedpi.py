import os
import google.generativeai as genai
from PIL import Image, ImageFilter
import time

# --- CONFIGURAÇÕES ---
MINHA_API_KEY = "AIzaSyBNXAQKVKShx39JzvfziFvbTAvcdoUT6Zw" 

# Caminho da imagem (PNG de alta qualidade) e saída
CAMINHO_IMAGEM = r"C:\Users\psoares\pyNestle\Private\Hinario_Digital\teste\1.png"
ARQUIVO_SAIDA = "hino_extraido_ia.txt"

# --- FATOR DE ESCALA DE RESOLUÇÃO OTIMIZADO ---
RESOLUCAO_SCALE_FACTOR = 8

def extrair_texto_hino():
    # ... (Configurações da API, Verificação de arquivo e Modelo permanecem inalteradas)
    try:
        model = genai.GenerativeModel('models/gemini-2.5-pro')
        
        # 3. Processamento de Imagem: Aumento de Resolução + Nitidez (Sharpness)
        imagem_original = Image.open(CAMINHO_IMAGEM)
        
        # Calcula as novas dimensões
        nova_largura = imagem_original.width * RESOLUCAO_SCALE_FACTOR
        nova_altura = imagem_original.height * RESOLUCAO_SCALE_FACTOR
        
        print(f"Redimensionando de {imagem_original.size} para ({nova_largura}, {nova_altura}) (Fator {RESOLUCAO_SCALE_FACTOR}x)...")
        
        # Redimensiona usando o filtro LANCZOS
        imagem_upscaled = imagem_original.resize(
            (nova_largura, nova_altura), 
            resample=Image.Resampling.LANCZOS
        )
        
        # Aplica um filtro de nitidez (Sharpness)
        imagem_final = imagem_upscaled.filter(ImageFilter.SHARPEN)

        # ---------------------------------------------------------------------
        # 🚀 NOVO: SALVA A IMAGEM PROCESSADA PARA AVALIAÇÃO
        
        # Cria um nome de arquivo para a imagem de alta resolução (ex: 1_upscaled.png)
        base, ext = os.path.splitext(CAMINHO_IMAGEM)
        CAMINHO_IMAGEM_SALVA = f"{base}_upscaled{ext}"
        
        # Salva a imagem final processada no disco
        imagem_final.save(CAMINHO_IMAGEM_SALVA)
        print(f"✅ Imagem de alta resolução salva em: {CAMINHO_IMAGEM_SALVA}")
        # ---------------------------------------------------------------------
        
        # 4. Prompt otimizado
        prompt = """
        ... (O SEU PROMPT DETALHADO PERMANECE AQUI) ...
        """

        print("Enviando para o Gemini (isso leva alguns segundos)...")
        
        # Faz a chamada para a IA com a imagem de altíssima resolução e nitidez
        response = model.generate_content([prompt, imagem_final])
        
        # ... (O restante do código de salvamento do texto e tratamento de exceções)
        
    except Exception as e:
        print(f"\nERRO DURANTE A EXTRAÇÃO: {e}")
# ... (restante do código)

if __name__ == "__main__":
    extrair_texto_hino()