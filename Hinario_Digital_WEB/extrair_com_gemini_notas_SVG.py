import os
import google.generativeai as genai
import time

# === CONFIGURAÇÕES ===
MINHA_API_KEY = "AIzaSyBRENF2oSv9_wCsQ5o01KNOCU4TBOYGxt4"   # sua chave Gemini

# Caminho do SVG (já vetorizado e perfeito)
CAMINHO_SVG = r"C:\Users\psoares\pyNestle\Private\Hinario_Digital\teste\1_full_vectorizer.svg"

ARQUIVO_SAIDA = r"C:\Users\psoares\pyNestle\Private\Hinario_Digital\teste\hino_extraido_do_svg.txt"

# === CONFIGURA A API ===
genai.configure(api_key=MINHA_API_KEY)

# Usa o modelo mais forte disponível (Gemini 1.5 Pro ou 2.0 Flash Experimental)
model = genai.GenerativeModel('models/gemini-2.5-pro')  # ou 'gemini-2.0-flash-exp'

# === PROMPT ULTRA-PRECISO PARA SVG ===
prompt = """
Você está analisando um arquivo SVG vetorizado perfeito de uma página de hinário.

Sua tarefa é transcrever com precisão absoluta:

1. Título do hino, número, autor/compositor, tempo e compasso
2. Todas as estrofes com suas letras alinhadas às notas
3. Duração exata de cada nota do soprano (voz superior) usando estes códigos visuais:

   • ○◦ = semibreve
   • ○│ = mínima
   • ●│ = semínima
   • ●│¹ = colcheia (1 bandeira ou barra)
   • ●│² = semicolcheia (2 bandeiras)
   • ●│³ = fusa
   • ●│: = nota pontuada (adicione : após o símbolo)

4. Indique ligaduras com ~ entre notas
5. Indique fermatas com ^ sobre a nota

Formato de saída (exemplo):
=== HINO 1 ===
Título: Christ, mon bon Maître
Autor: Leila Naylor Morris
Compasso: 2/2
Tempo: ♩=56-60

=== ESTROFE 1 ===
Christ, mon  bon   Maî---tre   et  mon  Sei-gneur,
●│    ○│    ●│¹   ●│¹    ○│:    ●│    ○│

Je    me  pros---ter---ne   a---vec   foi   et  fer---veur,
●│    ○│    ●│    ○│:     ○│     ●│    ○│

Retorne APENAS o texto formatado, sem explicações.
"""

# === ENVIA O SVG PARA O GEMINI ===
print("Enviando SVG vetorizado perfeito para o Gemini... (leva 10–20 segundos)")

try:
    # O Gemini aceita SVG diretamente como arquivo
    arquivo_svg = genai.upload_file(path=CAMINHO_SVG, mime_type="image/svg+xml")

    response = model.generate_content([prompt, arquivo_svg])
    
    resultado = response.text

    # Salva o resultado
    with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
        f.write("=== EXTRAÇÃO DO SVG PERFEITO ===\n\n")
        f.write(resultado)

    print("\n" + "="*60)
    print("SUCESSO TOTAL! Extração perfeita do SVG")
    print(f"Resultado salvo em: {os.path.abspath(ARQUIVO_SAIDA)}")
    print("="*60)
    print(resultado)

    # Abre o arquivo automaticamente
    os.startfile(ARQUIVO_SAIDA)

except Exception as e:
    print(f"Erro: {e}")