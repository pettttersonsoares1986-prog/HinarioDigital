# list_widgets.py
from PyQt6.QtWidgets import QListWidget, QMenu
from PyQt6.QtCore import Qt, QMimeData
from PyQt6.QtGui import QDrag, QAction
from core.utils import clean_filename


class ImageListWidget(QListWidget):
    """Lista de Imagens (Superior) - Permite seleção múltipla e arrasto"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)

    def startDrag(self, supportedActions):
        items = self.selectedItems()
        if items:
            drag = QDrag(self)
            mime_data = QMimeData()
            file_list = [clean_filename(i.text()) for i in items]
            mime_data.setText("|".join(file_list))
            drag.setMimeData(mime_data)
            drag.exec(Qt.DropAction.CopyAction)


class ProjectListWidget(QListWidget):
    """Lista de Projetos (Inferior) - Recebe o arrasto"""

    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.setAcceptDrops(True)
        self.setDragEnabled(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, pos):
        item = self.itemAt(pos)
        if item:
            menu = QMenu(self)
            action_rename = QAction("✏️ Renomear Projeto", self)
            action_rename.triggered.connect(lambda: self.main.rename_project(item))
            action_delete = QAction("🗑️ Excluir Projeto", self)
            action_delete.triggered.connect(self.main.delete_current_project)
            menu.addAction(action_rename)
            menu.addSeparator()
            menu.addAction(action_delete)
            menu.exec(self.mapToGlobal(pos))

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasText():
            files_string = event.mimeData().text()
            file_list = files_string.split("|")
            self.main.create_project_from_image_drop(file_list)
            event.accept()
