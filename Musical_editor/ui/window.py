# window.py - VERSÃO FINAL CONSOLIDADA (COMPLETA E CORRIGIDA)

import json
import os
import glob
import time
from functools import partial

from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QSize, QEvent, QThread, QTimer, QMimeData
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
from PyQt6.QtGui import QPixmap, QPen, QShortcut, QKeySequence

# Importar de config
from core.config import (
    IMG_FOLDER, JSON_FOLDER, GLOBAL_CONFIG, FERRAMENTAS_ORGANIZADAS, MAPA_ATALHOS,PREVIEW_FOLDER,
    ICONS_FOLDER, OUTPUT_FOLDER, MINHA_API_KEY
)

# Importar logger
from core.logger import log_info, log_debug, log_error, log_warning, init_logger

# Importar módulos locais
from core.utils import clean_filename, natural_sort_key
from core.cache import ImageCache
from ui.graphics_view import MusicalView
from ui.dialogs import SettingsDialog, PreviewDialog
from rendering.image_renderer import ImageRenderer
from ui.list_widgets import ImageListWidget, ProjectListWidget
from ui.panels import LeftPanel, RightPanel
from ui.graphics_items import NoteItem, LabelItem, HeaderBoxItem, TimeSigBoxItem
from core.workers import GeminiWorker

# Importar PIL
from PIL import Image, ImageDraw, ImageEnhance, ImageOps, ImageFont

# ====================== MAIN WINDOW ======================

class MainWindow(QMainWindow):
    """Janela principal da aplicacao"""

    def __init__(self):
        try:
            super().__init__()
            self.setWindowTitle("Editor Musical Pro V32 - Final Expandido")
            self.resize(1600, 1000)

            log_debug(f"IMG_FOLDER: {IMG_FOLDER}")
            log_debug(f"JSON_FOLDER: {JSON_FOLDER}")
            log_debug(f"ICONS_FOLDER: {ICONS_FOLDER}")
            log_debug(f"PREVIEW_FOLDER: {PREVIEW_FOLDER}")
            log_debug(f"OUTPUT_FOLDER: {OUTPUT_FOLDER}")
            log_debug(f"MINHA_API_KEY configurada: {bool(MINHA_API_KEY)}")

            # Estado
            self.current_tool = "SEMINIMA"
            self.current_image_paths = []
            self.current_json_path = None
            self.history = []
            self.history_pos = -1
            self.is_drawing_header = False
            self.is_drawing_timesig = False
            self.cooldown_remaining = 0
            self.worker = None
            self.progress_dialog = None
            self.progress_timer = None
            self.progress_value = 0
            log_debug("Estado inicial configurado")

            # Timers
            self.cooldown_timer = QTimer(self)
            self.cooldown_timer.timeout.connect(self.update_cooldown)
            self.cooldown_timer.start(1000)
            self.preview_timer = QTimer(self)
            self.preview_timer.setSingleShot(True)
            self.preview_timer.timeout.connect(self.generate_auto_preview)
            log_debug("Timers configurados")

            # Cria a cena ANTES de init_ui
            self.scene = QGraphicsScene()
            log_debug("QGraphicsScene criada")

            # UI
            log_info("Inicializando UI...")
            self.init_ui()
            log_info("UI inicializada com sucesso")

            # Conecta sinal DEPOIS que view foi criada
            self.scene.changed.connect(self.on_scene_changed)
            log_debug("Sinal scene.changed conectado")

            self.setup_shortcuts()
            log_debug("Atalhos configurados")

            # Atualizar listas na inicializacao
            log_info("Chamando refresh_playlists na inicializacao")
            self.refresh_playlists()

            log_info("APLICACAO INICIALIZADA COM SUCESSO")
            log_info("=" * 60 + "\n")

        except Exception as e:
            log_error("Erro fatal na inicializacao da MainWindow", e)
            raise

    def init_ui(self):
        """Inicializa a interface grafica"""
        log_debug("Iniciando init_ui")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Painel Esquerdo
        log_debug("Criando LeftPanel")
        self.left_panel = LeftPanel(self)
        splitter.addWidget(self.left_panel)

        # Painel Central
        log_debug("Criando painel central")
        center_widget = QWidget()
        self.setup_center_panel(center_widget)
        splitter.addWidget(center_widget)

        # Painel Direito
        log_debug("Criando RightPanel")
        self.right_panel = RightPanel(self)
        splitter.addWidget(self.right_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 1)
        main_layout.addWidget(splitter)
        log_debug("init_ui concluido")

    def setup_center_panel(self, parent_widget):
        """Configura painel central"""
        log_debug("Configurando painel central")
        layout = QVBoxLayout(parent_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = self.create_toolbar()
        layout.addWidget(toolbar)

        # Canvas
        log_debug("Criando MusicalView")
        self.view = MusicalView(self)
        self.view.coords_changed.connect(
            lambda x, y: self.lbl_coords.setText(f"x: {x} y: {y}")
        )
        self.view.set_scene(self.scene)
        layout.addWidget(self.view)
        log_debug("MusicalView criada e adicionada")

    def create_toolbar(self):
        """Cria toolbar central"""
        log_debug("Criando toolbar")
        toolbar = QFrame()
        toolbar.setStyleSheet("background-color: #2c3e50; color: white;")
        layout = QHBoxLayout(toolbar)

        self.add_btn(layout, "Salvar", lambda: self.trigger_save("em_andamento"), "#f39c12")
        self.add_btn(layout, "Concluir", lambda: self.trigger_save("concluido"), "#27ae60")
        layout.addSpacing(20)
        self.add_btn(layout, "Desenhar Cabecalho", self.enable_header_drawing, "#3498db")
        self.add_btn(layout, "Desenhar Compasso", self.enable_timesig_drawing, "#e67e22")
        layout.addSpacing(20)
        self.add_btn(layout, "PREVIEW", self.generate_preview, "#8e44ad")
        layout.addSpacing(20)

        self.snap_active = QCheckBox("Snap Grid")
        self.snap_active.setChecked(False)
        self.snap_active.setStyleSheet("color: white;")
        layout.addWidget(self.snap_active)

        self.chk_continuous = QCheckBox("Modo Continuo")
        self.chk_continuous.setStyleSheet("color: white;")
        layout.addWidget(self.chk_continuous)

        """self.chk_auto_preview = QCheckBox("Preview Auto")
        self.chk_auto_preview.setStyleSheet("color: white;")
        layout.addWidget(self.chk_auto_preview)"""

        layout.addStretch()

        self.lbl_zoom = QLabel("100%")
        layout.addWidget(self.lbl_zoom)

        self.lbl_coords = QLabel("x:0 y:0")
        layout.addWidget(self.lbl_coords)

        return toolbar

    def add_btn(self, layout, text, func, color):
        """Adiciona botao a toolbar"""
        btn = QPushButton(text)
        btn.clicked.connect(func)
        btn.setStyleSheet(
            f"background-color: {color}; color: white; border: none; padding: 5px 10px; font-weight: bold;"
        )
        layout.addWidget(btn)

    def setup_shortcuts(self):
        """Configura atalhos de teclado"""
        log_debug("Configurando atalhos de teclado")
        for key, tool in MAPA_ATALHOS.items():
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(partial(self.select_tool, tool))
            log_debug(f"Atalho '{key}' -> {tool}")

        QShortcut(QKeySequence("Delete"), self).activated.connect(self.delete_selected)
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self.undo)
        QShortcut(QKeySequence("Ctrl+0"), self).activated.connect(lambda: self.view.resetTransform())
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(lambda: self.trigger_save("em_andamento"))
        log_debug("Atalhos configurados com sucesso")

    # ========== GERENCIAMENTO DE PROJETOS ==========

    def create_project_from_image_drop(self, file_list):
        """Cria novo projeto a partir de imagens arrastadas"""
        log_info(f"Criando projeto a partir de {len(file_list)} imagem(ns)")
        log_debug(f"Arquivos: {file_list}")

        first_file = file_list[0]
        suggestion = os.path.splitext(first_file)[0]
        new_name, ok = QInputDialog.getText(self, "Novo Projeto", "Nome do Hino:", text=suggestion)

        if not ok or not new_name:
            log_warning("Criacao de projeto cancelada pelo usuario")
            return

        json_path = os.path.join(JSON_FOLDER, new_name + ".json")
        if os.path.exists(json_path):
            log_error(f"Projeto ja existe: {json_path}")
            QMessageBox.warning(self, "Erro", "Ja existe um projeto com este nome!")
            return

        full_paths = [os.path.join(IMG_FOLDER, f) for f in file_list]
        log_debug(f"Caminhos completos: {full_paths}")

        self.current_image_paths = full_paths
        self.current_json_path = json_path

        data = {
            "imagem_fundo": full_paths[0],
            "imagens": full_paths,
            "status": "em_andamento",
            "notas": [],
            "configuracoes": GLOBAL_CONFIG
        }

        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            log_info(f"Projeto salvo: {json_path}")
        except Exception as e:
            log_error(f"Erro ao salvar projeto", e)
            return

        self.load_images_to_scene(full_paths)
        self.refresh_playlists()
        self.statusBar().showMessage(f"Projeto '{new_name}' criado!", 3000)
        log_info(f"Projeto '{new_name}' criado com sucesso")

    def merge_selected_images(self):
        """Mescla imagens selecionadas"""
        log_debug("merge_selected_images chamado")
        items = self.left_panel.list_images.selectedItems()
        log_debug(f"Itens selecionados: {len(items)}")

        if not items:
            log_warning("Nenhuma imagem selecionada")
            QMessageBox.warning(self, "Aviso", "Selecione pelo menos uma imagem.")
            return

        file_list = [clean_filename(i.text()) for i in items]
        log_debug(f"Arquivos limpos: {file_list}")
        self.create_project_from_image_drop(file_list)

    def start_edit_from_image(self, item):
        """Inicia edicao a partir de imagem"""
        filename = clean_filename(item.text())
        path = os.path.join(IMG_FOLDER, filename)
        log_info(f"Iniciando edicao de: {filename}")
        log_debug(f"Caminho: {path}")

        self.current_json_path = None
        if os.path.exists(path):
            log_debug(f"Arquivo encontrado, carregando...")
            self.load_images_to_scene([path])
            self.statusBar().showMessage(f"Editando: {filename} (Novo)", 5000)
            log_info(f"Edicao iniciada: {filename}")
        else:
            log_error(f"Arquivo nao encontrado: {path}")
            QMessageBox.warning(self, "Erro", f"Imagem nao encontrada:\n{path}")

    def on_project_double_click(self, item):
        """Abre projeto ao duplo clique"""
        fname = clean_filename(item.text())
        path = os.path.join(JSON_FOLDER, fname)
        log_info(f"Abrindo projeto: {fname}")
        log_debug(f"Caminho: {path}")

        if os.path.exists(path):
            self.current_json_path = path
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    d = json.load(f)

                imgs = d.get('imagens')
                single = d.get('imagem_fundo')

                if imgs:
                    self.current_image_paths = [i for i in imgs if i]
                elif single:
                    self.current_image_paths = [single]
                else:
                    self.current_image_paths = []

                log_debug(f"Imagens carregadas: {len(self.current_image_paths)}")

                # CARREGAR CONFIGURAÇÕES DO PROJETO
                from core.config import load_project_config
                project_config = load_project_config(path)
                GLOBAL_CONFIG.update(project_config)
                log_info(f"Configuracoes do projeto carregadas: {project_config}")

                notas_data = d.get('notas', d.get('data', []))
                log_debug(f"Notas carregadas: {len(notas_data)}")
                self.load_scene_data(notas_data)
                log_info(f"Projeto '{fname}' aberto com sucesso")

            except Exception as e:
                log_error(f"Erro ao abrir projeto", e)
        else:
            log_error(f"Projeto nao encontrado: {path}")


    def rename_project(self, item):
        """Renomeia projeto"""
        old_name = clean_filename(item.text())
        old_path = os.path.join(JSON_FOLDER, old_name)
        log_info(f"Renomeando projeto: {old_name}")

        new_name, ok = QInputDialog.getText(self, "Renomear", "Novo nome:", text=old_name)
        if ok and new_name:
            if not new_name.endswith(".json"):
                new_name += ".json"

            new_path = os.path.join(JSON_FOLDER, new_name)
            try:
                os.rename(old_path, new_path)
                log_info(f"Projeto renomeado: {old_name} -> {new_name}")

                if self.current_json_path == old_path:
                    self.current_json_path = new_path

                self.refresh_playlists()
            except Exception as e:
                log_error(f"Erro ao renomear projeto", e)
                QMessageBox.critical(self, "Erro", str(e))

    def delete_current_project(self):
        """Deleta projeto"""
        item = self.left_panel.list_projects.currentItem()
        if not item:
            log_warning("Nenhum projeto selecionado para deletar")
            return

        fname = clean_filename(item.text())
        path = os.path.join(JSON_FOLDER, fname)
        log_info(f"Tentando deletar projeto: {fname}")

        if QMessageBox.question(
            self, "Excluir", f"Excluir '{fname}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            try:
                os.remove(path)
                log_info(f"Projeto deletado: {fname}")
                self.refresh_playlists()
            except Exception as e:
                log_error(f"Erro ao deletar projeto", e)
                QMessageBox.critical(self, "Erro", str(e))

    def refresh_playlists(self):
        """Atualiza listas"""
        log_debug("refresh_playlists chamado de MainWindow")
        self.left_panel.refresh_playlists()

    # ========== GERENCIAMENTO DE CENA ==========

    def load_images_to_scene(self, paths):
        """Carrega imagens para cena"""
        log_info(f"Carregando {len(paths)} imagem(ns) para cena")
        self.scene.clear()
        self.current_image_paths = paths
        y_offset = 0

        for p in paths:
            if not p or not os.path.exists(p):
                log_warning(f"Imagem nao encontrada: {p}")
                continue

            try:
                log_debug(f"Carregando imagem: {p}")
                pix = QPixmap(p)
                if pix.isNull():
                    log_error(f"Falha ao carregar pixmap: {p}")
                    continue

                item = self.scene.addPixmap(pix)
                item.setZValue(-100)
                item.setPos(0, y_offset)
                item.setData(0, "background")
                item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

                y_offset += pix.height() + 20
                line = self.scene.addLine(0, y_offset - 10, pix.width(), y_offset - 10, QPen(Qt.GlobalColor.black, 2))
                line.setZValue(-99)
                log_debug(f"Imagem carregada com sucesso: {p}")

            except Exception as e:
                log_error(f"Erro ao carregar imagem {p}", e)

        self.scene.setSceneRect(self.scene.itemsBoundingRect())
        self.history = []
        self.view.reset_ghost()
        self.view.update_ghost_icon(self.current_tool)
        self.update_title()
        log_info(f"Cena atualizada com {len(paths)} imagem(ns)")

    def add_item_at_mouse(self, p):
        """Adiciona item no mouse"""
        x, y = p.x(), p.y()
        log_debug(f"Adicionando item em: ({x}, {y})")

        if self.snap_active.isChecked():
            g = GLOBAL_CONFIG.get("SNAP_GRID", 20)
            x = round(x / g) * g
            y = round(y / g) * g
            log_debug(f"Snap ativado, nova posicao: ({x}, {y})")

        if "TAG" in self.current_tool:
            item = LabelItem(self.current_tool, x, y, self.snap_active.isChecked)
            log_debug(f"Tag adicionada: {self.current_tool}")
        else:
            item = NoteItem(self.current_tool, x, y, self.snap_active.isChecked)
            log_debug(f"Nota adicionada: {self.current_tool}")

        self.scene.addItem(item)

    def select_tool(self, tool_name):
        """Seleciona ferramenta"""
        log_debug(f"Ferramenta selecionada: {tool_name}")
        self.current_tool = tool_name
        self.right_panel.update_tool_display(tool_name)
        self.view.update_ghost_icon(tool_name)
        self.is_drawing_header = False
        self.is_drawing_timesig = False
        self.view.setCursor(Qt.CursorShape.ArrowCursor)

    def enable_header_drawing(self):
        """Ativa desenho de cabecalho"""
        log_info("Modo desenho de cabecalho ativado")
        self.is_drawing_header = True
        self.is_drawing_timesig = False
        self.view.setCursor(Qt.CursorShape.CrossCursor)
        self.statusBar().showMessage("Desenhando Cabecalho...")

    def enable_timesig_drawing(self):
        """Ativa desenho de compasso"""
        log_info("Modo desenho de compasso ativado")
        self.is_drawing_timesig = True
        self.is_drawing_header = False
        self.view.setCursor(Qt.CursorShape.CrossCursor)
        self.statusBar().showMessage("Desenhando Compasso...")

    # ========== PREVIEW E DIALOGOS ==========

    def open_settings(self):
        """Abre configuracoes"""
        log_info("Abrindo dialogo de configuracoes")
        SettingsDialog(self).exec()
        self.view.viewport().update()
        self.scene.update()

    def generate_preview(self):
        """Gera preview"""
        log_info("Gerando preview da imagem")

        if self.current_image_paths:
            log_info("Salvando automaticamente antes do preview")
            self.trigger_save("em_andamento")

        ordered_state = self.get_current_state()
        renderer = ImageRenderer(self.scene, self.current_image_paths)
        renderer.ordered_state = ordered_state
        pil_image = renderer.render()

        if not pil_image:
            log_warning("Falha ao gerar preview")
            QMessageBox.warning(self, "Aviso", "Nada para gerar.")
            return

        base_name = "preview"
        if self.current_json_path:
            base_name = os.path.splitext(os.path.basename(self.current_json_path))[0]

        log_debug(f"Preview gerado com nome base: {base_name}")
        PreviewDialog(pil_image, base_name, self).exec()

    def generate_auto_preview(self):
        """Preview automatico"""
        log_debug("Preview automatico acionado")
        pass

    def on_scene_changed(self):
        """Quando cena muda"""
        log_debug("Cena alterada")
        self.save_state()
        """if self.chk_auto_preview.isChecked():
            self.preview_timer.start(GLOBAL_CONFIG.get("AUTO_PREVIEW_DELAY", 2000))"""
        self.update_title()

    # ========== SALVAMENTO ==========

    def trigger_save(self, status):
        """Salva projeto COM CONFIGURAÇÕES"""
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
            hymn_title, ok = QInputDialog.getText(self, title_dialog, "Digite o Numero ou Titulo:", text=default_name)

            if not ok or not hymn_title:
                return

            clean_input = hymn_title.strip()

            # Se for número, salvar como "numero.json"
            if clean_input.isdigit():
                hymn_title = f"{clean_input}.json"
            else:
                # Se não for número, usar como está
                if not hymn_title.lower().endswith(".json"):
                    hymn_title += ".json"

            save_path = os.path.join(JSON_FOLDER, hymn_title)
            self.current_json_path = save_path

        current_state = self.get_current_state()

        # SALVAR COM CONFIGURAÇÕES DO PROJETO
        data = {
            "imagem_fundo": self.current_image_paths[0],
            "imagens": self.current_image_paths,
            "status": status,
            "notas": current_state,
            "configuracoes": GLOBAL_CONFIG  # Salva as configurações atuais
        }

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            self.statusBar().showMessage(f"Salvo em: {os.path.basename(save_path)}", 3000)
            self.refresh_playlists()
            log_info(f"Projeto salvo com configuracoes: {save_path}")

        except Exception as e:
            log_error(f"Erro ao salvar projeto", e)
            QMessageBox.critical(self, "Erro", f"Erro ao salvar: {e}")


    def get_current_state(self):
        """Obtem estado atual ordenado por Y depois X"""
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

        if not raw_items:
            return []

        # Separar notas de items especiais
        notes = [i for i in raw_items if "HEADER" not in i["tipo"] and "TIMESIG" not in i["tipo"]]
        specials = [i for i in raw_items if "HEADER" in i["tipo"] or "TIMESIG" in i["tipo"]]

        # Ordenar notas por Y primeiro, depois por X
        notes.sort(key=lambda n: n['y'])

        # Agrupar notas por linha (Y similar) e ordenar cada linha por X
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

    def load_scene_data(self, data):
        """Carrega dados da cena"""
        log_info(f"Carregando {len(data)} itens para cena")
        self.scene.clear()
        self.load_images_to_scene(self.current_image_paths)

        for d in data:
            if 'type' not in d:
                t = d.get('tipo', '')
                if "HEADER_BOX" in t:
                    d['type'] = 'HEADER'
                    d['r'] = (0, 0, d['w'], d['h'])
                    d['x'] = d['x']
                    d['y'] = d['y']
                elif "TIMESIG_BOX" in t:
                    d['type'] = 'TIME'
                    d['r'] = (0, 0, d['w'], d['h'])
                    d['x'] = d['x']
                    d['y'] = d['y']
                elif "TAG" in t:
                    d['type'] = 'TAG'
                    d['t'] = t
                else:
                    d['type'] = 'NOTE'
                    d['t'] = t

            try:
                if d['type'] == 'NOTE':
                    cp = d.get('cp')
                    if not cp and 'custom_w' in d:
                        cp = {'w': d['custom_w'], 'h': d['custom_h'], 'y': d['custom_y']}
                    it = NoteItem(d['t'], d['x'], d['y'], self.snap_active.isChecked, cp)
                    self.scene.addItem(it)

                elif d['type'] == 'TAG':
                    it = LabelItem(d['t'], d['x'], d['y'], self.snap_active.isChecked)
                    self.scene.addItem(it)

                elif d['type'] == 'HEADER':
                    it = HeaderBoxItem(QRectF(*d['r']))
                    it.setPos(d['x'], d['y'])
                    self.scene.addItem(it)

                elif d['type'] == 'TIME':
                    it = TimeSigBoxItem(QRectF(*d['r']))
                    it.setPos(d['x'], d['y'])
                    self.scene.addItem(it)

            except Exception as e:
                log_error(f"Erro ao carregar item: {d}", e)

        log_info(f"Cena carregada com sucesso")

    def delete_selected(self):
        """Deleta selecionados"""
        count = len(self.scene.selectedItems())
        log_info(f"Deletando {count} item(ns)")
        for i in self.scene.selectedItems():
            self.scene.removeItem(i)
        self.save_state()

    def delete_specific_item(self, item):
        """Deleta item especifico"""
        log_debug(f"Deletando item: {item.tipo if hasattr(item, 'tipo') else 'desconhecido'}")
        self.scene.removeItem(item)
        self.save_state()

    def swap_item_type(self, item):
        """Troca tipo de item"""
        log_debug(f"Trocando tipo de item: {item.tipo}")
        x, y = item.x(), item.y()
        self.scene.removeItem(item)
        self.add_item_at_mouse(self.view.mapToScene(self.view.mapFromGlobal(self.cursor().pos())))

    def open_individual_crop_dialog(self, item):
        """Abre dialogo de recorte individual"""
        from ui.dialogs import IndividualCropDialog
        log_info("Abrindo dialogo de recorte individual")
        d = IndividualCropDialog(item.custom_crop_params or {}, self)
        d.exec()
        item.custom_crop_params = d.result_data
        item.update()

    def save_state(self):
        """Salva estado no historico"""
        self.history.append(self.get_current_state())
        self.history_pos += 1
        log_debug(f"Estado salvo no historico (posicao: {self.history_pos})")

    def undo(self):
        """Desfaz"""
        if self.history_pos > 0:
            self.history_pos -= 1
            log_info(f"Desfazendo para posicao: {self.history_pos}")
            self.load_scene_data(self.history[self.history_pos])

    def clear_all(self):
        """Limpa tudo"""
        log_info("Limpando cena")
        self.scene.clear()
        self.load_images_to_scene(self.current_image_paths)

    def update_title(self):
        """Atualiza titulo"""
        item_count = len(self.scene.items())
        self.setWindowTitle(f"Editor V32 - {item_count} itens")
        log_debug(f"Titulo atualizado: {item_count} itens")

    def update_zoom_label(self, zoom):
        """Atualiza label de zoom"""
        self.lbl_zoom.setText(f"{int(zoom * 100)}%")
        log_debug(f"Zoom atualizado: {int(zoom * 100)}%")

    def update_cooldown(self):
        """Atualiza cooldown"""
        if self.cooldown_remaining > 0:
            self.cooldown_remaining -= 1
            log_debug(f"Cooldown: {self.cooldown_remaining}s restantes")

    def find_json_for_image(self, img_filename):
        """Encontra JSON associado a uma imagem"""
        log_debug(f"Procurando JSON para imagem: {img_filename}")
        json_files = glob.glob(os.path.join(JSON_FOLDER, "*.json"))

        for jf in json_files:
            try:
                with open(jf, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                imgs = data.get('imagens', [data.get('imagem_fundo', '')])
                img_names = [os.path.basename(p) for p in imgs if p]

                if img_filename in img_names:
                    log_debug(f"JSON encontrado: {jf}")
                    return jf

            except Exception as e:
                log_error(f"Erro ao verificar JSON {jf}", e)

        log_debug(f"Nenhum JSON encontrado para {img_filename}")
        return None

    def export_clean_sheet_with_crops(self):
        """Exporta folha limpa com recortes"""
        log_info("Iniciando renderizacao de imagem")
        state = self.get_current_state()
        if not state:
            log_warning("Nada para exportar")
            QMessageBox.warning(self, "Aviso", "Nada para exportar.")
            return

        # Separar notas de items especiais
        notes = [i for i in state if i.get('tipo') not in ['HEADER_BOX', 'TIMESIG_BOX']]
        specials = [i for i in state if i.get('tipo') in ['HEADER_BOX', 'TIMESIG_BOX']]

        # ORDENAR NOTAS: Primeiro por Y (linha), depois por X (posicao na linha)
        notes.sort(key=lambda n: (n.get('y', 0), n.get('x', 0)))

        # Reconstruir estado ordenado
        ordered_state = notes + specials

        # Usar ImageRenderer para renderizar
        renderer = ImageRenderer(self.scene, self.current_image_paths)
        pil_image = renderer.render()

        if not pil_image:
            log_error("Falha ao gerar imagem")
            QMessageBox.warning(self, "Erro", "Falha ao gerar imagem.")
            return

        # --- CORREÇÃO AQUI: Usar a variável oficial do paths.py ---
        # Garante que a pasta 'preview_images' existe
        try:
            os.makedirs(PREVIEW_FOLDER, exist_ok=True)
        except Exception as e:
            log_error(f"Erro ao criar pasta de previews: {PREVIEW_FOLDER}", e)
            return

        # Definir nome do arquivo
        base_name = "preview"
        if self.current_json_path:
            base_name = os.path.splitext(os.path.basename(self.current_json_path))[0]

        # Salva na pasta CORRETA (preview_images)
        output_path = os.path.join(PREVIEW_FOLDER, f"{base_name}.jpg")

        try:
            pil_image.save(output_path, quality=95)
            log_info(f"Imagem exportada para pasta de previews: {output_path}")

            try:
                os.startfile(output_path)
            except:
                pass

            QMessageBox.information(self, "Sucesso", f"Imagem salva na pasta de previews:\n{output_path}")

        except Exception as e:
            log_error(f"Erro ao salvar imagem de preview em {output_path}", e)
            QMessageBox.critical(self, "Erro", f"Não foi possível salvar a imagem:\n{str(e)}")


    def update_tool_display(self, tool_name):
        """Atualiza exibicao da ferramenta no painel direito"""
        log_debug(f"Atualizando ferramenta para: {tool_name}")
        if hasattr(self.right_panel, 'update_tool_display'):
            self.right_panel.update_tool_display(tool_name)

    # ========== GEMINI PROCESSING ==========

    def trigger_gemini_processing(self, image_path, base_filename):
        """Processa a imagem com Gemini API com barra de progresso"""
        log_info(f"Iniciando processamento Gemini para: {base_filename}")

        # Criar dialog de progresso
        self.progress_dialog = QProgressDialog(
            "Processando imagem com Gemini...",
            None,
            0,
            100,
            self
        )
        self.progress_dialog.setWindowTitle("Processamento Gemini")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setMinimumWidth(400)
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setValue(0)
        self.progress_dialog.show()

        # Timer para animar a barra
        self.progress_timer = QTimer()
        self.progress_value = 0
        self.progress_timer.timeout.connect(self.update_progress_bar)
        self.progress_timer.start(100)  # Atualiza a cada 100ms

        # Processar em thread separada
        self.worker = GeminiWorker(image_path, os.path.join(OUTPUT_FOLDER, base_filename + ".json"), MINHA_API_KEY)
        self.worker.progress_signal.connect(self.on_worker_progress)
        self.worker.finished_signal.connect(self.on_gemini_finished)
        self.worker.start()

    def on_worker_progress(self, message):
        """Recebe atualizacoes de progresso do worker"""
        log_debug(f"Progresso Gemini: {message}")
        if self.progress_dialog and self.progress_dialog.isVisible():
            self.progress_dialog.setLabelText(message)

    def update_progress_bar(self):
        """Atualiza a barra de progresso com animacao"""
        if hasattr(self, 'progress_dialog') and self.progress_dialog and self.progress_dialog.isVisible():
            self.progress_value += 2
            if self.progress_value > 90:
                self.progress_value = 90  # Nao chega a 100% ate terminar
            self.progress_dialog.setValue(self.progress_value)

    def on_gemini_finished(self, output_path, success, message):
        """Callback quando Gemini termina"""
        # Parar timer
        if hasattr(self, 'progress_timer') and self.progress_timer:
            self.progress_timer.stop()

        # Completar barra
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.setValue(100)
            time.sleep(0.3)
            self.progress_dialog.close()

        if success:
            log_info(f"Gemini concluido: {output_path}")
            QMessageBox.information(self, "Sucesso", f"Processamento concluido!\n{message}")
        else:
            log_error(f"Erro no Gemini: {message}")
            QMessageBox.critical(self, "Erro", f"Erro ao processar: {message}")


