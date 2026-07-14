import time
import os
import json
import re
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QLineEdit, QTextEdit, QFrame, QApplication,
    QListWidget, QListWidgetItem, QSplitter, QSizePolicy, QMessageBox,
    QTabWidget, QAbstractItemView
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont, QTextCharFormat, QTextCursor, QColor, QTextDocument

# Importações dos outros módulos
from config import config_manager, COR_INICIAR, COR_PERIGO, COR_AUTO_SCALE, COR_EDICAO, COR_BARRA_PADRAO, BPM_INICIAL, HINOS_FOLDER_PATH
from logic import get_syllable_tokens, calcular_duracao_ms, ler_arquivo_hino
from editor_ui import EditorDialog, ConfigDialog

class KaraokePlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hinário Digital - Player")
        self.setGeometry(100, 100, 1280, 768)

        self.fmt_norm = QTextCharFormat()
        self.fmt_dest = QTextCharFormat()

        # Estado do Player
        self.max_hinos = 0
        self.hino_data = None
        self.hino_atual = 0
        self.bpm = BPM_INICIAL

        self.estrofe_idx = 0
        self.pos_atual = 0
        self.compasso = "4/4"
        self.unidade_bpm = "SEMINIMA" # <--- AJUSTADO PARA O NOVO PADRÃO

        self.note_durations = []
        self.indices = []
        self.syllables = []
        self.estrofes_info = []
        self.estrofes_texto = []
        self.notas_estrofes = []

        self.tempo_inicio_nota = 0
        self.duracao_nota_orig = 0
        self.indice_coro = -1
        self.proxima_eh_coro = False
        self.mostrar_hifens = True
        self.cache_hinos = [] 
        self.is_paused = False
        self.is_fullscreen_mode = False

        # Timers
        self.timer_play = QTimer(self)
        self.timer_play.setSingleShot(True)
        self.timer_play.timeout.connect(self.play_step)

        self.timer_wait = QTimer(self)
        self.timer_wait.timeout.connect(self.step_wait)
        self.wait_sec = 0

        self.timer_zoom = QTimer(self)
        self.timer_zoom.setSingleShot(True)
        self.timer_zoom.timeout.connect(lambda: self.aplicar_zoom(True))

        # Timer do Metrônomo Visual
        self.timer_beat = QTimer(self)
        self.timer_beat.timeout.connect(self.flash_beat)
        self.current_beat = 1
        self.total_beats = 4

        self.recarregar_configs()
        self.setup_ui()

        # Carrega lista inicial
        self.mostrar_tela_inicial()
        QTimer.singleShot(500, self.carregar_lista_hinos)

    def mostrar_tela_inicial(self):
        self.hino_atual = 0
        self.lbl_title.setText("BEM-VINDO")
        self.lbl_info.setText("")
        msg = """
        <div style='text-align: center; margin-top: 50px;'>
            <h1 style='color: #FFD700; font-size: 50px;'>SELECIONE O HINO</h1>
            <p style='color: white; font-size: 24px;'>
               Use a biblioteca à esquerda ou digite o número no campo "Est".
            </p>
            <p style='color: #AAA; font-size: 18px; margin-top: 30px;'>
               <b>Atalhos:</b><br>
               [ESPAÇO] Play/Pause &nbsp;|&nbsp; [R] Reiniciar Estrofe &nbsp;|&nbsp; [F11] Tela Cheia
            </p>
        </div>
        """
        self.texto.setHtml(msg)

    def recarregar_configs(self):
        self.font_size = config_manager.get('tamanho_fonte', int) or 40
        self.espacamento = config_manager.get('espacamento_texto', int) or 150
        self.bpm_step = config_manager.get('bpm_step', int) or 5
        self.start_delay = config_manager.get('start_delay', int) or 2
        self.strofe_delay = config_manager.get('strofe_delay', int) or 3
        self.min_zoom = config_manager.get('min_zoom', int) or 12
        self.max_zoom = config_manager.get('max_zoom', int) or 150
        self.bpm = config_manager.get('BPM_padrao', int) or 60

        self.colors = {
            'cor_fundo_texto': config_manager.get('cor_fundo_texto', str),
            'cor_texto_normal': config_manager.get('cor_texto_normal', str),
            'cor_destaque_karaoke': config_manager.get('cor_destaque_karaoke', str),
            'cor_nota_normal': config_manager.get('cor_nota_normal', str),
            'cor_nota_destaque': config_manager.get('cor_nota_destaque', str),
            'cor_barra_navegacao': config_manager.get('cor_barra_navegacao', str),
        }
        self.colors['bg'] = self.colors['cor_fundo_texto']
        self.colors['fg'] = self.colors['cor_texto_normal']
        self.colors['hl'] = self.colors['cor_destaque_karaoke']
        self.colors['nav'] = self.colors['cor_barra_navegacao']

        if hasattr(self, 'texto'): self.apply_style()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout_principal = QHBoxLayout(central)
        layout_principal.setContentsMargins(0,0,0,0)
        layout_principal.setSpacing(0)

        # --- 1. SIDEBAR ---
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(300)
        self.sidebar.setStyleSheet("background-color: #202020; border-right: 1px solid #444;")
        l_sidebar = QVBoxLayout(self.sidebar)
        l_sidebar.setContentsMargins(0,0,0,0)

        self.tabs_sidebar = QTabWidget()
        self.tabs_sidebar.setStyleSheet("""
            QTabWidget::pane { border: 0; }
            QTabBar::tab { background: #333; color: #AAA; padding: 8px 20px; }
            QTabBar::tab:selected { background: #444; color: white; font-weight: bold; border-top: 2px solid #0050C0; }
        """)

        # ABA BIBLIOTECA
        tab_lib = QWidget(); l_lib = QVBoxLayout(tab_lib)
        self.txt_busca = QLineEdit()
        self.txt_busca.setPlaceholderText("🔍 Buscar hino...")
        self.txt_busca.setStyleSheet("padding: 6px; color: white; background-color: #333; border: 1px solid #555; border-radius: 4px;")
        self.txt_busca.textChanged.connect(self.filtrar_lista_hinos)
        l_lib.addWidget(self.txt_busca)

        self.lista_hinos = QListWidget()
        self.lista_hinos.setStyleSheet("QListWidget { background-color: #222; color: #EEE; border: none; } QListWidget::item:selected { background-color: #0050C0; color: white; }")
        self.lista_hinos.itemDoubleClicked.connect(self.selecionar_hino_lista)
        l_lib.addWidget(self.lista_hinos)
        self.tabs_sidebar.addTab(tab_lib, "Biblioteca")

        l_sidebar.addWidget(self.tabs_sidebar)

        # --- 2. ÁREA PRINCIPAL ---
        area_main = QFrame()
        area_main.setStyleSheet(f"background-color: {self.colors['bg']};")
        l_main = QVBoxLayout(area_main)
        l_main.setContentsMargins(0,0,0,0)
        l_main.setSpacing(0)

        # Header
        header = QFrame()
        header.setFixedHeight(60)
        header.setStyleSheet(f"background-color: {self.colors['nav']}; border-bottom: 2px solid #000;")
        l_header = QHBoxLayout(header)

        self.btn_menu = QPushButton("☰")
        self.btn_menu.setFixedSize(40,40)
        self.btn_menu.setStyleSheet("font-size: 20px; color: white; border: none;")
        self.btn_menu.clicked.connect(self.toggle_sidebar)
        l_header.addWidget(self.btn_menu)

        self.lbl_title = QLabel("HINÁRIO DIGITAL")
        self.lbl_title.setStyleSheet("color: white; font-size: 22px; font-weight: bold; margin-left: 10px;")
        l_header.addWidget(self.lbl_title)

        l_header.addStretch()

        self.lbl_beat_light = QLabel()
        self.lbl_beat_light.setFixedSize(20,20)
        self.lbl_beat_light.setStyleSheet("background-color: #333; border-radius: 10px; border: 1px solid #555;")
        l_header.addWidget(self.lbl_beat_light)

        self.lbl_bpm = QLabel(f"BPM: {self.bpm}")
        self.lbl_bpm.setStyleSheet("color: white; font-size: 16px; font-weight: bold; margin-right: 10px;")
        l_header.addWidget(self.lbl_bpm)

        l_main.addWidget(header)

        # Área do Texto (Karaokê)
        self.texto = QTextEdit()
        self.texto.setReadOnly(True)
        self.texto.setFrameShape(QFrame.NoFrame)
        self.texto.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.texto.setStyleSheet(f"background-color: {self.colors['bg']}; color: {self.colors['fg']}; border: none;")
        l_main.addWidget(self.texto)

        # Barra de Informações (Próxima estrofe, contagem)
        self.lbl_info = QLabel("")
        self.lbl_info.setAlignment(Qt.AlignCenter)
        self.lbl_info.setFixedHeight(40)
        self.lbl_info.setStyleSheet("background-color: rgba(0,0,0,100); color: #FFD700; font-size: 18px; font-weight: bold;")
        l_main.addWidget(self.lbl_info)

        # Barra de Controles Inferior
        controls = QFrame()
        controls.setFixedHeight(60)
        controls.setStyleSheet(f"background-color: {self.colors['nav']}; border-top: 2px solid #000;")
        l_controls = QHBoxLayout(controls)

        self.btn_prev = QPushButton("⏮")
        self.btn_prev.clicked.connect(lambda: self.nav_estrofe(-1))
        self.btn_start = QPushButton("INICIAR")
        self.btn_start.clicked.connect(self.toggle_play)
        self.btn_next = QPushButton("⏭")
        self.btn_next.clicked.connect(lambda: self.nav_estrofe(1))

        for b in [self.btn_prev, self.btn_start, self.btn_next]:
            b.setFixedSize(80, 40)
            b.setStyleSheet("background-color: #444; color: white; font-weight: bold; border-radius: 4px;")
            l_controls.addWidget(b)

        l_controls.addStretch()

        # Controles de BPM e Navegação Rápida
        btn_bpm_minus = QPushButton("-")
        btn_bpm_minus.setFixedSize(40,40)
        btn_bpm_minus.clicked.connect(lambda: self.change_bpm(-self.bpm_step))

        btn_bpm_plus = QPushButton("+")
        btn_bpm_plus.setFixedSize(40,40)
        btn_bpm_plus.clicked.connect(lambda: self.change_bpm(self.bpm_step))

        self.ent_est = QLineEdit()
        self.ent_est.setPlaceholderText("Est")
        self.ent_est.setFixedWidth(50)
        self.ent_est.setAlignment(Qt.AlignCenter)
        self.ent_est.returnPressed.connect(self.manual_estrofe)

        btn_edit = QPushButton("EDITAR")
        btn_edit.clicked.connect(self.abrir_editor)
        btn_config = QPushButton("CONFIG")
        btn_config.clicked.connect(self.abrir_tela_configuracao)

        for w in [btn_bpm_minus, btn_bpm_plus, self.ent_est, btn_edit, btn_config]:
            w.setStyleSheet("background-color: #444; color: white; border-radius: 4px; padding: 5px;")
            l_controls.addWidget(w)

        l_main.addWidget(controls)

        layout_principal.addWidget(self.sidebar)
        layout_principal.addWidget(area_main)

    def apply_style(self):
        self.texto.setStyleSheet(f"background-color: {self.colors['bg']}; color: {self.colors['fg']};")
        font = QFont("Arial", self.font_size)
        self.texto.setFont(font)

        self.fmt_norm.setForeground(QColor(self.colors['fg']))
        self.fmt_norm.setFontWeight(QFont.Normal)

        self.fmt_dest.setForeground(QColor(self.colors['hl']))
        self.fmt_dest.setFontWeight(QFont.Bold)

    def toggle_sidebar(self):
        if self.sidebar.isVisible(): self.sidebar.hide()
        else: self.sidebar.show()

    def carregar_lista_hinos(self):
        self.lista_hinos.clear()
        self.cache_hinos = []

        if not os.path.exists(HINOS_FOLDER_PATH):
            os.makedirs(HINOS_FOLDER_PATH)

        arquivos = [f for f in os.listdir(HINOS_FOLDER_PATH) if f.endswith('.json')]

        # Ordena numericamente
        def get_num(s):
            m = re.search(r'(\d+)', s)
            return int(m.group(1)) if m else 999999

        arquivos.sort(key=get_num)

        for f in arquivos:
            path = os.path.join(HINOS_FOLDER_PATH, f)
            try:
                with open(path, 'r', encoding='utf-8') as arq:
                    data = json.load(arq)
                    num = data.get('numero', 0)
                    tit = data.get('titulo', 'Sem Título')
                    display = f"{num} - {tit}"
                    self.cache_hinos.append((num, display, path))
            except: pass

        self.filtrar_lista_hinos("")

    def filtrar_lista_hinos(self, texto):
        self.lista_hinos.clear()
        texto = texto.lower()
        for num, display, path in self.cache_hinos:
            if texto in display.lower() or texto == str(num):
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, num)
                self.lista_hinos.addItem(item)

    def selecionar_hino_lista(self, item):
        num = item.data(Qt.UserRole)
        self.carregar_hino(num)

    def carregar_hino(self, numero, force_reload=False):
        data = ler_arquivo_hino(numero)
        if not data:
            QMessageBox.warning(self, "Erro", f"Hino {numero} não encontrado ou inválido.")
            return

        self.hino_data = data
        self.hino_atual = numero

        # --- CABEÇALHO HTML FORMATADO ---
        numero_hino = data.get('numero', numero)
        titulo = data.get('titulo', 'Sem Título')
        tom = data.get('tom', 'Não definido')
        bpm_val = data.get('BPM', self.bpm)
        compasso_json = data.get('compasso', '4/4')
        autor = data.get('autor', 'Desconhecido')

        header_html = f"""
        <div style='line-height: 1.2; text-align: center;'>
            <span style='font-size: 20pt; font-weight: bold; color: #FFD700;'>
                {numero_hino}. {titulo.upper()}
            </span>
            <br>
            <span style='font-size: 11pt; color: #CCCCCC;'>
                Tom: <b style='color: #00BFFF;'>{tom}</b> &nbsp;|&nbsp; 
                BPM: <b style='color: #00BFFF;'>{bpm_val}</b> &nbsp;|&nbsp; 
                Comp: <b style='color: #00BFFF;'>{compasso_json}</b> &nbsp;|&nbsp; 
                Autor: {autor}
            </span>
        </div>
        """
        self.lbl_title.setText(header_html)
        # --- FIM DO CABEÇALHO ---

        # Resto do código original continua aqui...
        self.indice_coro = -1
        self.estrofes_info = []
        self.estrofes_texto = []
        self.notas_estrofes = []

        for i, est in enumerate(data.get('estrofes', [])):
            tipo = est.get('tipo', 'Estrofe')
            numero_est = est.get('numero', i + 1)

            if tipo.lower() == 'coro':
                self.indice_coro = i

            self.estrofes_info.append(f"{tipo} {numero_est}")

            linhas_txt = []
            linhas_notas = []
            for line in est.get('linhas', []):
                linhas_txt.append(line.get('texto_silabado', ''))
                linhas_notas.append(line.get('notas_codes', []))

            self.estrofes_texto.append(linhas_txt)
            self.notas_estrofes.append(linhas_notas)

        self.load_estrofe(0)


    def load_estrofe(self, idx):
        """
        Carrega e exibe a estrofe no Player com espaçamento correto entre sílabas
        e quebras de linha após pontuação.
        """
        if not self.hino_data or idx < 0 or idx >= len(self.estrofes_texto):
            return

        self.estrofe_idx = idx
        self.stop_karaoke()

        # Atualiza info
        info = self.estrofes_info[idx]
        self.lbl_info.setText(info)

        # Monta o texto com espaçamento correto
        linhas = self.estrofes_texto[idx]
        notas_bloco = self.notas_estrofes[idx]

        self.indices = []
        self.note_durations = []
        self.syllables = []

        full_text = ""

        PAUSE_SYMBOLS = ["''", "_", '"', "__"]
        PUNCTUATION = [',', ';', '.', '!', '?']  # Pontuação que causa quebra de linha

        for l_idx, linha_txt in enumerate(linhas):
            if l_idx > 0:
                full_text += "\n"  # Quebra de linha entre linhas

            sils = get_syllable_tokens(linha_txt)
            notas = notas_bloco[l_idx]

            # Garante notas suficientes (FALLBACK COM SEMINIMA)
            if len(notas) < len(sils):
                notas += ["SEMINIMA"] * (len(sils) - len(notas))

            for s_idx, sil in enumerate(sils):
                # Pula símbolos de pausa
                if sil in PAUSE_SYMBOLS:
                    self.indices.append(None)
                    nota_code = notas[s_idx]
                    ms = calcular_duracao_ms(nota_code, self.bpm, self.unidade_bpm)
                    self.note_durations.append(ms)
                    continue

                # Adiciona espaço ANTES da sílaba (exceto na primeira ou após hífen)
                if s_idx > 0:
                    prev_sil = sils[s_idx - 1]
                    # Se a sílaba anterior NÃO termina com hífen, adiciona espaço
                    if not prev_sil.endswith('-') and prev_sil not in PAUSE_SYMBOLS:
                        full_text += " "

                # Registra posição e comprimento da sílaba
                start_pos = len(full_text)

                # Remove hífen para exibição se a opção estiver desativada
                display_sil = sil
                if not self.mostrar_hifens and sil.endswith('-'):
                    display_sil = sil[:-1]

                full_text += display_sil
                length = len(display_sil)

                self.indices.append((start_pos, length))
                self.syllables.append(sil)

                # Calcula duração da nota
                nota_code = notas[s_idx]
                ms = calcular_duracao_ms(nota_code, self.bpm, self.unidade_bpm)
                self.note_durations.append(ms)

                # --- QUEBRA DE LINHA APÓS PONTUAÇÃO ---
                if display_sil and display_sil[-1] in PUNCTUATION:
                    full_text += "\n"
                # ----------------------------------------

        # Exibe o texto
        self.texto.setPlainText(full_text)
        self.texto.setAlignment(Qt.AlignCenter)
        self.apply_style()

        # Prepara para iniciar
        self.pos_atual = 0
        self.lbl_info.setText(f"{info} - Pronto")



    def toggle_play(self):
        if self.timer_play.isActive():
            self.is_paused = True
            self.timer_play.stop()
            self.timer_beat.stop()
            self.btn_start.setText("CONTINUAR")
        elif self.is_paused:
            self.is_paused = False
            self.btn_start.setText("PAUSAR")
            # Retoma
            elapsed = (time.time() * 1000) - self.tempo_inicio_nota
            rem = self.duracao_nota_orig - elapsed
            self.timer_play.start(max(10, int(rem)))
            self.timer_beat.start(int(60000/self.bpm))
        else:
            self.start_karaoke_sequence()

    def start_karaoke_sequence(self):
        self.btn_start.setText("PAUSAR")
        self.btn_start.setStyleSheet(f"background:{COR_PERIGO}; color:white; font-weight:bold; padding: 6px; border-radius: 4px;")

        if self.start_delay > 0:
            self.lbl_info.setText(f"Iniciando em {self.start_delay}s...")
            self.wait_sec = self.start_delay
            self.timer_wait.start(1000)
        else:
            self.start_karaoke()

    def start_karaoke(self): 
        self.is_paused = False
        self.pos_atual = 0
        self.tempo_inicio_nota = 0
        self.current_beat = 1

        ms_beat = 60000 / self.bpm
        self.timer_beat.start(int(ms_beat))
        self.flash_beat()

        self.play_step()

    def stop_karaoke(self):
        self.timer_play.stop()
        self.timer_wait.stop()
        self.timer_beat.stop()
        self.is_paused = False

        self.lbl_beat_light.setStyleSheet("background-color: #333; border-radius: 10px; border: 1px solid #555;")
        self.btn_start.setText("INICIAR")
        self.btn_start.setStyleSheet(f"background:{COR_INICIAR}; color:white; font-weight:bold; padding: 6px; border-radius: 4px;")
        self.lbl_info.setStyleSheet(f"color: {self.colors['hl']};")

        # Reseta formatação
        if self.hino_atual > 0:
            try:
                cur = QTextCursor(self.texto.document())
                cur.select(QTextCursor.Document)
                cur.setCharFormat(self.fmt_norm)
                cur.clearSelection()
                self.texto.setTextCursor(cur)
            except: pass

            if self.hino_data and self.estrofes_info:
                if 0 <= self.estrofe_idx < len(self.estrofes_info):
                    self.lbl_info.setText(self.estrofes_info[self.estrofe_idx])

    def flash_beat(self):
        color = "#00FF00" if self.current_beat == 1 else "#FFFF00"
        self.lbl_beat_light.setStyleSheet(f"background-color: {color}; border-radius: 10px; border: 1px solid white;")
        QTimer.singleShot(150, lambda: self.lbl_beat_light.setStyleSheet("background-color: #333; border-radius: 10px; border: 1px solid #555;"))

        self.current_beat += 1
        if self.current_beat > self.total_beats: self.current_beat = 1

    def play_step(self):
        if self.pos_atual >= len(self.indices):
            self.timer_play.stop()
            self.timer_beat.stop()
            self.step_wait_for_next()
            return

        ms = self.note_durations[self.pos_atual]
        self.duracao_nota_orig = ms
        self.tempo_inicio_nota = time.time() * 1000

        idx_info = self.indices[self.pos_atual]
        if idx_info is not None:
            st, ln = idx_info

            # Reseta anterior (opcional, mas bom para garantir)
            # Aqui simplificamos para performance: apenas pintamos o atual
            # O ideal seria pintar o anterior de normal, mas o texto todo já é normal

            cur = QTextCursor(self.texto.document())
            cur.setPosition(st)
            cur.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, ln)
            cur.setCharFormat(self.fmt_dest)
            cur.clearSelection()
            self.texto.setTextCursor(cur)
            # self.texto.ensureCursorVisible() # Opcional, pode causar scroll indesejado

        self.pos_atual += 1
        self.timer_play.start(int(ms))

    def step_wait_for_next(self):
        proximo_idx = -1

        # Lógica de Coro
        if self.indice_coro != -1 and self.estrofe_idx != self.indice_coro:
            proximo_idx = self.indice_coro
            self.proxima_estrofe_real = self.estrofe_idx + 1
            if self.proxima_estrofe_real == self.indice_coro:
                self.proxima_estrofe_real += 1
        elif self.indice_coro != -1 and self.estrofe_idx == self.indice_coro:
            if hasattr(self, 'proxima_estrofe_real'):
                proximo_idx = self.proxima_estrofe_real
            else:
                proximo_idx = self.estrofe_idx + 1
        else:
            proximo_idx = self.estrofe_idx + 1

        if proximo_idx < len(self.hino_data.get('estrofes', [])):
            self.wait_sec = self.strofe_delay if self.strofe_delay > 0 else 2

            nome_prox = "Próxima"
            if self.indice_coro != -1:
                if proximo_idx == self.indice_coro: nome_prox = "Coro"
                else: nome_prox = "Estrofe"

            self.lbl_info.setText(f"{nome_prox} em {self.wait_sec}s...")
            self.target_idx = proximo_idx
            self.timer_wait.start(1000)
        else:
            self.show_end()

    def step_wait(self):
        self.wait_sec -= 1
        if self.wait_sec > 0:
            if "Iniciando" in self.lbl_info.text():
                msg = "Iniciando"
            else:
                parts = self.lbl_info.text().split(" em ")
                msg = parts[0] if len(parts) > 0 else "Próxima"
            self.lbl_info.setText(f"{msg} em {self.wait_sec}s...")
        else:
            self.timer_wait.stop()
            if "Iniciando" in self.lbl_info.text():
                self.start_karaoke()
            else:
                if hasattr(self, 'target_idx'):
                    self.load_estrofe(self.target_idx)
                    self.start_karaoke()

    def show_end(self):
        self.lbl_title.setText("")
        self.lbl_info.setText("")
        self.texto.clear()
        self.texto.setHtml(f"<div style='color:{self.colors['hl']}; font-size:100pt; font-weight:bold; text-align:center; padding-top:100px;'>FIM</div>")
        self.btn_start.setText("INICIAR")

    def abrir_editor(self):
        if not self.hino_data: return
        self.stop_karaoke()
        dlg = EditorDialog(self.hino_atual, self.estrofe_idx, self)
        if dlg.exec():
            self.carregar_hino(self.hino_atual, force_reload=True)
            self.load_estrofe(self.estrofe_idx)

    def nav_estrofe(self, d):
        if self.hino_atual == 0: return
        self.load_estrofe(self.estrofe_idx + d)

    def manual_estrofe(self):
        if self.hino_atual == 0 or not self.hino_data: return
        txt = self.ent_est.text().strip().lower()

        if txt == 'c':
            if self.indice_coro != -1: self.load_estrofe(self.indice_coro)
            return

        if txt.isdigit():
            target_num = int(txt)
            for i, est in enumerate(self.hino_data.get('estrofes', [])):
                try:
                    est_num = int(est.get('numero', -1))
                    if est_num == target_num and est.get('tipo', '').lower() != 'coro':
                        self.load_estrofe(i)
                        return
                except: pass

    def change_bpm(self, d):
        self.bpm = max(10, self.bpm + d)
        self.lbl_bpm.setText(f"BPM: {self.bpm}")
        config_manager.salvar_config('BPM_padrao', self.bpm)

        if self.timer_play.isActive():
            self.timer_play.stop()
            elapsed = (time.time() * 1000) - self.tempo_inicio_nota
            ratio = elapsed / self.duracao_nota_orig if self.duracao_nota_orig > 0 else 0
            rem = self.duracao_nota_orig * (1 - ratio)
            self.timer_play.start(max(10, int(rem)))
            self.timer_beat.setInterval(int(60000/self.bpm))

        # Recalcula durações se hino carregado
        if self.hino_data:
             est = self.hino_data['estrofes'][self.estrofe_idx]
             new_durs = []
             for line in est.get('linhas', []):
                 sils = get_syllable_tokens(line.get('texto_silabado',''))
                 notes = line.get('notas_codes', [])

                 # FALLBACK COM SEMINIMA
                 if len(notes) < len(sils):
                     notes += ["SEMINIMA"]*(len(sils)-len(notes))

                 durs = [calcular_duracao_ms(n, self.bpm, self.unidade_bpm) for n in notes[:len(sils)]]
                 new_durs.extend(durs)
             self.note_durations = new_durs

    def abrir_tela_configuracao(self):
        dlg = ConfigDialog(self)
        dlg.exec()
        self.recarregar_configs()
        if self.hino_atual > 0:
            self.load_estrofe(self.estrofe_idx)

    def aplicar_zoom(self, force=False):
        # Evita redimensionar excessivamente enquanto o usuário arrasta a janela
        if not force:
            self.timer_zoom.start(100)
            return

        if not self.hino_data: return

        # Cálculo dinâmico do tamanho da fonte baseado na altura da janela
        h = self.texto.viewport().height()
        w = self.texto.viewport().width()

        # Fator base: tenta manter proporção
        base_size = h / 15  # Ajuste este divisor conforme preferência

        # Limites definidos no config
        final_size = max(self.min_zoom, min(self.max_zoom, int(base_size)))

        # Aplica ao documento
        font = self.texto.font()
        font.setPointSize(final_size)
        self.texto.setFont(font)

        # Atualiza formatações para manter o tamanho correto nas sílabas
        self.fmt_norm.setFontPointSize(final_size)
        self.fmt_norm.setForeground(QColor(self.colors['fg']))

        self.fmt_dest.setFontPointSize(final_size)
        self.fmt_dest.setForeground(QColor(self.colors['hl']))
        self.fmt_dest.setFontWeight(QFont.Bold)

        # Reaplica o estilo no texto atual sem perder a posição
        cursor = self.texto.textCursor()
        doc = self.texto.document()

        # Reaplica formatação base em tudo
        cursor_all = QTextCursor(doc)
        cursor_all.select(QTextCursor.Document)
        cursor_all.setCharFormat(self.fmt_norm)

        # Se estiver tocando, reaplica o destaque na sílaba atual
        if self.pos_atual > 0 and self.pos_atual <= len(self.indices):
            try:
                idx_info = self.indices[self.pos_atual - 1]
                if idx_info:
                    st, ln = idx_info
                    cur_dest = QTextCursor(doc)
                    cur_dest.setPosition(st)
                    cur_dest.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, ln)
                    cur_dest.setCharFormat(self.fmt_dest)
            except: pass

    def flash_beat(self):
        """ Metrônomo visual simples (pisca a borda ou um indicador) """
        self.current_beat += 1
        if self.current_beat > self.total_beats:
            self.current_beat = 1

        # Exemplo: Alternar cor da borda da barra lateral ou um pequeno indicador
        # Aqui faremos algo sutil na barra de status/info
        if self.current_beat == 1:
            self.lbl_bpm.setStyleSheet(f"color: {COR_EDICAO}; font-weight: bold; font-size: 16px;")
        else:
            self.lbl_bpm.setStyleSheet("color: #AAA; font-size: 14px;")

    # --- EVENTOS DO SISTEMA ---

    def resizeEvent(self, event):
        self.aplicar_zoom(force=False)
        super().resizeEvent(event)

    def keyPressEvent(self, event):
        key = event.key()

        # [ESPAÇO] Play/Pause
        if key == Qt.Key_Space:
            if self.timer_play.isActive():
                self.stop_karaoke()
                self.is_paused = True
                self.lbl_info.setText("PAUSADO")
            elif self.timer_wait.isActive():
                self.timer_wait.stop()
                self.lbl_info.setText("PAUSADO (Espera)")
                self.is_paused = True
            else:
                if self.is_paused:
                    self.is_paused = False
                    if "Espera" in self.lbl_info.text():
                        self.timer_wait.start()
                    else:
                        # Retoma de onde parou
                        if self.duracao_nota_orig > 0:
                            self.timer_play.start(int(self.duracao_nota_orig))
                        else:
                            self.start_karaoke()
                else:
                    self.start_karaoke()

        # [R] Reiniciar Estrofe
        elif key == Qt.Key_R:
            self.load_estrofe(self.estrofe_idx)
            self.start_karaoke()

        # [F11] Tela Cheia
        elif key == Qt.Key_F11:
            self.toggle_fullscreen()

        # [ESC] Sair da Tela Cheia
        elif key == Qt.Key_Escape:
            if self.is_fullscreen_mode:
                self.toggle_fullscreen()

        # [SETAS] Navegação
        elif key == Qt.Key_Right:
            self.nav_estrofe(1)
        elif key == Qt.Key_Left:
            self.nav_estrofe(-1)

        # [+/-] Ajuste de BPM
        elif key == Qt.Key_Plus or key == Qt.Key_Equal:
            self.change_bpm(self.bpm_step)
        elif key == Qt.Key_Minus:
            self.change_bpm(-self.bpm_step)

        super().keyPressEvent(event)

    def toggle_fullscreen(self):
        if self.is_fullscreen_mode:
            self.showNormal()
            self.sidebar.show() # Mostra a barra lateral ao sair
            self.is_fullscreen_mode = False
        else:
            self.showFullScreen()
            self.sidebar.hide() # Esconde a barra lateral para imersão
            self.is_fullscreen_mode = True

        # Força reajuste do zoom após mudança de tamanho
        QTimer.singleShot(100, lambda: self.aplicar_zoom(True))

    def closeEvent(self, event):
        # Salva configurações finais se necessário
        config_manager.salvar_config('BPM_padrao', self.bpm)
        event.accept()

