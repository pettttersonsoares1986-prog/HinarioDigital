import sys
import os
import json
import glob
import time
import re 
from functools import partial
import io
import threading

# ============================================================================
#                       IMPORTAÇÕES DA INTERFACE GRÁFICA
# ============================================================================
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene, 
    QGraphicsItem, QGraphicsPixmapItem, QGraphicsRectItem, QWidget, QVBoxLayout, 
    QHBoxLayout, QPushButton, QCheckBox, QLabel, QScrollArea, 
    QFrame, QFileDialog, QMessageBox, QMenu, QGraphicsObject,
    QListWidget, QListWidgetItem, QInputDialog, QSplitter, 
    QDialog, QFormLayout, QSpinBox, QDoubleSpinBox, QProgressDialog, 
    QTabWidget, QToolBox, QGridLayout, QGroupBox, QStyle,
    QAbstractItemView 
)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QSize, QEvent, QThread, QTimer, QMimeData
from PyQt6.QtGui import (
    QPixmap, QPainter, QPen, QColor, QAction, 
    QTransform, QImage, QWheelEvent, QIcon, QFont, QBrush, 
    QMouseEvent, QPainterPath, QKeySequence, QShortcut, QDrag
)

# ============================================================================
#                       IMPORTAÇÕES DE PROCESSAMENTO E IA
# ============================================================================
from PIL import Image, ImageDraw, ImageEnhance, ImageOps, ImageFont
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai

# ============================================================================
#                          CONFIGURAÇÃO E CONSTANTES
# ============================================================================

BASE_DIR = Path(__file__).parent.resolve()

IMG_FOLDER = BASE_DIR / "data" / "musicos_images"
JSON_FOLDER = BASE_DIR / "data" / "json_notas"
ICONS_FOLDER = BASE_DIR / "data" / "Notas_Musicais"
OUTPUT_FOLDER = BASE_DIR / "data" / "output"

# Garante que as pastas existam
for folder in [IMG_FOLDER, JSON_FOLDER, ICONS_FOLDER, OUTPUT_FOLDER]:
    os.makedirs(folder, exist_ok=True)

load_dotenv()
MINHA_API_KEY = os.getenv("GEMINI_API_KEY")

GLOBAL_CONFIG = {
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

FERRAMENTAS_ORGANIZADAS = {
    "Estrutura e Tags": ["TAG_VERSO", "TAG_CORO", "TAG_FINAL"],
    "Notas Simples": ["SEMIBREVE", "MINIMA", "SEMINIMA", "COLCHEIA", "SEMICOLCHEIA"],
    "Notas Pontuadas": ["MINIMA PONTUADA", "SEMINIMA PONTUADA", "COLCHEIA PONTUADA", "SEMICOLCHEIA PONTUADA"],
    "Pausas": ["PAUSA SEMIBREVE", "PAUSA MINIMA", "PAUSA SEMINIMA", "PAUSA COLCHEIA", "PAUSA SEMICOLCHEIA"],
    "Pausas Pontuadas": ["PAUSA SEMINIMA PONTUADA", "PAUSA COLCHEIA PONTUADA", "PAUSA SEMICOLCHEIA PONTUADA"],
    "Outros": ["RESPIRACAO CURTA", "RESPIRACAO LONGA", "FERMATA MINIMA", "FERMATA COLCHEIA", "FERMATA SEMINIMA"]
}

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

MAX_HIST = 50

# ============================================================================
#                  CLASSES PERSONALIZADAS PARA LISTAS (DRAG & DROP)
# ============================================================================

def clean_filename(text):
    """Remove ícones e formatação extra para pegar só o nome do arquivo."""
    text = text.replace("✅ ", "")
    text = text.replace("🚧 ", "")
    text = text.replace("❓ ", "")
    text = text.replace("📂 ", "")
    return text.strip()

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
            
            # Cria uma lista de nomes limpos separados por '|'
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
        
        # Habilita Menu de Contexto (Botão Direito)
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

# ============================================================================
#                               UTILITÁRIOS (CACHE & WORKER)
# ============================================================================

class ImageCache:
    _cache = {}

    @classmethod
    def get_pixmap(cls, tipo, size=40):
        key = (tipo, size)
        if key in cls._cache:
            return cls._cache[key]

        caminho = os.path.join(ICONS_FOLDER, f"{tipo.replace(' ', '_')}.png")
        if os.path.exists(caminho):
            pixmap = QPixmap(caminho)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(
                    size, size, 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                cls._cache[key] = pixmap
                return pixmap
        
        # Lógica de Ponto Automático
        if "PONTUADA" in tipo:
            tipo_base = tipo.replace(" PONTUADA", "")
            caminho_base = os.path.join(ICONS_FOLDER, f"{tipo_base.replace(' ', '_')}.png")
            if os.path.exists(caminho_base):
                pixmap_base = QPixmap(caminho_base)
                if not pixmap_base.isNull():
                    pixmap_base = pixmap_base.scaled(
                        size, size, 
                        Qt.AspectRatioMode.KeepAspectRatio, 
                        Qt.TransformationMode.SmoothTransformation
                    )
                    imagem_com_ponto = QPixmap(pixmap_base.size())
                    imagem_com_ponto.fill(Qt.GlobalColor.transparent)
                    
                    painter = QPainter(imagem_com_ponto)
                    painter.drawPixmap(0, 0, pixmap_base)
                    painter.setBrush(QBrush(Qt.GlobalColor.black))
                    painter.setPen(Qt.PenStyle.NoPen)
                    
                    raio_ponto = size / 9
                    x_ponto = size * 0.70
                    y_ponto = size * 0.60
                    painter.drawEllipse(QPointF(x_ponto, y_ponto), raio_ponto, raio_ponto)
                    painter.end()
                    cls._cache[key] = imagem_com_ponto
                    return imagem_com_ponto

        pixmap = cls._generate_fallback(tipo, size)
        cls._cache[key] = pixmap
        return pixmap

    @staticmethod
    def _generate_fallback(texto, size):
        color_bg = '#3498db' if "TAG" in texto else '#ecf0f1'
        img = Image.new('RGBA', (size, size), color=color_bg)
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, size-1, size-1], outline='#bdc3c7')
        palavras = texto.replace("TAG_", "").split()
        if palavras:
            draw.text((2, size//3), palavras[0][:4], fill='white' if "TAG" in texto else 'black')
        return QPixmap.fromImage(QImage(img.tobytes("raw", "RGBA"), size, size, QImage.Format.Format_RGBA8888))

class GeminiWorker(QThread):
    finished_signal = pyqtSignal(str, bool, str)

    def __init__(self, image_path, output_path):
        super().__init__()
        self.image_path = image_path
        self.output_path = output_path

    def run(self):
        if not MINHA_API_KEY:
            self.finished_signal.emit("", False, "Chave API não configurada.")
            return
        try:
            genai.configure(api_key=MINHA_API_KEY)
            model = genai.GenerativeModel('models/gemini-2.5-pro')
            pil_img = Image.open(self.image_path)
            prompt = """You are a Sheet Music OCR expert. Digitize this sheet music into JSON."""
            response = model.generate_content([prompt, pil_img], generation_config=genai.types.GenerationConfig(temperature=0.1, response_mime_type="application/json"))
            with open(self.output_path, "w", encoding="utf-8") as f:
                f.write(response.text)
            self.finished_signal.emit(self.output_path, True, "Sucesso!")
        except Exception as error_msg:
            self.finished_signal.emit("", False, str(error_msg))

# ============================================================================
#                       ITENS GRÁFICOS (CENA)
# ============================================================================

class LabelItem(QGraphicsObject):
    def __init__(self, tipo, x, y, snap_enabled_callback):
        super().__init__()
        self.tipo = tipo
        self.snap_callback = snap_enabled_callback
        self.label_text = tipo.replace("TAG_", "")
        self.setPos(x, y)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self.is_hovered = False

    def boundingRect(self):
        return QRectF(0, 0, 80, 30)

    def paint(self, painter, option, widget):
        color = QColor("#3498db")
        if "CORO" in self.tipo: color = QColor("#e67e22")
        elif "FINAL" in self.tipo: color = QColor("#27ae60")
        
        if self.is_hovered:
            color = color.lighter(120)
        
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(Qt.GlobalColor.black if not self.isSelected() else Qt.GlobalColor.yellow, 1))
        painter.drawRoundedRect(self.boundingRect(), 5, 5)
        
        painter.setPen(QPen(Qt.GlobalColor.white))
        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        painter.drawText(self.boundingRect(), Qt.AlignmentFlag.AlignCenter, self.label_text)

    def hoverEnterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene() and self.snap_callback():
            grid = GLOBAL_CONFIG["SNAP_GRID"]
            return QPointF(round(value.x()/grid)*grid, round(value.y()/grid)*grid)
        return super().itemChange(change, value)

class HeaderBoxItem(QGraphicsRectItem):
    def __init__(self, rect):
        super().__init__(rect)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setBrush(QBrush(QColor(0, 120, 215, 80)))
        self.setPen(QPen(QColor(0, 120, 215), 2))
        self.tipo = "HEADER_BOX"

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        painter.setPen(QPen(Qt.GlobalColor.black))
        painter.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "CABEÇALHO")

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            snap = GLOBAL_CONFIG["SNAP_GRID"]
            return QPointF(round(value.x()/snap)*snap, round(value.y()/snap)*snap)
        return super().itemChange(change, value)

class TimeSigBoxItem(QGraphicsRectItem):
    def __init__(self, rect):
        super().__init__(rect)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setBrush(QBrush(QColor(255, 165, 0, 80)))
        self.setPen(QPen(QColor(255, 140, 0), 2))
        self.tipo = "TIMESIG_BOX"

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        painter.setPen(QPen(Qt.GlobalColor.black))
        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "COMPASSO")

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            snap = GLOBAL_CONFIG["SNAP_GRID"]
            return QPointF(round(value.x()/snap)*snap, round(value.y()/snap)*snap)
        return super().itemChange(change, value)

class NoteItem(QGraphicsObject):
    def __init__(self, tipo, x, y, snap_enabled_callback, custom_crop_params=None):
        super().__init__()
        self.tipo = tipo
        self.snap_callback = snap_enabled_callback
        self.pixmap_small = ImageCache.get_pixmap(tipo, 20)
        self.setPos(x, y)
        self.custom_crop_params = custom_crop_params 
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self.is_hovered = False

    def boundingRect(self):
        return QRectF(-150, -100, 300, 400)

    def shape(self):
        path = QPainterPath()
        path.addRect(QRectF(-20, -60, 40, 80))
        return path

    def paint(self, painter, option, widget):
        # Seleção
        if self.is_hovered or self.isSelected():
            painter.setPen(QPen(Qt.GlobalColor.yellow, 2))
            painter.drawRect(QRectF(-20, -20, 40, 40))
        
        # Marcação Central
        painter.setPen(QPen(Qt.GlobalColor.red, 2))
        y_mark = -40
        painter.drawLine(-5, -45, 5, -35)
        painter.drawLine(-5, -35, 5, -45)

        # Ícone
        if not self.pixmap_small.isNull():
            target_rect = QRectF(-10, y_mark + 10, 20, 20)
            painter.drawPixmap(target_rect.toRect(), self.pixmap_small)
        
        # Lógica Visual do Recorte (Pontilhado)
        if self.is_hovered and not any(x in self.tipo for x in ["PAUSA", "RESPIRACAO", "TAG"]):
            is_chorus_mode = False
            
            # Verifica contexto na cena para saber se é coro
            if self.scene():
                tags = [it for it in self.scene().items() if isinstance(it, LabelItem)]
                tags.sort(key=lambda item: (item.y(), item.x()))
                
                last_valid_tag = None
                for tag in tags:
                    if tag.y() < (self.y() - 50) or (abs(tag.y() - self.y()) <= 50 and tag.x() < self.x()):
                        last_valid_tag = tag
                
                if last_valid_tag and ("CORO" in last_valid_tag.tipo or "FINAL" in last_valid_tag.tipo):
                    is_chorus_mode = True

            # Define parâmetros do retângulo
            if self.custom_crop_params:
                w_box = self.custom_crop_params['w']
                h_box = self.custom_crop_params['h']
                y_box = self.custom_crop_params['y']
                color_pen = QColor(255, 0, 255) # Magenta
            elif is_chorus_mode:
                w_box = GLOBAL_CONFIG["CHORUS_WIDTH"]
                h_box = GLOBAL_CONFIG["CHORUS_HEIGHT"]
                y_box = GLOBAL_CONFIG["CHORUS_OFFSET_Y"]
                color_pen = QColor(255, 165, 0) # Laranja
            else:
                w_box = GLOBAL_CONFIG["CROP_WIDTH"]
                h_box = GLOBAL_CONFIG["CROP_HEIGHT"]
                y_box = GLOBAL_CONFIG["CROP_OFFSET_Y"]
                color_pen = QColor(0, 255, 255) # Ciano

            pen_crop = QPen(color_pen)
            pen_crop.setStyle(Qt.PenStyle.DashLine)
            pen_crop.setWidth(2)
            painter.setPen(pen_crop)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(-w_box / 2, y_box, w_box, h_box))

    def hoverEnterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            if self.snap_callback():
                grid = GLOBAL_CONFIG.get("SNAP_GRID", 20)
                x = round(value.x() / grid) * grid
                y = round(value.y() / grid) * grid
                return QPointF(x, y)
        return super().itemChange(change, value)

# ====================== GRAPHICS VIEW (CANVAS) ======================
class MusicalView(QGraphicsView):
    coords_changed = pyqtSignal(int, int)
    
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.ghost_item = None
        self.start_pos = None
        self.current_drawing_box = None

    def set_scene(self, scene):
        self.setScene(scene)
        self.reset_ghost()

    def reset_ghost(self):
        if self.ghost_item and self.scene():
            try: self.scene().removeItem(self.ghost_item)
            except: pass
        self.ghost_item = QGraphicsPixmapItem()
        self.ghost_item.setOpacity(0.7)
        self.ghost_item.setZValue(1000)
        self.ghost_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        if self.scene():
            self.scene().addItem(self.ghost_item)

    def update_ghost_icon(self, tipo):
        if self.ghost_item:
            pix = ImageCache.get_pixmap(tipo, 40 if "TAG" not in tipo else 30)
            self.ghost_item.setPixmap(pix)
            self.ghost_item.setOffset(-20, -20)

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        if self.main.snap_active.isChecked():
            grid = GLOBAL_CONFIG.get("SNAP_GRID", 20)
            pen = QPen(QColor(200, 200, 200, 50))
            pen.setStyle(Qt.PenStyle.DotLine)
            painter.setPen(pen)
            
            left = int(rect.left())
            top = int(rect.top())
            right = int(rect.right())
            bottom = int(rect.bottom())
            
            for x in range(left - (left % grid), right, grid):
                painter.drawLine(x, top, x, bottom)
            for y in range(top - (top % grid), bottom, grid):
                painter.drawLine(left, y, right, y)

    def mouseMoveEvent(self, event):
        sp = self.mapToScene(event.pos())
        self.coords_changed.emit(int(sp.x()), int(sp.y()))
        
        # Lógica de Desenho de Retângulos
        if (self.main.is_drawing_header or self.main.is_drawing_timesig) and self.start_pos:
            if not self.current_drawing_box:
                rect = QRectF(self.start_pos, sp).normalized()
                item = HeaderBoxItem(rect) if self.main.is_drawing_header else TimeSigBoxItem(rect)
                self.current_drawing_box = item
                self.scene().addItem(item)
            else:
                self.current_drawing_box.setRect(QRectF(self.start_pos, sp).normalized())
            return 

        # Fantasma
        if self.main.current_tool and self.ghost_item:
            x, y = sp.x(), sp.y()
            if self.main.snap_active.isChecked():
                grid = GLOBAL_CONFIG.get("SNAP_GRID", 20)
                x = round(x / grid) * grid
                y = round(y / grid) * grid
            self.ghost_item.setPos(x, y)
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Modo Desenho
            if self.main.is_drawing_header or self.main.is_drawing_timesig:
                self.start_pos = self.mapToScene(event.pos())
                t_type = HeaderBoxItem if self.main.is_drawing_header else TimeSigBoxItem
                # Remove anterior se existir
                for i in self.scene().items():
                    if isinstance(i, t_type): self.scene().removeItem(i)
                return

            # Adicionar Nota (se não clicar em nada ou modo contínuo)
            items = self.scene().items(self.mapToScene(event.pos()))
            real_items = [i for i in items if i != self.ghost_item and i.data(0) != "background"]
            
            if not real_items:
                self.main.add_item_at_mouse(self.mapToScene(event.pos()))
                return 
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        # Finaliza desenho de retângulo
        if (self.main.is_drawing_header or self.main.is_drawing_timesig) and self.start_pos:
            self.start_pos = None
            self.current_drawing_box = None
            self.main.is_drawing_header = False
            self.main.is_drawing_timesig = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.main.save_state()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self.main.save_state()
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        sp = self.mapToScene(event.pos())
        item = next((i for i in self.scene().items(sp) if isinstance(i, (NoteItem, LabelItem, HeaderBoxItem, TimeSigBoxItem))), None)
        
        if item:
            menu = QMenu()
            act_del = QAction("Excluir Item", self)
            act_del.triggered.connect(lambda: self.main.delete_specific_item(item))
            menu.addAction(act_del)
            
            if isinstance(item, NoteItem):
                if "TAG" not in self.main.current_tool:
                    action_swap = QAction(f"Trocar por '{self.main.current_tool}'", self)
                    action_swap.triggered.connect(lambda: self.main.swap_item_type(item))
                    menu.addSeparator()
                    menu.addAction(action_swap)

                if not any(x in item.tipo for x in ["PAUSA", "RESPIRACAO", "TAG"]):
                    menu.addSeparator()
                    act_crop = QAction("✂️ Ajustar Recorte (Sílaba)", self)
                    act_crop.triggered.connect(lambda: self.main.open_individual_crop_dialog(item))
                    menu.addAction(act_crop)
            menu.exec(event.globalPos())

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            zoom_in = event.angleDelta().y() > 0
            factor = 1.1 if zoom_in else 0.9
            self.scale(factor, factor)
            self.main.update_zoom_label(self.transform().m11())
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            self.main.delete_selected()
            return
        
        sel = self.scene().selectedItems()
        if sel:
            dx, dy = 0, 0
            if event.key() == Qt.Key.Key_Left: dx = -1
            if event.key() == Qt.Key.Key_Right: dx = 1
            if event.key() == Qt.Key.Key_Up: dy = -1
            if event.key() == Qt.Key.Key_Down: dy = 1
            
            if dx or dy:
                self.main.save_state()
                for i in sel: i.moveBy(dx, dy)
                return
        super().keyPressEvent(event)

# ====================== DIÁLOGOS ======================

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurações")
        self.resize(450, 500)
        self.layout = QVBoxLayout(self)
        tabs = QTabWidget()
        
        tab_std = QWidget(); form_std = QFormLayout(tab_std)
        self.spin_crop_y = self.add_spin(form_std, "Distância Y (Vertical):", GLOBAL_CONFIG["CROP_OFFSET_Y"])
        self.spin_crop_w = self.add_spin(form_std, "Largura do Recorte:", GLOBAL_CONFIG["CROP_WIDTH"])
        self.spin_crop_h = self.add_spin(form_std, "Altura do Recorte:", GLOBAL_CONFIG["CROP_HEIGHT"])
        tabs.addTab(tab_std, "Padrão / Versos")

        tab_chorus = QWidget(); form_chorus = QFormLayout(tab_chorus)
        self.spin_chorus_y = self.add_spin(form_chorus, "Distância Y (Coro/Final):", GLOBAL_CONFIG["CHORUS_OFFSET_Y"])
        self.spin_chorus_w = self.add_spin(form_chorus, "Largura (Coro/Final):", GLOBAL_CONFIG["CHORUS_WIDTH"])
        self.spin_chorus_h = self.add_spin(form_chorus, "Altura (Coro/Final):", GLOBAL_CONFIG["CHORUS_HEIGHT"])
        tabs.addTab(tab_chorus, "Coro / Final")

        tab_page = QWidget(); form_page = QFormLayout(tab_page)
        self.spin_zoom = QDoubleSpinBox(); self.spin_zoom.setRange(0.5, 5.0); self.spin_zoom.setSingleStep(0.1); self.spin_zoom.setValue(GLOBAL_CONFIG["CROP_ZOOM"])
        form_page.addRow(QLabel("Zoom do Texto:"), self.spin_zoom)
        self.spin_snap = self.add_spin(form_page, "Grade / Snap:", GLOBAL_CONFIG["SNAP_GRID"])
        self.spin_spacing = self.add_spin(form_page, "Espaço Notas:", GLOBAL_CONFIG["SPACING_NOTE"])
        self.spin_page_w = self.add_spin(form_page, "Largura Página:", GLOBAL_CONFIG["PAGE_WIDTH"])
        tabs.addTab(tab_page, "Página / Zoom")

        self.layout.addWidget(tabs)
        btn_box = QHBoxLayout()
        btn_save = QPushButton("Salvar e Fechar"); btn_save.clicked.connect(self.save)
        btn_cancel = QPushButton("Cancelar"); btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_save); btn_box.addWidget(btn_cancel)
        self.layout.addLayout(btn_box)

    def add_spin(self, layout, label, value):
        s = QSpinBox(); s.setRange(0, 5000); s.setValue(value); layout.addRow(QLabel(label), s); return s

    def save(self):
        GLOBAL_CONFIG["CROP_OFFSET_Y"] = self.spin_crop_y.value()
        GLOBAL_CONFIG["CROP_WIDTH"] = self.spin_crop_w.value()
        GLOBAL_CONFIG["CROP_HEIGHT"] = self.spin_crop_h.value()
        GLOBAL_CONFIG["CHORUS_OFFSET_Y"] = self.spin_chorus_y.value()
        GLOBAL_CONFIG["CHORUS_WIDTH"] = self.spin_chorus_w.value()
        GLOBAL_CONFIG["CHORUS_HEIGHT"] = self.spin_chorus_h.value()
        GLOBAL_CONFIG["CROP_ZOOM"] = self.spin_zoom.value()
        GLOBAL_CONFIG["SNAP_GRID"] = self.spin_snap.value()
        GLOBAL_CONFIG["SPACING_NOTE"] = self.spin_spacing.value()
        GLOBAL_CONFIG["PAGE_WIDTH"] = self.spin_page_w.value()
        self.accept()

class IndividualCropDialog(QDialog):
    def __init__(self, current_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajuste Individual")
        self.resize(300, 200)
        self.layout = QFormLayout(self)
        
        w = current_data.get('w', GLOBAL_CONFIG["CROP_WIDTH"])
        h = current_data.get('h', GLOBAL_CONFIG["CROP_HEIGHT"])
        y = current_data.get('y', GLOBAL_CONFIG["CROP_OFFSET_Y"])

        self.spin_w = QSpinBox(); self.spin_w.setRange(10, 500); self.spin_w.setValue(w); self.layout.addRow(QLabel("Largura:"), self.spin_w)
        self.spin_h = QSpinBox(); self.spin_h.setRange(10, 500); self.spin_h.setValue(h); self.layout.addRow(QLabel("Altura:"), self.spin_h)
        self.spin_y = QSpinBox(); self.spin_y.setRange(-100, 500); self.spin_y.setValue(y); self.layout.addRow(QLabel("Deslocamento Y:"), self.spin_y)
        
        btn_box = QHBoxLayout()
        btn_save = QPushButton("Salvar"); btn_save.clicked.connect(self.accept)
        btn_reset = QPushButton("Resetar Global"); btn_reset.clicked.connect(self.reset_global)
        btn_box.addWidget(btn_save); btn_box.addWidget(btn_reset)
        self.layout.addRow(btn_box)
        self.result_data = None
    def reset_global(self): self.result_data = None; self.accept()
    def accept(self): 
        if self.result_data is None: self.result_data = {'w': self.spin_w.value(), 'h': self.spin_h.value(), 'y': self.spin_y.value()}
        super().accept()

class PreviewDialog(QDialog):
    def __init__(self, pil_image, base_filename, main_window_ref):
        super().__init__(main_window_ref)
        self.setWindowTitle("Preview da Imagem Gerada")
        self.resize(1000, 700)
        self.pil_image = pil_image; self.base_filename = base_filename; self.main = main_window_ref; self.scale_factor = 1.0
        
        layout = QVBoxLayout(self)
        zoom_layout = QHBoxLayout()
        btn_out = QPushButton(" - "); btn_out.setFixedSize(40, 30); btn_out.clicked.connect(self.zoom_out)
        self.lbl_zoom = QLabel("100%"); self.lbl_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter); self.lbl_zoom.setFixedWidth(60)
        btn_in = QPushButton(" + "); btn_in.setFixedSize(40, 30); btn_in.clicked.connect(self.zoom_in)
        zoom_layout.addWidget(QLabel("Zoom:")); zoom_layout.addWidget(btn_out); zoom_layout.addWidget(self.lbl_zoom); zoom_layout.addWidget(btn_in); zoom_layout.addStretch(); layout.addLayout(zoom_layout)

        self.scroll_area = QScrollArea(); self.scroll_area.setWidgetResizable(True)
        self.img_label = QLabel(); self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.scroll_area.setWidget(self.img_label)
        layout.addWidget(self.scroll_area)
        self.update_image_display()
        
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancelar / Ajustar Mais"); btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("💾 Apenas Salvar Imagem"); btn_save.clicked.connect(self.save_only)
        self.btn_gemini = QPushButton("🤖 Enviar para Gemini")
        self.btn_gemini.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold; font-size: 14px; padding: 10px;")
        self.btn_gemini.clicked.connect(self.send_to_gemini)
        
        if self.main.cooldown_remaining > 0:
            self.btn_gemini.setEnabled(False)
            self.btn_gemini.setText(f"Aguarde {self.main.cooldown_remaining}s...")
        
        btn_layout.addWidget(btn_cancel); btn_layout.addWidget(btn_save); btn_layout.addWidget(self.btn_gemini)
        layout.addLayout(btn_layout)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_button_state)
        self.timer.start(1000)

    def update_image_display(self):
        if self.pil_image is None: return
        im_data = self.pil_image.convert("RGBA").tobytes("raw", "RGBA")
        qimage = QImage(im_data, self.pil_image.width, self.pil_image.height, QImage.Format.Format_RGBA8888)
        self.original_pixmap = QPixmap.fromImage(qimage)

        if self.original_pixmap.isNull(): return
        new_width = int(self.original_pixmap.width() * self.scale_factor)
        new_height = int(self.original_pixmap.height() * self.scale_factor)
        scaled_pixmap = self.original_pixmap.scaled(new_width, new_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.img_label.setPixmap(scaled_pixmap); self.lbl_zoom.setText(f"{int(self.scale_factor * 100)}%")

    def zoom_in(self): self.scale_factor *= 1.2; self.update_image_display()
    def zoom_out(self): self.scale_factor *= 0.8; self.update_image_display()
    
    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0: self.zoom_in()
            else: self.zoom_out()
            event.accept()
        else: super().wheelEvent(event)

    def update_button_state(self):
        remaining_time = self.main.cooldown_remaining
        if remaining_time > 0:
            self.btn_gemini.setEnabled(False); self.btn_gemini.setText(f"Aguarde {remaining_time}s...")
        else:
            self.btn_gemini.setEnabled(True); self.btn_gemini.setText("🤖 Enviar para Gemini")

    def save_file(self):
        save_path = os.path.join(IMG_FOLDER, f"{self.base_filename}.jpg")
        self.pil_image.convert("RGB").save(save_path, quality=95)
        return save_path

    def save_only(self): path = self.save_file(); QMessageBox.information(self, "Salvo", f"Imagem salva em:\n{path}"); self.accept()
    def send_to_gemini(self): path = self.save_file(); self.accept(); self.main.trigger_gemini_processing(path, self.base_filename)

# ====================== JANELA PRINCIPAL ======================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Editor Musical Pro V32 - Final Expandido")
        self.resize(1600, 1000)
        self.current_tool = "SEMINIMA"
        self.current_image_paths = []
        self.current_json_path = None 
        self.history = []; self.history_pos = -1; self.images_status = {} 
        self.is_drawing_header = False; self.is_drawing_timesig = False 
        
        self.cooldown_remaining = 0
        self.cooldown_timer = QTimer(self)
        self.cooldown_timer.timeout.connect(self.update_cooldown)
        self.cooldown_timer.start(1000)
        
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.generate_auto_preview)

        self.init_ui()
        self.scene = QGraphicsScene()
        self.view.set_scene(self.scene)
        self.scene.changed.connect(self.on_scene_changed)
        
        self.select_tool("SEMINIMA")
        self.refresh_playlists()
        self.setup_shortcuts()
        self.shortcut_save = QShortcut(QKeySequence("Ctrl+S"), self)
        self.shortcut_save.activated.connect(lambda: self.trigger_save("em_andamento"))

    def update_cooldown(self):
        if self.cooldown_remaining > 0: self.cooldown_remaining -= 1

    def on_scene_changed(self):
        if self.chk_auto_preview.isChecked(): self.preview_timer.start(GLOBAL_CONFIG["AUTO_PREVIEW_DELAY"])

    def generate_auto_preview(self):
        pass 

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- PAINEL ESQUERDO DUPLO ---
        left_widget = QWidget()
        self.setup_left_panel(left_widget)
        splitter.addWidget(left_widget)
        
        # --- PAINEL CENTRAL ---
        center_widget_panel = QWidget()
        self.setup_center_panel(center_widget_panel)
        splitter.addWidget(center_widget_panel)
        
        # --- PAINEL DIREITO ---
        right_widget = QWidget()
        self.setup_right_panel(right_widget)
        splitter.addWidget(right_widget)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 1)
        main_layout.addWidget(splitter)

    def setup_left_panel(self, parent_widget):
        layout = QVBoxLayout(parent_widget)
        splitter_vertical = QSplitter(Qt.Orientation.Vertical)
        
        # 1. Lista de Imagens (Cima)
        widget_images = QWidget(); layout_images = QVBoxLayout(widget_images); layout_images.setContentsMargins(0,0,0,0)
        layout_images.addWidget(QLabel("<b>IMAGENS (Arraste daqui)</b>"))
        self.list_images = ImageListWidget() 
        self.list_images.itemDoubleClicked.connect(self.start_edit_from_image)
        layout_images.addWidget(self.list_images)
        
        # 2. BOTÃO MERGE
        btn_merge = QPushButton("⬇ Criar Projeto com Selecionados")
        btn_merge.setStyleSheet("background-color: #2980b9; color: white; padding: 5px;")
        btn_merge.clicked.connect(self.merge_selected_images)
        layout_images.addWidget(btn_merge)

        # 3. Lista de Projetos (Baixo)
        widget_projects = QWidget(); layout_projects = QVBoxLayout(widget_projects); layout_projects.setContentsMargins(0,0,0,0)
        layout_projects.addWidget(QLabel("<b>PROJETOS SALVOS</b>"))
        self.list_projects = ProjectListWidget(self) 
        self.list_projects.itemDoubleClicked.connect(self.on_project_double_click) 
        layout_projects.addWidget(self.list_projects)
        
        # Botão Excluir Projeto
        btn_del_proj = QPushButton("🗑️ Excluir Projeto")
        btn_del_proj.clicked.connect(self.delete_current_project)
        btn_del_proj.setStyleSheet("background-color: #c0392b; color: white; padding: 5px;")
        layout_projects.addWidget(btn_del_proj)
        
        splitter_vertical.addWidget(widget_images)
        splitter_vertical.addWidget(widget_projects)
        layout.addWidget(splitter_vertical)
        
        btn_refresh = QPushButton("🔄 Atualizar Listas")
        btn_refresh.clicked.connect(self.refresh_playlists)
        layout.addWidget(btn_refresh)

    def setup_center_panel(self, parent_widget):
        layout = QVBoxLayout(parent_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        toolbar = QFrame()
        toolbar.setStyleSheet("background-color: #2c3e50; color: white;")
        toolbar_layout = QHBoxLayout(toolbar)
        
        self.add_btn(toolbar_layout, "Salvar", lambda: self.trigger_save("em_andamento"), "#f39c12")
        self.add_btn(toolbar_layout, "Concluir", lambda: self.trigger_save("concluido"), "#27ae60")
        
        toolbar_layout.addSpacing(20)
        
        # --- FUNÇÕES DE DESENHO (AGORA ESTÃO AQUI GARANTIDAS) ---
        self.add_btn(toolbar_layout, "Desenhar Cabeçalho", self.enable_header_drawing, "#3498db")
        self.add_btn(toolbar_layout, "Desenhar Compasso", self.enable_timesig_drawing, "#e67e22")
        
        toolbar_layout.addSpacing(20)
        
        # --- FUNÇÃO DE PREVIEW (AGORA AQUI TAMBÉM) ---
        self.add_btn(toolbar_layout, "👁️ PREVIEW", self.generate_preview, "#8e44ad")

        toolbar_layout.addSpacing(20)
        self.snap_active = QCheckBox("Snap Grid")
        self.snap_active.setChecked(True)
        self.snap_active.setStyleSheet("color: white;")
        toolbar_layout.addWidget(self.snap_active)
        
        self.chk_continuous = QCheckBox("Modo Contínuo")
        self.chk_continuous.setStyleSheet("color: white;")
        toolbar_layout.addWidget(self.chk_continuous)
        
        self.chk_auto_preview = QCheckBox("Preview Auto")
        self.chk_auto_preview.setStyleSheet("color: white;")
        toolbar_layout.addWidget(self.chk_auto_preview)

        toolbar_layout.addStretch()
        self.lbl_zoom = QLabel("100%")
        toolbar_layout.addWidget(self.lbl_zoom)
        self.lbl_coords = QLabel("x:0 y:0")
        toolbar_layout.addWidget(self.lbl_coords)
        
        layout.addWidget(toolbar)
        self.view = MusicalView(self)
        self.view.coords_changed.connect(lambda x, y: self.lbl_coords.setText(f"x: {x} y: {y}"))
        layout.addWidget(self.view)

    def setup_right_panel(self, parent_widget):
        layout = QVBoxLayout(parent_widget)
        info_layout = QHBoxLayout()
        self.lbl_icon_preview = QLabel()
        self.lbl_icon_preview.setFixedSize(50, 50)
        self.lbl_icon_preview.setStyleSheet("border: 1px solid gray;")
        self.lbl_tool_name = QLabel("SEMINIMA")
        self.lbl_tool_name.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50;")
        info_layout.addWidget(self.lbl_icon_preview)
        info_layout.addWidget(self.lbl_tool_name)
        layout.addLayout(info_layout)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        for categoria, lista_ferramentas in FERRAMENTAS_ORGANIZADAS.items():
            group_box = QGroupBox(categoria)
            group_box.setStyleSheet("QGroupBox { font-weight: bold; color: #2c3e50; border: 1px solid #bdc3c7; margin-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px 0 3px; }")
            grid_layout = QGridLayout()
            row, col = 0, 0
            for fer in lista_ferramentas:
                btn = QPushButton()
                pix = ImageCache.get_pixmap(fer, 35)
                btn.setIcon(QIcon(pix))
                btn.setIconSize(QSize(35, 35))
                btn.setToolTip(fer)
                btn.clicked.connect(partial(self.select_tool, fer))
                btn.setFixedSize(45, 45)
                grid_layout.addWidget(btn, row, col)
                col += 1
                if col > 3:
                    col = 0
                    row += 1
            group_box.setLayout(grid_layout)
            scroll_layout.addWidget(group_box)
            
        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)
        
        self.add_side_btn(layout, "⚙️ Configurações", self.open_settings)
        self.add_side_btn(layout, "↩️ Desfazer (Ctrl+Z)", self.undo)
        self.add_side_btn(layout, "🗑️ Limpar Tudo", self.clear_all)

    def add_btn(self, layout, text, func, color):
        btn = QPushButton(text)
        btn.clicked.connect(func)
        btn.setStyleSheet(f"background-color: {color}; color: white; border: none; padding: 5px 10px; font-weight: bold;")
        layout.addWidget(btn)
        
    def add_side_btn(self, layout, text, func):
        btn = QPushButton(text)
        btn.clicked.connect(func)
        btn.setStyleSheet("padding: 8px;")
        layout.addWidget(btn)

    def setup_shortcuts(self):
        for key, tool in MAPA_ATALHOS.items():
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(partial(self.select_tool, tool))
            
        QShortcut(QKeySequence("Delete"), self).activated.connect(self.delete_selected)
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self.undo)
        QShortcut(QKeySequence("Ctrl+0"), self).activated.connect(lambda: self.view.resetTransform())

    # --- LÓGICA DE NEGÓCIO ---

    def create_project_from_image_drop(self, file_list):
        first_file = file_list[0]
        suggestion = os.path.splitext(first_file)[0]
        new_name, ok = QInputDialog.getText(self, "Novo Projeto", "Nome do Hino:", text=suggestion)
        if not ok or not new_name: return

        json_path = os.path.join(JSON_FOLDER, new_name + ".json")
        if os.path.exists(json_path):
            QMessageBox.warning(self, "Erro", "Já existe um projeto com este nome!")
            return

        full_paths = [os.path.join(IMG_FOLDER, f) for f in file_list]
        self.current_image_paths = full_paths
        self.current_json_path = json_path
        self.save_state()
        
        data = {
            "imagem_fundo": full_paths[0],
            "imagens": full_paths,
            "status": "em_andamento",
            "notas": [],
            "configuracoes": GLOBAL_CONFIG
        }
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=4)
        
        self.load_images_to_scene(full_paths)
        self.refresh_playlists()
        self.statusBar().showMessage(f"Projeto '{new_name}' criado!", 3000)

    def merge_selected_images(self):
        items = self.list_images.selectedItems()
        if not items:
            QMessageBox.warning(self, "Aviso", "Selecione pelo menos uma imagem na lista acima.")
            return
        file_list = [clean_filename(i.text()) for i in items]
        self.create_project_from_image_drop(file_list)

    def start_edit_from_image(self, item):
        filename = clean_filename(item.text())
        path = os.path.join(IMG_FOLDER, filename)
        self.current_json_path = None 
        if os.path.exists(path):
            self.load_images_to_scene([path])
            self.statusBar().showMessage(f"Editando: {filename} (Novo)", 5000)
        else:
            QMessageBox.warning(self, "Erro", f"Imagem não encontrada:\n{path}")

    def on_project_double_click(self, item):
        fname = clean_filename(item.text())
        path = os.path.join(JSON_FOLDER, fname)
        if os.path.exists(path):
            self.current_json_path = path
            with open(path, 'r') as f:
                d = json.load(f)
                imgs = d.get('imagens')
                single = d.get('imagem_fundo')
                if imgs: self.current_image_paths = [i for i in imgs if i]
                elif single: self.current_image_paths = [single]
                else: self.current_image_paths = []

                if 'configuracoes' in d: GLOBAL_CONFIG.update(d['configuracoes'])
                notas_data = d.get('notas', d.get('data', []))
                self.load_scene_data(notas_data)

    def rename_project(self, item):
        old_name = clean_filename(item.text())
        old_path = os.path.join(JSON_FOLDER, old_name)
        new_name, ok = QInputDialog.getText(self, "Renomear", "Novo nome (com .json):", text=old_name)
        if ok and new_name:
            if not new_name.endswith(".json"): new_name += ".json"
            new_path = os.path.join(JSON_FOLDER, new_name)
            try:
                os.rename(old_path, new_path)
                if self.current_json_path == old_path: self.current_json_path = new_path
                self.refresh_playlists()
            except Exception as e:
                QMessageBox.critical(self, "Erro", str(e))

    def delete_current_project(self):
        item = self.list_projects.currentItem()
        if not item: return
        fname = clean_filename(item.text())
        path = os.path.join(JSON_FOLDER, fname)
        if QMessageBox.question(self, "Excluir", f"Excluir '{fname}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            try:
                os.remove(path)
                self.refresh_playlists()
            except Exception as e:
                QMessageBox.critical(self, "Erro", str(e))

    def refresh_playlists(self):
        # 1. Mapa de Status das Imagens
        status_map = {}
        if os.path.exists(JSON_FOLDER):
            for f_json in glob.glob(str(JSON_FOLDER / "*.json")):
                try:
                    with open(f_json, 'r', encoding='utf-8') as file:
                        data = json.load(file)
                        proj_status = data.get('status', 'em_andamento')
                        
                        imgs = [os.path.basename(i) for i in data.get('imagens', []) if i]
                        single = data.get('imagem_fundo')
                        if single: imgs.append(os.path.basename(single))
                        
                        for img_name in imgs:
                            if status_map.get(img_name) != 'concluido':
                                status_map[img_name] = proj_status
                except: pass

        # 2. Lista de Imagens (Cima)
        self.list_images.clear()
        if os.path.exists(IMG_FOLDER):
            def natural_keys(text): return [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', text)]
            arquivos = sorted([f for f in os.listdir(IMG_FOLDER) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))], key=natural_keys)
            for f in arquivos:
                item = QListWidgetItem(f)
                status = status_map.get(f)
                
                if status == "concluido":
                    item.setForeground(QBrush(QColor("#27ae60"))) # Verde
                    item.setBackground(QBrush(QColor("#e8f8f5")))
                    item.setText(f"✅ {f}")
                elif status == "em_andamento":
                    item.setForeground(QBrush(QColor("#2980b9"))) # Azul
                    item.setText(f"📂 {f}")
                
                self.list_images.addItem(item)

        # 3. Lista de Projetos (Baixo)
        self.list_projects.clear()
        if os.path.exists(JSON_FOLDER):
            def natural_keys(text): return [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', text)]
            arquivos_json = sorted(glob.glob(str(JSON_FOLDER / "*.json")), key=natural_keys)
            for f_path in arquivos_json:
                nome = os.path.basename(f_path)
                item = QListWidgetItem(nome)
                try:
                    with open(f_path, 'r', encoding='utf-8') as arq:
                        st = json.load(arq).get("status", "em_andamento")
                        if st == "concluido": 
                            item.setText(f"✅ {nome}")
                            item.setForeground(QBrush(QColor("#27ae60")))
                        else: 
                            item.setText(f"🚧 {nome}")
                            item.setForeground(QBrush(QColor("#d35400")))
                except: 
                    item.setText(f"❓ {nome}")
                self.list_projects.addItem(item)

    def load_images_to_scene(self, paths):
        self.scene.clear()
        self.current_image_paths = paths
        y_offset = 0
        for p in paths:
            if not p or not os.path.exists(p): 
                print(f"AVISO: Imagem não encontrada: {p}")
                continue
            
            pix = QPixmap(p)
            item = self.scene.addPixmap(pix)
            item.setZValue(-100)
            item.setPos(0, y_offset)
            y_offset += pix.height() + 20
            
            line = self.scene.addLine(0, y_offset - 10, pix.width(), y_offset - 10, QPen(Qt.GlobalColor.black, 2))
            line.setZValue(-99)
            
        self.scene.setSceneRect(self.scene.itemsBoundingRect())
        self.history = []
        self.view.reset_ghost()
        self.view.update_ghost_icon(self.current_tool)
        self.update_title()

    def add_item_at_mouse(self, p):
        x, y = p.x(), p.y()
        if self.snap_active.isChecked():
            g = GLOBAL_CONFIG.get("SNAP_GRID", 20)
            x = round(x/g)*g
            y = round(y/g)*g
        
        if "TAG" in self.current_tool:
            item = LabelItem(self.current_tool, x, y, self.snap_active.isChecked)
        else:
            item = NoteItem(self.current_tool, x, y, self.snap_active.isChecked)
        
        self.scene.addItem(item)
        if not self.chk_continuous.isChecked(): pass 

    def select_tool(self, tool_name):
        self.current_tool = tool_name
        self.lbl_tool_name.setText(tool_name)
        self.lbl_icon_preview.setPixmap(ImageCache.get_pixmap(tool_name, 35))
        self.view.update_ghost_icon(tool_name)
        self.is_drawing_header = False
        self.is_drawing_timesig = False
        self.view.setCursor(Qt.CursorShape.ArrowCursor)

    def enable_header_drawing(self):
        self.is_drawing_header = True
        self.is_drawing_timesig = False
        self.view.setCursor(Qt.CursorShape.CrossCursor)
        self.statusBar().showMessage("Desenhando Cabeçalho...")

    def enable_timesig_drawing(self):
        self.is_drawing_timesig = True
        self.is_drawing_header = False
        self.view.setCursor(Qt.CursorShape.CrossCursor)
        self.statusBar().showMessage("Desenhando Compasso...")

    def open_settings(self):
        SettingsDialog(self).exec()
        self.view.viewport().update()
        self.scene.update()
    
    def generate_preview(self):
        pil_image = self.render_final_image()
        if not pil_image:
            QMessageBox.warning(self, "Aviso", "Nada para gerar.")
            return
        base_name = "preview"
        if self.current_json_path:
            base_name = os.path.splitext(os.path.basename(self.current_json_path))[0]
        PreviewDialog(pil_image, base_name, self).exec()

    def render_final_image(self):
        state = self.get_current_state()
        if not state: return None
        state.sort(key=lambda k: (k.get('y',0), k.get('x',0)))

        PAGE_W = GLOBAL_CONFIG["PAGE_WIDTH"]
        SPACING = GLOBAL_CONFIG["SPACING_NOTE"]
        CROP_ZOOM = GLOBAL_CONFIG["CROP_ZOOM"]
        MARGIN_R = GLOBAL_CONFIG["RIGHT_MARGIN"]
        PAD_B = GLOBAL_CONFIG["BOTTOM_PADDING"]
        
        header_rect = None
        timesig_rect = None
        for item in self.scene.items():
            if isinstance(item, HeaderBoxItem):
                header_rect = (item.x(), item.y(), item.x()+item.rect().width(), item.y()+item.rect().height())
            elif isinstance(item, TimeSigBoxItem):
                timesig_rect = (item.x(), item.y(), item.x()+item.rect().width(), item.y()+item.rect().height())

        W, H = PAGE_W, max(4000, len(self.current_image_paths)*4000)
        img_out = Image.new('RGB', (W, H), 'white')
        draw = ImageDraw.Draw(img_out)
        
        try:
            font_note = ImageFont.truetype("arial.ttf", 18)
            font_tag = ImageFont.truetype("arial.ttf", 22)
        except:
            font_note = ImageFont.load_default()
            font_tag = ImageFont.load_default()
        
        src_imgs = []
        try:
            src_imgs = [Image.open(p).convert("RGBA") for p in self.current_image_paths if os.path.exists(p)]
        except: return None
        if not src_imgs: return None

        header_h_pasted = 0
        if src_imgs and header_rect:
            img = src_imgs[0]; x1, y1, x2, y2 = map(int, header_rect)
            if x2 > x1 and y2 > y1:
                crop = img.crop((max(0, x1), max(0, y1), min(img.width, x2), min(img.height, y2)))
                nw, nh = int(crop.width * CROP_ZOOM), int(crop.height * CROP_ZOOM)
                crop = crop.resize((nw, nh), Image.Resampling.LANCZOS)
                crop = ImageOps.grayscale(ImageEnhance.Contrast(crop).enhance(2.0)).convert("RGB")
                img_out.paste(crop, (int((W - nw)//2), 0))
                header_h_pasted = nh
        
        cy = header_h_pasted + 100
        cx = 100
        row_h = 450
        last_y = state[0]['y'] if state else 0
        
        if src_imgs and timesig_rect:
            img = src_imgs[0]; x1, y1, x2, y2 = map(int, timesig_rect)
            if x2 > x1 and y2 > y1:
                crop = img.crop((max(0, x1), max(0, y1), min(img.width, x2), min(img.height, y2)))
                nw, nh = int(crop.width * CROP_ZOOM), int(crop.height * CROP_ZOOM)
                crop = ImageOps.grayscale(ImageEnhance.Contrast(crop.resize((nw, nh), Image.Resampling.LANCZOS)).enhance(2.0)).convert("RGB")
                img_out.paste(crop, (cx, int(cy - nh//2)))
                cx += nw + 50
        
        is_chorus_mode = False
        for item in state:
            if item['type'] == 'HEADER' or item['type'] == 'TIME': continue
            if item['y'] > last_y + 150:
                cy += row_h; cx = 100; last_y = item['y']
            
            if item['type'] == 'TAG':
                txt = item['t'].replace("TAG_", "")
                if "CORO" in txt or "FINAL" in txt: is_chorus_mode = True
                else: is_chorus_mode = False
                
                bg = "#3498db"
                if "CORO" in txt: bg = "#e67e22"
                elif "FINAL" in txt: bg = "#27ae60"
                
                draw.rectangle([cx, cy-20, cx+100, cy+20], fill=bg)
                bbox = draw.textbbox((0, 0), txt, font=font_tag)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                draw.text((cx + (100 - tw)/2, cy - 20 + (40 - th)/2 - 2), txt, fill="white", font=font_tag)
                
                cx += GLOBAL_CONFIG["SPACING_TAG"]
            else:
                dname = item['t'].replace("_", " ").title()
                try: draw.text((cx, cy-70), dname, fill="black", font=font_note, anchor="mb")
                except: draw.text((cx-30, cy-90), dname, fill="black", font=font_note)

                if not any(x in item['t'] for x in ["PAUSA", "RESPIRACAO"]):
                    if 'cp' in item:
                        lw, lh, ly = item['cp']['w'], item['cp']['h'], item['cp']['y']
                    elif is_chorus_mode:
                        lw, lh, ly = GLOBAL_CONFIG["CHORUS_WIDTH"], GLOBAL_CONFIG["CHORUS_HEIGHT"], GLOBAL_CONFIG["CHORUS_OFFSET_Y"]
                    else:
                        lw, lh, ly = GLOBAL_CONFIG["CROP_WIDTH"], GLOBAL_CONFIG["CROP_HEIGHT"], GLOBAL_CONFIG["CROP_OFFSET_Y"]

                    ac_y = 0; src = None; rel_y = 0
                    for si in src_imgs:
                        if ac_y <= item['y'] < ac_y + si.height + 20:
                            src = si; rel_y = item['y'] - ac_y; break
                        ac_y += si.height + 20
                    
                    if src:
                        x1 = max(0, int(item['x'] - lw//2))
                        y1 = max(0, int(rel_y + ly))
                        x2 = min(src.width, int(item['x'] + lw//2))
                        y2 = min(src.height, int(rel_y + ly + lh))
                        if x2 > x1 and y2 > y1:
                            cr = src.crop((x1, y1, x2, y2))
                            nw, nh = int(cr.width * CROP_ZOOM), int(cr.height * CROP_ZOOM)
                            cr = cr.resize((nw, nh), Image.Resampling.LANCZOS)
                            cr = ImageEnhance.Contrast(cr).enhance(1.5)
                            img_out.paste(cr, (int(cx - nw//2), int(cy + 65)))
                
                cx += SPACING
            
            if cx > W - MARGIN_R: cx = 100; cy += row_h

        bbox = ImageOps.invert(img_out.convert('RGB')).getbbox()
        if bbox:
            img_out = img_out.crop((0, 0, W, min(H, bbox[3] + PAD_B)))
            
        return img_out

    def get_current_state(self):
        raw = []
        for i in self.scene.items():
            if isinstance(i, (NoteItem, LabelItem)):
                d = {'type': 'NOTE' if isinstance(i, NoteItem) else 'TAG', 't': i.tipo, 'x': i.x(), 'y': i.y()}
                if hasattr(i, 'custom_crop_params') and i.custom_crop_params: d['cp'] = i.custom_crop_params
                raw.append(d)
            elif isinstance(i, HeaderBoxItem): raw.append({'type': 'HEADER', 'r': i.rect().getRect(), 'x': i.x(), 'y': i.y()})
            elif isinstance(i, TimeSigBoxItem): raw.append({'type': 'TIME', 'r': i.rect().getRect(), 'x': i.x(), 'y': i.y()})
        return raw

    def load_scene_data(self, data):
        self.scene.clear(); self.load_images_to_scene(self.current_image_paths)
        for d in data:
            if 'type' not in d:
                t = d.get('tipo', '')
                if "HEADER_BOX" in t: d['type']='HEADER'; d['r']=(0,0,d['w'],d['h']); d['x']=d['x']; d['y']=d['y']
                elif "TIMESIG_BOX" in t: d['type']='TIME'; d['r']=(0,0,d['w'],d['h']); d['x']=d['x']; d['y']=d['y']
                elif "TAG" in t: d['type']='TAG'; d['t']=t
                else: d['type']='NOTE'; d['t']=t
            
            if d['type'] == 'NOTE':
                cp = d.get('cp'); 
                if not cp and 'custom_w' in d: cp = {'w': d['custom_w'], 'h': d['custom_h'], 'y': d['custom_y']}
                it = NoteItem(d['t'], d['x'], d['y'], self.snap_active.isChecked, cp); self.scene.addItem(it)
            elif d['type'] == 'TAG': it = LabelItem(d['t'], d['x'], d['y'], self.snap_active.isChecked); self.scene.addItem(it)
            elif d['type'] == 'HEADER': 
                it = HeaderBoxItem(QRectF(*d['r']))
                if 'pos' in d: it.setPos(*d['pos'])
                else: it.setPos(d['x'], d['y'])
                self.scene.addItem(it)
            elif d['type'] == 'TIME': 
                it = TimeSigBoxItem(QRectF(*d['r']))
                if 'pos' in d: it.setPos(*d['pos'])
                else: it.setPos(d['x'], d['y'])
                self.scene.addItem(it)

    def trigger_save(self, s):
        if not self.current_image_paths: return
        if not self.current_json_path:
            suggestion = ""
            if self.current_image_paths: suggestion = os.path.splitext(os.path.basename(self.current_image_paths[0]))[0]
            name, ok = QInputDialog.getText(self, "Salvar", "Nome do Arquivo:", text=suggestion)
            if not ok: return
            self.current_json_path = os.path.join(JSON_FOLDER, name + ".json")
            
        data = {"imagem_fundo": self.current_image_paths[0] if self.current_image_paths else "", "imagens": self.current_image_paths, "status": s, "notas": self.get_current_state(), "configuracoes": GLOBAL_CONFIG}
        with open(self.current_json_path, 'w') as f: json.dump(data, f, indent=4)
        self.refresh_playlists(); self.statusBar().showMessage("Salvo!", 2000)

    def delete_current_project(self):
        item = self.list_projects.currentItem()
        if not item: return
        fname = clean_filename(item.text())
        path = os.path.join(JSON_FOLDER, fname)
        if QMessageBox.question(self, "Excluir", f"Excluir '{fname}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            try: os.remove(path); self.refresh_playlists()
            except Exception as e: QMessageBox.critical(self, "Erro", str(e))

    def trigger_gemini_processing(self, path, name):
        self.worker = GeminiWorker(path, os.path.join(OUTPUT_FOLDER, name+".json"))
        self.worker.finished_signal.connect(lambda p,s,m: QMessageBox.information(self, "Fim", m))
        self.worker.start()

    def delete_selected(self): [self.scene.removeItem(i) for i in self.scene.selectedItems()]; self.save_state()
    def save_state(self): self.history.append(self.get_current_state()); self.history_pos+=1
    def undo(self): 
        if self.history_pos > 0: self.history_pos-=1; self.load_scene_data(self.history[self.history_pos])
    def clear_all(self): self.scene.clear(); self.load_images_to_scene(self.current_image_paths)
    def update_title(self): self.setWindowTitle(f"Editor V32 - {len(self.scene.items())} itens")
    def delete_specific_item(self, item): self.scene.removeItem(item)
    def swap_item_type(self, item): x,y=item.x(),item.y(); self.scene.removeItem(item); self.add_item_at_mouse(QPointF(x,y))
    def open_individual_crop_dialog(self, item): d = IndividualCropDialog(item.custom_crop_params or {}, self); d.exec(); item.custom_crop_params=d.result_data; item.update()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())