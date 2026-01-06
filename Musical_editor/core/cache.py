# cache.py
import os
from PIL import Image, ImageDraw
from PyQt6.QtGui import QPixmap, QImage, QPainter, QBrush, QPen, QColor
from PyQt6.QtCore import Qt, QPointF
from core.config import ICONS_FOLDER

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
