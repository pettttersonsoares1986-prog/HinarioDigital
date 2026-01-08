# panels.py
import os
import glob
import json
from functools import partial
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QScrollArea, QGroupBox, QGridLayout, QSplitter, QListWidgetItem,QMessageBox
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QBrush, QColor


from core.config import FERRAMENTAS_ORGANIZADAS, IMG_FOLDER, JSON_FOLDER, OUTPUT_FOLDER,PREVIEW_FOLDER
from core.cache import ImageCache
from ui.list_widgets import ImageListWidget, ProjectListWidget
from core.utils import natural_sort_key
from core.logger import log_info, log_error, log_debug, log_warning


class LeftPanel(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        log_info("Inicializando LeftPanel")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Vertical)

        # --- 1. Lista de Imagens (Originais) ---
        widget_images = QWidget()
        layout_images = QVBoxLayout(widget_images)
        layout_images.setContentsMargins(0, 0, 0, 0)
        layout_images.addWidget(QLabel("<b>IMAGENS (Originais)</b>"))
        self.list_images = ImageListWidget()
        self.list_images.itemDoubleClicked.connect(self.main.start_edit_from_image)
        layout_images.addWidget(self.list_images)

        btn_merge = QPushButton("⬇ Criar Projeto")
        btn_merge.setStyleSheet("background-color: #2980b9; color: white; padding: 5px;")
        btn_merge.clicked.connect(self.main.merge_selected_images)
        layout_images.addWidget(btn_merge)

        # --- 2. Lista de Projetos ---
        widget_projects = QWidget()
        layout_projects = QVBoxLayout(widget_projects)
        layout_projects.setContentsMargins(0, 0, 0, 0)
        layout_projects.addWidget(QLabel("<b>PROJETOS SALVOS</b>"))
        self.list_projects = ProjectListWidget(self.main)
        self.list_projects.itemDoubleClicked.connect(self.main.on_project_double_click)
        layout_projects.addWidget(self.list_projects)

        btn_del_proj = QPushButton("🗑️ Excluir Projeto")
        btn_del_proj.clicked.connect(self.main.delete_current_project)
        btn_del_proj.setStyleSheet("background-color: #c0392b; color: white; padding: 5px;")
        layout_projects.addWidget(btn_del_proj)

        # --- 3. NOVA LISTA: Previews Gerados ---
        widget_previews = QWidget()
        layout_previews = QVBoxLayout(widget_previews)
        layout_previews.setContentsMargins(0, 0, 0, 0)
        layout_previews.addWidget(QLabel("<b>PREVIEWS GERADOS</b>"))

        self.list_previews = ImageListWidget() # Reusamos o widget de lista de imagens
        self.list_previews.itemDoubleClicked.connect(self.open_preview) # Duplo clique abre a imagem
        layout_previews.addWidget(self.list_previews)

        # Adiciona os 3 widgets ao splitter
        splitter.addWidget(widget_images)
        splitter.addWidget(widget_projects)
        splitter.addWidget(widget_previews)

        layout.addWidget(splitter)

        btn_refresh = QPushButton("🔄 Atualizar Listas")
        btn_refresh.clicked.connect(self.refresh_playlists)
        layout.addWidget(btn_refresh)

        log_info("LeftPanel inicializado com sucesso")

    def open_preview(self, item):
        """Abre o arquivo de preview ao clicar duas vezes"""
        filename = item.text().replace("✅ ", "").replace("🖼️ ", "")
        # USA A VARIÁVEL DO PATHS.PY
        path = os.path.join(PREVIEW_FOLDER, filename)

        if os.path.exists(path):
            try:
                os.startfile(path)
                log_info(f"Abrindo preview: {path}")
            except Exception as e:
                log_error(f"Erro ao abrir preview {path}", e)
        else:
            QMessageBox.warning(self, "Erro", f"Arquivo não encontrado em:\n{path}")

    def refresh_playlists(self):
        """Atualiza listas de imagens e projetos"""
        log_info("=== INICIANDO refresh_playlists ===")
        log_debug(f"IMG_FOLDER: {IMG_FOLDER}")
        log_debug(f"JSON_FOLDER: {JSON_FOLDER}")

        # Verificar se pastas existem
        if not os.path.exists(IMG_FOLDER):
            log_error(f"Pasta de imagens não existe: {IMG_FOLDER}")
        else:
            log_info(f"Pasta de imagens existe: {IMG_FOLDER}")

        if not os.path.exists(JSON_FOLDER):
            log_error(f"Pasta de projetos não existe: {JSON_FOLDER}")
        else:
            log_info(f"Pasta de projetos existe: {JSON_FOLDER}")

        # Mapa de Status
        status_map = {}
        if os.path.exists(JSON_FOLDER):
            json_files = glob.glob(str(JSON_FOLDER / "*.json"))
            log_debug(f"Arquivos JSON encontrados: {len(json_files)}")

            for f_json in json_files:
                try:
                    log_debug(f"Processando JSON: {f_json}")
                    with open(f_json, 'r', encoding='utf-8') as file:
                        data = json.load(file)
                        proj_status = data.get('status', 'em_andamento')
                        imgs = [os.path.basename(i) for i in data.get('imagens', []) if i]
                        single = data.get('imagem_fundo')
                        if single:
                            imgs.append(os.path.basename(single))
                        log_debug(f"Projeto {f_json} tem imagens: {imgs}")
                        for img_name in imgs:
                            if status_map.get(img_name) != 'concluido':
                                status_map[img_name] = proj_status
                except Exception as e:
                    log_error(f"Erro ao processar {f_json}", e)

        log_debug(f"Status map final: {status_map}")

        # Lista de Imagens
        log_info("Atualizando lista de imagens...")
        self.list_images.clear()

        if os.path.exists(IMG_FOLDER):
            try:
                arquivos = sorted(
                    [f for f in os.listdir(IMG_FOLDER) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))],
                    key=natural_sort_key
                )
                log_info(f"Imagens encontradas: {len(arquivos)}")
                log_debug(f"Arquivos: {arquivos}")

                for f in arquivos:
                    item = QListWidgetItem(f)
                    status = status_map.get(f)
                    log_debug(f"Adicionando imagem: {f} (status: {status})")

                    if status == "concluido":
                        item.setForeground(QBrush(QColor("#27ae60")))
                        item.setBackground(QBrush(QColor("#e8f8f5")))
                        item.setText(f"✅ {f}")
                    elif status == "em_andamento":
                        item.setForeground(QBrush(QColor("#2980b9")))
                        item.setText(f"📂 {f}")
                    else:
                        item.setText(f"❓ {f}")

                    self.list_images.addItem(item)

                log_info(f"Total de imagens adicionadas: {self.list_images.count()}")
            except Exception as e:
                log_error(f"Erro ao listar imagens", e)
        else:
            log_warning(f"Pasta IMG_FOLDER não existe: {IMG_FOLDER}")

        # Lista de Projetos
        log_info("Atualizando lista de projetos...")
        self.list_projects.clear()

        if os.path.exists(JSON_FOLDER):
            try:
                arquivos_json = sorted(glob.glob(str(JSON_FOLDER / "*.json")), key=natural_sort_key)
                log_info(f"Projetos encontrados: {len(arquivos_json)}")
                log_debug(f"Arquivos JSON: {arquivos_json}")

                for f_path in arquivos_json:
                    nome = os.path.basename(f_path)
                    item = QListWidgetItem(nome)
                    try:
                        with open(f_path, 'r', encoding='utf-8') as arq:
                            st = json.load(arq).get("status", "em_andamento")
                            log_debug(f"Projeto {nome} tem status: {st}")
                            if st == "concluido":
                                item.setText(f"✅ {nome}")
                                item.setForeground(QBrush(QColor("#27ae60")))
                            else:
                                item.setText(f"🚧 {nome}")
                                item.setForeground(QBrush(QColor("#d35400")))
                    except Exception as e:
                        log_error(f"Erro ao ler {f_path}", e)
                        item.setText(f"❓ {nome}")
                    self.list_projects.addItem(item)

                log_info(f"Total de projetos adicionados: {self.list_projects.count()}")
            except Exception as e:
                log_error(f"Erro ao listar projetos", e)
        else:
            log_warning(f"Pasta JSON_FOLDER não existe: {JSON_FOLDER}")

        log_info("=== refresh_playlists CONCLUÍDO ===\n")

        # === Preparar um mapa de status (ler todos os JSONs uma vez) ===
        status_map = {}  # chave: nome base do arquivo (ex: "1" ou "1.png" dependendo do seu JSON), valor: "concluido"|"em_andamento"
        if os.path.exists(JSON_FOLDER):
            try:
                json_files = glob.glob(os.path.join(JSON_FOLDER, "*.json"))
                for jf in json_files:
                    try:
                        with open(jf, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            # Ajuste aqui conforme sua estrutura de JSON:
                            # Se o JSON tiver campo "image" ou uma lista "images", use ele.
                            # Vou tentar mapear pelo nome do json: se for "1.json" -> chave "1"
                            base_json = os.path.splitext(os.path.basename(jf))[0]
                            status = data.get("status", "em_andamento")
                            # grava tanto com chave simples quanto com extensão png/jpg para facilitar lookup
                            status_map[base_json] = status
                            status_map[f"{base_json}.png"] = status
                            status_map[f"{base_json}.jpg"] = status
                            # se o JSON listar imagens explicitamente:
                            if "images" in data and isinstance(data["images"], list):
                                for imgname in data["images"]:
                                    status_map[imgname] = status
                    except Exception as e:
                        log_error(f"Erro ao ler JSON {jf}: {e}")
            except Exception as e:
                log_error(f"Erro ao listar arquivos JSON em {JSON_FOLDER}: {e}")

        # --- 3. LISTA DE PREVIEWS ---
        # Adiciona ícones pois a função open_preview vai tratar o nome
        # === 3. LISTA DE PREVIEWS ===
        self.list_previews.clear()

        if not os.path.exists(PREVIEW_FOLDER):
            try:
                os.makedirs(PREVIEW_FOLDER, exist_ok=True)
            except Exception:
                pass

        if os.path.exists(PREVIEW_FOLDER):
            try:
                previews = glob.glob(os.path.join(PREVIEW_FOLDER, "*.jpg"))
                previews.sort(key=natural_sort_key)

                for p_path in previews:
                    p_name = os.path.basename(p_path)          # ex: "1.jpg"
                    base_name = os.path.splitext(p_name)[0]   # ex: "1"
                    item = QListWidgetItem(p_name)            # mantemos o texto limpo (open_preview vai tratar se necessário)

                    # procura status no mapa de formas alternativas
                    status = None
                    # checagens com as chaves que colocamos em status_map
                    for key in (p_name, f"{base_name}.png", f"{base_name}.jpg", base_name):
                        if key in status_map:
                            status = status_map[key]
                            break
                    if status  == "concluido":
                        item.setText(f"✅ {p_name}")
                        item.setForeground(QBrush(QColor("#27ae60")))
                    elif status == "em_andamento":                    
                        item.setText(f"🚧 {p_name}")
                        item.setForeground(QBrush(QColor("#d35400")))
                    else:
                        # sem status encontrado -> apenas preview (roxo)
                        item.setText(f"❓ {p_name}")
                        item.setForeground(QBrush(QColor("#8e44ad")))
                    self.list_previews.addItem(item)

                log_info(f"Total de previews adicionados: {self.list_previews.count()}")

            except Exception as e:
                log_error(f"Erro ao listar previews em {PREVIEW_FOLDER}: {e}")

class RightPanel(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        log_info("Inicializando RightPanel")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Preview do Ícone
        info_layout = QHBoxLayout()
        self.lbl_icon_preview = QLabel()
        self.lbl_icon_preview.setFixedSize(50, 50)
        self.lbl_icon_preview.setStyleSheet("border: 1px solid gray;")
        self.lbl_tool_name = QLabel("SEMINIMA")
        self.lbl_tool_name.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50;")
        info_layout.addWidget(self.lbl_icon_preview)
        info_layout.addWidget(self.lbl_tool_name)
        layout.addLayout(info_layout)

        # Scroll de Ferramentas
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        for categoria, lista_ferramentas in FERRAMENTAS_ORGANIZADAS.items():
            group_box = QGroupBox(categoria)
            group_box.setStyleSheet(
                "QGroupBox { font-weight: bold; color: #2c3e50; border: 1px solid #bdc3c7; "
                "margin-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; "
                "padding: 0 3px 0 3px; }"
            )
            grid_layout = QGridLayout()
            row, col = 0, 0

            for fer in lista_ferramentas:
                btn = QPushButton()
                pix = ImageCache.get_pixmap(fer, 35)
                btn.setIcon(QIcon(pix))
                btn.setIconSize(QSize(35, 35))
                btn.setToolTip(fer)
                btn.clicked.connect(partial(self.main.select_tool, fer))
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

        # Botões Inferiores
        self.add_side_btn(layout, "⚙️ Configurações", self.main.open_settings)
        self.add_side_btn(layout, "↩️ Desfazer (Ctrl+Z)", self.main.undo)
        self.add_side_btn(layout, "🗑️ Limpar Tudo", self.main.clear_all)

        log_info("RightPanel inicializado com sucesso")

    def add_side_btn(self, layout, text, func):
        """Adiciona botão ao painel lateral"""
        btn = QPushButton(text)
        btn.clicked.connect(func)
        btn.setStyleSheet("padding: 8px;")
        layout.addWidget(btn)

    def update_tool_display(self, tool_name):
        """Atualiza exibição da ferramenta selecionada"""
        log_debug(f"Atualizando ferramenta para: {tool_name}")
        self.lbl_tool_name.setText(tool_name)
        self.lbl_icon_preview.setPixmap(ImageCache.get_pixmap(tool_name, 35))
