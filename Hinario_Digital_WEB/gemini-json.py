import os
import google.generativeai as genai
from PIL import Image
from dotenv import load_dotenv
from pathlib import Path

# --- CONFIGURAÇÃO ---
BASE_DIR = Path(__file__).parent.resolve()
load_dotenv()
MINHA_API_KEY = os.getenv("GEMINI_API_KEY")

# Caminho da imagem
CAMINHO_IMAGEM = BASE_DIR / "imagens_dev" / "Hino_001.jpg"
ARQUIVO_SAIDA = BASE_DIR / "output" / "new_Hino_0001.json"

def extrair_json_hino():
    try:
        genai.configure(api_key=MINHA_API_KEY)
    except Exception as e:
        print(f"Erro na configuração da chave: {e}")
        return

    if not os.path.exists(CAMINHO_IMAGEM):
        print(f"ERRO: Imagem não encontrada: {CAMINHO_IMAGEM}")
        return

    print(f"Processando: {os.path.basename(CAMINHO_IMAGEM)}...")

    # Modelo Pro para seguir regras lógicas estritas
    nome_modelo_usar = 'models/gemini-2.5-pro'

    try:
        configuracao_geracao = genai.types.GenerationConfig(
            temperature=0.1,
            response_mime_type="application/json"
        )

        model = genai.GenerativeModel(nome_modelo_usar)
        imagem = Image.open(CAMINHO_IMAGEM)

        # --- PROMPT REFORÇADO PARA INCLUIR NOTAS VAZIAS (NULL) ---
        prompt = """
        You are a Sheet Music OCR expert. Your goal is to digitize the sheet music into JSON, capturing EVERY musical event.

        ### 1. NOTE-BY-NOTE EXTRACTION (CRITICAL):
        - **DO NOT skip any symbol.** You must generate an entry for EVERY Note, Rest (Pausa), or Breathing Mark (Respiracao) found on the staff, reading from Left to Right.
        - **The "Null" Rule:** - If a Note or Rest has NO lyrics underneath it (e.g., it is a melisma extension, a tie, or a rest), you **MUST** output: `{ "texto": null, "nota": "NoteValue" }`.
          - **Example:** After the word "dent" (Seminima Pontuada), if there is another Seminima Pontuada without text and then a Rest, output both as null text entries.

        ### 2. VERTICAL ALIGNMENT STRATEGY:
        - Identify the note on the staff.
        - Look vertically below it to find the lyrics for Verse 1, Verse 2, Verse 3.
        - If no lyrics are found directly below a note, apply the "Null" Rule above.

        ### 3. STRUCTURE & TAGS:
        - **Coro (Chorus):** Look for the label "CORO" (orange tag) or "Refrain". 
          - **Logic:** If the lyrics repeat the Title of the song, it is the Coro.
          - Set `"tipo": "Coro"` and `"numero": null` for the Chorus section.
        - **Estrofes:** Number them 1, 2, 3...

        ### 4. FORMATTING:
        - **Liaisons (~):** "ne a" -> "ne~a".
        - **Hyphens:** Only at end of syllables ("Maî -"). No leading hyphens.
        - **Metadata:** Title, Author, Key (Tom), BPM, Compasso.

        ### 5. BPM CALCULATION:
        - If BPM is not explicitly stated, infer it from the header notes.
        - Example: If header shows 112 and 144, set bpm:calculate based in the average of the notes in the header eg.112+144 /2 = 128

        ### 6. HEADER
        - Extract Title, Author, Key (Tom), Language (Idioma) from the header.
        - Extract BPM from the header if present, otherwise calculate it as described in section 5.
        - to extract the Language (Idioma) based on the lyrics language.
        - tom: extract the musical key from the header (e.g., "Dó Maior", "Fá Menor").


        ### OUTPUT JSON SCHEMA:
        {
            "titulo": "String",
            "numero": Integer,
            "idioma": "String",
            "tom": "String",
            "autor": "String",
            "BPM": Integer,
            "compasso": "String",
            "estrofes": [
                {
                    "numero": 1,
                    "tipo": "Estrofe",
                    "linhas": [
                        {
                            "silabas": [
                                { "texto": "Qui", "nota": "Colcheia" },
                                { "texto": "sur", "nota": "Colcheia" }
                            ]
                        }
                    ]
                },
                {
                    "numero": 2,
                    "tipo": "Estrofe",
                    "linhas": [
                        {
                            "silabas": [
                                { "texto": "Qui", "nota": "Colcheia" },
                                { "texto": "sur", "nota": "Colcheia" }
                            ]
                        }
                    ]
                },
                {
                    "numero": 3,
                    "tipo": "Estrofe",
                    "linhas": [
                        {
                            "silabas": [
                                { "texto": "Quand", "nota": "Colcheia" },
                                { "texto": "la", "nota": "Colcheia" }
                            ]
                        }
                    ]
                },
                {
                    "numero": null,
                    "tipo": "Coro",
                    "linhas": [
                        {
                            "silabas": [
                                { "texto": "Ro-", "nota": "Seminima Pontuada" },
                                { "texto": "cher", "nota": "Seminima" }
                            ]
                        }
                    ]
                }
            ]
        }
        """

        response = model.generate_content(
            [prompt, imagem],
            generation_config=configuracao_geracao
        )
        
        texto_resultado = response.text
        
        os.makedirs(ARQUIVO_SAIDA.parent, exist_ok=True)
        with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
            f.write(texto_resultado)
            
        print(f"Sucesso! Salvo em: {ARQUIVO_SAIDA}")
        print("="*30)
        print(texto_resultado[:1500] + "...") # Aumentei o preview para você ver mais detalhes
        
    except Exception as e:
        print(f"ERRO: {e}")

if __name__ == "__main__":
    extrair_json_hino()