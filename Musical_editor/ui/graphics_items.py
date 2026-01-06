# graphics_items.py
from PyQt6.QtWidgets import QGraphicsObject, QGraphicsRectItem
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath
from core.cache import ImageCache
from core.config import GLOBAL_CONFIG

class LabelItem(QGraphicsObject):
    def __init__(self, tipo, x, y, snap_enabled_callback):
        super().__init__()
        self.tipo = tipo
        self.snap_callback = snap_enabled_callback
        self.label_text = tipo.replace("TAG_", "")
        self.setPos(x, y)
        self.setFlags(
            QGraphicsObject.GraphicsItemFlag.ItemIsMovable |
            QGraphicsObject.GraphicsItemFlag.ItemIsSelectable
        )
        self.setAcceptHoverEvents(True)
        self.is_hovered = False

    def boundingRect(self):
        return QRectF(0, 0, 80, 30)

    def paint(self, painter, option, widget):
        color = QColor("#3498db")
        if "CORO" in self.tipo:
            color = QColor("#e67e22")
        elif "FINAL" in self.tipo:
            color = QColor("#27ae60")

        if self.is_hovered:
            color = color.lighter(120)

        painter.setBrush(QBrush(color))
        painter.setPen(QPen(
            Qt.GlobalColor.black if not self.isSelected() else Qt.GlobalColor.yellow, 1
        ))
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
        if change == QGraphicsObject.GraphicsItemChange.ItemPositionChange and self.scene() and self.snap_callback():
            grid = GLOBAL_CONFIG["SNAP_GRID"]
            return QPointF(round(value.x()/grid)*grid, round(value.y()/grid)*grid)
        return super().itemChange(change, value)


class HeaderBoxItem(QGraphicsRectItem):
    def __init__(self, rect):
        super().__init__(rect)
        self.setFlags(
            QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.setBrush(QBrush(QColor(0, 120, 215, 80)))
        self.setPen(QPen(QColor(0, 120, 215), 2))
        self.tipo = "HEADER_BOX"

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        painter.setPen(QPen(Qt.GlobalColor.black))
        painter.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "CABEÇALHO")

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.GraphicsItemChange.ItemPositionChange and self.scene():
            snap = GLOBAL_CONFIG["SNAP_GRID"]
            return QPointF(round(value.x()/snap)*snap, round(value.y()/snap)*snap)
        return super().itemChange(change, value)


class TimeSigBoxItem(QGraphicsRectItem):
    def __init__(self, rect):
        super().__init__(rect)
        self.setFlags(
            QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.setBrush(QBrush(QColor(255, 165, 0, 80)))
        self.setPen(QPen(QColor(255, 140, 0), 2))
        self.tipo = "TIMESIG_BOX"

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        painter.setPen(QPen(Qt.GlobalColor.black))
        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "COMPASSO")

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.GraphicsItemChange.ItemPositionChange and self.scene():
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
        self.setFlags(
            QGraphicsObject.GraphicsItemFlag.ItemIsMovable |
            QGraphicsObject.GraphicsItemFlag.ItemIsSelectable
        )
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
            if self.scene():
                tags = [it for it in self.scene().items() if isinstance(it, LabelItem)]
                tags.sort(key=lambda item: (item.y(), item.x()))
                last_valid_tag = None
                for tag in tags:
                    if tag.y() < (self.y() - 50) or (abs(tag.y() - self.y()) <= 50 and tag.x() < self.x()):
                        last_valid_tag = tag
                if last_valid_tag and ("CORO" in last_valid_tag.tipo or "FINAL" in last_valid_tag.tipo):
                    is_chorus_mode = True

            if self.custom_crop_params:
                w_box = self.custom_crop_params['w']
                h_box = self.custom_crop_params['h']
                y_box = self.custom_crop_params['y']
                color_pen = QColor(255, 0, 255)
            elif is_chorus_mode:
                w_box = GLOBAL_CONFIG["CHORUS_WIDTH"]
                h_box = GLOBAL_CONFIG["CHORUS_HEIGHT"]
                y_box = GLOBAL_CONFIG["CHORUS_OFFSET_Y"]
                color_pen = QColor(255, 165, 0)
            else:
                w_box = GLOBAL_CONFIG["CROP_WIDTH"]
                h_box = GLOBAL_CONFIG["CROP_HEIGHT"]
                y_box = GLOBAL_CONFIG["CROP_OFFSET_Y"]
                color_pen = QColor(0, 255, 255)

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
        if change == QGraphicsObject.GraphicsItemChange.ItemPositionChange and self.scene():
            if self.snap_callback():
                grid = GLOBAL_CONFIG.get("SNAP_GRID", 20)
                x = round(value.x() / grid) * grid
                y = round(value.y() / grid) * grid
                return QPointF(x, y)
        return super().itemChange(change, value)
