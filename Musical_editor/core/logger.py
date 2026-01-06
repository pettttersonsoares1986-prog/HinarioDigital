# logger.py - Otimizado para VS Code e PyInstaller (SEM importação circular)

import logging
import os
import sys
from pathlib import Path

# Importar paths diretamente (evita importação circular)
try:
    from core.paths import LOGS_DIR, LOG_FILE
except ImportError:
    # Fallback se paths.py não estiver disponível
    if getattr(sys, 'frozen', False):
        BASE_DIR = Path(sys.executable).parent
    else:
        BASE_DIR = Path(__file__).parent.resolve()

    LOGS_DIR = BASE_DIR / "logs"
    LOG_FILE = LOGS_DIR / "app.log"
    os.makedirs(LOGS_DIR, exist_ok=True)

# Criar pasta de logs se não existir
os.makedirs(LOGS_DIR, exist_ok=True)

# Configurar logging COM ENCODING UTF-8
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Handler para arquivo
file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.DEBUG)

# Handler para console
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.INFO)

# Configurar logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# ====================== FUNÇÕES DE LOG ======================

def log_info(msg):
    """Log de informação"""
    logger.info(msg)
    print(f"[INFO] {msg}")

def log_error(msg, exc=None):
    """Log de erro"""
    if exc:
        logger.error(msg, exc_info=exc)
        print(f"[ERROR] {msg}\n{exc}")
    else:
        logger.error(msg)
        print(f"[ERROR] {msg}")

def log_debug(msg):
    """Log de debug"""
    logger.debug(msg)
    print(f"[DEBUG] {msg}")

def log_warning(msg):
    """Log de aviso"""
    logger.warning(msg)
    print(f"[WARNING] {msg}")

# ====================== FUNÇÃO DE INICIALIZAÇÃO ======================

def init_logger():
    """Inicializa logger na startup"""
    print("=" * 60)
    print("LOGGER INICIALIZADO")
    print(f"Arquivo de log: {LOG_FILE}")
    print("=" * 60)
    log_info("Aplicacao iniciada")
