import json
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QLineEdit, QScrollArea, QFrame, QComboBox, QDialog, 
    QTabWidget, QSpinBox, QDoubleSpinBox, QSplitter, QMessageBox,
    QColorDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

from config import config_manager, COR_INICIAR, COR_BARRA_PADRAO, HINOS_FOLDER_PATH
from logic import NOTE_CODES, get_syllable_tokens, ler_arquivo_hino

class ConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurações Gerais")
        self.resize(500, 600)
        self.parent_ref = parent
        
        # Força estilo para garantir legibilidade na Configuração também
        self.setStyleSheet("""
            QDialog { background-color: #333; color: white; }
            QLabel { color: white; }
            QTabWidget::pane { border: 1px solid #444; }
            QTabBar::tab { background: #222; color: #AAA; padding: 8px; }
            QTabBar::tab:selected { background: #444; color: white; font-weight: bold; }
            QLineEdit, QSpinBox, QDoubleSpinBox { background-color: #222; color: white; border: 1px solid #555; padding: 4px; }
        """)
        
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        
        # ABA 1: Seleção
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
        
        # ABA 2: Cores
        tab_colors = QWidget(); l_colors = QVBoxLayout(tab_colors)
        color_keys = [('cor_fundo_texto', 'Fundo da Tela'), ('cor_texto_normal', 'Texto Normal'), ('cor_destaque_karaoke', 'Destaque (Karaokê)'), ('cor_nota_normal', 'Notas Musicais'), ('cor_barra_navegacao', 'Barra de Ferramentas')]
        for key, label in color_keys:
            h = QHBoxLayout(); h.addWidget(QLabel(label))
            btn = QPushButton(); btn.setFixedSize(60, 30); cor_atual = config_manager.get(key)
            btn.setStyleSheet(f"background-color: {cor_atual}; border: 1px solid gray;")
            btn.clicked.connect(lambda _, k=key, b=btn: self.pick_color(k, b))
            h.addWidget(btn); l_colors.addLayout(h)
        l_colors.addStretch(); tabs.addTab(tab_colors, "Cores")
        
        # ABA 3: Avançado
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
            
            # CORREÇÃO: Label amarela com fundo escuro para garantir contraste
            lbl = QLabel(f"L{i+1}:"); lbl.setStyleSheet("color: yellow; background-color: #444; font-weight: bold; padding: 2px; border-radius: 4px;")
            lbl.setFixedWidth(40); lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); rl.addWidget(lbl)
            
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
        self.comboboxes = []
        
        bg = app_colors.get('cor_fundo_texto', 'black')
        fg = app_colors.get('cor_texto_normal', 'white')
        self.content_widget.setStyleSheet(f"background-color: {bg};")
        
        codigos_ordenados = ["rc", "pc", "rl", "pl"] + [c for c in NOTE_CODES if c not in ["rc", "pc", "rl", "pl"]]
        
        for i, linha_txt in enumerate(texto_linhas):
            row_frame = QFrame(); row_frame.setStyleSheet("border-bottom: 1px solid #555;")
            row_layout = QHBoxLayout(row_frame); row_layout.setContentsMargins(0, 5, 0, 5); row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
            
            # CORREÇÃO: Label amarela com fundo escuro para garantir contraste
            lbl_line = QLabel(f"L{i+1}:"); lbl_line.setStyleSheet("color: yellow; background-color: #444; font-weight: bold; padding: 2px; border-radius: 4px;")
            lbl_line.setFixedWidth(40); lbl_line.setAlignment(Qt.AlignmentFlag.AlignCenter); row_layout.addWidget(lbl_line)
            
            sils = get_syllable_tokens(linha_txt); notas = notas_linhas[i] if i < len(notas_linhas) else []
            for j, sil in enumerate(sils):
                cod = notas[j] if j < len(notas) else "sm"
                group = QFrame(); g_layout = QVBoxLayout(group); g_layout.setContentsMargins(2,0,2,0); g_layout.setSpacing(2)
                lbl = QLabel(sil); lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); lbl.setFont(QFont("Arial", 11, QFont.Weight.Bold)); lbl.setStyleSheet(f"color: {fg};")
                g_layout.addWidget(lbl)
                cb = QComboBox(); cb.addItems(codigos_ordenados); cb.setCurrentText(cod); cb.setFixedWidth(80)
                cb.setStyleSheet("""
                    QComboBox { background-color: #000080; color: white; border: 1px solid white; padding: 2px; }
                    QComboBox QAbstractItemView {
                        background-color: #000080;
                        color: white;
                        selection-background-color: #4169E1;
                        selection-color: white;
                    }
                """)
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
        
        # CORREÇÃO: Força o fundo do diálogo para escuro (#222) para garantir que labels amarelas sejam visíveis
        self.setStyleSheet("background-color: #222; color: white;")
        
        self.hino_num = hino_num; self.estrofe_idx = estrofe_idx; self.hino_data = ler_arquivo_hino(hino_num)
        self.app_colors = {}; 
        if parent: self.app_colors = parent.colors
        else: self.app_colors = {'cor_fundo_texto': 'black', 'cor_texto_normal': 'white'}
        layout_main = QVBoxLayout(self)
        nav_layout = QHBoxLayout(); nav_layout.setContentsMargins(0, 0, 0, 10)
        self.btn_prev = QPushButton("<< Estrofe Anterior"); self.btn_prev.setShortcut("Ctrl+Left"); self.btn_prev.clicked.connect(lambda: self.navegar(-1))
        self.btn_prev.setStyleSheet("background-color: #444; color: white; padding: 5px;")
        
        self.lbl_titulo_estrofe = QLabel("Estrofe ..."); self.lbl_titulo_estrofe.setAlignment(Qt.AlignmentFlag.AlignCenter); self.lbl_titulo_estrofe.setStyleSheet("font-size: 18px; font-weight: bold; color: yellow;")
        
        self.btn_next = QPushButton("Próxima Estrofe >>"); self.btn_next.setShortcut("Ctrl+Right"); self.btn_next.clicked.connect(lambda: self.navegar(1))
        self.btn_next.setStyleSheet("background-color: #444; color: white; padding: 5px;")
        
        nav_layout.addWidget(self.btn_prev); nav_layout.addWidget(self.lbl_titulo_estrofe); nav_layout.addWidget(self.btn_next); layout_main.addLayout(nav_layout)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.text_editor = TextBlockEditor(); splitter.addWidget(self.text_editor)
        self.notes_editor = NotesEditor(); splitter.addWidget(self.notes_editor)
        layout_main.addWidget(splitter); splitter.setSizes([w//3, (w//3)*2])
        btn_sync = QPushButton(">>> ATUALIZAR / SINCRONIZAR NOTAS >>>"); btn_sync.setToolTip("Clique aqui após editar o texto para gerar as caixas de notas"); btn_sync.setStyleSheet("background-color: #008B8B; color: white; font-weight: bold; padding: 6px;"); btn_sync.clicked.connect(self.sincronizar_editores)
        layout_main.addWidget(btn_sync)
        
        h_tools = QHBoxLayout()
        self.btn_replicar = QPushButton("Replicar Ritmo para TODAS Estrofes"); self.btn_replicar.setToolTip("Copia as notas desta estrofe para todas as outras do mesmo tipo")
        self.btn_replicar.setStyleSheet("background-color: #FF8C00; color: white; font-weight: bold; padding: 6px;")
        self.btn_replicar.clicked.connect(self.replicar_ritmo_para_todos)
        h_tools.addWidget(self.btn_replicar)
        layout_main.addLayout(h_tools)

        btn_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("Fechar sem Salvar Arquivo"); self.btn_cancel.clicked.connect(self.reject)
        self.btn_cancel.setStyleSheet("background-color: #555; color: white; padding: 8px;")
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
            sils = get_syllable_tokens(txt_linha)
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