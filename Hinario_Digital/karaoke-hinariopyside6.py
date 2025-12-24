import sys
import os
import json
import re
import sqlite3
import time

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QLineEdit, QTextEdit, QScrollArea, QFrame,
    QComboBox, QDialog, QGroupBox, QSizePolicy, QStackedWidget, QSplitter, 
    QColorDialog, QTabWidget, QSpinBox, QDoubleSpinBox, QMessageBox
)
from PySide6.QtCore import (
    QTimer, Qt
)
from PySide6.QtGui import (
    QColor, QFont, QTextCharFormat, QTextCursor, QFontMetrics, QTextDocument
)

# ===================== 1. CONFIGURAÇÃO GLOBAL =====================

HINOS_FOLDER_PATH = os.path.normpath(r"C:\Users\psoares\pyNestle\Private\Hinario_Digital\textos_corrigidos")
CONFIG_DB_FILE = 'config.db'

# --- VALORES PADRÃO ---
BPM_INICIAL = 60
BPM_STEP = 5 
FERMATA_FACTOR = 1.5 
TAMANHO_PADRAO = 60
ESPACAMENTO_PADRAO = 20
MIN_ZOOM = 12   
MAX_ZOOM = 150 
STEP_ESPACAMENTO = 5
START_DELAY_PADRAO = 2
STROFE_DELAY_PADRAO = 3   
EDITOR_WIDTH_PADRAO = 1000
EDITOR_HEIGHT_PADRAO = 800

# Tempos padrão para as pausas (em ms)
DEFAULT_TIME_RC = 300  # Respiração Curta
DEFAULT_TIME_PC = 500  # Pausa Curta
DEFAULT_TIME_RL = 800  # Respiração Longa
DEFAULT_TIME_PL = 1000 # Pausa Longa

DEFAULT_PARAMS = {
    'bpm_step': BPM_STEP,
    'fermata_factor': FERMATA_FACTOR,
    'min_zoom': MIN_ZOOM,
    'max_zoom': MAX_ZOOM,
    'start_delay': START_DELAY_PADRAO,
    'strofe_delay': STROFE_DELAY_PADRAO,
    'time_rc': DEFAULT_TIME_RC,
    'time_pc': DEFAULT_TIME_PC,
    'time_rl': DEFAULT_TIME_RL,
    'time_pl': DEFAULT_TIME_PL,
    'editor_width': EDITOR_WIDTH_PADRAO,
    'editor_height': EDITOR_HEIGHT_PADRAO,
    'tamanho_fonte': TAMANHO_PADRAO,
    'espacamento_texto': ESPACAMENTO_PADRAO,
    'cor_fundo_texto': "black",
    'cor_texto_normal': "white",
    'cor_destaque_karaoke': "#FFFF00",
    'cor_nota_normal': "#00BFFF",
    'cor_nota_destaque': "#32CD32",
    'cor_barra_navegacao': "#000080",
    'BPM_padrao': BPM_INICIAL
}

# Códigos de nota
NOTE_DURATIONS_BASE = {
    "sm": 1.0, "m": 2.0, "c": 0.5, "sc": 0.25, "sb": 4.0, "cp": 0.75, 
    "rl": 0.0, "rc": 0.0, "pc": 0.0, "pl": 0.0 
}
NOTE_CODES = list(NOTE_DURATIONS_BASE.keys()) + [f"{k}_fermata" for k in NOTE_DURATIONS_BASE.keys() if k not in ["rl", "rc", "pc", "pl"]]

# Cores Fixas
COR_INICIAR = "#006400" 
COR_PERIGO = "#8B0000" 
COR_AUTO_SCALE = "#0050C0" 
COR_EDICAO = "#FF4500"
COR_BARRA_PADRAO = "#000080"

# ===================== 2. GERENCIADORES =====================

class ConfigManager:
    def __init__(self):
        self.iniciar_banco_config()

    def iniciar_banco_config(self):
        try:
            conn = sqlite3.connect(CONFIG_DB_FILE)
            conn.execute("CREATE TABLE IF NOT EXISTS configuracoes (chave TEXT PRIMARY KEY, valor TEXT)")
            conn.commit(); conn.close()
        except: pass
            
    def get(self, chave, tipo=str):
        val = None
        try:
            conn = sqlite3.connect(CONFIG_DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT valor FROM configuracoes WHERE chave = ?", (chave,))
            res = cursor.fetchone()
            conn.close()
            if res: val = res[0]
        except: pass
        if val is None: val = DEFAULT_PARAMS.get(chave)
        if val is not None:
            try:
                if tipo == int: return int(float(val))
                if tipo == float: return float(val)
                return str(val)
            except: pass
        return val
        
    def set(self, chave, valor):
        try:
            conn = sqlite3.connect(CONFIG_DB_FILE)
            conn.execute("INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES (?, ?)", (chave, str(valor)))
            conn.commit(); conn.close()
        except: pass

    def carregar_config(self, chave, padrao=None): 
        res = self.get(chave)
        return res if res is not None else padrao

    def salvar_config(self, chave, valor): 
        self.set(chave, valor)

config_manager = ConfigManager()

# --- TOKENIZAÇÃO ---
def _get_syllable_tokens(text_line):
    # Regex captura: __ (pl), '' (rc), _ (pc), " (rl), - (hifen)
    padrao = r'(__|\'\'|[_"\-]|\s+)'
    tokens_raw = re.split(padrao, text_line)
    lista_final = []
    for token in tokens_raw:
        if not token: continue
        token_limpo = token.strip()
        if token_limpo == '': pass
        elif token == '-':
            if lista_final: lista_final[-1] += "-"
            else: lista_final.append("-")
        else:
            simbolos_pausa = ["''", '"', "_", "__"]
            if token_limpo in simbolos_pausa: lista_final.append(token_limpo)
            else:
                limpo = re.sub(r'[^\w\',~\-.;:!?]', '', token) 
                if limpo or token_limpo in [",", ";", ".", "!", "?", ":"]: lista_final.append(token)
    return lista_final

def ler_arquivo_hino(num):
    for f in [f"hino_{num:03d}.json", f"hino_{num}.json"]:
        p = os.path.join(HINOS_FOLDER_PATH, f)
        if os.path.exists(p):
            try: 
                with open(p, 'r', encoding='utf-8') as file: return json.load(file)
            except: pass
    return None

def carregar_dados_json():
    if not os.path.exists(HINOS_FOLDER_PATH): 
        try: os.makedirs(HINOS_FOLDER_PATH)
        except: pass
        return 0
    max_n = 0
    pat = re.compile(r"^hino_(\d+)")
    for f in os.listdir(HINOS_FOLDER_PATH):
        m = pat.match(f)
        if m: max_n = max(max_n, int(m.group(1)))
    return max_n

def calcular_duracao_ms(code, bpm, unidade_bpm="sm"):
    if bpm <= 0: return 500
    nota_code = code.strip().lower()
    fermata = "_fermata" in nota_code
    if fermata: nota_code = nota_code.replace("_fermata", "")

    if nota_code == 'rc': return config_manager.get('time_rc', int) or 300
    if nota_code == 'pc': return config_manager.get('time_pc', int) or 500
    if nota_code == 'rl': return config_manager.get('time_rl', int) or 800
    if nota_code == 'pl': return config_manager.get('time_pl', int) or 1000

    ms_por_batida = 60000 / bpm
    valor_base_unidade = NOTE_DURATIONS_BASE.get(unidade_bpm, 1.0)
    ms_seminima = ms_por_batida / valor_base_unidade
    fator_nota = NOTE_DURATIONS_BASE.get(nota_code, 1.0)
    ms = ms_seminima * fator_nota
    if fermata: ms *= FERMATA_FACTOR
    return max(50, int(ms))

# ===================== 3. JANELA DE CONFIGURAÇÃO =====================

class ConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurações Gerais")
        self.resize(500, 550)
        self.parent_ref = parent
        layout = QVBoxLayout(self); tabs = QTabWidget()
        
        tab_selecao = QWidget(); l_selecao = QVBoxLayout(tab_selecao)
        lbl_msg = QLabel("Selecione o número do hino para carregar:"); lbl_msg.setStyleSheet("font-size: 14px; font-weight: bold;")
        l_selecao.addWidget(lbl_msg)
        h_sel = QHBoxLayout()
        self.spin_hino = QSpinBox(); self.spin_hino.setRange(1, 1000); self.spin_hino.setStyleSheet("font-size: 16px; padding: 5px;")
        if self.parent_ref and self.parent_ref.hino_atual > 0: self.spin_hino.setValue(self.parent_ref.hino_atual)
        else: self.spin_hino.setValue(1)
        btn_carregar = QPushButton("CARREGAR HINO"); btn_carregar.setStyleSheet(f"background-color: {COR_INICIAR}; color: white; font-weight: bold; padding: 10px;")
        btn_carregar.clicked.connect(self.acao_carregar_hino)
        h_sel.addWidget(self.spin_hino); h_sel.addWidget(btn_carregar); l_selecao.addLayout(h_sel); l_selecao.addStretch()
        tabs.addTab(tab_selecao, "Seleção")
        
        tab_colors = QWidget(); l_colors = QVBoxLayout(tab_colors)
        color_keys = [('cor_fundo_texto', 'Fundo da Tela'), ('cor_texto_normal', 'Texto Normal'), ('cor_destaque_karaoke', 'Destaque (Karaokê)'), ('cor_nota_normal', 'Notas Musicais'), ('cor_barra_navegacao', 'Barra de Ferramentas')]
        for key, label in color_keys:
            h = QHBoxLayout(); h.addWidget(QLabel(label))
            btn = QPushButton(); btn.setFixedSize(60, 30); cor_atual = config_manager.get(key)
            btn.setStyleSheet(f"background-color: {cor_atual}; border: 1px solid gray;")
            btn.clicked.connect(lambda _, k=key, b=btn: self.pick_color(k, b))
            h.addWidget(btn); l_colors.addLayout(h)
        l_colors.addStretch(); tabs.addTab(tab_colors, "Cores")
        
        tab_params = QWidget(); l_params = QVBoxLayout(tab_params)
        self.inputs = {}
        params = [
            ('start_delay', 'Delay Inicial (s):', int, 0, 10),
            ('strofe_delay', 'Intervalo Estrofes (s):', int, 0, 20),
            ('time_rc', 'Respiração Curta [rc] (ms):', int, 0, 5000),
            ('time_pc', 'Pausa Curta [pc] (ms):', int, 0, 5000),
            ('time_rl', 'Respiração Longa [rl] (ms):', int, 0, 10000),
            ('time_pl', 'Pausa Longa [pl] (ms):', int, 0, 10000),
            ('bpm_step', 'Passo do BPM (+/-):', int, 1, 20),
            ('fermata_factor', 'Fator Fermata (x):', float, 1.0, 4.0),
            ('min_zoom', 'Zoom Mínimo (pt):', int, 8, 40),
            ('max_zoom', 'Zoom Máximo (pt):', int, 50, 300),
            ('editor_width', 'Largura Editor (px):', int, 400, 3000),
            ('editor_height', 'Altura Editor (px):', int, 300, 2000)
        ]
        for key, label, tipo, vmin, vmax in params:
            h = QHBoxLayout(); h.addWidget(QLabel(label))
            if tipo == int: inp = QSpinBox()
            else: inp = QDoubleSpinBox(); inp.setSingleStep(0.1)
            inp.setRange(vmin, vmax); val = config_manager.get(key, tipo); inp.setValue(val)
            h.addWidget(inp); l_params.addLayout(h); self.inputs[key] = inp
        l_params.addStretch(); tabs.addTab(tab_params, "Avançado")
        layout.addWidget(tabs)
        btn_save = QPushButton("Salvar Configurações e Fechar"); btn_save.setStyleSheet(f"background-color: {COR_BARRA_PADRAO}; color: white; font-weight: bold; padding: 8px;")
        btn_save.clicked.connect(self.salvar_tudo); layout.addWidget(btn_save)

    def acao_carregar_hino(self):
        if self.parent_ref:
            num = self.spin_hino.value()
            self.parent_ref.carregar_hino(num)
            self.accept()

    def pick_color(self, key, btn):
        c = QColorDialog.getColor(QColor(config_manager.get(key)), self)
        if c.isValid():
            hex_c = c.name(); config_manager.set(key, hex_c); btn.setStyleSheet(f"background-color: {hex_c}; border: 1px solid white;")

    def salvar_tudo(self):
        for key, inp in self.inputs.items(): config_manager.set(key, inp.value())
        if self.parent_ref: self.parent_ref.recarregar_configs()
        self.accept()

# ===================== 4. WIDGETS DO EDITOR =====================

class TextBlockEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_zoom = 18; self.lines_widgets = [] 
        self.layout = QVBoxLayout(self); self.layout.setContentsMargins(0,0,0,0); self.layout.setSpacing(0)
        toolbar = QFrame(); toolbar.setStyleSheet("background-color: #444; border-bottom: 1px solid gray;")
        tb_layout = QHBoxLayout(toolbar); tb_layout.setContentsMargins(5,2,5,2)
        lbl = QLabel("Texto (Letra):"); lbl.setStyleSheet("color: white; font-weight: bold;"); tb_layout.addWidget(lbl)
        btn_minus = QPushButton("-"); btn_minus.setFixedWidth(30); btn_minus.clicked.connect(lambda: self.change_zoom(-2)); tb_layout.addWidget(btn_minus)
        btn_plus = QPushButton("+"); btn_plus.setFixedWidth(30); btn_plus.clicked.connect(lambda: self.change_zoom(2)); tb_layout.addWidget(btn_plus)
        tb_layout.addStretch(1); self.layout.addWidget(toolbar)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.content_widget = QWidget(); self.scroll_layout = QVBoxLayout(self.content_widget); self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.content_widget); self.layout.addWidget(self.scroll)

    def populate(self, linhas_texto):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0); 
            if item.widget(): item.widget().deleteLater()
        self.lines_widgets = []; self.content_widget.setStyleSheet("background-color: #222;")
        for i, texto in enumerate(linhas_texto):
            row = QFrame(); row.setStyleSheet("border-bottom: 1px solid #333;")
            rl = QHBoxLayout(row); rl.setContentsMargins(5,5,5,5)
            
            # CORREÇÃO: Cor amarela para contraste no fundo azul
            lbl = QLabel(f"L{i+1}:"); lbl.setStyleSheet("color: yellow; font-weight: bold;")
            lbl.setFixedWidth(30); rl.addWidget(lbl)
            
            # CORREÇÃO: Fundo escuro e letra branca
            edt = QLineEdit(texto); edt.setStyleSheet("color: white; background-color: #222; border: 1px solid #555; padding: 4px;")
            self.lines_widgets.append(edt); rl.addWidget(edt); self.scroll_layout.addWidget(row)
        self.scroll_layout.addStretch(1); self.apply_zoom()

    def change_zoom(self, d): self.current_zoom = max(10, min(60, self.current_zoom + d)); self.apply_zoom()
    def apply_zoom(self):
        font = QFont("Arial", self.current_zoom)
        for edt in self.lines_widgets: edt.setFont(font)
    def get_text_lines(self): return [edt.text() for edt in self.lines_widgets]

class NotesEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_zoom = 12; self.layout = QVBoxLayout(self); self.layout.setContentsMargins(0,0,0,0); self.layout.setSpacing(0)
        toolbar = QFrame(); toolbar.setStyleSheet("background-color: #333; border-bottom: 1px solid gray;")
        tb_layout = QHBoxLayout(toolbar); tb_layout.setContentsMargins(5,2,5,2)
        lbl = QLabel("Ritmo/Notas:"); lbl.setStyleSheet("color: white; font-weight: bold;"); tb_layout.addWidget(lbl)
        btn_minus = QPushButton("-"); btn_minus.setFixedWidth(30); btn_minus.clicked.connect(lambda: self.change_zoom(-2)); tb_layout.addWidget(btn_minus)
        btn_plus = QPushButton("+"); btn_plus.setFixedWidth(30); btn_plus.clicked.connect(lambda: self.change_zoom(2)); tb_layout.addWidget(btn_plus)
        tb_layout.addStretch(1); self.layout.addWidget(toolbar)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.content_widget = QWidget(); self.scroll_layout = QVBoxLayout(self.content_widget); self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.content_widget); self.layout.addWidget(self.scroll); self.comboboxes = [] 

    def populate(self, estrofe_data, app):
        colors = getattr(app, 'colors', {'cor_fundo_texto': 'black', 'cor_texto_normal': 'white'})
        self.populate_from_data(estrofe_data, colors)

    def populate_from_data(self, estrofe_data, app_colors):
        linhas = estrofe_data.get('linhas', [])
        texto_linhas = [l.get('texto_silabado', '') for l in linhas]
        notas_linhas = [l.get('notas_codes', []) for l in linhas]
        self.build_ui(texto_linhas, notas_linhas, app_colors)

    def build_ui(self, texto_linhas, notas_linhas, app_colors):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0); 
            if item.widget(): item.widget().deleteLater()
        self.comboboxes = []; bg = app_colors.get('cor_fundo_texto', 'black'); fg = app_colors.get('cor_texto_normal', 'white')
        self.content_widget.setStyleSheet(f"background-color: {bg};")
        codigos_ordenados = ["rc", "pc", "rl", "pl"] + [c for c in NOTE_CODES if c not in ["rc", "pc", "rl", "pl"]]
        for i, linha_txt in enumerate(texto_linhas):
            row_frame = QFrame(); row_frame.setStyleSheet("border-bottom: 1px solid #555;")
            row_layout = QHBoxLayout(row_frame); row_layout.setContentsMargins(0, 5, 0, 5); row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
            
            # CORREÇÃO: Label Amarela
            row_layout.addWidget(QLabel(f"L{i+1}:", styleSheet="color: yellow; font-weight: bold;"))
            
            sils = _get_syllable_tokens(linha_txt); notas = notas_linhas[i] if i < len(notas_linhas) else []
            for j, sil in enumerate(sils):
                cod = notas[j] if j < len(notas) else "sm"
                group = QFrame(); g_layout = QVBoxLayout(group); g_layout.setContentsMargins(2,0,2,0); g_layout.setSpacing(2)
                lbl = QLabel(sil); lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); lbl.setFont(QFont("Arial", 11, QFont.Weight.Bold)); lbl.setStyleSheet(f"color: {fg};")
                g_layout.addWidget(lbl)
                cb = QComboBox(); cb.addItems(codigos_ordenados); cb.setCurrentText(cod); cb.setFixedWidth(80)
                
                # --- CORREÇÃO CSS PARA O COMBOBOX FICAR VISÍVEL ---
                cb.setStyleSheet("""
                    QComboBox { background-color: #000080; color: white; border: 1px solid white; padding: 2px; }
                    QComboBox QAbstractItemView {
                        background-color: #000080;
                        color: white;
                        selection-background-color: #4169E1;
                        selection-color: white;
                    }
                """)
                # --------------------------------------------------
                
                g_layout.addWidget(cb); self.comboboxes.append((cb, i, j)); row_layout.addWidget(group)
            row_layout.addStretch(1); self.scroll_layout.addWidget(row_frame)
        self.scroll_layout.addStretch(1); self.apply_zoom()

    def change_zoom(self, delta): self.current_zoom = max(8, min(40, self.current_zoom + delta)); self.apply_zoom()
    def apply_zoom(self):
        font_combo = QFont("Courier New", max(8, self.current_zoom - 2)); width_combo = int(60 + (self.current_zoom * 2.5))
        for cb, _, _ in self.comboboxes: cb.setFont(font_combo); cb.setFixedWidth(width_combo)

class EditorDialog(QDialog):
    def __init__(self, hino_num, estrofe_idx, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Editor - Hino {hino_num}")
        w = config_manager.get('editor_width', int); h = config_manager.get('editor_height', int); self.resize(w, h)
        self.hino_num = hino_num; self.estrofe_idx = estrofe_idx; self.hino_data = ler_arquivo_hino(hino_num)
        self.app_colors = {}; 
        if parent: self.app_colors = parent.colors
        else: self.app_colors = {'cor_fundo_texto': 'black', 'cor_texto_normal': 'white'}
        layout_main = QVBoxLayout(self)
        nav_layout = QHBoxLayout(); nav_layout.setContentsMargins(0, 0, 0, 10)
        self.btn_prev = QPushButton("<< Estrofe Anterior"); self.btn_prev.setShortcut("Ctrl+Left"); self.btn_prev.clicked.connect(lambda: self.navegar(-1))
        self.lbl_titulo_estrofe = QLabel("Estrofe ..."); self.lbl_titulo_estrofe.setAlignment(Qt.AlignmentFlag.AlignCenter); self.lbl_titulo_estrofe.setStyleSheet("font-size: 18px; font-weight: bold; color: yellow;")
        self.btn_next = QPushButton("Próxima Estrofe >>"); self.btn_next.setShortcut("Ctrl+Right"); self.btn_next.clicked.connect(lambda: self.navegar(1))
        nav_layout.addWidget(self.btn_prev); nav_layout.addWidget(self.lbl_titulo_estrofe); nav_layout.addWidget(self.btn_next); layout_main.addLayout(nav_layout)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.text_editor = TextBlockEditor(); splitter.addWidget(self.text_editor)
        self.notes_editor = NotesEditor(); splitter.addWidget(self.notes_editor)
        layout_main.addWidget(splitter); splitter.setSizes([w//3, (w//3)*2])
        
        h_tools = QHBoxLayout()
        btn_sync = QPushButton("Sincronizar Texto -> Notas"); btn_sync.setToolTip("Recria as caixas de notas baseada no texto da esquerda"); btn_sync.setStyleSheet("background-color: #008B8B; color: white; font-weight: bold; padding: 6px;"); btn_sync.clicked.connect(self.sincronizar_editores)
        h_tools.addWidget(btn_sync)
        
        self.btn_replicar = QPushButton("Replicar Ritmo para TODAS Estrofes"); self.btn_replicar.setToolTip("Copia as notas desta estrofe para todas as outras do mesmo tipo")
        self.btn_replicar.setStyleSheet("background-color: #FF8C00; color: white; font-weight: bold; padding: 6px;")
        self.btn_replicar.clicked.connect(self.replicar_ritmo_para_todos)
        h_tools.addWidget(self.btn_replicar)
        layout_main.addLayout(h_tools)

        btn_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("Fechar sem Salvar Arquivo"); self.btn_cancel.clicked.connect(self.reject)
        self.btn_save = QPushButton("SALVAR TUDO NO ARQUIVO"); self.btn_save.setStyleSheet(f"background-color: {COR_INICIAR}; color: white; font-weight: bold; padding: 10px;"); self.btn_save.clicked.connect(self.salvar_em_disco)
        btn_layout.addWidget(self.btn_cancel); btn_layout.addWidget(self.btn_save); layout_main.addLayout(btn_layout)
        self.popular_interface()

    def popular_interface(self):
        if not self.hino_data: return
        total_estrofes = len(self.hino_data.get('estrofes', []))
        self.btn_prev.setEnabled(self.estrofe_idx > 0); self.btn_next.setEnabled(self.estrofe_idx < total_estrofes - 1)
        try: 
            estrofe = self.hino_data['estrofes'][self.estrofe_idx]
            tipo = estrofe.get('tipo', 'Estrofe'); num = estrofe.get('numero', '')
            if str(num) == '0': num = ""
            self.lbl_titulo_estrofe.setText(f"{tipo} {num} ({self.estrofe_idx + 1} de {total_estrofes})")
        except IndexError: return
        linhas_texto = [l.get('texto_silabado', '') for l in estrofe.get('linhas', [])]
        self.text_editor.populate(linhas_texto); self.notes_editor.populate_from_data(estrofe, self.app_colors)

    def guardar_dados_atuais(self):
        linhas_novas = self.text_editor.get_text_lines()
        notas_map = {}
        for cb, l_idx, _ in self.notes_editor.comboboxes:
            if l_idx not in notas_map: notas_map[l_idx] = []
            notas_map[l_idx].append(cb.currentText())
        nova_estrofe = self.hino_data['estrofes'][self.estrofe_idx]
        nova_estrofe['linhas'] = []
        for i, txt_linha in enumerate(linhas_novas):
            txt_linha = txt_linha.strip()
            if not txt_linha: continue
            sils = _get_syllable_tokens(txt_linha)
            cods = notas_map.get(i, ["sm"]*len(sils))
            if len(cods) < len(sils): cods += ["sm"] * (len(sils) - len(cods))
            cods = cods[:len(sils)]
            nova_estrofe['linhas'].append({"texto_silabado": txt_linha, "notas_codes": cods})
        self.hino_data['estrofes'][self.estrofe_idx] = nova_estrofe

    def navegar(self, direcao):
        self.guardar_dados_atuais()
        novo_idx = self.estrofe_idx + direcao
        if 0 <= novo_idx < len(self.hino_data['estrofes']):
            self.estrofe_idx = novo_idx; self.popular_interface()

    def sincronizar_editores(self):
        novas_linhas_texto = self.text_editor.get_text_lines()
        notas_map = {}
        for cb, l_idx, s_idx in self.notes_editor.comboboxes:
            if l_idx not in notas_map: notas_map[l_idx] = []
            notas_map[l_idx].append(cb.currentText())
        notas_para_ui = []
        for i, _ in enumerate(novas_linhas_texto): notas_para_ui.append(notas_map.get(i, []))
        self.notes_editor.build_ui(novas_linhas_texto, notas_para_ui, self.app_colors)
    
    def replicar_ritmo_para_todos(self):
        self.guardar_dados_atuais()
        source_idx = self.estrofe_idx
        source_estrofe = self.hino_data['estrofes'][source_idx]
        source_tipo = source_estrofe.get('tipo', 'Estrofe')
        source_linhas = source_estrofe.get('linhas', [])
        padrao_ritmico = [l.get('notas_codes', []) for l in source_linhas]
        count = 0
        for i, estrofe in enumerate(self.hino_data['estrofes']):
            if i == source_idx: continue
            if estrofe.get('tipo', 'Estrofe') == source_tipo:
                target_linhas = estrofe.get('linhas', [])
                if len(target_linhas) == len(padrao_ritmico):
                    for j, linha in enumerate(target_linhas):
                        linha['notas_codes'] = list(padrao_ritmico[j])
                    count += 1
        QMessageBox.information(self, "Sucesso", f"Ritmo replicado para outras {count} estrofes do tipo '{source_tipo}'.")

    def salvar_em_disco(self):
        self.guardar_dados_atuais()
        try:
            path = os.path.join(HINOS_FOLDER_PATH, f"hino_{self.hino_num:03d}.json")
            with open(path, 'w', encoding='utf-8') as f: json.dump(self.hino_data, f, indent=2, ensure_ascii=False)
            self.accept()
        except Exception as e: print(f"Erro salvar: {e}")

# ===================== 5. PLAYER =====================

class KaraokePlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hinário Digital - Player")
        self.setGeometry(100, 100, 1024, 768)
        self.fmt_norm = QTextCharFormat(); self.fmt_dest = QTextCharFormat()
        self.max_hinos = 0; self.hino_data = None; self.hino_atual = 0; self.bpm = BPM_INICIAL
        self.estrofe_idx = 0; self.pos_atual = 0; self.compasso = "4/4"; self.unidade_bpm = "sm"
        self.note_durations = []; self.indices = []; self.syllables = []; self.estrofes_info = []; self.estrofes_texto = []; self.notas_estrofes = []
        self.tempo_inicio_nota = 0; self.duracao_nota_orig = 0
        self.indice_coro = -1; self.proxima_eh_coro = False
        
        # Estado do botão de hifens
        self.mostrar_hifens = True 

        self.timer_play = QTimer(self); self.timer_play.timeout.connect(self.play_step)
        self.timer_wait = QTimer(self); self.timer_wait.timeout.connect(self.step_wait)
        self.wait_sec = 0
        self.timer_zoom = QTimer(self); self.timer_zoom.setSingleShot(True)
        self.timer_zoom.timeout.connect(lambda: self.aplicar_zoom(True))

        self.recarregar_configs(); self.setup_ui(); self.max_hinos = carregar_dados_json(); self.mostrar_tela_inicial()

    def mostrar_tela_inicial(self):
        self.hino_atual = 0; self.lbl_title.setText("BEM-VINDO"); self.lbl_info.setText("")
        msg = """<div style='text-align: center; margin-top: 50px;'><h1 style='color: #FFD700; font-size: 50px;'>SELECIONE O HINO DESEJADO</h1><p style='color: white; font-size: 24px;'>Utilize o botão <b>CFG</b> ou as setas de navegação.</p></div>"""
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
        layout = QVBoxLayout(central); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        tb = QFrame(); tb_l = QHBoxLayout(tb); tb_l.setContentsMargins(5,5,5,5)
        tb_l.addWidget(QPushButton("<<", clicked=lambda: self.carregar_hino(self.hino_atual-1)))
        tb_l.addWidget(QPushButton(">>", clicked=lambda: self.carregar_hino(self.hino_atual+1)))
        self.lbl_bpm = QLabel(f"BPM: {self.bpm}"); self.lbl_bpm.setStyleSheet("color: white; font-weight: bold;")
        tb_l.addWidget(self.lbl_bpm)
        tb_l.addWidget(QPushButton("-", clicked=lambda: self.change_bpm(-self.bpm_step)))
        tb_l.addWidget(QPushButton("+", clicked=lambda: self.change_bpm(self.bpm_step)))
        tb_l.addWidget(QLabel(" Est:", styleSheet="color: white;"))
        self.ent_est = QLineEdit("1"); self.ent_est.setFixedWidth(40); self.ent_est.returnPressed.connect(self.manual_estrofe)
        tb_l.addWidget(QPushButton("<", clicked=lambda: self.nav_estrofe(-1), fixedWidth=30))
        tb_l.addWidget(self.ent_est)
        tb_l.addWidget(QPushButton(">", clicked=lambda: self.nav_estrofe(1), fixedWidth=30))
        
        self.btn_hifen = QPushButton("A-B"); self.btn_hifen.setCheckable(True); self.btn_hifen.setChecked(True)
        self.btn_hifen.setToolTip("Mostrar/Ocultar separação silábica"); self.btn_hifen.setStyleSheet(f"background-color: {COR_AUTO_SCALE}; color: white; font-weight: bold;")
        self.btn_hifen.clicked.connect(self.toggle_hifen); tb_l.addWidget(self.btn_hifen)

        btn_start = QPushButton("INICIAR", clicked=self.iniciar_karaoke_com_delay); btn_start.setStyleSheet(f"background:{COR_INICIAR}; color:white; font-weight:bold;"); tb_l.addWidget(btn_start)
        btn_stop = QPushButton("PARAR", clicked=self.stop_karaoke); btn_stop.setStyleSheet(f"background:{COR_PERIGO}; color:white; font-weight:bold;"); tb_l.addWidget(btn_stop)
        btn_zoom = QPushButton("AUTO ZOOM", clicked=lambda: self.aplicar_zoom(True)); btn_zoom.setStyleSheet(f"background:{COR_AUTO_SCALE}; color:white;"); tb_l.addWidget(btn_zoom)
        btn_edit = QPushButton("EDITAR", clicked=self.abrir_editor); btn_edit.setStyleSheet(f"background:{COR_EDICAO}; color:white; font-weight:bold;"); tb_l.addWidget(btn_edit)
        btn_cfg = QPushButton("CFG", clicked=self.abrir_tela_configuracao); btn_cfg.setStyleSheet(f"background:{COR_BARRA_PADRAO}; color:white;"); tb_l.addWidget(btn_cfg)
        self.tb_frame = tb; layout.addWidget(tb)
        self.lbl_title = QLabel("..."); self.lbl_title.setFont(QFont("Arial", 36, QFont.Weight.Bold)); self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(self.lbl_title)
        self.lbl_info = QLabel(""); self.lbl_info.setFont(QFont("Arial", 20)); self.lbl_info.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(self.lbl_info)
        self.texto = QTextEdit(); self.texto.setReadOnly(True); self.texto.setFrameShape(QFrame.Shape.NoFrame); self.texto.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); self.texto.setStyleSheet("padding: 20px;"); layout.addWidget(self.texto)
        self.apply_style()

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
            tokens = _get_syllable_tokens(txt); notes = line.get('notas_codes', [])
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

    def iniciar_karaoke_com_delay(self):
        if self.hino_atual == 0: return
        self.stop_karaoke()
        if self.indice_coro != -1 and self.estrofe_idx != self.indice_coro: self.proxima_eh_coro = True
        else: self.proxima_eh_coro = False
        if self.start_delay > 0:
            self.wait_sec = self.start_delay; self.lbl_info.setText(f"Iniciando em {self.wait_sec}..."); self.timer_wait.start(1000)
        else: self.start_karaoke()

    def start_karaoke(self): self.stop_karaoke(); self.pos_atual = 0; self.tempo_inicio_nota = 0; self.play_step()

    def stop_karaoke(self):
        self.timer_play.stop(); self.timer_wait.stop()
        if self.hino_atual > 0:
            try:
                if hasattr(self, 'fmt_norm') and self.fmt_norm is not None:
                    cur = QTextCursor(self.texto.document()); cur.select(QTextCursor.Document); cur.setCharFormat(self.fmt_norm); cur.clearSelection(); self.texto.setTextCursor(cur)
            except Exception as e: print(f"Aviso ao parar: {e}")
            if self.hino_data and self.estrofes_info:
                if 0 <= self.estrofe_idx < len(self.estrofes_info): self.lbl_info.setText(self.estrofes_info[self.estrofe_idx])

    def play_step(self):
        if self.pos_atual >= len(self.indices): self.timer_play.stop(); self.step_wait_for_next(); return
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
        self.pos_atual += 1; self.timer_play.start(ms)

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

    def abrir_editor(self):
        if not self.hino_data: return
        self.stop_karaoke(); dlg = EditorDialog(self.hino_atual, self.estrofe_idx, self)
        if dlg.exec(): self.carregar_hino(self.hino_atual, force_reload=True); self.load_estrofe(self.estrofe_idx)

    def nav_estrofe(self, d):
        if self.hino_atual == 0: return
        self.load_estrofe(self.estrofe_idx + d)

    # --- MANUAL ESTROFE CORRIGIDO ---
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
        if self.hino_data:
             est = self.hino_data['estrofes'][self.estrofe_idx]; new_durs = []
             for line in est.get('linhas', []):
                 sils = _get_syllable_tokens(line.get('texto_silabado','')); notes = line.get('notas_codes', [])
                 if len(notes) < len(sils): notes += ["sm"]*(len(sils)-len(notes))
                 durs = [calcular_duracao_ms(n, self.bpm, self.unidade_bpm) for n in notes[:len(sils)]]; new_durs.extend(durs)
             self.note_durations = new_durs

    def abrir_tela_configuracao(self): dlg = ConfigDialog(self); dlg.exec()

if __name__ == "__main__":
    app = QApplication(sys.argv); app.setStyle("Fusion"); w = KaraokePlayer(); w.show(); sys.exit(app.exec())