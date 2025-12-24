import google.generativeai as genai
from PIL import Image
import json
import os

# --- CONFIGURAÇÕES ---
MINHA_API_KEY = "AIzaSyBZqVgrhplbTXDSAcNb4ammpjrBKecqgM0"

# CAMINHOS DOS ARQUIVOS (Edite aqui)
CAMINHO_IMAGEM = r"C:\Users\psoares\pyNestle\Private\Hinario_Digital\teste\1.png"
CAMINHO_JSON_ENTRADA = r"C:\Users\psoares\pyNestle\Private\Hinario_Digital\teste\dados_notas.json" # <--- Coloque o caminho do seu JSON aqui
ARQUIVO_SAIDA_JSON = "Hino_001_Alinhado.json"

def alinhar_notas_e_silabas():
    # 1. Configura a API
    try:
        genai.configure(api_key=MINHA_API_KEY)
    except Exception as e:
        print(f"Erro na configuração da chave: {e}")
        return

    # 2. Verifica e Carrega a Imagem
    if not os.path.exists(CAMINHO_IMAGEM):
        print(f"ERRO: Imagem não encontrada em: {CAMINHO_IMAGEM}")
        return
    imagem = Image.open(CAMINHO_IMAGEM)
    print(f"Imagem carregada: {os.path.basename(CAMINHO_IMAGEM)}")

    # 3. Verifica e Carrega o JSON de Entrada
    if not os.path.exists(CAMINHO_JSON_ENTRADA):
        print(f"ERRO: Arquivo JSON não encontrado em: {CAMINHO_JSON_ENTRADA}")
        return
    
    try:
        with open(CAMINHO_JSON_ENTRADA, 'r', encoding='utf-8') as f:
            dados_completos = json.load(f)
            # Assume que suas notas estão dentro da chave "notas", conforme seu exemplo
            lista_notas = dados_completos.get('notas', [])
            
        if not lista_notas:
            print("ERRO: Nenhuma nota encontrada dentro da chave 'notas' do JSON.")
            return
            
        print(f"JSON carregado. Total de notas para processar: {len(lista_notas)}")
        
    except json.JSONDecodeError as e:
        print(f"ERRO: O arquivo não é um JSON válido. Detalhes: {e}")
        return

    # 4. Prepara o Modelo (Use o 1.5 Pro ou 2.5 Pro se disponível, pois eles têm melhor visão espacial)
    nome_modelo = 'models/gemini-1.5-pro' 
    print(f"Usando modelo: {nome_modelo}")
    
    model = genai.GenerativeModel(nome_modelo)

    # Converta apenas a lista de notas para string para economizar tokens
    notas_str = json.dumps(lista_notas, indent=2)

    # --- PROMPT DE ALINHAMENTO ---
    prompt = f"""
    You are a Music OCR Alignment Expert.
    I am providing a list of musical notes detected in the image, with their EXACT (x, y) coordinates.
    
    YOUR TASK:
    Look at the image at the specific coordinates of each note and identify the text syllable directly below it (associated with Verse 1).

    ### INSTRUCTIONS:
    1. **Strict Coordinate Matching:** Use the 'x' and 'y' values to locate the note head.
    2. **Look Down:** Read the text syllable immediately below that note.
    3. **Verse 1 Only:** Ignore text from verse 2, 3, or 4. We are only aligning the top line of lyrics.
    4. **Empty Notes:** If the note is a rest (Pausa) or has no text, return an empty string "".
    5. **Output:** Return a JSON list exactly matching the input, but adding a "silaba" field to each object.

    ### INPUT NOTES (JSON):
    ```json
    {notas_str}
    ```

    ### DESIRED OUTPUT FORMAT (JSON ONLY):
    [
      {{ "Nota": "SEMINIMA", "Texto": "Christ," }},
      {{ "Nota": "COLCHEIA", "Texto": "mon" }},
      ...
    ]
    """

    print("Enviando para o Gemini... (Isso pode levar um minuto)")

    try:
        # Solicita resposta em JSON
        response = model.generate_content(
            [prompt, imagem],
            generation_config={"response_mime_type": "application/json", "temperature": 0.0}
        )
        
        # 5. Salva o Resultado
        resultado_json = json.loads(response.text)
        
        # (Opcional) Mescla de volta com os dados originais se quiser manter o cabeçalho
        dados_finais = dados_completos.copy()
        dados_finais['notas'] = resultado_json
        
        with open(ARQUIVO_SAIDA_JSON, "w", encoding="utf-8") as f:
            json.dump(dados_finais, f, indent=4, ensure_ascii=False)
            
        print("\n" + "="*50)
        print("SUCESSO! Notas alinhadas com sílabas.")
        print(f"Salvo em: {os.path.abspath(ARQUIVO_SAIDA_JSON)}")
        print("="*50)
        
        # Mostra uma prévia
        print(json.dumps(resultado_json[:3], indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"\nERRO AO PROCESSAR RESPOSTA: {e}")
        # print(response.text) # Descomente para debugar se der erro

if __name__ == "__main__":
    alinhar_notas_e_silabas()