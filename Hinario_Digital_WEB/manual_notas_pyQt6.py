import sys
import os
import json
import glob
from functools import partial

from PyQt6.QtWidgets import (QApplication, QMainWindow, QGraphicsView, QGraphicsScene, 
                             QGraphicsItem, QGraphicsPixmapItem, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QCheckBox, QLabel, QScrollArea, 
                             QFrame, QFileDialog, QMessageBox, QMenu, QGraphicsObject,
                             QListWidget, QListWidgetItem, QInputDialog, QSplitter)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QSize
from PyQt6.QtGui import (QPixmap, QPainter, QPen, QColor, QAction, 
                         QTransform, QImage, QWheelEvent, QIcon, QFont, QBrush)

from PIL import Image, ImageDraw

# ====================== CONFIGURAÇÃO ======================
IMG_FOLDER = r"C:\Users\psoares\pyNestle\Private\Hinario_Digital\teste"
JSON_FOLDER = r"C:\Users\psoares\pyNestle\Private\Hinario_Digital\json_notas"
ICONS_FOLDER = r"C:\Users\psoares\pyNestle\Private\Notas_Musicais"

os.makedirs(JSON_FOLDER, exist_ok=True)

# ====================== CONSTANTES ======================
VALORES_NOTAS = [
    "SEMIBREVE", "MINIMA", "MINIMA PONTUADA",
    "SEMINIMA", "SEMINIMA PONTUADA",
    "COLCHEIA", "COLCHEIA PONTUADA",
    "SEMICOLCHEIA", "SEMICOLCHEIA PONTUADA",
    "RESPIRACAO CURTA", "RESPIRACAO LONGA",
    "PAUSA COLCHEIA", "PAUSA SEMIBREVE", "PAUSA SEMICOLCHEIA", "PAUSA SEMINIMA",
    "FERMATA MINIMA", "FERMATA COLCHEIA", "FERMATA SEMINIMA"
]

# Novas ferramentas de estrutura
TAGS_ESTRUTURA = ["TAG_VERSO", "TAG_CORO", "TAG_FINAL"]

PASSO_SNAP = 20
MAX_HIST = 50

# ====================== CACHE DE IMAGEM ======================
class ImageCache:
    _cache = {}

    @classmethod
    def get_pixmap(cls, tipo, size=40):
        # Se for uma TAG, não buscamos imagem no disco, geramos on-the-fly na classe LabelItem
        # mas precisamos de um icone para o botão
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
        
        # Gera fallback (usado para notas sem icone ou para as TAGS na paleta)
        pixmap = cls._generate_fallback(tipo, size)
        cls._cache[key] = pixmap
        return pixmap

    @staticmethod
    def _generate_fallback(texto, size):
        # Diferencia visualmente TAGS de NOTAS no botão
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

# ====================== ITEM 1: NOTA MUSICAL ======================
class NoteItem(QGraphicsObject):
    def __init__(self, tipo, x, y, snap_enabled_callback):
        super().__init__()
        self.tipo = tipo
        self.snap_callback = snap_enabled_callback
        self.pixmap_main = ImageCache.get_pixmap(tipo, 40)
        self.pixmap_small = ImageCache.get_pixmap(tipo, 20)
        self.setPos(x, y)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | 
                      QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.is_hovered = False

    def boundingRect(self):
        return QRectF(-20, -60, 40, 80)

    def paint(self, painter, option, widget):
        click_rect = QRectF(-20, -20, 40, 40)
        if self.is_hovered or self.isSelected():
            painter.setPen(QPen(Qt.GlobalColor.yellow, 2))
            painter.drawRect(click_rect)
        
        painter.setPen(QPen(Qt.GlobalColor.red, 2))
        distancia = 40
        y_mark = -distancia
        painter.drawLine(-5, y_mark - 5, 5, y_mark + 5)
        painter.drawLine(-5, y_mark + 5, 5, y_mark - 5)

        if not self.pixmap_small.isNull():
            target_rect = QRectF(-10, y_mark + 20 - 10, 20, 20)
            painter.drawPixmap(target_rect.toRect(), self.pixmap_small)

    def hoverEnterEvent(self, event):
        self.is_hovered = True; self.update(); super().hoverEnterEvent(event)
    def hoverLeaveEvent(self, event):
        self.is_hovered = False; self.update(); super().hoverLeaveEvent(event)
    
    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            if self.snap_callback():
                new_pos = value
                x = round(new_pos.x() / PASSO_SNAP) * PASSO_SNAP
                y = round(new_pos.y() / PASSO_SNAP) * PASSO_SNAP
                return QPointF(x, y)
        return super().itemChange(change, value)

# ====================== ITEM 2: ETIQUETA DE ESTRUTURA (NOVO) ======================
class LabelItem(QGraphicsObject):
    def __init__(self, tipo, x, y, snap_enabled_callback):
        super().__init__()
        self.tipo = tipo
        self.snap_callback = snap_enabled_callback
        self.label_text = tipo.replace("TAG_", "") # Ex: "CORO"
        
        self.setPos(x, y)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | 
                      QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.is_hovered = False

    def boundingRect(self):
        # Caixa larga para caber o texto
        return QRectF(0, 0, 80, 30)

    def paint(self, painter, option, widget):
        rect = self.boundingRect()
        
        # Cor de fundo baseada na seleção
        color = QColor("#3498db") if not self.isSelected() else QColor("#f1c40f")
        if self.is_hovered: color = color.lighter(120)

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
                x = round(new_pos.x() / PASSO_SNAP) * PASSO_SNAP
                y = round(new_pos.y() / PASSO_SNAP) * PASSO_SNAP
                return QPointF(x, y)
        return super().itemChange(change, value)


# ====================== VIEW ======================
class MusicalView(QGraphicsView):
    coords_changed = pyqtSignal(int, int)

    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag) # Padrão: Seleção
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.ghost_item = None 
        self.is_adding = False 

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
            # Se for TAG, usa o fallback gerado pelo cache
            pix = ImageCache.get_pixmap(tipo, 40 if "TAG" not in tipo else 30)
            self.ghost_item.setPixmap(pix)
            self.ghost_item.setOffset(-20, -20)

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        if self.main.snap_active.isChecked():
            grid_size = PASSO_SNAP
            left = int(rect.left()) - (int(rect.left()) % grid_size)
            top = int(rect.top()) - (int(rect.top()) % grid_size)
            pen = QPen(QColor(200, 200, 200, 50)); pen.setStyle(Qt.PenStyle.DotLine)
            painter.setPen(pen)
            for x in range(left, int(rect.right()), grid_size):
                painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
            for y in range(top, int(rect.bottom()), grid_size):
                painter.drawLine(int(rect.left()), y, int(rect.right()), y)

    def mouseMoveEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        self.coords_changed.emit(int(scene_pos.x()), int(scene_pos.y()))
        if self.main.current_tool and self.ghost_item:
            x, y = scene_pos.x(), scene_pos.y()
            if self.main.snap_active.isChecked():
                x = round(x / PASSO_SNAP) * PASSO_SNAP
                y = round(y / PASSO_SNAP) * PASSO_SNAP
            self.ghost_item.setPos(x, y)
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            items = self.scene().items(self.mapToScene(event.pos()))
            items = [i for i in items if i != self.ghost_item]
            
            # Se clicar no fundo ou vazio, adiciona item
            if not items or items[0].data(0) == "background":
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
            # Aceita tanto NoteItem quanto LabelItem
            if isinstance(item, (NoteItem, LabelItem)):
                target_item = item
                break 
        
        if target_item:
            menu = QMenu()
            action_del = QAction(f"Excluir ({target_item.tipo})", self)
            action_del.triggered.connect(lambda: self.main.delete_specific_item(target_item))
            menu.addAction(action_del)
            
            # Só permite trocar se for Nota Musical (Tags não trocam por Notas e vice-versa para simplicidade)
            if isinstance(target_item, NoteItem) and "TAG" not in self.main.current_tool:
                action_swap = QAction(f"Trocar por '{self.main.current_tool}'", self)
                action_swap.triggered.connect(lambda: self.main.swap_item_type(target_item))
                menu.addSeparator()
                menu.addAction(action_swap)
                
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
            self.main.delete_selected(); return
        
        selected_items = self.scene().selectedItems()
        if selected_items:
            dx, dy = 0, 0
            if event.key() == Qt.Key.Key_Left:  dx = -1
            if event.key() == Qt.Key.Key_Right: dx = 1
            if event.key() == Qt.Key.Key_Up:    dy = -1
            if event.key() == Qt.Key.Key_Down:  dy = 1
            if dx or dy:
                self.main.save_state()
                for item in selected_items: item.moveBy(dx, dy)
                return
        super().keyPressEvent(event)

# ====================== JANELA PRINCIPAL ======================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Editor Musical Pro (Multi-Páginas)")
        self.resize(1600, 1000)
        
        self.current_tool = "SEMINIMA"
        self.current_image_paths = [] # AGORA É UMA LISTA
        self.history = []
        self.history_pos = -1
        self.images_status = {} 
        
        self.init_ui()
        self.scene = QGraphicsScene()
        self.view.set_scene(self.scene)
        self.select_tool("SEMINIMA")
        self.refresh_playlist()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_box = QHBoxLayout(central_widget)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_box.addWidget(splitter)

        # PAINEL ESQUERDO
        left_panel = QWidget(); left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("LISTA DE HINOS (IMAGENS)"))
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.on_playlist_click)
        left_layout.addWidget(self.list_widget)
        btn_refresh = QPushButton("Atualizar Lista"); btn_refresh.clicked.connect(self.refresh_playlist)
        left_layout.addWidget(btn_refresh)
        splitter.addWidget(left_panel); splitter.setStretchFactor(0, 1)

        # PAINEL DIREITO
        right_panel = QWidget(); right_layout = QVBoxLayout(right_panel); right_layout.setContentsMargins(0,0,0,0)
        
        # Barra Topo
        top_bar = QFrame(); top_bar.setStyleSheet("background-color: #2c3e50; color: white;")
        top_layout = QHBoxLayout(top_bar)
        
        self.add_btn(top_layout, "Nova Img (Multi)", self.select_images, "#2980b9")
        top_layout.addSpacing(10)
        self.add_btn(top_layout, "Salvar Rascunho", lambda: self.trigger_save("em_andamento"), "#f39c12")
        self.add_btn(top_layout, "✅ CONCLUIR", lambda: self.trigger_save("concluido"), "#27ae60")
        
        top_layout.addSpacing(10)
        self.add_btn(top_layout, "Limpar", self.clear_all, "#c0392b")
        self.add_btn(top_layout, "Undo", self.undo, "#7f8c8d")
        
        self.snap_active = QCheckBox("Snap"); self.snap_active.setChecked(True)
        top_layout.addWidget(self.snap_active)

        # Zoom
        btn_zout = QPushButton("-"); btn_zout.clicked.connect(lambda: self.view.scale(0.9, 0.9)); btn_zout.setFixedSize(30,25)
        self.lbl_zoom = QLabel("100%"); self.lbl_zoom.setFixedWidth(50)
        btn_zin = QPushButton("+"); btn_zin.clicked.connect(lambda: self.view.scale(1.1, 1.1)); btn_zin.setFixedSize(30,25)
        top_layout.addWidget(btn_zout); top_layout.addWidget(self.lbl_zoom); top_layout.addWidget(btn_zin)

        # Preview
        self.lbl_icon_preview = QLabel(); self.lbl_icon_preview.setFixedSize(40,40); self.lbl_icon_preview.setStyleSheet("border: 1px solid gray;")
        self.lbl_tool_name = QLabel("SEMINIMA"); self.lbl_tool_name.setStyleSheet("color: #f1c40f; font-weight: bold;")
        top_layout.addWidget(self.lbl_icon_preview); top_layout.addWidget(self.lbl_tool_name)
        
        top_layout.addStretch()
        self.lbl_coords = QLabel("x: 0 y: 0"); top_layout.addWidget(self.lbl_coords)
        right_layout.addWidget(top_bar)

        # Paleta
        scroll_paleta = QScrollArea(); scroll_paleta.setFixedHeight(80); scroll_paleta.setWidgetResizable(True)
        paleta_content = QWidget(); paleta_layout = QHBoxLayout(paleta_content); paleta_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.tool_buttons = {}
        
        # 1. Adiciona Tags de Estrutura PRIMEIRO
        for tag in TAGS_ESTRUTURA:
            self.create_palette_btn(tag, paleta_layout, is_tag=True)
        
        # Divisor
        line = QFrame(); line.setFrameShape(QFrame.Shape.VLine); line.setFrameShadow(QFrame.Shadow.Sunken); paleta_layout.addWidget(line)

        # 2. Adiciona Notas Musicais
        for nota in VALORES_NOTAS:
            self.create_palette_btn(nota, paleta_layout, is_tag=False)
            
        scroll_paleta.setWidget(paleta_content)
        right_layout.addWidget(scroll_paleta)

        self.view = MusicalView(self)
        self.view.coords_changed.connect(lambda x, y: self.lbl_coords.setText(f"x: {x} y: {y}"))
        right_layout.addWidget(self.view)
        splitter.addWidget(right_panel); splitter.setStretchFactor(1, 4)

    def add_btn(self, layout, text, func, color):
        btn = QPushButton(text); btn.clicked.connect(func)
        btn.setStyleSheet(f"background-color: {color}; color: white; border: none; padding: 5px 10px; font-weight: bold;")
        layout.addWidget(btn)

    def create_palette_btn(self, nome, layout, is_tag):
        btn = QPushButton(); btn.setFixedSize(60 if is_tag else 45, 45)
        pix = ImageCache.get_pixmap(nome, 35)
        btn.setIcon(QIcon(pix)); btn.setIconSize(btn.size() * 0.8)
        btn.setToolTip(nome)
        btn.clicked.connect(partial(self.select_tool, nome))
        # Estilo diferente para tags
        border_col = "#2980b9" if is_tag else "#bdc3c7"
        btn.setStyleSheet(f"background-color: #ecf0f1; border: 1px solid {border_col};")
        layout.addWidget(btn)
        self.tool_buttons[nome] = btn

    # ================= CARREGAMENTO DE IMAGENS (MULTI) =================
    def select_images(self):
        # Permite selecionar múltiplos arquivos
        fnames, _ = QFileDialog.getOpenFileNames(self, "Selecionar Imagens (Segure Ctrl)", IMG_FOLDER, "Images (*.png *.jpg *.jpeg)")
        if fnames:
            # Ordena por nome para garantir ordem (página 1, página 2...)
            fnames.sort()
            self.load_images_to_scene(fnames)

    def load_images_to_scene(self, paths):
        """Carrega uma ou mais imagens empilhadas verticalmente"""
        self.scene.clear()
        self.current_image_paths = paths # Guarda a lista
        
        y_cursor = 0
        
        for path in paths:
            if not os.path.exists(path): continue
            
            pixmap = QPixmap(path)
            bg_item = self.scene.addPixmap(pixmap)
            bg_item.setData(0, "background")
            bg_item.setZValue(-100)
            
            # Posiciona a imagem atual abaixo da anterior
            bg_item.setPos(0, y_cursor)
            
            # Atualiza cursor + padding (20px entre páginas)
            y_cursor += pixmap.height() + 20

            # Desenha uma linha divisória visual
            line = self.scene.addLine(0, y_cursor - 10, pixmap.width(), y_cursor - 10, QPen(Qt.GlobalColor.black, 2))
            line.setZValue(-99)

        self.scene.setSceneRect(self.scene.itemsBoundingRect())
        self.history = []
        self.history_pos = -1
        self.view.reset_ghost()
        self.view.update_ghost_icon(self.current_tool)
        self.update_title()

    # ================= EDIÇÃO =================
    def add_item_at_mouse(self, pos):
        if not self.current_image_paths: return
        
        x, y = pos.x(), pos.y()
        if self.snap_active.isChecked():
            x = round(x / PASSO_SNAP) * PASSO_SNAP
            y = round(y / PASSO_SNAP) * PASSO_SNAP
            
        # Decide se cria Nota ou Tag
        if "TAG_" in self.current_tool:
            item = LabelItem(self.current_tool, x, y, self.snap_active.isChecked)
        else:
            item = NoteItem(self.current_tool, x, y, self.snap_active.isChecked)
            
        self.scene.addItem(item)

    # ================= ESTADO / JSON =================
    def get_current_state(self):
        # Pega TODOS os itens (notas e tags)
        raw_items = []
        for item in self.scene.items():
            if isinstance(item, (NoteItem, LabelItem)):
                raw_items.append({
                    "tipo": item.tipo,
                    "x": round(item.x(), 1),
                    "y": round(item.y(), 1)
                })
        
        if not raw_items: return []
        
        # Ordenação inteligente
        raw_items.sort(key=lambda n: n['y'])
        
        sorted_final = []
        current_line = []
        if raw_items:
            current_line.append(raw_items[0])
            line_y_ref = raw_items[0]['y']
            
        LINE_THRESHOLD = 80
        for i in range(1, len(raw_items)):
            it = raw_items[i]
            # Se for TAG, tratamos como uma linha separada geralmente, mas o sort Y já cuida disso
            if abs(it['y'] - line_y_ref) < LINE_THRESHOLD:
                current_line.append(it)
            else:
                current_line.sort(key=lambda n: n['x'])
                sorted_final.extend(current_line)
                current_line = [it]
                line_y_ref = it['y']
        
        if current_line:
            current_line.sort(key=lambda n: n['x'])
            sorted_final.extend(current_line)
        return sorted_final

    def apply_state(self, state_list):
        # Remove itens móveis
        for item in self.scene.items():
            if isinstance(item, (NoteItem, LabelItem)):
                self.scene.removeItem(item)
        
        for data in state_list:
            tipo = data["tipo"]
            if "TAG_" in tipo:
                item = LabelItem(tipo, data["x"], data["y"], self.snap_active.isChecked)
            else:
                item = NoteItem(tipo, data["x"], data["y"], self.snap_active.isChecked)
            self.scene.addItem(item)
        self.update_title()

    # ================= SALVAMENTO =================
    def trigger_save(self, status):
        if not self.current_image_paths:
            QMessageBox.warning(self, "Aviso", "Nenhuma imagem carregada!")
            return

        # Pega nome da PRIMEIRA imagem como referência para sugestão inicial
        first_img_name = os.path.basename(self.current_image_paths[0])
        default_name = os.path.splitext(first_img_name)[0]
        
        # Tenta achar JSON existente
        existing = self.find_json_for_image(first_img_name)
        if existing: default_name = os.path.splitext(os.path.basename(existing))[0]

        title_dialog = "Salvar Rascunho" if status == "em_andamento" else "Concluir Hino"
        
        # Prompt atualizado para indicar que pode ser número
        hymn_title, ok = QInputDialog.getText(self, title_dialog, "Digite o Número (ex: 1) ou Título:", text=default_name)
        
        if ok and hymn_title:
            # === NOVA LÓGICA DE FORMATAÇÃO ===
            clean_input = hymn_title.strip()
            
            # Verifica se o usuário digitou apenas números (ex: "1", "55", "100")
            if clean_input.isdigit():
                numero = int(clean_input)
                # Formata para Hino_XXX (ex: Hino_001, Hino_055, Hino_100)
                hymn_title = f"Hino_{numero:03d}"
            else:
                # Se não for número, mantém o texto original
                hymn_title = clean_input
            # =================================

            if not hymn_title.lower().endswith(".json"): hymn_title += ".json"
            save_path = os.path.join(JSON_FOLDER, hymn_title)
            
            data = {
                "imagem_fundo": self.current_image_paths[0], 
                "imagens_fundo": self.current_image_paths,   
                "hino_titulo": hymn_title.replace(".json", ""),
                "status": status,
                "notas": self.get_current_state()
            }
            
            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                QMessageBox.information(self, "Sucesso", f"Salvo como: {hymn_title}") # Mostra confirmação do nome
                self.refresh_playlist()
            except Exception as e: QMessageBox.critical(self, "Erro", f"Erro: {e}")

    # ================= PLAYLIST E LOADER =================
    def on_playlist_click(self, item):
        clean_name = item.text().replace("✅ ", "").replace("⬜ ", "").replace("🚧 ", "")
        
        # Procura JSON
        json_path = self.find_json_for_image(clean_name)
        
        if json_path:
            # Carrega pelo JSON (que sabe se tem multiplas páginas)
            self.load_from_json_file(json_path)
        else:
            # Carrega só a imagem clicada
            self.load_images_to_scene([os.path.join(IMG_FOLDER, clean_name)])

    def find_json_for_image(self, img_filename):
        # Prioriza concluídos
        json_files = glob.glob(os.path.join(JSON_FOLDER, "*.json"))
        candidate = None
        for jf in json_files:
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Verifica na lista nova ou na string antiga
                    imgs = data.get("imagens_fundo", [data.get("imagem_fundo", "")])
                    # Pega apenas nomes de arquivo
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
            
            # Suporte a legado (string) e novo (lista)
            paths = data.get("imagens_fundo", [])
            if not paths and data.get("imagem_fundo"):
                paths = [data.get("imagem_fundo")]
            
            # Verifica se arquivos existem
            valid_paths = []
            for p in paths:
                if os.path.exists(p): valid_paths.append(p)
                else:
                    # Tenta achar na pasta padrão se caminho mudou
                    local_p = os.path.join(IMG_FOLDER, os.path.basename(p))
                    if os.path.exists(local_p): valid_paths.append(local_p)
            
            if valid_paths:
                self.load_images_to_scene(valid_paths)
                self.apply_state(data.get("notas", []))
                self.save_state()
            else:
                QMessageBox.warning(self, "Erro", "Imagens não encontradas no disco.")
                
        except Exception as e: QMessageBox.critical(self, "Erro", f"Erro JSON: {e}")

    def refresh_playlist(self):
        self.list_widget.clear()
        self.images_status = {}
        json_files = glob.glob(os.path.join(JSON_FOLDER, "*.json"))
        
        for jf in json_files:
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Pega todas as imagens associadas a este JSON
                    imgs = data.get("imagens_fundo", [data.get("imagem_fundo", "")])
                    status = data.get("status", "em_andamento")
                    
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
            try: images.sort(key=lambda x: int(''.join(filter(str.isdigit, x))) if any(char.isdigit() for char in x) else x)
            except: images.sort()
            
            for img_name in images:
                item = QListWidgetItem(img_name)
                if img_name in self.images_status:
                    st = self.images_status[img_name]
                    if st == "concluido":
                        item.setForeground(QColor("#27ae60")); item.setText(f"✅ {img_name}"); item.setBackground(QColor("#e8f8f5"))
                    else:
                        item.setForeground(QColor("#d35400")); item.setText(f"🚧 {img_name}"); item.setBackground(QColor("#fef9e7"))
                else:
                    item.setForeground(QColor("black")); item.setText(f"⬜ {img_name}")
                self.list_widget.addItem(item)

    # ================= PADRÃO =================
    def select_tool(self, nome):
        self.current_tool = nome; self.lbl_tool_name.setText(nome)
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
        if len(self.history) > MAX_HIST: self.history.pop(0)
        else: self.history_pos += 1
        self.update_title()

    def undo(self):
        if self.history_pos > 0:
            self.history_pos -= 1
            self.apply_state(self.history[self.history_pos])

    def delete_selected(self):
        selected = self.scene.selectedItems()
        if not selected: return
        self.save_state()
        for item in selected: self.scene.removeItem(item)

    def delete_specific_item(self, item):
        self.save_state(); self.scene.removeItem(item)

    def swap_item_type(self, item):
        self.save_state()
        x, y = item.x(), item.y()
        self.scene.removeItem(item)
        self.add_item_at_mouse(QPointF(x, y)) # Re-adiciona com ferramenta atual

    def clear_all(self):
        if QMessageBox.question(self, "Limpar", "Remover tudo?") == QMessageBox.Yes:
            self.save_state()
            for item in self.scene.items(): 
                if isinstance(item, (NoteItem, LabelItem)): self.scene.removeItem(item)

    def update_zoom_label(self, scale):
        self.lbl_zoom.setText(f"{int(scale*100)}%")

    def update_title(self):
        if not self.current_image_paths: t = "Sem Imagem"
        else: t = f"{len(self.current_image_paths)} Imagens Carregadas"
        c = sum(1 for i in self.scene.items() if isinstance(i, (NoteItem, LabelItem)))
        self.setWindowTitle(f"Editor Musical Pro - {t} ({c} itens)")

if __name__ == "__main__":
    app = QApplication(sys.argv); app.setStyle("Fusion"); window = MainWindow(); window.show(); sys.exit(app.exec())