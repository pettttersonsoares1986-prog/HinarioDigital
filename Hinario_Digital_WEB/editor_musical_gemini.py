import sys
import os
import json
import glob
import time
from functools import partial
import io
import threading

# Importações da Interface Gráfica (PyQt6)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene, 
    QGraphicsItem, QGraphicsPixmapItem, QGraphicsRectItem, QWidget, QVBoxLayout, 
    QHBoxLayout, QPushButton, QCheckBox, QLabel, QScrollArea, 
    QFrame, QFileDialog, QMessageBox, QMenu, QGraphicsObject,
    QListWidget, QListWidgetItem, QInputDialog, QSplitter, 
    QDialog, QFormLayout, QSpinBox, QDoubleSpinBox, QProgressDialog, QTabWidget
)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QSize, QEvent, QThread, QTimer
from PyQt6.QtGui import (
    QPixmap, QPainter, QPen, QColor, QAction, 
    QTransform, QImage, QWheelEvent, QIcon, QFont, QBrush, 
    QMouseEvent, QPainterPath, QKeySequence, QShortcut
)

# Importações para processamento de imagem e Inteligência Artificial
from PIL import Image, ImageDraw, ImageEnhance, ImageOps, ImageFont
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai

# ============================================================================
#                               CONFIGURAÇÃO INICIAL
# ============================================================================

# Pega a pasta onde ESTE arquivo .py está salvo
BASE_DIR = Path(__file__).parent.resolve()

# Definição dos diretórios do projeto
IMG_FOLDER = BASE_DIR / "imagens_dev"
JSON_FOLDER = BASE_DIR / "json_notas"
ICONS_FOLDER = BASE_DIR / "Notas_Musicais"
OUTPUT_FOLDER = BASE_DIR / "output" # Pasta para JSONs brutos gerados pela IA

# Garante que as pastas existam
os.makedirs(IMG_FOLDER, exist_ok=True)
os.makedirs(JSON_FOLDER, exist_ok=True)
os.makedirs(ICONS_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Carrega API Key do arquivo .env
load_dotenv()
MINHA_API_KEY = os.getenv("GEMINI_API_KEY")

# --- CONSTANTES GLOBAIS ---
GLOBAL_CONFIG = {
    # Configuração Padrão (Usada para Versos/Estrofes)
    "CROP_OFFSET_Y": 40,    
    "CROP_WIDTH": 60,       
    "CROP_HEIGHT": 90,
    
    # Configuração Específica (Usada para Coro e Final)
    "CHORUS_OFFSET_Y": 40,
    "CHORUS_WIDTH": 50,     # Geralmente o texto do coro é mais denso
    "CHORUS_HEIGHT": 80,

    # Configurações Gerais da Página
    "CROP_ZOOM": 1.3,       # Zoom aplicado no recorte da sílaba
    "SPACING_NOTE": 160,    # Espaço horizontal entre notas na imagem gerada
    "SPACING_TAG": 220,     # Espaço horizontal após uma TAG
    "PAGE_WIDTH": 2000,     # Largura da imagem gerada
    "RIGHT_MARGIN": 150,    # Margem para quebra de linha
    "BOTTOM_PADDING": 50,
    "SNAP_GRID": 20,        # Grade de alinhamento
    "API_COOLDOWN": 40      # Tempo em segundos de espera entre envios (Free Tier)
}

VALORES_NOTAS = [
    "SEMIBREVE", "MINIMA", "MINIMA PONTUADA",
    "SEMINIMA", "SEMINIMA PONTUADA",
    "COLCHEIA", "COLCHEIA PONTUADA",
    "SEMICOLCHEIA", "SEMICOLCHEIA PONTUADA",
    
    # --- PAUSAS (INCLUINDO PONTUADAS) ---
    "PAUSA SEMIBREVE", 
    "PAUSA MINIMA", 
    "PAUSA SEMINIMA", "PAUSA SEMINIMA PONTUADA",
    "PAUSA COLCHEIA", "PAUSA COLCHEIA PONTUADA",
    "PAUSA SEMICOLCHEIA", "PAUSA SEMICOLCHEIA PONTUADA",
    
    "RESPIRACAO CURTA", "RESPIRACAO LONGA",
    "FERMATA MINIMA", "FERMATA COLCHEIA", "FERMATA SEMINIMA"
]

TAGS_ESTRUTURA = ["TAG_VERSO", "TAG_CORO", "TAG_FINAL"]

MAX_HIST = 50 # Limite de histórico para desfazer (Undo)

# ============================================================================
#                           UTILITÁRIOS (CACHE DE IMAGEM)
# ============================================================================
class ImageCache:
    """Gerencia o carregamento e cache dos ícones das notas musicais."""
    _cache = {}

    @classmethod
    def get_pixmap(cls, tipo, size=40):
        key = (tipo, size)
        if key in cls._cache:
            return cls._cache[key]

        # 1. Tenta carregar a imagem exata do disco
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
        
        # 2. LÓGICA DE PONTO AUTOMÁTICO
        if "PONTUADA" in tipo:
            tipo_base = tipo.replace(" PONTUADA", "")
            caminho_base = os.path.join(ICONS_FOLDER, f"{tipo_base.replace(' ', '_')}.png")
            
            if os.path.exists(caminho_base):
                # Carrega a base
                pixmap_base = QPixmap(caminho_base)
                if not pixmap_base.isNull():
                    pixmap_base = pixmap_base.scaled(
                        size, size, 
                        Qt.AspectRatioMode.KeepAspectRatio, 
                        Qt.TransformationMode.SmoothTransformation
                    )
                    
                    # Cria nova imagem transparente
                    imagem_com_ponto = QPixmap(pixmap_base.size())
                    imagem_com_ponto.fill(Qt.GlobalColor.transparent)
                    
                    painter = QPainter(imagem_com_ponto)
                    painter.drawPixmap(0, 0, pixmap_base)
                    
                    # Configura pincel para o ponto (preto)
                    painter.setBrush(QBrush(Qt.GlobalColor.black))
                    painter.setPen(Qt.PenStyle.NoPen)
                    
                    # Posição do ponto
                    raio_ponto = size / 9
                    x_ponto = size * 0.70
                    y_ponto = size * 0.60
                    
                    painter.drawEllipse(QPointF(x_ponto, y_ponto), raio_ponto, raio_ponto)
                    painter.end()
                    
                    cls._cache[key] = imagem_com_ponto
                    return imagem_com_ponto

        # 3. Se não existir nada, gera um quadrado colorido (fallback)
        pixmap = cls._generate_fallback(tipo, size)
        cls._cache[key] = pixmap
        return pixmap

    @staticmethod
    def _generate_fallback(texto, size):
        color_bg = '#3498db' if "TAG" in texto else '#ecf0f1'
        color_outline = '#2980b9' if "TAG" in texto else '#bdc3c7'
        color_text = 'white' if "TAG" in texto else 'black'

        img = Image.new('RGBA', (size, size), color=color_bg)
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, size-1, size-1], outline=color_outline)
        
        palavras = texto.replace("TAG_", "").split()
        if palavras:
            abrev = palavras[0][:4]
            draw.text((2, size//3), abrev, fill=color_text)
        
        data = img.tobytes("raw", "RGBA")
        qimage = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
        return QPixmap.fromImage(qimage)

# ============================================================================
#                       WORKER DO GEMINI (THREAD EM BACKGROUND)
# ============================================================================
class GeminiWorker(QThread):
    finished_signal = pyqtSignal(str, bool, str)

    def __init__(self, image_path, output_path):
        super().__init__()
        self.image_path = image_path
        self.output_path = output_path

    def run(self):
        if not MINHA_API_KEY:
            self.finished_signal.emit("", False, "ERRO: A chave API não foi encontrada no arquivo .env")
            return

        try:
            genai.configure(api_key=MINHA_API_KEY)
            model_name = 'models/gemini-2.5-pro' 
            
            config = genai.types.GenerationConfig(
                temperature=0.1,
                response_mime_type="application/json"
            )
            
            model = genai.GenerativeModel(model_name)
            
            if not os.path.exists(self.image_path):
                self.finished_signal.emit("", False, f"Imagem não encontrada: {self.image_path}")
                return

            pil_img = Image.open(self.image_path)

            prompt = """
            You are a Sheet Music OCR expert. Your goal is to digitize the sheet music into JSON.
            ### CRITICAL RULES:
            1. **Notes & Nulls:** Extract every note left-to-right. If a note has NO lyrics (slur, rest), output { "texto": null, "nota": "NoteValue" }.
            2. **Structure:** Extract verses 1, 2, 3 stacked vertically. 
            3. **Chorus:** Identify "CORO" label. Chorus must be the LAST item in 'estrofes' list with "numero": null.
            4. **Format:** Output strict JSON.
            """

            response = model.generate_content([prompt, pil_img], generation_config=config)
            texto_resultado = response.text
            json.loads(texto_resultado) # Validação

            with open(self.output_path, "w", encoding="utf-8") as f:
                f.write(texto_resultado)
            
            self.finished_signal.emit(self.output_path, True, "Extração concluída com sucesso!")

        except Exception as e:
            self.finished_signal.emit("", False, f"Erro no processamento do Gemini:\n{str(e)}")

# ============================================================================
#                       JANELA DE PREVIEW (COM ZOOM)
# ============================================================================
class PreviewDialog(QDialog):
    def __init__(self, pil_image, base_filename, main_window_ref):
        super().__init__(main_window_ref)
        self.setWindowTitle("Preview da Imagem Gerada")
        self.resize(1000, 700)
        self.pil_image = pil_image
        self.base_filename = base_filename
        self.main = main_window_ref
        self.scale_factor = 1.0
        
        layout = QVBoxLayout(self)
        zoom_layout = QHBoxLayout()
        btn_out = QPushButton(" - "); btn_out.setFixedSize(40, 30); btn_out.clicked.connect(self.zoom_out)
        self.lbl_zoom = QLabel("100%"); self.lbl_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter); self.lbl_zoom.setFixedWidth(60)
        btn_in = QPushButton(" + "); btn_in.setFixedSize(40, 30); btn_in.clicked.connect(self.zoom_in)
        zoom_layout.addWidget(QLabel("Zoom:")); zoom_layout.addWidget(btn_out); zoom_layout.addWidget(self.lbl_zoom); zoom_layout.addWidget(btn_in); zoom_layout.addStretch()
        layout.addLayout(zoom_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.img_label)
        layout.addWidget(self.scroll_area)
        
        self.update_image_display()
        
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancelar / Ajustar Mais"); btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("💾 Apenas Salvar Imagem"); btn_save.clicked.connect(self.save_only)
        self.btn_gemini = QPushButton("🤖 Enviar para Gemini")
        self.btn_gemini.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold; font-size: 14px; padding: 10px;")
        self.btn_gemini.clicked.connect(self.send_to_gemini)
        
        if self.main.cooldown_remaining > 0:
            self.btn_gemini.setEnabled(False); self.btn_gemini.setText(f"Aguarde {self.main.cooldown_remaining}s...")
        
        btn_layout.addWidget(btn_cancel); btn_layout.addWidget(btn_save); btn_layout.addWidget(self.btn_gemini)
        layout.addLayout(btn_layout)
        
        self.timer = QTimer(self); self.timer.timeout.connect(self.update_button_state); self.timer.start(1000)

    def update_image_display(self):
        im_data = self.pil_image.convert("RGBA").tobytes("raw", "RGBA")
        qimage = QImage(im_data, self.pil_image.width, self.pil_image.height, QImage.Format.Format_RGBA8888)
        self.original_pixmap = QPixmap.fromImage(qimage)

        if self.original_pixmap.isNull(): return
        
        new_width = int(self.original_pixmap.width() * self.scale_factor)
        new_height = int(self.original_pixmap.height() * self.scale_factor)
        
        scaled_pixmap = self.original_pixmap.scaled(
            new_width, new_height, 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
        self.img_label.setPixmap(scaled_pixmap)
        self.lbl_zoom.setText(f"{int(self.scale_factor * 100)}%")

    def zoom_in(self): self.scale_factor *= 1.2; self.update_image_display()
    def zoom_out(self): self.scale_factor *= 0.8; self.update_image_display()
    
    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            angle = event.angleDelta().y()
            if angle > 0: self.zoom_in()
            else: self.zoom_out()
            event.accept()
        else: super().wheelEvent(event)

    def update_button_state(self):
        remaining_time = self.main.cooldown_remaining
        if remaining_time > 0:
            self.btn_gemini.setEnabled(False)
            self.btn_gemini.setText(f"Aguarde {remaining_time}s...")
        else:
            self.btn_gemini.setEnabled(True)
            self.btn_gemini.setText("🤖 Enviar para Gemini")

    def save_file(self):
        save_path = os.path.join(IMG_FOLDER, f"{self.base_filename}.jpg")
        self.pil_image.convert("RGB").save(save_path, quality=95)
        return save_path

    def save_only(self):
        path = self.save_file(); QMessageBox.information(self, "Salvo", f"Imagem salva em:\n{path}"); self.accept()

    def send_to_gemini(self):
        path = self.save_file(); self.accept(); self.main.trigger_gemini_processing(path, self.base_filename)

# ====================== ITENS DA CENA GRÁFICA ======================

# --- LABEL MOVIDO PARA CIMA PARA SER REFERENCIADO PELA NOTA ---
class LabelItem(QGraphicsObject):
    def __init__(self, tipo, x, y, snap_enabled_callback):
        super().__init__(); self.tipo = tipo; self.snap_callback = snap_enabled_callback; self.label_text = tipo.replace("TAG_", ""); self.setPos(x, y)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True); self.is_hovered = False

    def boundingRect(self): return QRectF(0, 0, 80, 30)
    def shape(self): path = QPainterPath(); path.addRect(self.boundingRect()); return path

    def paint(self, painter, option, widget):
        rect = self.boundingRect()
        color = QColor("#e67e22") if "CORO" in self.tipo else QColor("#27ae60") if "FINAL" in self.tipo else QColor("#3498db")
        if self.is_hovered: color = color.lighter(120)
        
        if self.isSelected(): painter.setPen(QPen(Qt.GlobalColor.yellow, 2))
        else: painter.setPen(QPen(Qt.GlobalColor.black, 1))

        painter.setBrush(QBrush(color)); painter.drawRoundedRect(rect, 5, 5)
        painter.setPen(QPen(Qt.GlobalColor.white)); painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.label_text)

    def hoverEnterEvent(self, event): self.is_hovered = True; self.update(); super().hoverEnterEvent(event)
    def hoverLeaveEvent(self, event): self.is_hovered = False; self.update(); super().hoverLeaveEvent(event)
    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            if self.snap_callback(): snap = GLOBAL_CONFIG.get("SNAP_GRID", 20); x = round(value.x() / snap) * snap; y = round(value.y() / snap) * snap; return QPointF(x, y)
        return super().itemChange(change, value)

class HeaderBoxItem(QGraphicsRectItem):
    def __init__(self, rect):
        super().__init__(rect)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True); self.setBrush(QBrush(QColor(0, 120, 215, 80))); self.setPen(QPen(QColor(0, 120, 215), 2)); self.tipo = "HEADER_BOX"

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget); painter.setPen(QPen(Qt.GlobalColor.black))
        painter.setFont(QFont("Arial", 14, QFont.Weight.Bold)); painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "CABEÇALHO")

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene(): snap = GLOBAL_CONFIG.get("SNAP_GRID", 20); x = round(value.x() / snap) * snap; y = round(value.y() / snap) * snap; return QPointF(x, y)
        return super().itemChange(change, value)

class TimeSigBoxItem(QGraphicsRectItem):
    def __init__(self, rect):
        super().__init__(rect)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True); self.setBrush(QBrush(QColor(255, 165, 0, 80))); self.setPen(QPen(QColor(255, 140, 0), 2)); self.tipo = "TIMESIG_BOX"

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget); painter.setPen(QPen(Qt.GlobalColor.black))
        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold)); painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "COMPASSO")

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene(): snap = GLOBAL_CONFIG.get("SNAP_GRID", 20); x = round(value.x() / snap) * snap; y = round(value.y() / snap) * snap; return QPointF(x, y)
        return super().itemChange(change, value)

class NoteItem(QGraphicsObject):
    def __init__(self, tipo, x, y, snap_enabled_callback, custom_crop_params=None):
        super().__init__(); self.tipo = tipo; self.snap_callback = snap_enabled_callback
        self.pixmap_main = ImageCache.get_pixmap(tipo, 40); self.pixmap_small = ImageCache.get_pixmap(tipo, 20)
        self.setPos(x, y); self.custom_crop_params = custom_crop_params 
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True); self.is_hovered = False

    def boundingRect(self): return QRectF(-150, -100, 300, 400)
    def shape(self): path = QPainterPath(); path.addRect(QRectF(-20, -60, 40, 80)); return path

    def paint(self, painter, option, widget):
        if self.is_hovered or self.isSelected(): painter.setPen(QPen(Qt.GlobalColor.yellow, 2)); painter.drawRect(QRectF(-20, -20, 40, 40))
        painter.setPen(QPen(Qt.GlobalColor.red, 2)); y_mark = -40; painter.drawLine(-5, y_mark - 5, 5, y_mark + 5); painter.drawLine(-5, y_mark + 5, 5, y_mark - 5)

        if not self.pixmap_small.isNull():
            target_rect = QRectF(-10, y_mark + 10, 20, 20); painter.drawPixmap(target_rect.toRect(), self.pixmap_small)
        
        # === VISUALIZAÇÃO DO PONTILHADO COM LÓGICA DE CORO ===
        if self.is_hovered and not any(x in self.tipo for x in ["PAUSA", "RESPIRACAO", "TAG"]):
            is_chorus_mode = False
            
            if self.scene():
                all_items = self.scene().items()
                tags = [it for it in all_items if isinstance(it, LabelItem)]
                tags.sort(key=lambda item: (item.y(), item.x())) # Ordena tags
                
                last_valid_tag = None
                my_y = self.y(); my_x = self.x()
                
                for tag in tags:
                    is_line_above = tag.y() < (my_y - 50) 
                    is_same_line_before = (abs(tag.y() - my_y) <= 50) and (tag.x() < my_x)
                    if is_line_above or is_same_line_before: last_valid_tag = tag
                
                if last_valid_tag:
                    if "CORO" in last_valid_tag.tipo or "FINAL" in last_valid_tag.tipo: is_chorus_mode = True

            if self.custom_crop_params:
                w_box = self.custom_crop_params['w']; h_box = self.custom_crop_params['h']; y_box = self.custom_crop_params['y']
                color_pen = QColor(255, 0, 255) # Magenta (Manual)
            elif is_chorus_mode:
                w_box = GLOBAL_CONFIG["CHORUS_WIDTH"]; h_box = GLOBAL_CONFIG["CHORUS_HEIGHT"]; y_box = GLOBAL_CONFIG["CHORUS_OFFSET_Y"]
                color_pen = QColor(255, 165, 0) # Laranja (Coro)
            else:
                w_box = GLOBAL_CONFIG["CROP_WIDTH"]; h_box = GLOBAL_CONFIG["CROP_HEIGHT"]; y_box = GLOBAL_CONFIG["CROP_OFFSET_Y"]
                color_pen = QColor(0, 255, 255) # Ciano (Padrão)

            pen_crop = QPen(color_pen); pen_crop.setStyle(Qt.PenStyle.DashLine); pen_crop.setWidth(2)
            painter.setPen(pen_crop); painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(-w_box / 2, y_box, w_box, h_box))

    def hoverEnterEvent(self, event): self.is_hovered = True; self.update(); super().hoverEnterEvent(event)
    def hoverLeaveEvent(self, event): self.is_hovered = False; self.update(); super().hoverLeaveEvent(event)
    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            if self.snap_callback(): snap = GLOBAL_CONFIG.get("SNAP_GRID", 20); x = round(value.x() / snap) * snap; y = round(value.y() / snap) * snap; return QPointF(x, y)
        return super().itemChange(change, value)

# ====================== DIÁLOGOS DE AJUSTE ======================

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("Configurações"); self.resize(450, 500); self.layout = QVBoxLayout(self)
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
        btn_box = QHBoxLayout(); btn_save = QPushButton("Salvar e Fechar"); btn_save.clicked.connect(self.save)
        btn_cancel = QPushButton("Cancelar"); btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_save); btn_box.addWidget(btn_cancel); self.layout.addLayout(btn_box)

    def add_spin(self, layout, label, value):
        s = QSpinBox(); s.setRange(0, 5000); s.setValue(value); layout.addRow(QLabel(label), s); return s

    def save(self):
        GLOBAL_CONFIG["CROP_OFFSET_Y"] = self.spin_crop_y.value(); GLOBAL_CONFIG["CROP_WIDTH"] = self.spin_crop_w.value(); GLOBAL_CONFIG["CROP_HEIGHT"] = self.spin_crop_h.value()
        GLOBAL_CONFIG["CHORUS_OFFSET_Y"] = self.spin_chorus_y.value(); GLOBAL_CONFIG["CHORUS_WIDTH"] = self.spin_chorus_w.value(); GLOBAL_CONFIG["CHORUS_HEIGHT"] = self.spin_chorus_h.value()
        GLOBAL_CONFIG["CROP_ZOOM"] = self.spin_zoom.value(); GLOBAL_CONFIG["SNAP_GRID"] = self.spin_snap.value(); GLOBAL_CONFIG["SPACING_NOTE"] = self.spin_spacing.value()
        GLOBAL_CONFIG["PAGE_WIDTH"] = self.spin_page_w.value()
        self.accept()

class IndividualCropDialog(QDialog):
    def __init__(self, current_data, parent=None):
        super().__init__(parent); self.setWindowTitle("Ajuste Individual"); self.layout = QFormLayout(self)
        w = current_data.get('w', GLOBAL_CONFIG["CROP_WIDTH"]); h = current_data.get('h', GLOBAL_CONFIG["CROP_HEIGHT"]); y = current_data.get('y', GLOBAL_CONFIG["CROP_OFFSET_Y"])
        self.spin_w = QSpinBox(); self.spin_w.setRange(10, 500); self.spin_w.setValue(w); self.layout.addRow(QLabel("Largura:"), self.spin_w)
        self.spin_h = QSpinBox(); self.spin_h.setRange(10, 500); self.spin_h.setValue(h); self.layout.addRow(QLabel("Altura:"), self.spin_h)
        self.spin_y = QSpinBox(); self.spin_y.setRange(-100, 500); self.spin_y.setValue(y); self.layout.addRow(QLabel("Deslocamento Y:"), self.spin_y)
        btn_box = QHBoxLayout(); btn_save = QPushButton("Salvar"); btn_save.clicked.connect(self.accept); btn_reset = QPushButton("Resetar Global"); btn_reset.clicked.connect(self.reset_global)
        btn_box.addWidget(btn_save); btn_box.addWidget(btn_reset); self.layout.addRow(btn_box); self.result_data = None
    def reset_global(self): self.result_data = None; self.accept()
    def accept(self): 
        if self.result_data is None: self.result_data = {'w': self.spin_w.value(), 'h': self.spin_h.value(), 'y': self.spin_y.value()}
        super().accept()

# ====================== GRAPHICS VIEW (CANVAS) ======================
class MusicalView(QGraphicsView):
    coords_changed = pyqtSignal(int, int)
    def __init__(self, main_window):
        super().__init__(); self.main = main_window
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate); self.setRenderHint(QPainter.RenderHint.Antialiasing); self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform); self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.ghost_item = None; self.start_pos = None; self.current_drawing_box = None

    def set_scene(self, scene): self.setScene(scene); self.reset_ghost()
    def reset_ghost(self):
        if self.ghost_item and self.scene(): 
            try: self.scene().removeItem(self.ghost_item) 
            except: pass
        self.ghost_item = QGraphicsPixmapItem(); self.ghost_item.setOpacity(0.7); self.ghost_item.setZValue(1000); self.ghost_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        if self.scene(): self.scene().addItem(self.ghost_item)

    def update_ghost_icon(self, tipo):
        if self.ghost_item: pix = ImageCache.get_pixmap(tipo, 40 if "TAG" not in tipo else 30); self.ghost_item.setPixmap(pix); self.ghost_item.setOffset(-20, -20)

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        if self.main.snap_active.isChecked():
            grid = GLOBAL_CONFIG.get("SNAP_GRID", 20); pen = QPen(QColor(200, 200, 200, 50)); pen.setStyle(Qt.PenStyle.DotLine); painter.setPen(pen)
            left = int(rect.left()); top = int(rect.top()); right = int(rect.right()); bottom = int(rect.bottom())
            for x in range(left - (left % grid), right, grid): painter.drawLine(x, top, x, bottom)
            for y in range(top - (top % grid), bottom, grid): painter.drawLine(left, y, right, y)

    def mouseMoveEvent(self, event):
        sp = self.mapToScene(event.pos()); self.coords_changed.emit(int(sp.x()), int(sp.y()))
        if (self.main.is_drawing_header or self.main.is_drawing_timesig) and self.start_pos:
            if not self.current_drawing_box:
                rect = QRectF(self.start_pos, sp).normalized()
                item = HeaderBoxItem(rect) if self.main.is_drawing_header else TimeSigBoxItem(rect)
                self.current_drawing_box = item; self.scene().addItem(item)
            else: self.current_drawing_box.setRect(QRectF(self.start_pos, sp).normalized())
            return 
        if self.main.current_tool and self.ghost_item:
            x, y = sp.x(), sp.y()
            if self.main.snap_active.isChecked(): grid = GLOBAL_CONFIG.get("SNAP_GRID", 20); x = round(x / grid) * grid; y = round(y / grid) * grid
            self.ghost_item.setPos(x, y)
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.main.is_drawing_header or self.main.is_drawing_timesig:
                self.start_pos = self.mapToScene(event.pos())
                t_type = HeaderBoxItem if self.main.is_drawing_header else TimeSigBoxItem
                for i in self.scene().items():
                    if isinstance(i, t_type): self.scene().removeItem(i)
                return
            items = self.scene().items(self.mapToScene(event.pos()))
            real_items = [i for i in items if i != self.ghost_item and i.data(0) != "background"]
            if not real_items: self.main.add_item_at_mouse(self.mapToScene(event.pos())); return 
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if (self.main.is_drawing_header or self.main.is_drawing_timesig) and self.start_pos:
            self.start_pos = None; self.current_drawing_box = None; self.main.is_drawing_header = False; self.main.is_drawing_timesig = False
            self.setCursor(Qt.CursorShape.ArrowCursor); self.main.save_state(); return
        if event.button() == Qt.MouseButton.LeftButton: self.main.save_state()
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        sp = self.mapToScene(event.pos())
        item = next((i for i in self.scene().items(sp) if isinstance(i, (NoteItem, LabelItem, HeaderBoxItem, TimeSigBoxItem))), None)
        if item:
            menu = QMenu(); act_del = QAction("Excluir Item", self); act_del.triggered.connect(lambda: self.main.delete_specific_item(item)); menu.addAction(act_del)
            if isinstance(item, NoteItem):
                if "TAG" not in self.main.current_tool:
                    action_swap = QAction(f"Trocar por '{self.main.current_tool}'", self); action_swap.triggered.connect(lambda: self.main.swap_item_type(item)); menu.addSeparator(); menu.addAction(action_swap)
                if not any(x in item.tipo for x in ["PAUSA", "RESPIRACAO", "TAG"]):
                    menu.addSeparator(); act_crop = QAction("✂️ Ajustar Recorte (Sílaba)", self); act_crop.triggered.connect(lambda: self.main.open_individual_crop_dialog(item)); menu.addAction(act_crop)
            menu.exec(event.globalPos())

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            zoom_in = event.angleDelta().y() > 0; factor = 1.1 if zoom_in else 0.9; self.scale(factor, factor); self.main.update_zoom_label(self.transform().m11())
        else: super().wheelEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete: self.main.delete_selected(); return
        sel = self.scene().selectedItems()
        if sel:
            dx, dy = 0, 0
            if event.key() == Qt.Key.Key_Left: dx = -1
            if event.key() == Qt.Key.Key_Right: dx = 1
            if event.key() == Qt.Key.Key_Up: dy = -1
            if event.key() == Qt.Key.Key_Down: dy = 1
            if dx or dy: self.main.save_state(); [i.moveBy(dx, dy) for i in sel]; return
        super().keyPressEvent(event)

# ====================== JANELA PRINCIPAL ======================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Editor Musical Pro + Gemini AI Integration")
        self.resize(1600, 1000)
        self.current_tool = "SEMINIMA"
        self.current_image_paths = []
        self.current_json_path = None 
        self.history = []; self.history_pos = -1; self.images_status = {} 
        self.is_drawing_header = False; self.is_drawing_timesig = False 
        self.cooldown_remaining = 0; self.cooldown_timer = QTimer(self); self.cooldown_timer.timeout.connect(self.update_cooldown); self.cooldown_timer.start(1000)

        self.init_ui()
        self.scene = QGraphicsScene(); self.view.set_scene(self.scene); self.select_tool("SEMINIMA"); self.refresh_playlist()
        self.shortcut_save = QShortcut(QKeySequence("Ctrl+S"), self); self.shortcut_save.activated.connect(lambda: self.trigger_save("em_andamento"))

    def update_cooldown(self):
        if self.cooldown_remaining > 0: self.cooldown_remaining -= 1

    def init_ui(self):
        cw = QWidget(); self.setCentralWidget(cw); main_box = QHBoxLayout(cw); splitter = QSplitter(Qt.Orientation.Horizontal); main_box.addWidget(splitter)
        lp = QWidget(); ll = QVBoxLayout(lp); ll.addWidget(QLabel("LISTA DE HINOS"))
        self.list_widget = QListWidget(); self.list_widget.itemClicked.connect(self.on_playlist_click); ll.addWidget(self.list_widget)
        b_ref = QPushButton("Atualizar Lista"); b_ref.clicked.connect(self.refresh_playlist); ll.addWidget(b_ref); splitter.addWidget(lp); splitter.setStretchFactor(0, 1)

        rp = QWidget(); rl = QVBoxLayout(rp); rl.setContentsMargins(0,0,0,0)
        tb = QFrame(); tb.setStyleSheet("background-color: #2c3e50; color: white;"); tl = QHBoxLayout(tb)
        
        self.add_btn(tl, "Nova Img", self.select_images, "#2980b9")
        self.add_btn(tl, "Salvar", lambda: self.trigger_save("em_andamento"), "#f39c12")
        self.add_btn(tl, "Concluir", lambda: self.trigger_save("concluido"), "#27ae60")
        tl.addSpacing(20)
        self.add_btn(tl, "Desenhar Cabeçalho", self.enable_header_drawing, "#3498db")
        self.add_btn(tl, "Desenhar Compasso", self.enable_timesig_drawing, "#e67e22")
        self.add_btn(tl, "Configurações", self.open_settings, "#7f8c8d")
        tl.addSpacing(20)
        self.add_btn(tl, "👁️ GERAR PREVIEW & EXTRAIR", self.generate_preview, "#8e44ad")
        tl.addSpacing(20)
        self.add_btn(tl, "Limpar", self.clear_all, "#c0392b")
        self.add_btn(tl, "Desfazer", self.undo, "#95a5a6")

        self.snap_active = QCheckBox("Snap"); self.snap_active.setChecked(True); tl.addWidget(self.snap_active)
        self.lbl_zoom = QLabel("100%"); tl.addWidget(self.lbl_zoom)
        self.lbl_icon_preview = QLabel(); self.lbl_icon_preview.setFixedSize(40,40); self.lbl_icon_preview.setStyleSheet("border: 1px solid gray;"); tl.addWidget(self.lbl_icon_preview)
        self.lbl_tool_name = QLabel("SEMINIMA"); self.lbl_tool_name.setStyleSheet("color: #f1c40f; font-weight: bold;"); tl.addWidget(self.lbl_tool_name)
        tl.addStretch(); self.lbl_coords = QLabel("x:0 y:0"); tl.addWidget(self.lbl_coords); rl.addWidget(tb)

        scroll_paleta = QScrollArea(); scroll_paleta.setFixedHeight(80); scroll_paleta.setWidgetResizable(True)
        paleta_content = QWidget(); paleta_layout = QHBoxLayout(paleta_content); paleta_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.tool_buttons = {}
        for tag in TAGS_ESTRUTURA: self.create_palette_button(tag, paleta_layout, is_tag=True)
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.VLine); paleta_layout.addWidget(sep)
        for nota in VALORES_NOTAS: self.create_palette_button(nota, paleta_layout, is_tag=False)
        scroll_paleta.setWidget(paleta_content); rl.addWidget(scroll_paleta)
        
        self.view = MusicalView(self); self.view.coords_changed.connect(lambda x, y: self.lbl_coords.setText(f"x: {x} y: {y}")); rl.addWidget(self.view)
        splitter.addWidget(rp); splitter.setStretchFactor(1, 4)

    def add_btn(self, layout, text, func, color):
        btn = QPushButton(text); btn.clicked.connect(func); btn.setStyleSheet(f"background-color: {color}; color: white; border: none; padding: 5px 10px; font-weight: bold;"); layout.addWidget(btn)

    def create_palette_button(self, nome, layout, is_tag):
        btn = QPushButton(); btn.setFixedSize(60 if is_tag else 45, 45)
        pix = ImageCache.get_pixmap(nome, 35); btn.setIcon(QIcon(pix)); btn.setIconSize(QSize(35, 35))
        btn.setToolTip(nome); btn.clicked.connect(partial(self.select_tool, nome))
        border_col = "#2980b9" if is_tag else "#bdc3c7"
        btn.setStyleSheet(f"background-color: #ecf0f1; border: 1px solid {border_col};"); layout.addWidget(btn); self.tool_buttons[nome] = btn

    # ================= GERAÇÃO DA IMAGEM E PREVIEW =================
    def generate_preview(self):
        pil_image = self.render_final_image()
        if not pil_image: QMessageBox.warning(self, "Aviso", "Nada para gerar."); return
        base = os.path.splitext(os.path.basename(self.current_json_path or self.current_image_paths[0]))[0] if self.current_image_paths else "export_recorte_gemini"
        dlg = PreviewDialog(pil_image, base, self); dlg.exec()

    def render_final_image(self):
        state = self.get_current_state()
        if not state: return None
        
        PAGE_W = GLOBAL_CONFIG["PAGE_WIDTH"]; SPACING = GLOBAL_CONFIG["SPACING_NOTE"]; CROP_ZOOM = GLOBAL_CONFIG["CROP_ZOOM"]
        MARGIN_R = GLOBAL_CONFIG["RIGHT_MARGIN"]; PAD_B = GLOBAL_CONFIG["BOTTOM_PADDING"]

        header_rect = next(((i.pos().x()+i.rect().left(), i.pos().y()+i.rect().top(), i.pos().x()+i.rect().right(), i.pos().y()+i.rect().bottom()) for i in self.scene.items() if isinstance(i, HeaderBoxItem)), None)
        timesig_rect = next(((i.pos().x()+i.rect().left(), i.pos().y()+i.rect().top(), i.pos().x()+i.rect().right(), i.pos().y()+i.rect().bottom()) for i in self.scene.items() if isinstance(i, TimeSigBoxItem)), None)

        W, H = PAGE_W, max(4000, len(self.current_image_paths)*4000)
        img_out = Image.new('RGB', (W, H), 'white'); draw = ImageDraw.Draw(img_out)
        try: font_note = ImageFont.truetype("arial.ttf", 18); font_tag = ImageFont.truetype("arial.ttf", 22)
        except: font_note = ImageFont.load_default(); font_tag = ImageFont.load_default()

        src_imgs = []
        try: src_imgs = [Image.open(p).convert("RGBA") for p in self.current_image_paths]
        except: return None

        header_h_pasted = 0
        if src_imgs and header_rect:
            img = src_imgs[0]; x1, y1, x2, y2 = map(int, header_rect)
            if x2>x1 and y2>y1:
                crop = img.crop((max(0,x1), max(0,y1), min(img.width,x2), min(img.height,y2)))
                nw, nh = int(crop.width*CROP_ZOOM), int(crop.height*CROP_ZOOM)
                crop = ImageOps.grayscale(ImageEnhance.Contrast(crop.resize((nw, nh), Image.Resampling.LANCZOS)).enhance(2.0)).convert("RGB")
                img_out.paste(crop, (int((W-nw)//2), 0)); header_h_pasted = nh
        
        cy = header_h_pasted + 100; cx = 100; row_h = 450; last_y = state[0]['y'] if state else 0

        if src_imgs and timesig_rect:
            img = src_imgs[0]; x1, y1, x2, y2 = map(int, timesig_rect)
            if x2>x1 and y2>y1:
                crop = img.crop((max(0,x1), max(0,y1), min(img.width,x2), min(img.height,y2)))
                nw, nh = int(crop.width*CROP_ZOOM), int(crop.height*CROP_ZOOM)
                crop = ImageOps.grayscale(ImageEnhance.Contrast(crop.resize((nw, nh), Image.Resampling.LANCZOS)).enhance(2.0)).convert("RGB")
                img_out.paste(crop, (cx, int(cy - nh//2))); cx += nw + 50

        is_chorus_mode = False
        
        for item in state:
            if "HEADER" in item['tipo'] or "TIMESIG" in item['tipo']: continue
            if item['y'] > last_y + 150: cy += row_h; cx = 100; last_y = item['y']
            
            if "TAG" in item['tipo']:
                txt = item['tipo'].replace("TAG_", "")
                if "CORO" in txt or "FINAL" in txt: is_chorus_mode = True
                else: is_chorus_mode = False
                
                bg = "#3498db"
                if "CORO" in txt: bg = "#e67e22"
                elif "FINAL" in txt: bg = "#27ae60"
                
                draw.rectangle([cx, cy-20, cx+100, cy+20], fill=bg)
                bb = draw.textbbox((0,0), txt, font=font_tag); tw = bb[2]-bb[0]; th = bb[3]-bb[1]
                draw.text((cx + (100-tw)/2, cy-20 + (40-th)/2 - 2), txt, fill="white", font=font_tag)
                cx += GLOBAL_CONFIG["SPACING_TAG"]
            else:
                dname = item['tipo'].replace("_", " ").title()
                try: draw.text((cx, cy-70), dname, fill="black", font=font_note, anchor="mb")
                except: draw.text((cx-30, cy-90), dname, fill="black", font=font_note)

                if not any(x in item['tipo'] for x in ["PAUSA", "RESPIRACAO"]):
                    if 'custom_w' in item:
                        lw, lh, ly = item['custom_w'], item['custom_h'], item['custom_y']
                    elif is_chorus_mode:
                        lw, lh, ly = GLOBAL_CONFIG["CHORUS_WIDTH"], GLOBAL_CONFIG["CHORUS_HEIGHT"], GLOBAL_CONFIG["CHORUS_OFFSET_Y"]
                    else:
                        lw, lh, ly = GLOBAL_CONFIG["CROP_WIDTH"], GLOBAL_CONFIG["CROP_HEIGHT"], GLOBAL_CONFIG["CROP_OFFSET_Y"]

                    ac_y=0; src=None; rel_y=0
                    for si in src_imgs:
                        if ac_y <= item['y'] < ac_y + si.height + 20: src=si; rel_y=item['y']-ac_y; break
                        ac_y += si.height + 20
                    if src:
                        x1 = max(0, int(item['x'] - lw//2)); y1 = max(0, int(rel_y + ly))
                        x2 = min(src.width, int(item['x'] + lw//2)); y2 = min(src.height, int(rel_y + ly + lh))
                        if x2>x1 and y2>y1:
                            cr = src.crop((x1, y1, x2, y2))
                            nw, nh = int(cr.width*CROP_ZOOM), int(cr.height*CROP_ZOOM)
                            cr = cr.resize((nw, nh), Image.Resampling.LANCZOS)
                            cr = ImageEnhance.Contrast(cr).enhance(1.5)
                            img_out.paste(cr, (int(cx - nw//2), int(cy + 65)))
                cx += SPACING
            if cx > W - MARGIN_R: cx = 100; cy += row_h

        bbox = ImageOps.invert(img_out.convert('RGB')).getbbox()
        if bbox: img_out = img_out.crop((0, 0, W, min(H, bbox[3] + PAD_B)))
        return img_out

    def trigger_gemini_processing(self, image_path, base_name):
        self.cooldown_remaining = GLOBAL_CONFIG["API_COOLDOWN"]
        json_out = os.path.join(OUTPUT_FOLDER, f"{base_name}_gemini.json")
        self.pd = QProgressDialog("Enviando para o Gemini... Aguarde...", "Cancelar", 0,0, self)
        self.pd.setWindowModality(Qt.WindowModality.WindowModal); self.pd.show()
        self.worker = GeminiWorker(image_path, json_out)
        self.worker.finished_signal.connect(self.gemini_done)
        self.worker.start()

    def gemini_done(self, path, success, msg):
        self.pd.close()
        if success:
            if QMessageBox.question(self, "Sucesso", "JSON Salvo. Abrir pasta?", QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                try: os.startfile(os.path.dirname(path))
                except: pass
        else: QMessageBox.critical(self, "Erro", msg)

    # ================= FUNÇÕES PADRÃO (SALVAR/CARREGAR/LISTA) =================
    def open_settings(self): SettingsDialog(self).exec(); self.view.viewport().update(); self.scene.update()
    def enable_header_drawing(self): self.is_drawing_header=True; self.is_drawing_timesig=False; self.view.setCursor(Qt.CursorShape.CrossCursor)
    def enable_timesig_drawing(self): self.is_drawing_timesig=True; self.is_drawing_header=False; self.view.setCursor(Qt.CursorShape.CrossCursor)
    
    # --- FUNÇÃO SELECT_IMAGES REINSERIDA CORRETAMENTE ---
    def select_images(self):
        file_names, _ = QFileDialog.getOpenFileNames(self, "Selecionar Imagens", str(IMG_FOLDER), "Images (*.png *.jpg *.jpeg)")
        if file_names:
            file_names.sort()
            self.current_json_path = None
            self.load_images_to_scene(file_names)

    def open_individual_crop_dialog(self, item): 
        d = IndividualCropDialog(item.custom_crop_params or {}, self)
        if d.exec(): item.custom_crop_params=d.result_data; item.update(); self.save_state()

    def load_images_to_scene(self, paths):
        self.scene.clear(); self.current_image_paths=paths; y=0
        for p in paths:
            if not os.path.exists(p): continue
            pix = QPixmap(p); i=self.scene.addPixmap(pix); i.setData(0, "background"); i.setZValue(-100); i.setPos(0, y); y+=pix.height()+20
            l = self.scene.addLine(0, y-10, pix.width(), y-10, QPen(Qt.GlobalColor.black, 2)); l.setZValue(-99)
        self.scene.setSceneRect(self.scene.itemsBoundingRect()); self.history=[]; self.view.reset_ghost(); self.view.update_ghost_icon(self.current_tool); self.update_title()
    def add_item_at_mouse(self, p):
        x,y=p.x(),p.y(); 
        if self.snap_active.isChecked(): g=GLOBAL_CONFIG.get("SNAP_GRID",20); x=round(x/g)*g; y=round(y/g)*g
        i = LabelItem(self.current_tool,x,y,self.snap_active.isChecked) if "TAG" in self.current_tool else NoteItem(self.current_tool,x,y,self.snap_active.isChecked)
        self.scene.addItem(i)
    def get_current_state(self):
        raw = []
        for i in self.scene.items():
            if isinstance(i, (NoteItem, LabelItem)):
                d = {"tipo": i.tipo, "x": round(i.x(),1), "y": round(i.y(),1)}
                if hasattr(i, 'custom_crop_params') and i.custom_crop_params: d.update({'custom_w': i.custom_crop_params['w'], 'custom_h': i.custom_crop_params['h'], 'custom_y': i.custom_crop_params['y']})
                raw.append(d)
            elif isinstance(i, HeaderBoxItem): raw.append({"tipo": "HEADER_BOX", "x": round(i.pos().x(),1), "y": round(i.pos().y(),1), "w": round(i.rect().width(),1), "h": round(i.rect().height(),1)})
            elif isinstance(i, TimeSigBoxItem): raw.append({"tipo": "TIMESIG_BOX", "x": round(i.pos().x(),1), "y": round(i.pos().y(),1), "w": round(i.rect().width(),1), "h": round(i.rect().height(),1)})
        if not raw: return []
        notes = sorted([x for x in raw if "BOX" not in x['tipo']], key=lambda k: k['y'])
        boxes = [x for x in raw if "BOX" in x['tipo']]
        final = []; line = []; last_y = notes[0]['y'] if notes else 0
        for n in notes:
            if abs(n['y'] - last_y) < 80: line.append(n)
            else:
                final.extend(sorted(line, key=lambda k: (k['x'], 0 if "TAG" in k['tipo'] else 1)))
                line = [n]; last_y = n['y']
        final.extend(sorted(line, key=lambda k: (k['x'], 0 if "TAG" in k['tipo'] else 1)))
        return final + boxes
    def select_tool(self, n):
        self.current_tool=n; self.lbl_tool_name.setText(n); self.lbl_icon_preview.setPixmap(ImageCache.get_pixmap(n, 35)); self.view.update_ghost_icon(n)
        for name, btn in self.tool_buttons.items():
            c = "#f1c40f" if name == n else "#ecf0f1"; b = "2px inset" if name == n else "1px solid"; bc = "#2980b9" if "TAG" in name else "#bdc3c7"
            btn.setStyleSheet(f"background-color: {c}; border: {b} {bc};")
    def save_state(self): self.history=self.history[:self.history_pos+1]+[self.get_current_state()]; self.history_pos=min(self.history_pos+1, MAX_HIST); self.update_title()
    def undo(self): 
        if self.history_pos>0: self.history_pos-=1; self.apply_state(self.history[self.history_pos])
    def apply_state(self, state):
        self.scene.clear(); self.load_images_to_scene(self.current_image_paths)
        for d in state:
            t = d.get('tipo', '')
            if "HEADER_BOX" == t: i=HeaderBoxItem(QRectF(0,0,d['w'],d['h'])); i.setPos(d['x'],d['y']); self.scene.addItem(i)
            elif "TIMESIG_BOX" == t: i=TimeSigBoxItem(QRectF(0,0,d['w'],d['h'])); i.setPos(d['x'],d['y']); self.scene.addItem(i)
            elif "TAG" in t: i=LabelItem(t,d['x'],d['y'],self.snap_active.isChecked); self.scene.addItem(i)
            else: 
                cp = {'w': d['custom_w'], 'h': d['custom_h'], 'y': d['custom_y']} if 'custom_w' in d else None
                i=NoteItem(t,d['x'],d['y'],self.snap_active.isChecked, cp); self.scene.addItem(i)
        self.update_title()
    def delete_selected(self): 
        sel = self.scene.selectedItems()
        if sel: self.save_state(); [self.scene.removeItem(i) for i in sel]
    def delete_specific_item(self, i): self.save_state(); self.scene.removeItem(i)
    def swap_item_type(self, item):
        self.save_state()
        x = item.x()
        y = item.y()
        self.scene.removeItem(item)
        self.add_item_at_mouse(QPointF(x, y))

    def clear_all(self):
        if QMessageBox.question(self, "Limpar", "Apagar tudo?") == QMessageBox.StandardButton.Yes: self.save_state(); self.scene.clear(); self.load_images_to_scene(self.current_image_paths)
    def refresh_playlist(self): 
        self.list_widget.clear(); fs=glob.glob(str(JSON_FOLDER/"*.json")); st={os.path.basename(json.load(open(f,encoding='utf-8')).get('imagem_fundo','')): json.load(open(f,encoding='utf-8')).get('status') for f in fs}
        for f in sorted([x for x in os.listdir(IMG_FOLDER) if x.endswith(('jpg','png'))]):
            item=QListWidgetItem(f); s=st.get(f,'')
            item.setText(f"✅ {f}" if s=="concluido" else f"🚧 {f}" if s else f"⬜ {f}")
            self.list_widget.addItem(item)
    def on_playlist_click(self, item):
        fn=item.text().replace("✅ ","").replace("🚧 ","").replace("⬜ ","")
        jp=next((f for f in glob.glob(str(JSON_FOLDER/"*.json")) if os.path.basename(json.load(open(f,encoding='utf-8')).get('imagem_fundo',''))==fn), None)
        if jp: self.current_json_path=jp; self.load_from_json_file(jp)
        else: self.current_json_path=None; self.load_images_to_scene([os.path.join(IMG_FOLDER,fn)])
    def load_from_json_file(self, p):
        d=json.load(open(p,encoding='utf-8')); imgs=d.get('imagens_fundo', [d.get('imagem_fundo')])
        res = [i for i in imgs if os.path.exists(i)] or [os.path.join(IMG_FOLDER, os.path.basename(i)) for i in imgs if os.path.exists(os.path.join(IMG_FOLDER, os.path.basename(i)))]
        if res: self.load_images_to_scene(res); self.apply_state(d.get('notas', []))
        if 'configuracoes' in d: GLOBAL_CONFIG.update(d['configuracoes'])

    def trigger_save(self, s): 
        if not self.current_image_paths: return
        if not self.current_json_path:
            name, ok = QInputDialog.getText(self, "Salvar", "Nome:", text=os.path.splitext(os.path.basename(self.current_image_paths[0]))[0])
            if not ok: return
            self.current_json_path = os.path.join(JSON_FOLDER, name + ".json")
        
        data_to_save = {
            "imagem_fundo": self.current_image_paths[0],
            "imagens_fundo": self.current_image_paths,
            "status": s,
            "notas": self.get_current_state(),
            "configuracoes": GLOBAL_CONFIG
        }
        json.dump(data_to_save, open(self.current_json_path, 'w', encoding='utf-8'), indent=4)
        self.refresh_playlist(); self.statusBar().showMessage("Salvo!", 2000)
    def update_title(self): self.setWindowTitle(f"Editor Musical Pro ({len([i for i in self.scene.items() if isinstance(i, NoteItem)])} notas)")
    def update_zoom_label(self, s): self.lbl_zoom.setText(f"{int(s*100)}%")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())