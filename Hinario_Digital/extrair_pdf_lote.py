import os
import re
from PIL import Image
import pytesseract
from pdf2image import convert_from_path # Importante para PDF de Imagem

# ===================== CONFIGURAÇÃO =====================
NOME_ARQUIVO_PDF = "2025 - Hinário de Canto em Francês - peterson.pdf" # ← Ajuste o nome do seu arquivo PDF completo
PASTA_TEXTOS = "textos_corrigidos" 
IDIOMA_OCR = 'fra' # Use 'por' ou 'fra'
# Caminho para os binários do Poppler (APENAS SE NECESSÁRIO NO WINDOWS)
PATH_POPPLER = r'C:\Poppler\poppler-24.02.0\Library\bin' # ← SUBSTITUA PELO SEU CAMINHO

# =======================================================


def extrair_hinos_do_pdf_imagem():
    
    # --- CÁLCULO DO CAMINHO ROBUSTO ---
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    pasta_textos_completa = os.path.join(SCRIPT_DIR, PASTA_TEXTOS)
    arquivo_pdf = os.path.join(SCRIPT_DIR, NOME_ARQUIVO_PDF)
    
    os.makedirs(pasta_textos_completa, exist_ok=True)
    
    if not os.path.exists(arquivo_pdf):
        print(f"ERRO: Arquivo PDF não encontrado. O script procurou em: {arquivo_pdf}")
        return

    # === PASSO 1: OCR de todas as páginas e junção do texto ===
    print(f"\nIniciando OCR em {NOME_ARQUIVO_PDF} (PDF de Imagem)...")
    
    try:
        # Tenta converter as páginas do PDF para imagens (requer Poppler)
        print("Convertendo páginas do PDF para imagens...")
        # Adiciona o caminho do Poppler se estiver no Windows
        if os.name == 'nt' and PATH_POPPLER:
            images = convert_from_path(arquivo_pdf, poppler_path=PATH_POPPLER)
        else:
            images = convert_from_path(arquivo_pdf)

    except Exception as e:
        print("\nERRO CRÍTICO: Falha ao converter PDF para Imagem. Verifique a instalação do Poppler.")
        print(f"Detalhes do erro: {e}")
        return

    texto_bruto_completo = ""
    for i, image in enumerate(images):
        print(f"   -> Processando página {i+1}/{len(images)}...")
        # Executa OCR na imagem
        texto_pagina = pytesseract.image_to_string(image, lang=IDIOMA_OCR)
        # Adiciona o texto ao bloco completo, com um separador forte
        texto_bruto_completo += texto_pagina + "\n\n\n--- SEPARADOR_PAGINA ---\n\n\n"

    # === PASSO 2: Pós-processamento e Divisão em Hinos ===
    
    # 1. Limpeza inicial (unir pontuação, remover espaços múltiplos)
    texto_normalizado = re.sub(r'\s([.,!?;:])', r'\1', texto_bruto_completo)
    texto_normalizado = re.sub(r'[ \t]+', ' ', texto_normalizado)
    
    # 2. Divisão por número de hino.
    # Regex: Encontra o número do hino (1 a 4 dígitos) seguido por um ponto e possível texto.
    # Usa lookahead (?=...) para dividir ANTES do número do próximo hino.
    # A primeira parte do PDF (capa, índice, etc.) é tratada como lixo.
    
    # Padroniza quebras de linha múltiplas para facilitar a regex
    texto_normalizado = re.sub(r'\n{2,}', '\n', texto_normalizado)
    
    # O padrão procura por um número de 1 a 4 dígitos seguido por um ponto, no início de uma nova linha
    regex_hino = r'(?=\n\d{1,4}\.)'
    hinos_split = re.split(regex_hino, texto_normalizado)
    
    # Se o primeiro item for lixo (capa, etc.), nós o descartamos e assumimos que o hino 1 está no segundo bloco
    if len(hinos_split) > 1 and not re.match(r'^\d{1,4}\.', hinos_split[0].strip()):
        hinos_split.pop(0)

    print(f"\n{len(hinos_split)} blocos de hino identificados. Iniciando o salvamento...")

    # === PASSO 3: Salva cada hino em um arquivo .txt separado ===
    hinos_salvos = 0
    for bloco in hinos_split:
        bloco_limpo = bloco.strip()
        if not bloco_limpo:
            continue
            
        # Tenta extrair o número do hino do bloco
        match_num = re.match(r'(\d{1,4})\.', bloco_limpo)
        if match_num:
            num_hino = int(match_num.group(1))
        else:
            # Se não encontrar o número, usa a contagem sequencial (muito raro se a regex funcionar)
            num_hino = hinos_salvos + 1 

        nome_arquivo_hino = os.path.join(pasta_textos_completa, f"hino_{num_hino:03d}.txt")
        
        with open(nome_arquivo_hino, "w", encoding="utf-8") as f:
            f.write(bloco_limpo)
            
        hinos_salvos += 1
        print(f"   -> Hino {num_hino} salvo em: {nome_arquivo_hino}")

    print(f"\n=======================================================================")
    print(f"✅ FINALIZADO: {hinos_salvos} arquivos de texto criados na pasta '{PASTA_TEXTOS}'.")
    print("=======================================================================")
    print("\nPRÓXIMO PASSO: Corrija o texto (remova ruído, una sílabas, corrija OCR) nos arquivos .txt.")


if __name__ == "__main__":
    extrair_hinos_do_pdf_imagem()