import sys
import os
import json
import glob
from functools import partial

from PyQt6.QtWidgets import (QApplication, QMainWindow, QGraphicsView, QGraphicsScene, 
                             QGraphicsItem, QGraphicsPixmapItem, QGraphicsRectItem, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QCheckBox, QLabel, QScrollArea, 
                             QFrame, QFileDialog, QMessageBox, QMenu, QGraphicsObject,
                             QListWidget, QListWidgetItem, QInputDialog, QSplitter, 
                             QDialog, QFormLayout, QSpinBox, QDoubleSpinBox)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QSize, QEvent
from PyQt6.QtGui import (QPixmap, QPainter, QPen, QColor, QAction, 
                         QTransform, QImage, QWheelEvent, QIcon, QFont, QBrush, QMouseEvent, QPainterPath, QKeySequence, QShortcut)

# Importações para processamento de imagem
from PIL import Image, ImageDraw, ImageEnhance, ImageOps, ImageFont
from pathlib import Path

# Pega a pasta onde ESTE arquivo .py está salvo
BASE_DIR = Path(__file__).parent.resolve()

# ====================== CONFIGURAÇÃO DE DIRETÓRIOS ======================
IMG_FOLDER = BASE_DIR / "data" / "imagens_dev"
JSON_FOLDER = BASE_DIR / "data" / "json_notas"
ICONS_FOLDER = BASE_DIR / "data" / "Notas_Musicais"

# Garante que as pastas existam
os.makedirs(IMG_FOLDER, exist_ok=True)
os.makedirs(JSON_FOLDER, exist_ok=True)
os.makedirs(ICONS_FOLDER, exist_ok=True)

print(f"Diretório de Ícones: {ICONS_FOLDER}")

# ====================== CONSTANTES GLOBAIS ======================
GLOBAL_CONFIG = {
    "CROP_OFFSET_Y": 40,    
    "CROP_WIDTH": 60,       
    "CROP_HEIGHT": 90,
    "CROP_ZOOM": 1.3,       
    "SPACING_NOTE": 160,    
    "SPACING_TAG": 220,     
    "PAGE_WIDTH": 2000,     
    "RIGHT_MARGIN": 150,
    "BOTTOM_PADDING": 50,
    "SNAP_GRID": 20
}

VALORES_NOTAS = [
    "SEMIBREVE", "MINIMA", "MINIMA PONTUADA",
    "SEMINIMA", "SEMINIMA PONTUADA",
    "COLCHEIA", "COLCHEIA PONTUADA",
    "SEMICOLCHEIA", "SEMICOLCHEIA PONTUADA",
    "PAUSA SEMIBREVE", "PAUSA MINIMA", "PAUSA SEMINIMA", 
    "PAUSA COLCHEIA", "PAUSA SEMICOLCHEIA",
    "RESPIRACAO CURTA", "RESPIRACAO LONGA",
    "FERMATA MINIMA", "FERMATA COLCHEIA", "FERMATA SEMINIMA"
]

TAGS_ESTRUTURA = ["TAG_VERSO", "TAG_CORO", "TAG_FINAL"]

PASSO_SNAP = 20
MAX_HIST = 50

# ====================== JANELA DE CONFIGURAÇÕES ======================
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurações de Exportação")
        self.resize(400, 450)
        self.layout = QFormLayout(self)

        self.layout.addRow(QLabel("<b>--- Ajuste de Recorte (Sílabas) ---</b>"))
        self.spin_crop_y = self.add_spin("Distância Y (Vertical):", GLOBAL_CONFIG["CROP_OFFSET_Y"], 0, 200)
        self.spin_crop_w = self.add_spin("Largura do Recorte:", GLOBAL_CONFIG["CROP_WIDTH"], 20, 300)
        self.spin_crop_h = self.add_spin("Altura do Recorte:", GLOBAL_CONFIG["CROP_HEIGHT"], 20, 300)
        
        self.spin_zoom = QDoubleSpinBox()
        self.spin_zoom.setRange(0.5, 5.0)
        self.spin_zoom.setSingleStep(0.1)
        self.spin_zoom.setValue(GLOBAL_CONFIG["CROP_ZOOM"])
        self.layout.addRow(QLabel("Zoom do Texto/Cabeçalho (Multiplicador):"), self.spin_zoom)
        
        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine); self.layout.addRow(line)

        self.layout.addRow(QLabel("<b>--- Ajuste da Página ---</b>"))
        self.spin_snap = self.add_spin("Grade / Snap (Pixels):", GLOBAL_CONFIG["SNAP_GRID"], 1, 100)
        self.spin_spacing = self.add_spin("Espaço entre Notas:", GLOBAL_CONFIG["SPACING_NOTE"], 50, 400)
        self.spin_page_w = self.add_spin("Largura da Página:", GLOBAL_CONFIG["PAGE_WIDTH"], 1000, 5000)
        self.spin_bottom_pad = self.add_spin("Margem Inferior (Fim):", GLOBAL_CONFIG["BOTTOM_PADDING"], 0, 500)
        
        btn_box = QHBoxLayout()
        btn_save = QPushButton("Salvar e Atualizar"); btn_save.clicked.connect(self.save_settings)
        btn_cancel = QPushButton("Cancelar"); btn_cancel.clicked.connect(self.reject)
        
        btn_box.addWidget(btn_save)
        btn_box.addWidget(btn_cancel)
        self.layout.addRow(btn_box)

    def add_spin(self, label, value, vmin, vmax):
        spin = QSpinBox()
        spin.setRange(vmin, vmax)
        spin.setValue(value)
        self.layout.addRow(QLabel(label), spin)
        return spin

    def save_settings(self):
        GLOBAL_CONFIG["CROP_OFFSET_Y"] = self.spin_crop_y.value()
        GLOBAL_CONFIG["CROP_WIDTH"] = self.spin_crop_w.value()
        GLOBAL_CONFIG["CROP_HEIGHT"] = self.spin_crop_h.value()
        GLOBAL_CONFIG["CROP_ZOOM"] = self.spin_zoom.value()
        GLOBAL_CONFIG["SNAP_GRID"] = self.spin_snap.value()
        GLOBAL_CONFIG["SPACING_NOTE"] = self.spin_spacing.value()
        GLOBAL_CONFIG["PAGE_WIDTH"] = self.spin_page_w.value()
        GLOBAL_CONFIG["BOTTOM_PADDING"] = self.spin_bottom_pad.value()
        self.accept()

# ====================== CACHE DE IMAGEM ======================
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
                pixmap = pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                cls._cache[key] = pixmap
                return pixmap
        
        pixmap = cls._generate_fallback(tipo, size)
        cls._cache[key] = pixmap
        return pixmap

    @staticmethod
    def _generate_fallback(texto, size):
        color_bg = '#3498db' if "TAG" in texto else '#ecf0f1'
        color_outline = '#2980b9' if "TAG" in texto else '#bdc3c7'
        color_text = 'white' if "TAG" in texto else 'black'

        img = Image.new('RGBA', (size, size), color=color_bg)
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, size-1, size-1], outline=color_outline)
        
        palavras = texto.replace("TAG_", "").split()
        abrev = palavras[0][:4]
        d.text((2, size//3), abrev, fill=color_text)
        
        data = img.tobytes("raw", "RGBA")
        qim = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
        return QPixmap.fromImage(qim)

# ====================== ITEM: CAIXA DO CABEÇALHO ======================
class HeaderBoxItem(QGraphicsRectItem):
    def __init__(self, rect):
        super().__init__(rect)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | 
                      QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setBrush(QBrush(QColor(0, 120, 215, 80))) # Azul transparente
        self.setPen(QPen(QColor(0, 120, 215), 2))
        self.tipo = "HEADER_BOX"

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        painter.setPen(QPen(Qt.GlobalColor.black))
        font = QFont("Arial", 14, QFont.Weight.Bold)
        painter.setFont(font)
        rect = self.rect()
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "CABEÇALHO")

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            new_pos = value
            snap = GLOBAL_CONFIG.get("SNAP_GRID", 20)
            if snap <= 0: snap = 1
            x = round(new_pos.x() / snap) * snap
            y = round(new_pos.y() / snap) * snap
            return QPointF(x, y)
        return super().itemChange(change, value)

# ====================== ITEM: CAIXA DO COMPASSO ======================
class TimeSigBoxItem(QGraphicsRectItem):
    def __init__(self, rect):
        super().__init__(rect)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | 
                      QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setBrush(QBrush(QColor(255, 165, 0, 80))) # Laranja transparente
        self.setPen(QPen(QColor(255, 140, 0), 2))
        self.tipo = "TIMESIG_BOX"

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        painter.setPen(QPen(Qt.GlobalColor.black))
        font = QFont("Arial", 10, QFont.Weight.Bold)
        painter.setFont(font)
        rect = self.rect()
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "COMPASSO")

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            new_pos = value
            snap = GLOBAL_CONFIG.get("SNAP_GRID", 20)
            if snap <= 0: snap = 1
            x = round(new_pos.x() / snap) * snap
            y = round(new_pos.y() / snap) * snap
            return QPointF(x, y)
        return super().itemChange(change, value)

# ====================== ITEM: NOTA ======================
class NoteItem(QGraphicsObject):
    def __init__(self, tipo, x, y, snap_enabled_callback, custom_crop_params=None):
        super().__init__()
        self.tipo = tipo
        self.snap_callback = snap_enabled_callback
        self.pixmap_main = ImageCache.get_pixmap(tipo, 40)
        self.pixmap_small = ImageCache.get_pixmap(tipo, 20)
        self.setPos(x, y)
        self.custom_crop_params = custom_crop_params 
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | 
                      QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.is_hovered = False

    def boundingRect(self):
        return QRectF(-150, -100, 300, 400)

    def shape(self):
        path = QPainterPath()
        path.addRect(QRectF(-20, -60, 40, 80))
        return path

    def paint(self, painter, option, widget):
        click_rect = QRectF(-20, -20, 40, 40)
        if self.is_hovered or self.isSelected():
            painter.setPen(QPen(Qt.GlobalColor.yellow, 2))
            painter.drawRect(click_rect)
        
        painter.setPen(QPen(Qt.GlobalColor.red, 2))
        y_mark = -40
        painter.drawLine(-5, y_mark - 5, 5, y_mark + 5)
        painter.drawLine(-5, y_mark + 5, 5, y_mark - 5)

        if not self.pixmap_small.isNull():
            target_rect = QRectF(-10, y_mark + 20 - 10, 20, 20)
            painter.drawPixmap(target_rect.toRect(), self.pixmap_small)
        
        if self.is_hovered and not any(x in self.tipo for x in ["PAUSA", "RESPIRACAO", "TAG"]):
            if self.custom_crop_params:
                w = self.custom_crop_params['w']
                h = self.custom_crop_params['h']
                off_y = self.custom_crop_params['y']
                color_pen = QColor(255, 0, 255)
            else:
                w = GLOBAL_CONFIG["CROP_WIDTH"]
                h = GLOBAL_CONFIG["CROP_HEIGHT"]
                off_y = GLOBAL_CONFIG["CROP_OFFSET_Y"]
                color_pen = QColor(0, 255, 255)

            pen_crop = QPen(color_pen)
            pen_crop.setStyle(Qt.PenStyle.DashLine)
            pen_crop.setWidth(2)
            painter.setPen(pen_crop)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            
            tl_x = -w / 2
            tl_y = off_y
            crop_rect_visual = QRectF(tl_x, tl_y, w, h)
            painter.drawRect(crop_rect_visual)

    def hoverEnterEvent(self, event):
        self.is_hovered = True; self.update(); super().hoverEnterEvent(event)
    def hoverLeaveEvent(self, event):
        self.is_hovered = False; self.update(); super().hoverLeaveEvent(event)
    
    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            if self.snap_callback():
                new_pos = value
                snap = GLOBAL_CONFIG.get("SNAP_GRID", 20)
                if snap <= 0: snap = 1
                x = round(new_pos.x() / snap) * snap
                y = round(new_pos.y() / snap) * snap
                return QPointF(x, y)
        return super().itemChange(change, value)

# ====================== ITEM: ETIQUETA ======================
class LabelItem(QGraphicsObject):
    def __init__(self, tipo, x, y, snap_enabled_callback):
        super().__init__()
        self.tipo = tipo
        self.snap_callback = snap_enabled_callback
        self.label_text = tipo.replace("TAG_", "")
        self.setPos(x, y)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.is_hovered = False

    def boundingRect(self):
        return QRectF(0, 0, 80, 30)

    def shape(self):
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def paint(self, painter, option, widget):
        rect = self.boundingRect()
        color = QColor("#3498db") if not self.isSelected() else QColor("#f1c40f")
        if self.is_hovered:
            color = color.lighter(120)
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.drawRoundedRect(rect, 5, 5)
        painter.setPen(QPen(Qt.GlobalColor.white if not self.isSelected() else Qt.GlobalColor.black))
        font = QFont("Arial", 10, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.label_text)

    def hoverEnterEvent(self, event):
        self.is_hovered = True; self.update(); super().hoverEnterEvent(event)
    def hoverLeaveEvent(self, event):
        self.is_hovered = False; self.update(); super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            if self.snap_callback():
                new_pos = value
                snap = GLOBAL_CONFIG.get("SNAP_GRID", 20)
                if snap <= 0: snap = 1
                x = round(new_pos.x() / snap) * snap
                y = round(new_pos.y() / snap) * snap
                return QPointF(x, y)
        return super().itemChange(change, value)

# ====================== JANELA DE AJUSTE INDIVIDUAL ======================
class IndividualCropDialog(QDialog):
    def __init__(self, current_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajuste Individual de Recorte")
        self.resize(300, 200)
        self.layout = QFormLayout(self)
        
        w = current_data.get('w', GLOBAL_CONFIG["CROP_WIDTH"])
        h = current_data.get('h', GLOBAL_CONFIG["CROP_HEIGHT"])
        y = current_data.get('y', GLOBAL_CONFIG["CROP_OFFSET_Y"])

        self.spin_w = QSpinBox(); self.spin_w.setRange(10, 500); self.spin_w.setValue(w)
        self.spin_h = QSpinBox(); self.spin_h.setRange(10, 500); self.spin_h.setValue(h)
        self.spin_y = QSpinBox(); self.spin_y.setRange(-100, 500); self.spin_y.setValue(y)

        self.layout.addRow(QLabel("Largura (Width):"), self.spin_w)
        self.layout.addRow(QLabel("Altura (Height):"), self.spin_h)
        self.layout.addRow(QLabel("Deslocamento Y:"), self.spin_y)

        btn_box = QHBoxLayout()
        btn_save = QPushButton("Aplicar"); btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancelar"); btn_cancel.clicked.connect(self.reject)
        btn_reset = QPushButton("Resetar p/ Padrão"); btn_reset.clicked.connect(self.reset_to_global)
        
        btn_box.addWidget(btn_save); btn_box.addWidget(btn_reset); btn_box.addWidget(btn_cancel)
        self.layout.addRow(btn_box)
        self.result_data = None

    def reset_to_global(self):
        self.result_data = None 
        self.accept()

    def accept(self):
        if self.result_data is not None: 
            self.result_data = {
                'w': self.spin_w.value(),
                'h': self.spin_h.value(),
                'y': self.spin_y.value()
            }
        super().accept()

# ====================== VIEW ======================
class MusicalView(QGraphicsView):
    coords_changed = pyqtSignal(int, int)

    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.ghost_item = None
        self.is_adding = False
        
        # Variáveis para desenhar retângulo
        self.start_pos = None
        self.current_drawing_box = None

    def set_scene(self, scene):
        self.setScene(scene)
        self.reset_ghost()

    def reset_ghost(self):
        if self.ghost_item and self.scene():
            try: 
                self.scene().removeItem(self.ghost_item)
            except: 
                pass
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
            grid_size = GLOBAL_CONFIG.get("SNAP_GRID", 20)
            if grid_size <= 0: grid_size = 20

            left = int(rect.left()) - (int(rect.left()) % grid_size)
            top = int(rect.top()) - (int(rect.top()) % grid_size)
            pen = QPen(QColor(200, 200, 200, 50))
            pen.setStyle(Qt.PenStyle.DotLine)
            painter.setPen(pen)
            
            x = left
            while x < int(rect.right()):
                painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
                x += grid_size
                
            y = top
            while y < int(rect.bottom()):
                painter.drawLine(int(rect.left()), y, int(rect.right()), y)
                y += grid_size

    def mouseMoveEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        self.coords_changed.emit(int(scene_pos.x()), int(scene_pos.y()))
        
        # LÓGICA DE DESENHO (Cabeçalho OU Compasso)
        if (self.main.is_drawing_header or self.main.is_drawing_timesig) and self.start_pos:
            if not self.current_drawing_box:
                rect = QRectF(self.start_pos, scene_pos).normalized()
                if self.main.is_drawing_header:
                    self.current_drawing_box = HeaderBoxItem(rect)
                else:
                    self.current_drawing_box = TimeSigBoxItem(rect)
                self.scene().addItem(self.current_drawing_box)
            else:
                self.current_drawing_box.setRect(QRectF(self.start_pos, scene_pos).normalized())
            return 

        if self.main.current_tool and self.ghost_item:
            x, y = scene_pos.x(), scene_pos.y()
            if self.main.snap_active.isChecked():
                snap = GLOBAL_CONFIG.get("SNAP_GRID", 20)
                if snap <= 0: snap = 1
                x = round(x / snap) * snap
                y = round(y / snap) * snap
            self.ghost_item.setPos(x, y)
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            
            # MODO DESENHO
            if self.main.is_drawing_header or self.main.is_drawing_timesig:
                self.start_pos = self.mapToScene(event.pos())
                
                # Remove itens antigos do mesmo tipo para ter apenas um
                target_type = HeaderBoxItem if self.main.is_drawing_header else TimeSigBoxItem
                for item in self.scene().items():
                    if isinstance(item, target_type):
                        self.scene().removeItem(item)
                return

            items = self.scene().items(self.mapToScene(event.pos()))
            real_items = [i for i in items if i != self.ghost_item and i.data(0) != "background"]
            if not real_items:
                self.is_adding = True
                self.main.add_item_at_mouse(self.mapToScene(event.pos()))
                return 
        if event.button() == Qt.MouseButton.MiddleButton:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            fake_event = QMouseEvent(QEvent.Type.MouseButtonPress, event.pos(), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            super().mousePressEvent(fake_event)
            return
        self.is_adding = False
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if (self.main.is_drawing_header or self.main.is_drawing_timesig) and self.start_pos:
            self.start_pos = None
            self.current_drawing_box = None
            self.main.is_drawing_header = False
            self.main.is_drawing_timesig = False # Reseta ambos
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.main.save_state()
            return

        if event.button() == Qt.MouseButton.MiddleButton:
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        if event.button() == Qt.MouseButton.LeftButton:
            self.main.save_state()
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        items_under_mouse = self.scene().items(scene_pos)
        target_item = None
        for item in items_under_mouse:
            if isinstance(item, (NoteItem, LabelItem, HeaderBoxItem, TimeSigBoxItem)):
                target_item = item
                break 
        if target_item:
            menu = QMenu()
            
            action_del = QAction(f"Excluir ({target_item.tipo})", self)
            action_del.triggered.connect(lambda: self.main.delete_specific_item(target_item))
            menu.addAction(action_del)
            
            if isinstance(target_item, NoteItem):
                if "TAG" not in self.main.current_tool:
                    action_swap = QAction(f"Trocar por '{self.main.current_tool}'", self)
                    action_swap.triggered.connect(lambda: self.main.swap_item_type(target_item))
                    menu.addSeparator()
                    menu.addAction(action_swap)
                
                if not any(x in target_item.tipo for x in ["PAUSA", "RESPIRACAO", "TAG"]):
                    menu.addSeparator()
                    action_crop = QAction("✂️ Ajustar Recorte Desta Nota", self)
                    action_crop.triggered.connect(lambda: self.main.open_individual_crop_dialog(target_item))
                    menu.addAction(action_crop)

            menu.exec(event.globalPos())

    def wheelEvent(self, event: QWheelEvent):
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
        
        selected_items = self.scene().selectedItems()
        if selected_items:
            dx, dy = 0, 0
            if event.key() == Qt.Key.Key_Left: dx = -1
            if event.key() == Qt.Key.Key_Right: dx = 1
            if event.key() == Qt.Key.Key_Up: dy = -1
            if event.key() == Qt.Key.Key_Down: dy = 1
            
            if dx or dy:
                self.main.save_state()
                for item in selected_items:
                    item.moveBy(dx, dy)
                return
        super().keyPressEvent(event)

# ====================== JANELA PRINCIPAL ======================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Editor Musical Pro (Recorte de Texto Automático)")
        self.resize(1600, 1000)
        self.current_tool = "SEMINIMA"
        self.current_image_paths = []
        self.current_json_path = None 
        self.history = []
        self.history_pos = -1
        self.images_status = {} 
        self.is_drawing_header = False
        self.is_drawing_timesig = False 
        
        self.init_ui()
        self.scene = QGraphicsScene()
        self.view.set_scene(self.scene)
        self.select_tool("SEMINIMA")
        self.refresh_playlist()

        self.shortcut_save = QShortcut(QKeySequence("Ctrl+S"), self)
        self.shortcut_save.activated.connect(lambda: self.trigger_save("em_andamento"))

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_box = QHBoxLayout(central_widget)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_box.addWidget(splitter)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("LISTA DE HINOS"))
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.on_playlist_click)
        left_layout.addWidget(self.list_widget)
        btn_refresh = QPushButton("Atualizar Lista")
        btn_refresh.clicked.connect(self.refresh_playlist)
        left_layout.addWidget(btn_refresh)
        splitter.addWidget(left_panel)
        splitter.setStretchFactor(0, 1)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0,0,0,0)
        
        top_bar = QFrame()
        top_bar.setStyleSheet("background-color: #2c3e50; color: white;")
        top_layout = QHBoxLayout(top_bar)
        
        self.add_btn(top_layout, "Nova Img", self.select_images, "#2980b9")
        top_layout.addSpacing(10)
        self.add_btn(top_layout, "Salvar", lambda: self.trigger_save("em_andamento"), "#f39c12")
        self.add_btn(top_layout, "✅ Concluir", lambda: self.trigger_save("concluido"), "#27ae60")
        
        top_layout.addSpacing(10)
        # BOTÕES DE DESENHO
        self.add_btn(top_layout, "🖱️ Desenhar Cabeçalho", self.enable_header_drawing, "#3498db")
        self.add_btn(top_layout, "🎼 Desenhar Compasso", self.enable_timesig_drawing, "#e67e22") # Laranja
        self.add_btn(top_layout, "⚙️ Config", self.open_settings, "#7f8c8d")
        self.add_btn(top_layout, "✂️ EXPORTAR", self.export_clean_sheet_with_crops, "#e74c3c")
        
        top_layout.addSpacing(10)
        self.add_btn(top_layout, "Limpar", self.clear_all, "#c0392b")
        self.add_btn(top_layout, "Undo", self.undo, "#7f8c8d")
        
        self.snap_active = QCheckBox("Snap")
        self.snap_active.setChecked(True)
        top_layout.addWidget(self.snap_active)

        btn_zout = QPushButton("-")
        btn_zout.clicked.connect(lambda: self.view.scale(0.9, 0.9))
        btn_zout.setFixedSize(30,25)
        top_layout.addWidget(btn_zout)
        
        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setFixedWidth(50)
        top_layout.addWidget(self.lbl_zoom)
        
        btn_zin = QPushButton("+")
        btn_zin.clicked.connect(lambda: self.view.scale(1.1, 1.1))
        btn_zin.setFixedSize(30,25)
        top_layout.addWidget(btn_zin)
        
        self.lbl_icon_preview = QLabel()
        self.lbl_icon_preview.setFixedSize(40,40)
        self.lbl_icon_preview.setStyleSheet("border: 1px solid gray;")
        
        self.lbl_tool_name = QLabel("SEMINIMA")
        self.lbl_tool_name.setStyleSheet("color: #f1c40f; font-weight: bold;")
        
        top_layout.addWidget(self.lbl_icon_preview)
        top_layout.addWidget(self.lbl_tool_name)
        top_layout.addStretch()
        
        self.lbl_coords = QLabel("x: 0 y: 0")
        top_layout.addWidget(self.lbl_coords)
        right_layout.addWidget(top_bar)

        scroll_paleta = QScrollArea()
        scroll_paleta.setFixedHeight(80)
        scroll_paleta.setWidgetResizable(True)
        
        paleta_content = QWidget()
        paleta_layout = QHBoxLayout(paleta_content)
        paleta_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.tool_buttons = {}
        for tag in TAGS_ESTRUTURA:
            self.create_palette_btn(tag, paleta_layout, is_tag=True)
            
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        paleta_layout.addWidget(line)
        
        for nota in VALORES_NOTAS:
            self.create_palette_btn(nota, paleta_layout, is_tag=False)
            
        scroll_paleta.setWidget(paleta_content)
        right_layout.addWidget(scroll_paleta)
        
        self.view = MusicalView(self)
        self.view.coords_changed.connect(lambda x, y: self.lbl_coords.setText(f"x: {x} y: {y}"))
        right_layout.addWidget(self.view)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(1, 4)

    def add_btn(self, layout, text, func, color):
        btn = QPushButton(text)
        btn.clicked.connect(func)
        btn.setStyleSheet(f"background-color: {color}; color: white; border: none; padding: 5px 10px; font-weight: bold;")
        layout.addWidget(btn)

    def create_palette_btn(self, nome, layout, is_tag):
        btn = QPushButton()
        btn.setFixedSize(60 if is_tag else 45, 45)
        pix = ImageCache.get_pixmap(nome, 35)
        btn.setIcon(QIcon(pix))
        btn.setIconSize(btn.size() * 0.8)
        btn.setToolTip(nome)
        btn.clicked.connect(partial(self.select_tool, nome))
        border_col = "#2980b9" if is_tag else "#bdc3c7"
        btn.setStyleSheet(f"background-color: #ecf0f1; border: 1px solid {border_col};")
        layout.addWidget(btn)
        self.tool_buttons[nome] = btn

    # ================= AÇÕES =================
    def open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self.view.viewport().update()
            self.scene.update()

    def enable_header_drawing(self):
        self.is_drawing_header = True
        self.is_drawing_timesig = False
        self.view.setCursor(Qt.CursorShape.CrossCursor)
        self.statusBar().showMessage("Modo de Desenho: Clique e arraste para definir a área do CABEÇALHO.")

    def enable_timesig_drawing(self):
        self.is_drawing_timesig = True
        self.is_drawing_header = False
        self.view.setCursor(Qt.CursorShape.CrossCursor)
        self.statusBar().showMessage("Modo de Desenho: Clique e arraste para definir a área do COMPASSO.")

    def open_individual_crop_dialog(self, note_item):
        current = note_item.custom_crop_params if note_item.custom_crop_params else {}
        dlg = IndividualCropDialog(current, self)
        if dlg.exec():
            note_item.custom_crop_params = dlg.result_data
            note_item.update() 
            self.save_state()  

    def select_images(self):
        fnames, _ = QFileDialog.getOpenFileNames(self, "Selecionar Imagens", str(IMG_FOLDER), "Images (*.png *.jpg *.jpeg)")
        if fnames:
            fnames.sort()
            self.current_json_path = None
            self.load_images_to_scene(fnames)

    def load_images_to_scene(self, paths):
        self.scene.clear()
        self.current_image_paths = paths
        y_cursor = 0
        for path in paths:
            if not os.path.exists(path): continue
            pixmap = QPixmap(path)
            bg_item = self.scene.addPixmap(pixmap)
            bg_item.setData(0, "background")
            bg_item.setZValue(-100)
            bg_item.setPos(0, y_cursor)
            y_cursor += pixmap.height() + 20
            line = self.scene.addLine(0, y_cursor - 10, pixmap.width(), y_cursor - 10, QPen(Qt.GlobalColor.black, 2))
            line.setZValue(-99)
        self.scene.setSceneRect(self.scene.itemsBoundingRect())
        self.history = []
        self.history_pos = -1
        self.view.reset_ghost()
        self.view.update_ghost_icon(self.current_tool)
        self.update_title()

    def add_item_at_mouse(self, pos):
        if not self.current_image_paths: return
        x, y = pos.x(), pos.y()
        if self.snap_active.isChecked():
            snap = GLOBAL_CONFIG.get("SNAP_GRID", 20)
            if snap <= 0: snap = 1
            x = round(x / snap) * snap
            y = round(y / snap) * snap
        if "TAG_" in self.current_tool:
            item = LabelItem(self.current_tool, x, y, self.snap_active.isChecked)
        else:
            item = NoteItem(self.current_tool, x, y, self.snap_active.isChecked)
        self.scene.addItem(item)

    # ================= GERADOR (MODIFICADO COM MELHORIAS DE ZOOM) =================
    def export_clean_sheet_with_crops(self):
        state = self.get_current_state()
        if not state:
            QMessageBox.warning(self, "Aviso", "Nada para exportar.")
            return

        # Carrega configurações
        PAGE_W = GLOBAL_CONFIG["PAGE_WIDTH"]
        SPACING = GLOBAL_CONFIG["SPACING_NOTE"]
        CROP_W = GLOBAL_CONFIG["CROP_WIDTH"]
        CROP_H = GLOBAL_CONFIG["CROP_HEIGHT"]
        CROP_OFF_Y = GLOBAL_CONFIG["CROP_OFFSET_Y"]
        CROP_ZOOM = GLOBAL_CONFIG["CROP_ZOOM"] # Fator de Zoom
        MARGIN_R = GLOBAL_CONFIG["RIGHT_MARGIN"]
        PAD_B = GLOBAL_CONFIG["BOTTOM_PADDING"]
        
        # PROCURA PELOS RETÂNGULOS ESPECIAIS NA CENA
        header_rect_coords = None
        timesig_rect_coords = None
        
        for item in self.scene.items():
            if isinstance(item, HeaderBoxItem):
                r = item.rect(); p = item.pos()
                header_rect_coords = (p.x() + r.left(), p.y() + r.top(), p.x() + r.right(), p.y() + r.bottom())
            elif isinstance(item, TimeSigBoxItem):
                r = item.rect(); p = item.pos()
                timesig_rect_coords = (p.x() + r.left(), p.y() + r.top(), p.x() + r.right(), p.y() + r.bottom())

        W, H = PAGE_W, max(4000, len(self.current_image_paths) * 4000)
        img_out = Image.new('RGB', (W, H), color='white')
        draw = ImageDraw.Draw(img_out)

        # Fontes
        try:
            font_note_name = ImageFont.truetype("arial.ttf", 18)
            font_tag = ImageFont.truetype("arial.ttf", 22) 
        except:
            font_note_name = ImageFont.load_default()
            font_tag = ImageFont.load_default()

        source_images = []
        try:
            for path in self.current_image_paths:
                src = Image.open(path).convert("RGBA")
                source_images.append(src)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao abrir imagens originais: {e}")
            return

        # ---------------------------------------------------------
        # 1. CORTA E COLA O CABEÇALHO (COM ZOOM E CONTRASTE)
        # ---------------------------------------------------------
        header_height_pasted = 0
        if source_images and header_rect_coords:
            first_img = source_images[0]
            hx1, hy1, hx2, hy2 = header_rect_coords
            hy1 = max(0, int(hy1)); hy2 = min(first_img.height, int(hy2))
            hx1 = max(0, int(hx1)); hx2 = min(first_img.width, int(hx2))
            
            if hy2 > hy1 and hx2 > hx1:
                header_crop = first_img.crop((hx1, hy1, hx2, hy2))
                
                # Aplica Zoom
                new_hw = int(header_crop.width * CROP_ZOOM)
                new_hh = int(header_crop.height * CROP_ZOOM)
                header_crop = header_crop.resize((new_hw, new_hh), Image.Resampling.LANCZOS)
                
                # Melhora qualidade para evitar borrões
                enhancer = ImageEnhance.Contrast(header_crop)
                header_crop = enhancer.enhance(2.0) # Aumenta contraste drasticamente
                header_crop = ImageOps.grayscale(header_crop).convert("RGB") # Remove ruído de cor
                
                paste_x = int((W - new_hw) // 2)
                img_out.paste(header_crop, (paste_x, 0))
                header_height_pasted = new_hh 

        start_y_offset = header_height_pasted + 100
        cursor_x = 100
        cursor_y_staff_center = start_y_offset
        row_height = 450 
        current_y_ref = state[0]['y'] if state else 0

        # Função auxiliar para desenhar linha
        def draw_staff_debug(draw_obj, center_y, width):
            pass

        draw_staff_debug(draw, cursor_y_staff_center, W)
        
        # ---------------------------------------------------------
        # 2. CORTA E COLA O COMPASSO (COM ZOOM E CONTRASTE)
        # ---------------------------------------------------------
        if source_images and timesig_rect_coords:
            first_img = source_images[0]
            tx1, ty1, tx2, ty2 = timesig_rect_coords
            
            tx1 = max(0, int(tx1)); tx2 = min(first_img.width, int(tx2))
            ty1 = max(0, int(ty1)); ty2 = min(first_img.height, int(ty2))
            
            if tx2 > tx1 and ty2 > ty1:
                ts_crop = first_img.crop((tx1, ty1, tx2, ty2))
                
                # Aplica Zoom
                new_w = int(ts_crop.width * CROP_ZOOM)
                new_h = int(ts_crop.height * CROP_ZOOM)
                ts_crop = ts_crop.resize((new_w, new_h), Image.Resampling.LANCZOS)
                
                # Melhora qualidade
                enhancer = ImageEnhance.Contrast(ts_crop)
                ts_crop = enhancer.enhance(2.0)
                ts_crop = ImageOps.grayscale(ts_crop).convert("RGB")

                dest_y_ts = int(cursor_y_staff_center - (new_h // 2))
                img_out.paste(ts_crop, (cursor_x, dest_y_ts))
                
                cursor_x += new_w + 50

        # 3. EXPORTA NOTAS E TAGS
        for item in state:
            tipo = item['tipo']
            if "HEADER" in tipo or "TIMESIG" in tipo: continue

            item_y = item['y']
            
            # Quebra de linha se a posição Y mudar muito
            if item_y > current_y_ref + 150: 
                cursor_y_staff_center += row_height
                cursor_x = 100
                current_y_ref = item_y
                draw_staff_debug(draw, cursor_y_staff_center, W)
            
            # --- LÓGICA PARA DESENHAR TAGS VISÍVEIS ---
            if "TAG" in tipo:
                tag_text = tipo.replace("TAG_", "")
                
                # Define cores baseadas no tipo de tag (Similar ao CSS visual)
                bg_color = "#3498db" # Azul padrão
                if "CORO" in tag_text: bg_color = "#e67e22" # Laranja
                elif "FINAL" in tag_text: bg_color = "#27ae60" # Verde
                elif "VERSO" in tag_text: bg_color = "#2980b9" # Azul

                # Dimensões da caixa da tag na imagem final
                tag_w, tag_h = 100, 40
                tag_x1 = cursor_x
                tag_y1 = cursor_y_staff_center - 20
                tag_x2 = tag_x1 + tag_w
                tag_y2 = tag_y1 + tag_h

                # Desenha retângulo colorido
                draw.rectangle([tag_x1, tag_y1, tag_x2, tag_y2], fill=bg_color, outline=None)
                
                # Desenha o texto centralizado na caixa
                bbox = draw.textbbox((0, 0), tag_text, font=font_tag)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
                
                text_x = tag_x1 + (tag_w - text_w) / 2
                text_y = tag_y1 + (tag_h - text_h) / 2 - 2 
                
                draw.text((text_x, text_y), tag_text, fill="white", font=font_tag)

                # Avança cursor
                espaco = GLOBAL_CONFIG["SPACING_TAG"]
                cursor_x += espaco

            # --- LÓGICA PARA DESENHAR NOTAS (SEM ÍCONES AGORA) ---
            else:
                # Desenha nome da nota (Ex: Seminima) acima
                display_name = tipo.replace("_", " ").title()
                try:
                    # Texto da nota (Seminima, etc)
                    draw.text((cursor_x, cursor_y_staff_center - 70), display_name, fill="black", font=font_note_name, anchor="mb")
                except ValueError:
                    draw.text((cursor_x - 30, cursor_y_staff_center - 90), display_name, fill="black", font=font_note_name)

                # REMOVIDO: Código que colava o ícone da nota musical
                # if os.path.exists(icon_path): ... (desativado para limpar a imagem)

                # --- LÓGICA DE RECORTE DA SÍLABA (CROP) ---
                if not any(x in tipo for x in ["PAUSA", "RESPIRACAO"]):
                    
                    local_w = item.get('custom_w', CROP_W)
                    local_h = item.get('custom_h', CROP_H)
                    local_y = item.get('custom_y', CROP_OFF_Y)

                    accumulated_y = 0
                    source_img_to_use = None
                    relative_y = 0
                    for src_img in source_images:
                        h = src_img.height
                        if accumulated_y <= item_y < (accumulated_y + h + 20):
                            source_img_to_use = src_img
                            relative_y = item_y - accumulated_y
                            break
                        accumulated_y += h + 20 
                    
                    if source_img_to_use:
                        crop_x1 = int(item['x'] - local_w // 2)
                        crop_y1 = int(relative_y + local_y)
                        crop_x2 = int(item['x'] + local_w // 2)
                        crop_y2 = int(relative_y + local_y + local_h)
                        
                        crop_x1 = max(0, crop_x1)
                        crop_y1 = max(0, crop_y1)
                        crop_x2 = min(source_img_to_use.width, crop_x2)
                        crop_y2 = min(source_img_to_use.height, crop_y2)
                        
                        if crop_x2 > crop_x1 and crop_y2 > crop_y1:
                            cropped_text = source_img_to_use.crop((crop_x1, crop_y1, crop_x2, crop_y2))
                            
                            # Zoom na sílaba
                            new_text_w = int(cropped_text.width * CROP_ZOOM)
                            new_text_h = int(cropped_text.height * CROP_ZOOM)
                            cropped_text = cropped_text.resize((new_text_w, new_text_h), Image.Resampling.LANCZOS)
                            
                            enhancer = ImageEnhance.Contrast(cropped_text)
                            cropped_text = enhancer.enhance(1.5)
                            
                            dest_x = int(cursor_x - (new_text_w // 2))
                            dest_y = int(cursor_y_staff_center + 65)
                            img_out.paste(cropped_text, (dest_x, dest_y))

                # Avança cursor da nota
                cursor_x += SPACING

            # Verifica se precisa quebrar linha horizontalmente
            if cursor_x > W - MARGIN_R:
                cursor_x = 100
                cursor_y_staff_center += row_height
                draw_staff_debug(draw, cursor_y_staff_center, W)

        # Corta espaços em branco no final da imagem gerada
        img_inverted = ImageOps.invert(img_out.convert('RGB'))
        bbox = img_inverted.getbbox()
        if bbox:
            crop_h = min(H, bbox[3] + PAD_B)
            img_out = img_out.crop((0, 0, W, crop_h))
            
        # NOME DO ARQUIVO DINÂMICO
        if self.current_json_path:
            # Usa o nome do JSON atual
            base_name = os.path.splitext(os.path.basename(self.current_json_path))[0]
        elif self.current_image_paths:
            # Fallback para o nome da primeira imagem
            base_name = os.path.splitext(os.path.basename(self.current_image_paths[0]))[0]
        else:
            base_name = "export_recorte_gemini"

        save_filename = f"{base_name}.jpg"
        save_path = os.path.join(IMG_FOLDER, save_filename)
        
        img_out.convert("RGB").save(save_path, quality=95)
        try:
            os.startfile(save_path)
        except:
            pass
        QMessageBox.information(self, "Sucesso", f"Imagem gerada com sucesso!\n{save_path}")

    # ================= ESTADO / SALVAMENTO =================
    def get_current_state(self):
        raw_items = []
        for item in self.scene.items():
            if isinstance(item, (NoteItem, LabelItem)):
                data = {"tipo": item.tipo, "x": round(item.x(), 1), "y": round(item.y(), 1)}
                if isinstance(item, NoteItem) and item.custom_crop_params:
                    data['custom_w'] = item.custom_crop_params['w']
                    data['custom_h'] = item.custom_crop_params['h']
                    data['custom_y'] = item.custom_crop_params['y']
                raw_items.append(data)
            
            if isinstance(item, HeaderBoxItem):
                r = item.rect()
                p = item.pos()
                raw_items.append({
                    "tipo": "HEADER_BOX", 
                    "x": round(p.x(), 1), "y": round(p.y(), 1),
                    "w": round(r.width(), 1), "h": round(r.height(), 1)
                })
            
            if isinstance(item, TimeSigBoxItem):
                r = item.rect()
                p = item.pos()
                raw_items.append({
                    "tipo": "TIMESIG_BOX", 
                    "x": round(p.x(), 1), "y": round(p.y(), 1),
                    "w": round(r.width(), 1), "h": round(r.height(), 1)
                })

        if not raw_items: return []
        
        notes = [i for i in raw_items if "HEADER" not in i["tipo"] and "TIMESIG" not in i["tipo"]]
        specials = [i for i in raw_items if "HEADER" in i["tipo"] or "TIMESIG" in i["tipo"]]
        
        notes.sort(key=lambda n: n['y'])
        
        sorted_notes = []
        current_line = []
        
        if notes:
            current_line.append(notes[0])
            line_y_ref = notes[0]['y']
        
        LINE_THRESHOLD = 80
        for i in range(1, len(notes)):
            it = notes[i]
            if abs(it['y'] - line_y_ref) < LINE_THRESHOLD:
                current_line.append(it)
            else:
                current_line.sort(key=lambda n: n['x'])
                sorted_notes.extend(current_line)
                current_line = [it]
                line_y_ref = it['y']
        
        if current_line:
            current_line.sort(key=lambda n: n['x'])
            sorted_notes.extend(current_line)
            
        return sorted_notes + specials

    def apply_state(self, state_list):
        for item in self.scene.items(): 
            if isinstance(item, (NoteItem, LabelItem, HeaderBoxItem, TimeSigBoxItem)):
                self.scene.removeItem(item)
        
        for data in state_list:
            tipo = data.get("tipo", "")
            
            if tipo == "HEADER_BOX":
                rect = QRectF(0, 0, data["w"], data["h"])
                box = HeaderBoxItem(rect)
                box.setPos(data["x"], data["y"])
                self.scene.addItem(box)
                continue
            
            if tipo == "TIMESIG_BOX":
                rect = QRectF(0, 0, data["w"], data["h"])
                box = TimeSigBoxItem(rect)
                box.setPos(data["x"], data["y"])
                self.scene.addItem(box)
                continue

            if "TAG_" in tipo:
                item = LabelItem(tipo, data["x"], data["y"], self.snap_active.isChecked)
            else:
                custom_params = None
                if 'custom_w' in data:
                    custom_params = {
                        'w': data['custom_w'],
                        'h': data['custom_h'],
                        'y': data['custom_y']
                    }
                item = NoteItem(tipo, data["x"], data["y"], self.snap_active.isChecked, custom_crop_params=custom_params)
            self.scene.addItem(item)
        self.update_title()

    def trigger_save(self, status):
        if not self.current_image_paths:
            QMessageBox.warning(self, "Aviso", "Nenhuma imagem carregada!")
            return
        
        save_path = None
        if self.current_json_path and os.path.exists(self.current_json_path):
            save_path = self.current_json_path
        else:
            first_img_name = os.path.basename(self.current_image_paths[0])
            default_name = os.path.splitext(first_img_name)[0]
            existing = self.find_json_for_image(first_img_name)
            if existing:
                default_name = os.path.splitext(os.path.basename(existing))[0]
            title_dialog = "Salvar Hino"
            hymn_title, ok = QInputDialog.getText(self, title_dialog, "Digite o Número ou Título:", text=default_name)
            if not ok or not hymn_title:
                return 
            clean_input = hymn_title.strip()
            if clean_input.isdigit():
                numero = int(clean_input)
                hymn_title = f"Hino_{numero:03d}"
            else:
                hymn_title = clean_input
            if not hymn_title.lower().endswith(".json"):
                hymn_title += ".json"
            save_path = os.path.join(JSON_FOLDER, hymn_title)
            self.current_json_path = save_path

        data = {
            "imagem_fundo": self.current_image_paths[0],
            "imagens_fundo": self.current_image_paths,
            "hino_titulo": os.path.basename(save_path).replace(".json", ""),
            "status": status,
            "notas": self.get_current_state()
        }
        
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            self.statusBar().showMessage(f"Salvo em: {os.path.basename(save_path)}", 3000)
            self.refresh_playlist()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao salvar: {e}")

    def on_playlist_click(self, item):
        clean_name = item.text().replace("✅ ", "").replace("⬜ ", "").replace("🚧 ", "")
        json_path = self.find_json_for_image(clean_name)
        if json_path:
            self.current_json_path = json_path
            self.load_from_json_file(json_path)
        else:
            self.current_json_path = None
            self.load_images_to_scene([os.path.join(IMG_FOLDER, clean_name)])

    def find_json_for_image(self, img_filename):
        json_files = glob.glob(os.path.join(JSON_FOLDER, "*.json"))
        candidate = None
        for jf in json_files:
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    imgs = data.get("imagens_fundo", [data.get("imagem_fundo", "")])
                    img_names = [os.path.basename(p) for p in imgs]
                    if img_filename in img_names:
                        if data.get("status") == "concluido": return jf
                        candidate = jf
            except: pass
        return candidate

    def load_from_json_file(self, json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            paths = data.get("imagens_fundo", [])
            if not paths and data.get("imagem_fundo"):
                paths = [data.get("imagem_fundo")]
            valid_paths = []
            for p in paths:
                if os.path.exists(p):
                    valid_paths.append(p)
                else:
                    local_p = os.path.join(IMG_FOLDER, os.path.basename(p))
                    if os.path.exists(local_p):
                        valid_paths.append(local_p)
            if valid_paths:
                self.load_images_to_scene(valid_paths)
                self.apply_state(data.get("notas", []))
            else:
                QMessageBox.warning(self, "Erro", "Imagens não encontradas no disco.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro JSON: {e}")

    def refresh_playlist(self):
        self.list_widget.clear()
        self.images_status = {}
        json_files = glob.glob(os.path.join(JSON_FOLDER, "*.json"))
        for jf in json_files:
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    imgs = data.get("imagens_fundo", [data.get("imagem_fundo", "")]); status = data.get("status", "em_andamento")
                    for p in imgs:
                        if not p: continue
                        bname = os.path.basename(p)
                        if bname in self.images_status:
                             if self.images_status[bname] != "concluido" and status == "concluido":
                                 self.images_status[bname] = "concluido"
                        else:
                            self.images_status[bname] = status
            except: pass
        if os.path.exists(IMG_FOLDER):
            images = [f for f in os.listdir(IMG_FOLDER) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            try:
                images.sort(key=lambda x: int(''.join(filter(str.isdigit, x))) if any(char.isdigit() for char in x) else x)
            except:
                images.sort()
            for img_name in images:
                item = QListWidgetItem(img_name)
                if img_name in self.images_status:
                    st = self.images_status[img_name]
                    if st == "concluido":
                        item.setForeground(QColor("#27ae60"))
                        item.setText(f"✅ {img_name}")
                        item.setBackground(QColor("#e8f8f5"))
                    else:
                        item.setForeground(QColor("#d35400"))
                        item.setText(f"🚧 {img_name}")
                        item.setBackground(QColor("#fef9e7"))
                else:
                    item.setForeground(QColor("black"))
                    item.setText(f"⬜ {img_name}")
                self.list_widget.addItem(item)

    def select_tool(self, nome):
        self.current_tool = nome
        self.lbl_tool_name.setText(nome)
        pix = ImageCache.get_pixmap(nome, 35)
        self.lbl_icon_preview.setPixmap(pix)
        for n, btn in self.tool_buttons.items():
            col = "#f1c40f" if n == nome else "#ecf0f1"
            border = "2px inset" if n == nome else "1px solid"
            b_col = "#2980b9" if "TAG" in n else "#bdc3c7"
            btn.setStyleSheet(f"background-color: {col}; border: {border} {b_col};")
        self.view.update_ghost_icon(nome)

    def save_state(self):
        self.history = self.history[:self.history_pos + 1]
        self.history.append(self.get_current_state())
        if len(self.history) > MAX_HIST:
            self.history.pop(0)
        else:
            self.history_pos += 1
        self.update_title()

    def undo(self):
        if self.history_pos > 0:
            self.history_pos -= 1
            self.apply_state(self.history[self.history_pos])

    def delete_selected(self):
        selected = self.scene.selectedItems()
        if not selected: return
        self.save_state()
        for item in selected:
            self.scene.removeItem(item)

    def delete_specific_item(self, item):
        self.save_state()
        self.scene.removeItem(item)

    def swap_item_type(self, item):
        self.save_state()
        x, y = item.x(), item.y()
        self.scene.removeItem(item)
        self.add_item_at_mouse(QPointF(x, y))

    def clear_all(self):
        if QMessageBox.question(self, "Limpar", "Remover tudo?") == QMessageBox.StandardButton.Yes:
            self.save_state()
            for item in self.scene.items(): 
                if isinstance(item, (NoteItem, LabelItem)):
                    self.scene.removeItem(item)

    def update_zoom_label(self, scale):
        self.lbl_zoom.setText(f"{int(scale*100)}%")

    def update_title(self):
        if not self.current_image_paths:
            t = "Sem Imagem"
        else:
            t = f"{len(self.current_image_paths)} Imagens Carregadas"
        c = sum(1 for i in self.scene.items() if isinstance(i, (NoteItem, LabelItem)))
        self.setWindowTitle(f"Editor Musical Pro - {t} ({c} itens)")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())