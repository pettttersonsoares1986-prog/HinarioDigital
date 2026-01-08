# dialogs.py (COMPLETO)
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget, QWidget,
    QPushButton, QLabel, QSpinBox, QDoubleSpinBox, QScrollArea,
    QMessageBox, QInputDialog
)
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt, QTimer
from PIL import Image
from core.config import GLOBAL_CONFIG, IMG_FOLDER, OUTPUT_FOLDER,PREVIEW_FOLDER
import os
from core.logger import log_info, log_debug, log_error


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurações")
        self.resize(450, 500)
        self.layout = QVBoxLayout(self)

        tabs = QTabWidget()

        # Tab Padrão
        tab_std = QWidget()
        form_std = QFormLayout(tab_std)
        self.spin_crop_y = self.add_spin(form_std, "Distância Y (Vertical):", GLOBAL_CONFIG["CROP_OFFSET_Y"])
        self.spin_crop_w = self.add_spin(form_std, "Largura do Recorte:", GLOBAL_CONFIG["CROP_WIDTH"])
        self.spin_crop_h = self.add_spin(form_std, "Altura do Recorte:", GLOBAL_CONFIG["CROP_HEIGHT"])
        tabs.addTab(tab_std, "Padrão / Versos")

        # Tab Coro
        tab_chorus = QWidget()
        form_chorus = QFormLayout(tab_chorus)
        self.spin_chorus_y = self.add_spin(form_chorus, "Distância Y (Coro/Final):", GLOBAL_CONFIG["CHORUS_OFFSET_Y"])
        self.spin_chorus_w = self.add_spin(form_chorus, "Largura (Coro/Final):", GLOBAL_CONFIG["CHORUS_WIDTH"])
        self.spin_chorus_h = self.add_spin(form_chorus, "Altura (Coro/Final):", GLOBAL_CONFIG["CHORUS_HEIGHT"])
        tabs.addTab(tab_chorus, "Coro / Final")

        # Tab Página
        tab_page = QWidget()
        form_page = QFormLayout(tab_page)
        self.spin_zoom = QDoubleSpinBox()
        self.spin_zoom.setRange(0.5, 5.0)
        self.spin_zoom.setSingleStep(0.1)
        self.spin_zoom.setValue(GLOBAL_CONFIG["CROP_ZOOM"])
        form_page.addRow(QLabel("Zoom do Texto:"), self.spin_zoom)
        self.spin_snap = self.add_spin(form_page, "Grade / Snap:", GLOBAL_CONFIG["SNAP_GRID"])
        self.spin_spacing = self.add_spin(form_page, "Espaço Notas:", GLOBAL_CONFIG["SPACING_NOTE"])
        self.spin_page_w = self.add_spin(form_page, "Largura Página:", GLOBAL_CONFIG["PAGE_WIDTH"])
        tabs.addTab(tab_page, "Página / Zoom")

        self.layout.addWidget(tabs)

        btn_box = QHBoxLayout()
        btn_save = QPushButton("Salvar e Fechar")
        btn_save.clicked.connect(self.save)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_save)
        btn_box.addWidget(btn_cancel)
        self.layout.addLayout(btn_box)

    def add_spin(self, layout, label, value):
        s = QSpinBox()
        s.setRange(0, 5000)
        s.setValue(value)
        layout.addRow(QLabel(label), s)
        return s

    def save(self):
        log_info("Salvando configurações")
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
        log_debug("Configurações salvas com sucesso")
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

        self.spin_w = QSpinBox()
        self.spin_w.setRange(10, 500)
        self.spin_w.setValue(w)
        self.layout.addRow(QLabel("Largura:"), self.spin_w)

        self.spin_h = QSpinBox()
        self.spin_h.setRange(10, 500)
        self.spin_h.setValue(h)
        self.layout.addRow(QLabel("Altura:"), self.spin_h)

        self.spin_y = QSpinBox()
        self.spin_y.setRange(-100, 500)
        self.spin_y.setValue(y)
        self.layout.addRow(QLabel("Deslocamento Y:"), self.spin_y)

        btn_box = QHBoxLayout()
        btn_save = QPushButton("Salvar")
        btn_save.clicked.connect(self.accept)
        btn_reset = QPushButton("Resetar Global")
        btn_reset.clicked.connect(self.reset_global)
        btn_box.addWidget(btn_save)
        btn_box.addWidget(btn_reset)
        self.layout.addRow(btn_box)

        self.result_data = None

    def reset_global(self):
        log_debug("Resetando para configurações globais")
        self.result_data = None
        self.accept()

    def accept(self):
        if self.result_data is None:
            self.result_data = {
                'w': self.spin_w.value(),
                'h': self.spin_h.value(),
                'y': self.spin_y.value()
            }
        super().accept()


class PreviewDialog(QDialog):
    def __init__(self, pil_image, base_filename, main_window_ref):
        super().__init__(main_window_ref)
        self.setWindowTitle("Preview da Imagem Gerada")
        self.resize(1000, 700)
        self.pil_image = pil_image
        self.base_filename = base_filename
        self.main = main_window_ref
        self.scale_factor = 1.0
        self.original_pixmap = None

        log_info("Abrindo PreviewDialog")

        layout = QVBoxLayout(self)

        # Zoom Controls
        zoom_layout = QHBoxLayout()
        btn_out = QPushButton(" - ")
        btn_out.setFixedSize(40, 30)
        btn_out.clicked.connect(self.zoom_out)
        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_zoom.setFixedWidth(60)
        btn_in = QPushButton(" + ")
        btn_in.setFixedSize(40, 30)
        btn_in.clicked.connect(self.zoom_in)
        zoom_layout.addWidget(QLabel("Zoom:"))
        zoom_layout.addWidget(btn_out)
        zoom_layout.addWidget(self.lbl_zoom)
        zoom_layout.addWidget(btn_in)
        zoom_layout.addStretch()
        layout.addLayout(zoom_layout)

        # Image Display
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.img_label)
        layout.addWidget(self.scroll_area)
        self.update_image_display()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancelar / Ajustar Mais")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("💾 Apenas Salvar Imagem")
        btn_save.clicked.connect(self.save_only)
        self.btn_gemini = QPushButton("🤖 Enviar para Gemini")
        self.btn_gemini.setStyleSheet(
            "background-color: #8e44ad; color: white; font-weight: bold; font-size: 14px; padding: 10px;"
        )
        self.btn_gemini.clicked.connect(self.send_to_gemini)

        if self.main.cooldown_remaining > 0:
            self.btn_gemini.setEnabled(False)
            self.btn_gemini.setText(f"Aguarde {self.main.cooldown_remaining}s...")

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(self.btn_gemini)
        layout.addLayout(btn_layout)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_button_state)
        self.timer.start(1000)

    def update_image_display(self):
        """Atualiza a exibição da imagem"""
        log_debug("Atualizando exibição da imagem")
        if self.pil_image is None:
            return

        im_data = self.pil_image.convert("RGBA").tobytes("raw", "RGBA")
        qimage = QImage(
            im_data, self.pil_image.width, self.pil_image.height,
            QImage.Format.Format_RGBA8888
        )
        self.original_pixmap = QPixmap.fromImage(qimage)

        if self.original_pixmap.isNull():
            log_error("Falha ao converter para QPixmap")
            return

        new_width = int(self.original_pixmap.width() * self.scale_factor)
        new_height = int(self.original_pixmap.height() * self.scale_factor)
        scaled_pixmap = self.original_pixmap.scaled(
            new_width, new_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.img_label.setPixmap(scaled_pixmap)
        self.lbl_zoom.setText(f"{int(self.scale_factor * 100)}%")

    def zoom_in(self):
        """Aumenta zoom"""
        log_debug("Zoom in")
        self.scale_factor *= 1.2
        self.update_image_display()

    def zoom_out(self):
        """Diminui zoom"""
        log_debug("Zoom out")
        self.scale_factor *= 0.8
        self.update_image_display()

    def wheelEvent(self, event):
        """Suporta zoom com roda do mouse"""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)

    def update_button_state(self):
        """Atualiza estado do botão Gemini baseado no cooldown"""
        remaining_time = self.main.cooldown_remaining
        if remaining_time > 0:
            self.btn_gemini.setEnabled(False)
            self.btn_gemini.setText(f"Aguarde {remaining_time}s...")
        else:
            self.btn_gemini.setEnabled(True)
            self.btn_gemini.setText("🤖 Enviar para Gemini")

    def save_file(self):
        """Salva a imagem na pasta de PREVIEWS"""
        log_info(f"Salvando imagem: {self.base_filename}")

        # Garante que a pasta existe
        os.makedirs(PREVIEW_FOLDER, exist_ok=True)

        save_path = os.path.join(PREVIEW_FOLDER, f"{self.base_filename}.jpg")
        try:
            self.pil_image.convert("RGB").save(save_path, quality=95)
            log_debug(f"Imagem salva em: {save_path}")
            return save_path
        except Exception as e:
            log_error(f"Erro ao salvar imagem", e)
            return None

    def save_only(self):
        """Salva apenas a imagem e fecha"""
        log_info("Salvando apenas a imagem")
        path = self.save_file()
        if path:
            QMessageBox.information(self, "Salvo", f"Imagem salva em:\n{path}")
        self.accept()

    def send_to_gemini(self):
        """Salva e envia para Gemini"""
        log_info("Enviando para Gemini")
        path = self.save_file()
        if path:
            self.accept()
            self.main.trigger_gemini_processing(path, self.base_filename)
