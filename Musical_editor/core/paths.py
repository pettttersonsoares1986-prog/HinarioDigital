# core/paths.py - Gerenciador de caminhos para VS Code e PyInstaller

import sys
import os
from pathlib import Path

def get_base_dir():
    """
    Retorna o diretório base da aplicação.
    - Em desenvolvimento (VS Code): pasta Musical_editor
    - Em produção (PyInstaller): pasta do executável
    """
    if getattr(sys, 'frozen', False):
        # Executando como .exe (PyInstaller)
        base_dir = Path(sys.executable).parent
    else:
        # Executando no VS Code - pasta Musical_editor
        base_dir = Path(__file__).parent.parent.resolve()
    return base_dir

def get_parent_dir():
    """
    Retorna o diretório PAI (onde está .env)
    - Em desenvolvimento: HinarioDigital (um nível acima de Musical_editor)
    - Em produção: mesma pasta do .exe
    """
    if getattr(sys, 'frozen', False):
        # Em .exe, o .env está na mesma pasta
        return Path(sys.executable).parent
    else:
        # Em desenvolvimento, o .env está UM NÍVEL ACIMA
        return Path(__file__).parent.parent.parent.resolve()

# Diretório base (Musical_editor)
BASE_DIR = get_base_dir()

# Diretório pai (HinarioDigital) - onde está .env
PARENT_DIR = get_parent_dir()

# Diretórios de dados
DATA_DIR = BASE_DIR / "data"
IMG_FOLDER = DATA_DIR / "musicos_images"
JSON_FOLDER = DATA_DIR / "json_notas"
ICONS_FOLDER = DATA_DIR / "Notas_Musicais"
OUTPUT_FOLDER = DATA_DIR / "output"

# Diretório de logs
LOGS_DIR = BASE_DIR / "logs"
LOG_FILE = LOGS_DIR / "app.log"

# Arquivo de configuração (.env fora de Musical_editor)
CONFIG_FILE = PARENT_DIR / ".env"

# Criar pastas se não existirem
for folder in [DATA_DIR, IMG_FOLDER, JSON_FOLDER, ICONS_FOLDER, OUTPUT_FOLDER, LOGS_DIR]:
    os.makedirs(folder, exist_ok=True)

# Função auxiliar para obter caminho absoluto
def get_path(relative_path):
    """Converte caminho relativo em absoluto"""
    return BASE_DIR / relative_path

# Debug: mostrar caminhos
def print_paths():
    print(f"Base Dir: {BASE_DIR}")
    print(f"Parent Dir: {PARENT_DIR}")
    print(f"Config File (.env): {CONFIG_FILE}")
    print(f"Data Dir: {DATA_DIR}")
    print(f"Images: {IMG_FOLDER}")
    print(f"JSON: {JSON_FOLDER}")
    print(f"Icons: {ICONS_FOLDER}")
    print(f"Output: {OUTPUT_FOLDER}")
    print(f"Logs: {LOGS_DIR}")
