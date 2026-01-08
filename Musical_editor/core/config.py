# config.py - Versão final com suporte a configurações por projeto

import os
import json
from dotenv import load_dotenv
from core.paths import BASE_DIR, IMG_FOLDER, JSON_FOLDER, ICONS_FOLDER, OUTPUT_FOLDER,PREVIEW_FOLDER
from core.logger import log_debug, log_error
from pathlib import Path

# Arquivo .env está dentro de Musical_editor
CONFIG_FILE = BASE_DIR / ".env"

# Carregar variáveis de ambiente
if CONFIG_FILE.exists():
    load_dotenv(CONFIG_FILE)
else:
    print(f"Aviso: Arquivo .env não encontrado em {CONFIG_FILE}")

# ====================== CONFIGURAÇÕES GLOBAIS PADRÃO ======================
GLOBAL_CONFIG_DEFAULT = {
    "CROP_OFFSET_Y": 40,
    "CROP_WIDTH": 60,
    "CROP_HEIGHT": 90,
    "CHORUS_OFFSET_Y": 40,
    "CHORUS_WIDTH": 50,
    "CHORUS_HEIGHT": 80,
    "CROP_ZOOM": 1.3,
    "SPACING_NOTE": 160,
    "SPACING_TAG": 220,
    "PAGE_WIDTH": 2000,
    "RIGHT_MARGIN": 150,
    "BOTTOM_PADDING": 50,
    "SNAP_GRID": 20,
    "API_COOLDOWN": 40,
    "AUTO_PREVIEW_DELAY": 2000
}

# Configuração global (padrão)
GLOBAL_CONFIG = GLOBAL_CONFIG_DEFAULT.copy()

# ====================== FERRAMENTAS ======================
FERRAMENTAS_ORGANIZADAS = {
    "Estrutura e Tags": ["TAG_VERSO", "TAG_CORO", "TAG_FINAL"],
    "Notas Simples": ["SEMIBREVE", "MINIMA", "SEMINIMA", "COLCHEIA", "SEMICOLCHEIA"],
    "Notas Pontuadas": ["MINIMA PONTUADA", "SEMINIMA PONTUADA", "COLCHEIA PONTUADA", "SEMICOLCHEIA PONTUADA"],
    "Pausas": ["PAUSA SEMIBREVE", "PAUSA MINIMA", "PAUSA SEMINIMA", "PAUSA COLCHEIA", "PAUSA SEMICOLCHEIA"],
    "Pausas Pontuadas": ["PAUSA SEMINIMA PONTUADA", "PAUSA COLCHEIA PONTUADA", "PAUSA SEMICOLCHEIA PONTUADA"],
    "Outros": ["RESPIRACAO CURTA", "RESPIRACAO LONGA", "FERMATA MINIMA", "FERMATA COLCHEIA", "FERMATA SEMINIMA"]
}

# ====================== ATALHOS ======================
MAPA_ATALHOS = {
    "1": "SEMINIMA",
    "2": "COLCHEIA",
    "3": "MINIMA",
    "4": "SEMICOLCHEIA",
    "T": "TAG_VERSO",
    "C": "TAG_CORO",
    "F": "TAG_FINAL",
    "R": "PAUSA SEMINIMA"
}

# ====================== CONSTANTES ======================
MAX_HIST = 50

# ====================== API ======================
MINHA_API_KEY = os.getenv("GEMINI_API_KEY")

# ====================== FUNÇÕES DE CONFIGURAÇÃO POR PROJETO ======================

def load_project_config(json_path):
    """Carrega configurações de um projeto específico"""
    from core.logger import log_debug

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        config = data.get('configuracoes', GLOBAL_CONFIG_DEFAULT.copy())
        log_debug(f"Configuracoes do projeto carregadas: {json_path}")
        return config

    except Exception as e:
        from core.logger import log_error
        log_error(f"Erro ao carregar configuracoes do projeto", e)
        return GLOBAL_CONFIG_DEFAULT.copy()

def save_project_config(json_path, config):
    """Salva configurações de um projeto específico"""
    from core.logger import log_debug, log_error

    try:
        # Carregar dados existentes
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Atualizar configuracoes
        data['configuracoes'] = config

        # Salvar
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        log_debug(f"Configuracoes do projeto salvas: {json_path}")
        return True

    except Exception as e:
        log_error(f"Erro ao salvar configuracoes do projeto", e)
        return False

def reset_config_to_default():
    """Reseta configurações globais para padrão"""
    global GLOBAL_CONFIG
    GLOBAL_CONFIG = GLOBAL_CONFIG_DEFAULT.copy()

# ====================== DEBUG ======================
def print_config():
    """Mostra configuração de caminhos (útil para debug)"""
    print(f"Base Dir: {BASE_DIR}")
    print(f"Imagens: {IMG_FOLDER}")
    print(f"JSON: {JSON_FOLDER}")
    print(f"Icones: {ICONS_FOLDER}")
    print(f"PREVIEW_FOLDER: {PREVIEW_FOLDER}")
    print(f"Output: {OUTPUT_FOLDER}")
    print(f"API Key configurada: {bool(MINHA_API_KEY)}")
