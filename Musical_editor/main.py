# main.py - Versão corrigida (SEM duplicação de logger)

import sys
from pathlib import Path

# Adicionar pasta do projeto ao path
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication
from core.logger import init_logger, log_info, log_error
from ui.window import MainWindow

def main():
    """Funcao principal da aplicacao"""
    try:
        # Inicializar logger PRIMEIRO (apenas aqui)
        init_logger()
        log_info("=" * 60)
        log_info("INICIANDO APLICACAO")
        log_info("=" * 60)

        # Criar aplicacao
        app = QApplication(sys.argv)
        app.setStyle("Fusion")

        # Criar e mostrar janela
        log_info("Criando janela principal...")
        window = MainWindow()
        window.show()
        log_info("Janela principal exibida")

        # Executar
        sys.exit(app.exec())

    except Exception as e:
        log_error("Erro fatal na inicializacao", e)
        sys.exit(1)

if __name__ == "__main__":
    main()
