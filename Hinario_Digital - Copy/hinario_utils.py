import re
import json

def indexar_hinos(texto):
    hinos = {}
    padrao = re.compile(r'(\\d{1,4})\\.\\s+([A-ZÉÈÀÙÂÊÎÔÛÇ,\'\\-\\s]+)\\n(.*?)(?=\\n\\d{1,4}\\.\\s+[A-ZÉÈÀÙÂÊÎÔÛÇ,\'\\-\\s]+|\\Z)', re.DOTALL)
    for match in padrao.finditer(texto):
        numero = int(match.group(1))
        titulo = match.group(2).strip()
        letra = match.group(3).strip()
        hinos[numero] = {"titulo": titulo, "letra": letra}
    return hinos

def carregar_hinos_pdf(pdf_path):
    import fitz  # PyMuPDF
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    return indexar_hinos(full_text)
