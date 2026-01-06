# graphics_view.py (atualizado com logs)
from PyQt6.QtWidgets import QGraphicsView, QMenu
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QColor, QAction

from core.config import GLOBAL_CONFIG
from ui.graphics_items import NoteItem, LabelItem, HeaderBoxItem, TimeSigBoxItem
from core.logger import log_info, log_debug, log_error, log_warning


class MusicalView(QGraphicsView):
    coords_changed = pyqtSignal(int, int)

    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        log_info("Inicializando MusicalView")
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.ghost_item = None
        self.start_pos = None
        self.current_drawing_box = None
        log_debug("MusicalView inicializada")

    def set_scene(self, scene):
        log_debug("Definindo cena para MusicalView")
        self.setScene(scene)
        self.reset_ghost()

    def reset_ghost(self):
        from PyQt6.QtWidgets import QGraphicsPixmapItem
        log_debug("Resetando ghost item")
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
        log_debug("Ghost item resetado")

    def update_ghost_icon(self, tipo):
        log_debug(f"Atualizando ghost icon para: {tipo}")
        if self.ghost_item:
            from core.cache import ImageCache
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
            log_debug("Modo desenho ativo, movendo retângulo")
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

    # graphics_view.py - Atualize mousePressEvent com mais logs

    def mousePressEvent(self, event):
        log_debug(f"Mouse pressionado em: {event.pos()}")
        log_debug(f"is_drawing_header: {self.main.is_drawing_header}")
        log_debug(f"is_drawing_timesig: {self.main.is_drawing_timesig}")
        log_debug(f"current_tool: {self.main.current_tool}")

        if event.button() == Qt.MouseButton.LeftButton:
            # Modo Desenho
            if self.main.is_drawing_header or self.main.is_drawing_timesig:
                log_info("Iniciando desenho de retângulo")
                self.start_pos = self.mapToScene(event.pos())
                t_type = HeaderBoxItem if self.main.is_drawing_header else TimeSigBoxItem
                for i in self.scene().items():
                    if isinstance(i, t_type):
                        self.scene().removeItem(i)
                return

            # Adicionar Nota
            scene_pos = self.mapToScene(event.pos())
            log_debug(f"Posição na cena: {scene_pos}")

            items = self.scene().items(scene_pos)
            log_debug(f"Itens na posição: {len(items)}")
            for item in items:
                log_debug(f"  - {type(item).__name__}")

            real_items = [i for i in items if i != self.ghost_item and i.data(0) != "background"]
            log_debug(f"Itens reais (sem ghost): {len(real_items)}")

            if not real_items:
                log_info(f"Adicionando nota: {self.main.current_tool}")
                self.main.add_item_at_mouse(scene_pos)
                log_info(f"Total de itens na cena agora: {len(self.scene().items())}")
                return
            else:
                log_debug(f"Item real encontrado, não adicionando nota")

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        log_debug("Mouse liberado")
        # Finaliza desenho de retângulo
        if (self.main.is_drawing_header or self.main.is_drawing_timesig) and self.start_pos:
            log_info("Finalizando desenho de retângulo")
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
        item = next(
            (i for i in self.scene().items(sp) if isinstance(i, (NoteItem, LabelItem, HeaderBoxItem, TimeSigBoxItem))),
            None
        )

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
            if event.key() == Qt.Key.Key_Left:
                dx = -1
            if event.key() == Qt.Key.Key_Right:
                dx = 1
            if event.key() == Qt.Key.Key_Up:
                dy = -1
            if event.key() == Qt.Key.Key_Down:
                dy = 1

            if dx or dy:
                self.main.save_state()
                for i in sel:
                    i.moveBy(dx, dy)
                return

        super().keyPressEvent(event)
