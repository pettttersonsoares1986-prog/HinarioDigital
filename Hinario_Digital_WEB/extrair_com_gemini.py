import os
import google.generativeai as genai
from PIL import Image


from pathlib import Path

# Pega a pasta onde ESTE arquivo .py está salvo
BASE_DIR = Path(__file__).parent.resolve()


# --- CONFIGURAÇÕES ---
MINHA_API_KEY = "AIzaSyBZqVgrhplbTXDSAcNb4ammpjrBKecqgM0"

# Caminho da imagem 
CAMINHO_IMAGEM = BASE_DIR / "imagens" / "1.png"
ARQUIVO_SAIDA = BASE_DIR / "output" / "Hino_001.txt"

def extrair_texto_hino():
    try:
        genai.configure(api_key=MINHA_API_KEY)
    except Exception as e:
        print(f"Erro na configuração da chave: {e}")
        return

    if not os.path.exists(CAMINHO_IMAGEM):
        print(f"ERRO: Imagem não encontrada.")
        return

    print(f"Processando: {os.path.basename(CAMINHO_IMAGEM)}...")
    
    # Mantendo o modelo gemini-2.5-pro
    nome_modelo_usar = 'models/gemini-2.5-pro'

    try:
        # Temperatura 0.0 mantida para precisão
        configuracao_geracao = genai.types.GenerationConfig(
            temperature=0.0,
            top_p=1.0,
        )

        model = genai.GenerativeModel(nome_modelo_usar)
        imagem = Image.open(CAMINHO_IMAGEM)

        # --- PROMPT ATUALIZADO COM CÁLCULO DE MÉDIA ---
        prompt = """
        You are a Sheet Music OCR expert. 
        Your goal is to extract lyrics with 100% pixel-perfect accuracy and calculate metadata.

        ### TASK 1: METADATA & CALCULATION
        1. **Time Signature:** If symbol is "C", write "4/4". If numbers, write numbers.
        2. **Tempo:** Extract exactly (e.g., ♩= 56-66).
        3. **Media (Average Tempo):** Look at the numbers in the Tempo.
           - Calculate the mathematical average (mean).
           - Example 1: If Tempo is "56 - 66", calculation is (56+66)/2 = 61. Output: "61".
           - Example 2: If Tempo is single value "80", Output: "80".
           - Round to the nearest whole number.

        ### TASK 2: LYRICS (THE "LEFT MARGIN" RULE)
        - **IGNORE THE NOTES, READ THE TEXT:** Do not align your reading with the first musical note. The text often starts to the LEFT of the first note, directly under the Clef (🎼).
        - **FORCE LEFT SCAN:** For every system (line of music), force your vision to the absolute LEFT edge of the image to catch words like "gar-de", "gran-de", "En", "Sur".

        ### TASK 3: FORMATTING
        - **Liaisons (`~`):** If a curved line connects two syllables (e.g. "Gloi - re‿à"), output "Gloi - re~à".
        - **Hyphens:** Keep them (e.g., "al - lé - lu - ia").
        - **Structure:** Match the visual line breaks.

        ### OUTPUT FORMAT:
        === METADATA ===
        Title: [Text] | Number: [N] | Author: [Name] | Tempo: [Value] | Media: [Calculated Value] | Time Signature: [Value]

        === VERSE 1 ===
        1. [Lyrics...]
        [Lyrics...]

        === VERSE 2 ===
        2. [Lyrics...]

        === VERSE 3 ===
        3. [Lyrics...]

        (Transcribe all verses present)
        """

        response = model.generate_content(
            [prompt, imagem],
            generation_config=configuracao_geracao
        )
        
        texto_resultado = response.text
        
        with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
            f.write(texto_resultado)
            
        print(f"Sucesso! Salvo em: {ARQUIVO_SAIDA}")
        print("="*30)
        print(texto_resultado)
        
    except Exception as e:
        print(f"ERRO: {e}")

if __name__ == "__main__":
    extrair_texto_hino()