import sys
from PySide6.QtWidgets import QApplication
from player_ui import KaraokePlayer

if __name__ == "__main__":
    # Cria a aplicação Qt
    app = QApplication(sys.argv)
    
    # Define um estilo visual moderno (opcional, mas recomendado)
    app.setStyle("Fusion")
    
    # Inicia a janela principal (Player)
    window = KaraokePlayer()
    window.show()
    
    # Executa o loop de eventos
    sys.exit(app.exec())