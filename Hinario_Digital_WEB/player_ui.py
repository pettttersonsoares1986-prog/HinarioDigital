import time
import os
import json
import re
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QLineEdit, QTextEdit, QFrame, QApplication,
    QListWidget, QListWidgetItem, QSplitter, QSizePolicy, QMessageBox,
    QTabWidget, QAbstractItemView # <--- NOVOS IMPORTS
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont, QTextCharFormat, QTextCursor, QColor, QTextDocument

# Importações dos outros módulos
from config import config_manager, COR_INICIAR, COR_PERIGO, COR_AUTO_SCALE, COR_EDICAO, COR_BARRA_PADRAO, BPM_INICIAL, HINOS_FOLDER_PATH
from logic import get_syllable_tokens, calcular_duracao_ms, ler_arquivo_hino, carregar_dados_json
from editor_ui import EditorDialog, ConfigDialog

class KaraokePlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hinário Digital - Player")
        self.setGeometry(100, 100, 1280, 768)
        
        self.fmt_norm = QTextCharFormat()
        self.fmt_dest = QTextCharFormat()

        # Estado do Player
        self.max_hinos = 0; self.hino_data = None; self.hino_atual = 0
        self.bpm = BPM_INICIAL
        self.estrofe_idx = 0; self.pos_atual = 0; self.compasso = "4/4"; self.unidade_bpm = "sm"
        
        self.note_durations = []; self.indices = []; self.syllables = []
        self.estrofes_info = []; self.estrofes_texto = []; self.notas_estrofes = []
        self.tempo_inicio_nota = 0; self.duracao_nota_orig = 0
        
        self.indice_coro = -1; self.proxima_eh_coro = False
        self.mostrar_hifens = True
        self.cache_hinos = [] 
        self.is_paused = False
        self.is_fullscreen_mode = False

        # Timers
        self.timer_play = QTimer(self); self.timer_play.setSingleShot(True); self.timer_play.timeout.connect(self.play_step)
        self.timer_wait = QTimer(self); self.timer_wait.timeout.connect(self.step_wait)
        self.wait_sec = 0
        self.timer_zoom = QTimer(self); self.timer_zoom.setSingleShot(True)
        self.timer_zoom.timeout.connect(lambda: self.aplicar_zoom(True))

        # Timer do Metrônomo Visual
        self.timer_beat = QTimer(self); self.timer_beat.timeout.connect(self.flash_beat)
        self.current_beat = 1; self.total_beats = 4

        self.recarregar_configs()
        self.setup_ui()
        self.max_hinos = carregar_dados_json()
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
        self.font_size = config_manager.get('tamanho_fonte', int); self.espacamento = config_manager.get('espacamento_texto', int)
        self.bpm_step = config_manager.get('bpm_step', int); self.start_delay = config_manager.get('start_delay', int); self.strofe_delay = config_manager.get('strofe_delay', int)
        self.min_zoom = config_manager.get('min_zoom', int); self.max_zoom = config_manager.get('max_zoom', int); self.bpm = config_manager.get('BPM_padrao', int)
        self.colors = {
            'cor_fundo_texto': config_manager.get('cor_fundo_texto', str),
            'cor_texto_normal': config_manager.get('cor_texto_normal', str),
            'cor_destaque_karaoke': config_manager.get('cor_destaque_karaoke', str),
            'cor_nota_normal': config_manager.get('cor_nota_normal', str),
            'cor_nota_destaque': config_manager.get('cor_nota_destaque', str),
            'cor_barra_navegacao': config_manager.get('cor_barra_navegacao', str),
        }
        self.colors['bg'] = self.colors['cor_fundo_texto']; self.colors['fg'] = self.colors['cor_texto_normal']
        self.colors['hl'] = self.colors['cor_destaque_karaoke']; self.colors['nav'] = self.colors['cor_barra_navegacao']
        if hasattr(self, 'texto'): self.apply_style()

    def setup_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        layout_principal = QHBoxLayout(central)
        layout_principal.setContentsMargins(0,0,0,0); layout_principal.setSpacing(0)
        
        # --- 1. SIDEBAR (AGORA COM ABAS) ---
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(300) # Um pouco mais largo
        self.sidebar.setStyleSheet("background-color: #202020; border-right: 1px solid #444;")
        l_sidebar = QVBoxLayout(self.sidebar)
        l_sidebar.setContentsMargins(0,0,0,0) # Sem margem para as abas encostarem

        self.tabs_sidebar = QTabWidget()
        self.tabs_sidebar.setStyleSheet("""
            QTabWidget::pane { border: 0; }
            QTabBar::tab { background: #333; color: #AAA; padding: 8px 20px; }
            QTabBar::tab:selected { background: #444; color: white; font-weight: bold; border-top: 2px solid #0050C0; }
        """)
        
        # --- ABA BIBLIOTECA ---
        tab_lib = QWidget(); l_lib = QVBoxLayout(tab_lib)
        self.txt_busca = QLineEdit(); self.txt_busca.setPlaceholderText("🔍 Buscar hino...")
        self.txt_busca.setStyleSheet("padding: 6px; color: white; background-color: #333; border: 1px solid #555; border-radius: 4px;")
        self.txt_busca.textChanged.connect(self.filtrar_lista_hinos)
        l_lib.addWidget(self.txt_busca)
        
        self.lista_hinos = QListWidget()
        self.lista_hinos.setStyleSheet("QListWidget { background-color: #252525; color: #DDD; border: none; } QListWidget::item { padding: 8px; border-bottom: 1px solid #333; } QListWidget::item:selected { background-color: #0050C0; color: white; }")
        self.lista_hinos.itemDoubleClicked.connect(self.hino_selecionado_lista) # Duplo clique para carregar
        l_lib.addWidget(self.lista_hinos)
        
        btn_add_playlist = QPushButton("Adicionar à Playlist ➔")
        btn_add_playlist.setStyleSheet(f"background-color: {COR_BARRA_PADRAO}; color: white; padding: 6px;")
        btn_add_playlist.clicked.connect(self.adicionar_a_playlist)
        l_lib.addWidget(btn_add_playlist)
        
        # --- ABA PLAYLIST ---
        tab_play = QWidget(); l_play = QVBoxLayout(tab_play)
        lbl_info_pl = QLabel("Arraste para reordenar"); lbl_info_pl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_info_pl.setStyleSheet("color: #777; font-size: 11px; margin-bottom: 5px;")
        l_play.addWidget(lbl_info_pl)

        self.lista_playlist = QListWidget()
        self.lista_playlist.setDragDropMode(QAbstractItemView.InternalMove) # Permite arrastar
        self.lista_playlist.setStyleSheet("QListWidget { background-color: #1E1E1E; color: #EEE; border: none; } QListWidget::item { padding: 10px; border-bottom: 1px solid #333; } QListWidget::item:selected { background-color: #2E8B57; color: white; }")
        self.lista_playlist.itemDoubleClicked.connect(self.hino_selecionado_playlist)
        l_play.addWidget(self.lista_playlist)
        
        h_btns_pl = QHBoxLayout()
        btn_rem_pl = QPushButton("Remover"); btn_rem_pl.clicked.connect(self.remover_da_playlist)
        btn_rem_pl.setStyleSheet("background-color: #8B0000; color: white;")
        btn_clear_pl = QPushButton("Limpar"); btn_clear_pl.clicked.connect(self.lista_playlist.clear)
        btn_clear_pl.setStyleSheet("background-color: #555; color: white;")
        
        h_btns_pl.addWidget(btn_rem_pl); h_btns_pl.addWidget(btn_clear_pl)
        l_play.addLayout(h_btns_pl)

        self.tabs_sidebar.addTab(tab_lib, "Biblioteca")
        self.tabs_sidebar.addTab(tab_play, "Playlist")
        l_sidebar.addWidget(self.tabs_sidebar)
        
        layout_principal.addWidget(self.sidebar)

        # --- 2. ÁREA DO PLAYER (DIREITA) ---
        right_container = QWidget()
        layout_player = QVBoxLayout(right_container)
        layout_player.setContentsMargins(0,0,0,0); layout_player.setSpacing(0)
        
        # Toolbar Superior
        self.tb_frame = QFrame(); tb_l = QHBoxLayout(self.tb_frame); tb_l.setContentsMargins(5,5,5,5)
        
        btn_menu = QPushButton("☰"); btn_menu.setFixedWidth(30)
        btn_menu.setStyleSheet("background-color: #444; color: white; font-weight: bold;")
        btn_menu.clicked.connect(self.toggle_sidebar)
        tb_l.addWidget(btn_menu)
        
        # Metrônomo
        self.lbl_beat_light = QLabel()
        self.lbl_beat_light.setFixedSize(20, 20)
        self.lbl_beat_light.setStyleSheet("background-color: #333; border-radius: 10px; border: 1px solid #555;")
        tb_l.addWidget(self.lbl_beat_light)

        # BPM
        self.lbl_bpm = QLabel(f"BPM: {self.bpm}"); self.lbl_bpm.setStyleSheet("color: white; font-weight: bold; margin-left: 10px;")
        tb_l.addWidget(self.lbl_bpm)
        tb_l.addWidget(QPushButton("-", clicked=lambda: self.change_bpm(-self.bpm_step)))
        tb_l.addWidget(QPushButton("+", clicked=lambda: self.change_bpm(self.bpm_step)))
        
        # Estrofe
        tb_l.addWidget(QLabel(" Est:", styleSheet="color: white;"))
        self.ent_est = QLineEdit("1"); self.ent_est.setFixedWidth(40); self.ent_est.returnPressed.connect(self.manual_estrofe)
        tb_l.addWidget(self.ent_est)
        
        # Botão Hifens
        self.btn_hifen = QPushButton("A-B"); self.btn_hifen.setCheckable(True); self.btn_hifen.setChecked(True)
        self.btn_hifen.setToolTip("Mostrar/Ocultar separação silábica"); self.btn_hifen.setStyleSheet(f"background-color: {COR_AUTO_SCALE}; color: white; font-weight: bold; margin-left: 10px;")
        self.btn_hifen.clicked.connect(self.toggle_hifen); tb_l.addWidget(self.btn_hifen)

        # CONTROLES PRINCIPAIS
        self.btn_start = QPushButton("INICIAR")
        self.btn_start.setMinimumWidth(90)
        self.btn_start.setStyleSheet(f"background:{COR_INICIAR}; color:white; font-weight:bold; padding: 6px; border-radius: 4px; margin-left: 15px;")
        self.btn_start.clicked.connect(self.toggle_play_pause)
        tb_l.addWidget(self.btn_start)

        self.btn_restart_strofe = QPushButton("↺ ESTROFE")
        self.btn_restart_strofe.setToolTip("Reiniciar estrofe atual")
        self.btn_restart_strofe.setStyleSheet("background-color: #FF8C00; color: white; font-weight: bold; padding: 6px; border-radius: 4px;")
        self.btn_restart_strofe.clicked.connect(self.reiniciar_estrofe)
        tb_l.addWidget(self.btn_restart_strofe)
        
        btn_stop = QPushButton("PARAR", clicked=self.stop_karaoke)
        btn_stop.setStyleSheet(f"background:{COR_PERIGO}; color:white; font-weight:bold; padding: 6px; border-radius: 4px;")
        tb_l.addWidget(btn_stop)
        
        tb_l.addStretch()
        
        btn_fs = QPushButton("⛶"); btn_fs.setToolTip("Modo Apresentação (F11)"); btn_fs.setStyleSheet("background-color: #555; color: white; font-weight: bold;")
        btn_fs.clicked.connect(self.toggle_fullscreen); tb_l.addWidget(btn_fs)
        
        btn_zoom = QPushButton("ZOOM", clicked=lambda: self.aplicar_zoom(True)); btn_zoom.setStyleSheet(f"background:{COR_AUTO_SCALE}; color:white;"); tb_l.addWidget(btn_zoom)
        btn_edit = QPushButton("EDITAR", clicked=self.abrir_editor); btn_edit.setStyleSheet(f"background:{COR_EDICAO}; color:white; font-weight:bold;"); tb_l.addWidget(btn_edit)
        btn_cfg = QPushButton("CFG", clicked=self.abrir_tela_configuracao); btn_cfg.setStyleSheet(f"background:{COR_BARRA_PADRAO}; color:white;"); tb_l.addWidget(btn_cfg)
        
        layout_player.addWidget(self.tb_frame)
        
        # Display
        self.lbl_title = QLabel("..."); self.lbl_title.setFont(QFont("Arial", 36, QFont.Weight.Bold)); self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter); layout_player.addWidget(self.lbl_title)
        self.lbl_info = QLabel(""); self.lbl_info.setFont(QFont("Arial", 20)); self.lbl_info.setAlignment(Qt.AlignmentFlag.AlignCenter); layout_player.addWidget(self.lbl_info)
        self.texto = QTextEdit(); self.texto.setReadOnly(True); self.texto.setFrameShape(QFrame.Shape.NoFrame); self.texto.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); self.texto.setStyleSheet("padding: 20px;"); layout_player.addWidget(self.texto)
        
        layout_principal.addWidget(right_container)
        self.apply_style()

    # --- EVENTOS DE TECLADO ---
    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Space: self.toggle_play_pause()
        elif key == Qt.Key_R: self.reiniciar_estrofe()
        elif key == Qt.Key_P: self.stop_karaoke()
        elif key == Qt.Key_F11: self.toggle_fullscreen()
        elif key == Qt.Key_Escape and self.is_fullscreen_mode: self.toggle_fullscreen()
        else: super().keyPressEvent(event)

    def toggle_fullscreen(self):
        self.is_fullscreen_mode = not self.is_fullscreen_mode
        if self.is_fullscreen_mode:
            self.sidebar.hide(); self.tb_frame.hide(); self.showFullScreen()
        else:
            self.sidebar.show(); self.tb_frame.show(); self.showNormal()
        QTimer.singleShot(100, lambda: self.aplicar_zoom(True))

    # --- FUNÇÕES DA BIBLIOTECA E PLAYLIST ---
    def toggle_sidebar(self):
        if self.sidebar.isVisible(): self.sidebar.hide()
        else: self.sidebar.show()

    def carregar_lista_hinos(self):
        self.lista_hinos.clear(); self.cache_hinos = []
        if not os.path.exists(HINOS_FOLDER_PATH): return
        files = sorted([f for f in os.listdir(HINOS_FOLDER_PATH) if f.endswith('.json')])
        for f in files:
            try:
                m = re.search(r"(\d+)", f)
                num = int(m.group(1)) if m else 0
                with open(os.path.join(HINOS_FOLDER_PATH, f), 'r', encoding='utf-8') as arq:
                    data = json.load(arq); titulo = data.get('titulo', 'Sem Título')
                display_text = f"{num}. {titulo}"
                self.cache_hinos.append((num, display_text))
            except: pass
        self.cache_hinos.sort(key=lambda x: x[0])
        for num, display in self.cache_hinos:
            item = QListWidgetItem(display); item.setData(Qt.UserRole, num); self.lista_hinos.addItem(item)

    def filtrar_lista_hinos(self, text):
        self.lista_hinos.clear(); text = text.lower()
        for num, display in self.cache_hinos:
            if text in str(num) or text in display.lower():
                item = QListWidgetItem(display); item.setData(Qt.UserRole, num); self.lista_hinos.addItem(item)

    def hino_selecionado_lista(self, item):
        num = item.data(Qt.UserRole); self.carregar_hino(num)

    def adicionar_a_playlist(self):
        # Pega o item selecionado na biblioteca
        items = self.lista_hinos.selectedItems()
        if not items: return
        for item in items:
            # Clona o item para a playlist
            new_item = QListWidgetItem(item.text())
            new_item.setData(Qt.UserRole, item.data(Qt.UserRole))
            self.lista_playlist.addItem(new_item)
        # Muda para a aba playlist para feedback visual
        self.tabs_sidebar.setCurrentIndex(1)

    def remover_da_playlist(self):
        items = self.lista_playlist.selectedItems()
        if not items: return
        for item in items:
            self.lista_playlist.takeItem(self.lista_playlist.row(item))

    def hino_selecionado_playlist(self, item):
        num = item.data(Qt.UserRole); self.carregar_hino(num)
    # --------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.hino_atual > 0 and not self.timer_play.isActive() and self.estrofes_texto: self.timer_zoom.start(150)

    def apply_style(self):
        bg = self.colors['cor_fundo_texto']; fg = self.colors['cor_texto_normal']
        self.centralWidget().setStyleSheet(f"background-color: {bg}; color: {fg};")
        self.texto.setStyleSheet(f"background-color: {bg}; color: {fg}; border: none; padding: 20px;")
        self.tb_frame.setStyleSheet(f"background-color: {self.colors['cor_barra_navegacao']};")
        self.lbl_title.setStyleSheet(f"color: {self.colors['cor_destaque_karaoke']};")
        self.lbl_info.setStyleSheet(f"color: {self.colors['cor_destaque_karaoke']};")
        font_base = QFont("Arial", int(self.font_size), QFont.Weight.Bold)
        self.fmt_norm = QTextCharFormat(); self.fmt_norm.setForeground(QColor(self.colors['cor_texto_normal'])); self.fmt_norm.setFont(font_base)
        self.fmt_dest = QTextCharFormat(); self.fmt_dest.setForeground(QColor(self.colors['cor_destaque_karaoke'])); self.fmt_dest.setFont(font_base) 
        if self.hino_atual > 0: self.aplicar_zoom()

    def aplicar_espacamento(self):
        cursor = QTextCursor(self.texto.document()); cursor.beginEditBlock(); block = self.texto.document().begin()
        while block.isValid():
            cursor.setPosition(block.position()); fmt = cursor.blockFormat(); fmt.setBottomMargin(self.espacamento); cursor.setBlockFormat(fmt); block = block.next()
        cursor.endEditBlock()

    def aplicar_zoom(self, forcar=False):
        if self.timer_play.isActive() or self.hino_atual == 0: return
        font_base = QFont("Arial", int(self.font_size), QFont.Weight.Bold)
        self.texto.setFont(font_base)
        self.fmt_norm = QTextCharFormat(); self.fmt_norm.setForeground(QColor(self.colors['cor_texto_normal'])); self.fmt_norm.setFont(font_base)
        self.fmt_dest = QTextCharFormat(); self.fmt_dest.setForeground(QColor(self.colors['cor_destaque_karaoke'])); size_dest = min(self.max_zoom, int(self.font_size * 1.5)); self.fmt_dest.setFont(QFont("Arial", size_dest, QFont.Weight.Bold))
        cur = QTextCursor(self.texto.document()); cur.clearSelection(); self.texto.setTextCursor(cur)
        if not forcar: return
        QApplication.processEvents(); h_view = self.texto.viewport().height(); w_view = self.texto.viewport().width()
        if h_view < 50: return
        w_util = w_view - 40; h_util = h_view - 40; txt = self.texto.toPlainText()
        if not txt: return
        doc = QTextDocument(); doc.setPlainText(txt); doc.setTextWidth(w_util)
        best = self.min_zoom
        for s in range(self.max_zoom, self.min_zoom -1, -2):
            f = QFont("Arial", s, QFont.Weight.Bold); doc.setDefaultFont(f); curs = QTextCursor(doc); curs.beginEditBlock(); blk = doc.begin()
            while blk.isValid():
                fmt = blk.blockFormat(); fmt.setBottomMargin(self.espacamento); curs.setPosition(blk.position()); curs.setBlockFormat(fmt); blk = blk.next()
            curs.endEditBlock()
            if doc.size().height() <= h_util * 0.95: best = s; break
        if best != self.font_size:
            self.font_size = best; config_manager.salvar_config('tamanho_fonte', best); self.aplicar_zoom(); self.aplicar_espacamento()
            cur = QTextCursor(self.texto.document()); cur.select(QTextCursor.Document); cur.setCharFormat(self.fmt_norm); cur.clearSelection(); self.texto.setTextCursor(cur)

    def toggle_hifen(self):
        self.mostrar_hifens = self.btn_hifen.isChecked()
        self.btn_hifen.setText("A-B" if self.mostrar_hifens else "AB")
        if self.hino_atual > 0: self.load_estrofe(self.estrofe_idx)

    def carregar_hino(self, num, force_reload=False):
        if not force_reload and num == self.hino_atual and self.hino_data: self.load_estrofe(0); return
        if num < 1 or num > self.max_hinos: return
        d = ler_arquivo_hino(num)
        if not d: return
        self.hino_data = d; self.hino_atual = num
        self.indice_coro = -1; self.proxima_eh_coro = False; estrofes = d.get('estrofes', [])
        for i, est in enumerate(estrofes):
            if est.get('tipo', '').lower() == 'coro': self.indice_coro = i; break
        json_bpm = d.get("BPM"); 
        if json_bpm: self.bpm = json_bpm
        else: self.bpm = config_manager.get('BPM_padrao', 60)
        self.compasso = d.get("compasso", "4/4")
        
        # Parse do compasso para o metrônomo
        try: self.total_beats = int(self.compasso.split('/')[0])
        except: self.total_beats = 4

        self.unidade_bpm = d.get("unidade_bpm", "sm")
        self.lbl_title.setText(d.get("titulo", f"Hino {num}")); self.lbl_bpm.setText(f"BPM: {self.bpm}")
        self.estrofes_info = []
        for est in d.get("estrofes", []):
            if est.get('tipo', '').lower() == 'coro': self.estrofes_info.append("Coro")
            else: self.estrofes_info.append(f"{est.get('tipo','Est')} {est.get('numero','')}")
        self.load_estrofe(0)

    def load_estrofe(self, idx):
        self.stop_karaoke()
        if not self.hino_data: return
        estrofes = self.hino_data.get('estrofes', [])
        if idx < 0 or idx >= len(estrofes): return
        self.estrofe_idx = idx; est = estrofes[idx]; self.lbl_info.setText(self.estrofes_info[idx])
        if idx == self.indice_coro: self.ent_est.setText("C")
        else:
            if str(est.get('numero','')).isdigit(): self.ent_est.setText(str(est.get('numero')))
            else: self.ent_est.setText(str(idx+1))
        self.texto.clear(); self.texto.setFont(QFont("Arial", self.min_zoom, QFont.Weight.Bold))
        full_text = ""; self.note_durations = []; self.indices = []; current_char_idx = 0
        PAUSE_SYMBOLS = ["''", "_", '"', "__"]
        for l_idx, line in enumerate(est.get('linhas', [])):
            txt = line.get('texto_silabado', '').strip()
            if l_idx > 0: full_text += "\n"; current_char_idx += 1
            tokens = get_syllable_tokens(txt); notes = line.get('notas_codes', [])
            if len(notes) < len(tokens): notes += ["sm"] * (len(tokens) - len(notes))
            for k, token in enumerate(tokens):
                note = notes[k]
                dur = calcular_duracao_ms(note, self.bpm, self.unidade_bpm)
                self.note_durations.append(dur)
                if token in PAUSE_SYMBOLS: self.indices.append(None)
                else:
                    display_token = token
                    if not self.mostrar_hifens and display_token.endswith('-'): display_token = display_token[:-1]
                    prefix = ""
                    if k > 0:
                        prev = tokens[k-1]
                        if not prev.endswith('-') and prev not in PAUSE_SYMBOLS: prefix = " "
                    if k > 0:
                        prev = tokens[k-1]
                        if prev.endswith('-') and not self.mostrar_hifens: prefix = ""
                        elif prev.endswith('-') and self.mostrar_hifens: prefix = ""
                    if k == 0: prefix = ""
                    word_to_display = prefix + display_token; full_text += word_to_display
                    start_pos = current_char_idx + len(prefix); self.indices.append((start_pos, len(display_token)))
                    current_char_idx += len(word_to_display)
        self.texto.setText(full_text); self.texto.setAlignment(Qt.AlignmentFlag.AlignLeft)
        QTimer.singleShot(50, lambda: self.aplicar_zoom(True))

    # --- LÓGICA DE PLAY/PAUSE/RESUME ---
    def toggle_play_pause(self):
        if self.hino_atual == 0: return
        if self.timer_play.isActive() or self.timer_wait.isActive(): self.pausar()
        elif self.is_paused: self.continuar()
        else: self.iniciar_karaoke_com_delay()

    def pausar(self):
        self.is_paused = True
        self.timer_play.stop(); self.timer_wait.stop(); self.timer_beat.stop()
        self.btn_start.setText("CONTINUAR"); self.btn_start.setStyleSheet("background-color: #FFA500; color: black; font-weight: bold; padding: 6px; border-radius: 4px;")
        elapsed = (time.time() * 1000) - self.tempo_inicio_nota
        self.tempo_restante_pausa = max(0, self.duracao_nota_orig - elapsed)
        self.lbl_info.setText(f"{self.lbl_info.text()} (PAUSADO)"); self.lbl_info.setStyleSheet("color: yellow;")
        self.lbl_beat_light.setStyleSheet("background-color: #333; border-radius: 10px; border: 1px solid #555;")

    def continuar(self):
        self.is_paused = False
        self.btn_start.setText("PAUSAR"); self.btn_start.setStyleSheet(f"background:{COR_INICIAR}; color:white; font-weight:bold; padding: 6px; border-radius: 4px;")
        txt = self.lbl_info.text().replace(" (PAUSADO)", ""); self.lbl_info.setText(txt); self.lbl_info.setStyleSheet(f"color: {self.colors['hl']};")
        ms_beat = 60000 / self.bpm
        self.timer_beat.start(int(ms_beat))
        if self.tempo_restante_pausa > 0:
            self.timer_play.start(int(self.tempo_restante_pausa)); self.tempo_inicio_step = time.time() * 1000 - (self.duracao_nota_orig - self.tempo_restante_pausa)
        else: self.play_step()

    def reiniciar_estrofe(self):
        if self.hino_atual == 0: return
        self.stop_karaoke(); self.load_estrofe(self.estrofe_idx); self.start_karaoke()

    def iniciar_karaoke_com_delay(self):
        if self.hino_atual == 0: return
        self.stop_karaoke()
        if self.indice_coro != -1 and self.estrofe_idx != self.indice_coro: self.proxima_eh_coro = True
        else: self.proxima_eh_coro = False
        self.btn_start.setText("PAUSAR"); self.btn_start.setStyleSheet(f"background:{COR_INICIAR}; color:white; font-weight:bold; padding: 6px; border-radius: 4px;")
        if self.start_delay > 0:
            self.wait_sec = self.start_delay; self.lbl_info.setText(f"Iniciando em {self.wait_sec}..."); self.timer_wait.start(1000)
        else: self.start_karaoke()

    def start_karaoke(self): 
        self.is_paused = False; self.pos_atual = 0; self.tempo_inicio_nota = 0; self.current_beat = 1
        ms_beat = 60000 / self.bpm
        self.timer_beat.start(int(ms_beat)); self.flash_beat(); self.play_step()

    def stop_karaoke(self):
        self.timer_play.stop(); self.timer_wait.stop(); self.timer_beat.stop()
        self.is_paused = False; self.tempo_restante_pausa = 0
        self.lbl_beat_light.setStyleSheet("background-color: #333; border-radius: 10px; border: 1px solid #555;")
        self.btn_start.setText("INICIAR"); self.btn_start.setStyleSheet(f"background:{COR_INICIAR}; color:white; font-weight:bold; padding: 6px; border-radius: 4px;")
        self.lbl_info.setStyleSheet(f"color: {self.colors['hl']};")
        if self.hino_atual > 0:
            try:
                if hasattr(self, 'fmt_norm') and self.fmt_norm is not None:
                    cur = QTextCursor(self.texto.document()); cur.select(QTextCursor.Document); cur.setCharFormat(self.fmt_norm); cur.clearSelection(); self.texto.setTextCursor(cur)
            except Exception as e: print(f"Aviso ao parar: {e}")
            if self.hino_data and self.estrofes_info:
                if 0 <= self.estrofe_idx < len(self.estrofes_info): self.lbl_info.setText(self.estrofes_info[self.estrofe_idx])

    def flash_beat(self):
        color = "#00FF00" if self.current_beat == 1 else "#FFFF00"
        self.lbl_beat_light.setStyleSheet(f"background-color: {color}; border-radius: 10px; border: 1px solid white;")
        QTimer.singleShot(150, lambda: self.lbl_beat_light.setStyleSheet("background-color: #333; border-radius: 10px; border: 1px solid #555;"))
        self.current_beat += 1
        if self.current_beat > self.total_beats: self.current_beat = 1

    def play_step(self):
        if self.pos_atual >= len(self.indices): self.timer_play.stop(); self.timer_beat.stop(); self.step_wait_for_next(); return
        ms = self.note_durations[self.pos_atual]; self.duracao_nota_orig = ms; self.tempo_inicio_nota = time.time() * 1000
        idx_info = self.indices[self.pos_atual]
        if idx_info is not None:
            st, ln = idx_info
            try:
                if hasattr(self, 'fmt_norm'):
                    reset_cur = QTextCursor(self.texto.document()); reset_cur.select(QTextCursor.Document); reset_cur.setCharFormat(self.fmt_norm); reset_cur.clearSelection()
            except: pass
            cur = QTextCursor(self.texto.document()); cur.setPosition(st); cur.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, ln); cur.setCharFormat(self.fmt_dest); cur.clearSelection(); self.texto.setTextCursor(cur); self.texto.ensureCursorVisible()
        else:
            try:
                if hasattr(self, 'fmt_norm'):
                    reset_cur = QTextCursor(self.texto.document()); reset_cur.select(QTextCursor.Document); reset_cur.setCharFormat(self.fmt_norm); reset_cur.clearSelection()
            except: pass
        self.pos_atual += 1; self.timer_play.start(int(ms))

    def step_wait_for_next(self):
        proximo_idx = -1
        if self.indice_coro != -1 and self.estrofe_idx != self.indice_coro:
            proximo_idx = self.indice_coro; self.proxima_estrofe_real = self.estrofe_idx + 1
            if self.proxima_estrofe_real == self.indice_coro: self.proxima_estrofe_real += 1
        elif self.indice_coro != -1 and self.estrofe_idx == self.indice_coro:
            if hasattr(self, 'proxima_estrofe_real'): proximo_idx = self.proxima_estrofe_real
            else: proximo_idx = self.estrofe_idx + 1
        else: proximo_idx = self.estrofe_idx + 1

        if proximo_idx < len(self.hino_data.get('estrofes', [])):
            self.wait_sec = self.strofe_delay if self.strofe_delay > 0 else 2
            nome_prox = "Próxima"
            if self.indice_coro != -1:
                if proximo_idx == self.indice_coro: nome_prox = "Coro"
                else: nome_prox = "Estrofe"
            self.lbl_info.setText(f"{nome_prox} em {self.wait_sec}s...")
            self.target_idx = proximo_idx; self.timer_wait.start(1000)
        else: self.show_end()

    def step_wait(self):
        self.wait_sec -= 1
        if self.wait_sec > 0:
            if "Iniciando" in self.lbl_info.text(): msg = "Iniciando"
            else: parts = self.lbl_info.text().split(" em "); msg = parts[0] if len(parts) > 0 else "Próxima"
            self.lbl_info.setText(f"{msg} em {self.wait_sec}s...")
        else:
            self.timer_wait.stop()
            if "Iniciando" in self.lbl_info.text(): self.start_karaoke()
            else:
                if hasattr(self, 'target_idx'): self.load_estrofe(self.target_idx); self.start_karaoke()

    def show_end(self):
        self.lbl_title.setText(""); self.lbl_info.setText(""); self.texto.clear(); self.texto.setHtml(f"<div style='color:{self.colors['hl']}; font-size:100pt; font-weight:bold; text-align:center; padding-top:100px;'>FIM</div>")
        self.btn_start.setText("INICIAR")

    def abrir_editor(self):
        if not self.hino_data: return
        self.stop_karaoke(); dlg = EditorDialog(self.hino_atual, self.estrofe_idx, self)
        if dlg.exec(): self.carregar_hino(self.hino_atual, force_reload=True); self.load_estrofe(self.estrofe_idx)

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
                        self.load_estrofe(i); return
                except: pass

    def change_bpm(self, d):
        self.bpm = max(10, self.bpm + d); self.lbl_bpm.setText(f"BPM: {self.bpm}"); config_manager.salvar_config('BPM_padrao', self.bpm)
        if self.timer_play.isActive():
            self.timer_play.stop(); elapsed = (time.time() * 1000) - self.tempo_inicio_nota
            ratio = elapsed / self.duracao_nota_orig if self.duracao_nota_orig > 0 else 0
            rem = self.duracao_nota_orig * (1 - ratio); self.timer_play.start(max(10, int(rem)))
            self.timer_beat.setInterval(int(60000/self.bpm))
        if self.hino_data:
             est = self.hino_data['estrofes'][self.estrofe_idx]; new_durs = []
             for line in est.get('linhas', []):
                 sils = get_syllable_tokens(line.get('texto_silabado','')); notes = line.get('notas_codes', [])
                 if len(notes) < len(sils): notes += ["sm"]*(len(sils)-len(notes))
                 durs = [calcular_duracao_ms(n, self.bpm, self.unidade_bpm) for n in notes[:len(sils)]]; new_durs.extend(durs)
             self.note_durations = new_durs

    def abrir_tela_configuracao(self): dlg = ConfigDialog(self); dlg.exec()