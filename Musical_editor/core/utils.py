# utils.py
import os
import re

def clean_filename(text):
    """Remove ícones e formatação extra para pegar só o nome do arquivo."""
    text = text.replace("✅ ", "")
    text = text.replace("🚧 ", "")
    text = text.replace("❓ ", "")
    text = text.replace("📂 ", "")
    return text.strip()

def natural_sort_key(text):
    """Retorna chave para ordenação natural de strings com números."""
    return [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', text)]
