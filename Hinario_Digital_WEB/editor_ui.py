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

        # Estilo visual robusto
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

        # --- ABA 1: Seleção ---
        tab_selecao = QWidget()
        l_selecao = QVBoxLayout(tab_selecao)

        lbl_msg = QLabel("Selecione o número do hino para carregar:")
        lbl_msg.setStyleSheet("font-size: 14px; font-weight: bold;")
        l_selecao.addWidget(lbl_msg)

        h_sel = QHBoxLayout()
        self.spin_hino = QSpinBox()
        self.spin_hino.setRange(1, 1000)
        self.spin_hino.setStyleSheet("font-size: 16px; padding: 5px;")

        if self.parent_ref and hasattr(self.parent_ref, 'hino_atual') and self.parent_ref.hino_atual > 0:
            self.spin_hino.setValue(self.parent_ref.hino_atual)
        else:
            self.spin_hino.setValue(1)

        btn_carregar = QPushButton("CARREGAR HINO")
        btn_carregar.setStyleSheet(f"background-color: {COR_INICIAR}; color: white; font-weight: bold; padding: 10px;")
        btn_carregar.clicked.connect(self.acao_carregar_hino)

        h_sel.addWidget(self.spin_hino)
        h_sel.addWidget(btn_carregar)
        l_selecao.addLayout(h_sel)
        l_selecao.addStretch()
        tabs.addTab(tab_selecao, "Seleção")

        # --- ABA 2: Cores ---
        tab_colors = QWidget()
        l_colors = QVBoxLayout(tab_colors)

        color_keys = [
            ('cor_fundo_texto', 'Fundo da Tela'), 
            ('cor_texto_normal', 'Texto Normal'), 
            ('cor_destaque_karaoke', 'Destaque (Karaokê)'), 
            ('cor_nota_normal', 'Notas Musicais'), 
            ('cor_barra_navegacao', 'Barra de Ferramentas')
        ]

        for key, label in color_keys:
            h = QHBoxLayout()
            h.addWidget(QLabel(label))
            btn = QPushButton()
            btn.setFixedSize(60, 30)
            cor_atual = config_manager.get(key)
            btn.setStyleSheet(f"background-color: {cor_atual}; border: 1px solid gray;")
            btn.clicked.connect(lambda _, k=key, b=btn: self.pick_color(k, b))
            h.addWidget(btn)
            l_colors.addLayout(h)

        l_colors.addStretch()
        tabs.addTab(tab_colors, "Cores")

        # --- ABA 3: Avançado ---
        tab_params = QWidget()
        l_params = QVBoxLayout(tab_params)
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
            h = QHBoxLayout()
            h.addWidget(QLabel(label))
            if tipo == int: 
                inp = QSpinBox()
            else: 
                inp = QDoubleSpinBox()
                inp.setSingleStep(0.1)

            inp.setRange(vmin, vmax)
            val = config_manager.get(key, tipo)
            inp.setValue(val)
            h.addWidget(inp)
            l_params.addLayout(h)
            self.inputs[key] = inp

        l_params.addStretch()
        tabs.addTab(tab_params, "Avançado")

        layout.addWidget(tabs)

        btn_save = QPushButton("Salvar Configurações e Fechar")
        btn_save.setStyleSheet(f"background-color: {COR_BARRA_PADRAO}; color: white; font-weight: bold; padding: 8px;")
        btn_save.clicked.connect(self.salvar_tudo)
        layout.addWidget(btn_save)

    def acao_carregar_hino(self):
        if self.parent_ref:
            num = self.spin_hino.value()
            self.parent_ref.carregar_hino(num)
            self.accept()

    def pick_color(self, key, btn):
        c = QColorDialog.getColor(QColor(config_manager.get(key)), self)
        if c.isValid():
            hex_c = c.name()
            config_manager.set(key, hex_c)
            btn.setStyleSheet(f"background-color: {hex_c}; border: 1px solid white;")

    def salvar_tudo(self):
        for key, inp in self.inputs.items():
            config_manager.set(key, inp.value())

        if self.parent_ref:
            self.parent_ref.recarregar_configs()
        self.accept()


class TextBlockEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_zoom = 18
        self.lines_widgets = [] 

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        self.layout.setSpacing(0)

        # Toolbar
        toolbar = QFrame()
        toolbar.setStyleSheet("background-color: #444; border-bottom: 1px solid gray;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(5,2,5,2)

        lbl = QLabel("Texto (Letra):")
        lbl.setStyleSheet("color: white; font-weight: bold;")
        tb_layout.addWidget(lbl)

        btn_minus = QPushButton("-")
        btn_minus.setFixedWidth(30)
        btn_minus.clicked.connect(lambda: self.change_zoom(-2))
        tb_layout.addWidget(btn_minus)

        btn_plus = QPushButton("+")
        btn_plus.setFixedWidth(30)
        btn_plus.clicked.connect(lambda: self.change_zoom(2))
        tb_layout.addWidget(btn_plus)

        tb_layout.addStretch(1)
        self.layout.addWidget(toolbar)

        # Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.content_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.content_widget)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll.setWidget(self.content_widget)
        self.layout.addWidget(self.scroll)

    def populate(self, linhas_texto):
        # Limpa widgets anteriores
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        self.lines_widgets = []
        self.content_widget.setStyleSheet("background-color: #222;")

        for i, texto in enumerate(linhas_texto):
            row = QFrame()
            row.setStyleSheet("border-bottom: 1px solid #333;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(5,5,5,5)

            lbl = QLabel(f"L{i+1}:")
            lbl.setStyleSheet("color: yellow; background-color: #444; font-weight: bold; padding: 2px; border-radius: 4px;")
            lbl.setFixedWidth(40)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rl.addWidget(lbl)

            edit = QLineEdit(texto)
            edit.setStyleSheet("background-color: #111; color: white; border: 1px solid #555; padding: 4px;")
            font = QFont("Arial", self.current_zoom)
            edit.setFont(font)
            rl.addWidget(edit)

            self.lines_widgets.append(edit)
            self.scroll_layout.addWidget(row)

        self.scroll_layout.addStretch(1)

    def get_text_lines(self):
        return [w.text() for w in self.lines_widgets]

    def change_zoom(self, delta):
        self.current_zoom = max(8, min(40, self.current_zoom + delta))
        font = QFont("Arial", self.current_zoom)
        for w in self.lines_widgets:
            w.setFont(font)


class NotesEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.comboboxes = [] 

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        self.layout.setSpacing(0)

        # Toolbar
        toolbar = QFrame()
        toolbar.setStyleSheet("background-color: #444; border-bottom: 1px solid gray;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(5,2,5,2)

        lbl = QLabel("Notas Musicais (Sílabas):")
        lbl.setStyleSheet("color: white; font-weight: bold;")
        tb_layout.addWidget(lbl)
        tb_layout.addStretch(1)
        self.layout.addWidget(toolbar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.content_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.content_widget)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll.setWidget(self.content_widget)
        self.layout.addWidget(self.scroll)

    def populate(self, estrofe_data, parent_dialog):
        linhas = estrofe_data.get('linhas', [])
        txts = [l.get('texto_silabado', '') for l in linhas]
        cods = [l.get('notas_codes', []) for l in linhas]
        self.build_ui(txts, cods, parent_dialog.app_colors)

    def populate_from_data(self, estrofe_data, app_colors):
        linhas = estrofe_data.get('linhas', [])
        txts = [l.get('texto_silabado', '') for l in linhas]
        cods = [l.get('notas_codes', []) for l in linhas]
        self.build_ui(txts, cods, app_colors)

    def build_ui(self, linhas_texto, linhas_notas, colors):
        # Limpa UI anterior
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        self.comboboxes = []
        self.content_widget.setStyleSheet("background-color: #222;")

        for i, txt_linha in enumerate(linhas_texto):
            if not txt_linha.strip(): continue

            row_frame = QFrame()
            row_frame.setStyleSheet("border-bottom: 1px solid #444; margin-bottom: 5px;")
            row_layout = QVBoxLayout(row_frame)
            row_layout.setContentsMargins(5,5,5,5)

            # Cabeçalho da Linha
            lbl_info = QLabel(f"Linha {i+1}: \"{txt_linha}\"")
            lbl_info.setStyleSheet(f"color: {colors.get('cor_texto_normal','white')}; font-weight: bold; font-size: 14px;")
            row_layout.addWidget(lbl_info)

            # Área de Flow para as sílabas
            flow_widget = QWidget()
            flow_layout = QHBoxLayout(flow_widget)
            flow_layout.setContentsMargins(0,0,0,0)
            flow_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

            silabas = get_syllable_tokens(txt_linha)
            notas_atuais = linhas_notas[i] if i < len(linhas_notas) else []

            # Garante tamanho igual
            if len(notas_atuais) < len(silabas):
                notas_atuais += ["SEMINIMA"] * (len(silabas) - len(notas_atuais))

            for j, silaba in enumerate(silabas):
                box = QFrame()
                box.setStyleSheet("background-color: #333; border-radius: 4px; border: 1px solid #555;")
                vbox = QVBoxLayout(box)
                vbox.setContentsMargins(2,2,2,2)

                lbl_sil = QLabel(silaba)
                lbl_sil.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl_sil.setStyleSheet("color: cyan; font-weight: bold; font-size: 14px;")
                vbox.addWidget(lbl_sil)

                cb = QComboBox()
                cb.addItems(NOTE_CODES) # Usa a lista completa do logic.py

                # Seleciona a nota atual (agora usando o nome completo)
                nota_code = notas_atuais[j]
                idx = cb.findText(nota_code)
                if idx >= 0: cb.setCurrentIndex(idx)
                else:
                    # Fallback se não achar
                    idx_sm = cb.findText("SEMINIMA")
                    if idx_sm >= 0: cb.setCurrentIndex(idx_sm)

                # Estilização do ComboBox
                cb.setStyleSheet("""
                    QComboBox { background-color: #111; color: white; border: 1px solid #666; min-width: 120px; }
                    QComboBox QAbstractItemView { background-color: #222; color: white; selection-background-color: #555; }
                """)

                vbox.addWidget(cb)
                flow_layout.addWidget(box)

                # Armazena referência para salvar depois
                self.comboboxes.append((cb, i, j))

            row_layout.addWidget(flow_widget)
            self.scroll_layout.addWidget(row_frame)

        self.scroll_layout.addStretch(1)


class EditorDialog(QDialog):
    def __init__(self, hino_num, estrofe_idx, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Editor - Hino {hino_num}")

        # Dimensões configuráveis
        w = config_manager.get('editor_width', int)
        h = config_manager.get('editor_height', int)
        self.resize(w, h)

        self.setStyleSheet("background-color: #222; color: white;")

        self.hino_num = hino_num
        self.estrofe_idx = estrofe_idx
        self.hino_data = ler_arquivo_hino(hino_num)

        # Cores
        self.app_colors = {}
        if parent: self.app_colors = parent.colors
        else: self.app_colors = {'cor_fundo_texto': 'black', 'cor_texto_normal': 'white'}

        # Se não existir dados, cria estrutura vazia
        if not self.hino_data:
            self.hino_data = {"numero": hino_num, "titulo": "", "estrofes": []}

        layout_main = QVBoxLayout(self)

        # --- Navegação Superior ---
        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(0, 0, 0, 10)

        self.btn_prev = QPushButton("<< Estrofe Anterior")
        self.btn_prev.setShortcut("Ctrl+Left")
        self.btn_prev.clicked.connect(lambda: self.navegar(-1))
        self.btn_prev.setStyleSheet("background-color: #444; color: white; padding: 5px;")

        self.lbl_titulo_estrofe = QLabel("Estrofe ...")
        self.lbl_titulo_estrofe.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_titulo_estrofe.setStyleSheet("font-size: 18px; font-weight: bold; color: yellow;")

        self.btn_next = QPushButton("Próxima Estrofe >>")
        self.btn_next.setShortcut("Ctrl+Right")
        self.btn_next.clicked.connect(lambda: self.navegar(1))
        self.btn_next.setStyleSheet("background-color: #444; color: white; padding: 5px;")

        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.lbl_titulo_estrofe)
        nav_layout.addWidget(self.btn_next)
        layout_main.addLayout(nav_layout)

        # --- Área Central (Splitter) ---
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.text_editor = TextBlockEditor()
        splitter.addWidget(self.text_editor)

        self.notes_editor = NotesEditor()
        splitter.addWidget(self.notes_editor)

        layout_main.addWidget(splitter)
        splitter.setSizes([w//3, (w//3)*2])

        # --- Botão de Sincronia ---
        btn_sync = QPushButton(">>> ATUALIZAR / SINCRONIZAR NOTAS >>>")
        btn_sync.setToolTip("Clique aqui após editar o texto para gerar as caixas de notas")
        btn_sync.setStyleSheet("background-color: #008B8B; color: white; font-weight: bold; padding: 6px;")
        btn_sync.clicked.connect(self.sincronizar_editores)
        layout_main.addWidget(btn_sync)

        # --- Ferramentas Extras ---
        h_tools = QHBoxLayout()
        self.btn_replicar = QPushButton("Replicar Ritmo para TODAS Estrofes")
        self.btn_replicar.setToolTip("Copia as notas desta estrofe para todas as outras do mesmo tipo")
        self.btn_replicar.setStyleSheet("background-color: #FF8C00; color: white; font-weight: bold; padding: 6px;")
        self.btn_replicar.clicked.connect(self.replicar_ritmo_para_todos)
        h_tools.addWidget(self.btn_replicar)
        layout_main.addLayout(h_tools)

        # --- Botões Inferiores ---
        btn_layout = QHBoxLayout()

        self.btn_cancel = QPushButton("Fechar sem Salvar Arquivo")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_cancel.setStyleSheet("background-color: #555; color: white; padding: 8px;")

        self.btn_save = QPushButton("SALVAR TUDO NO ARQUIVO")
        self.btn_save.setStyleSheet(f"background-color: {COR_INICIAR}; color: white; font-weight: bold; padding: 10px;")
        self.btn_save.clicked.connect(self.salvar_em_disco)

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        layout_main.addLayout(btn_layout)

        self.popular_interface()

    def popular_interface(self):
        if not self.hino_data: return

        # Garante que a estrofe existe na lista
        if 'estrofes' not in self.hino_data: self.hino_data['estrofes'] = []

        # Se índice fora, cria nova
        if self.estrofe_idx >= len(self.hino_data['estrofes']):
             self.hino_data['estrofes'].append({"numero": self.estrofe_idx+1, "linhas": []})

        total_estrofes = len(self.hino_data['estrofes'])

        # Atualiza botões nav
        self.btn_prev.setEnabled(self.estrofe_idx > 0)
        # Permite ir para próxima (criando nova se necessário)
        self.btn_next.setEnabled(True) 

        try: 
            estrofe = self.hino_data['estrofes'][self.estrofe_idx]
            tipo = estrofe.get('tipo', 'Estrofe')
            num = estrofe.get('numero', '')
            if str(num) == '0': num = ""
            self.lbl_titulo_estrofe.setText(f"{tipo} {num} ({self.estrofe_idx + 1} de {total_estrofes})")
        except IndexError:
            return

        # Extrai dados já processados pelo logic.py (que já converteu o JSON verbose para listas planas)
        linhas_texto = [l.get('texto_silabado', '') for l in estrofe.get('linhas', [])]

        self.text_editor.populate(linhas_texto)
        self.notes_editor.populate_from_data(estrofe, self.app_colors)

    def sincronizar_editores(self):
        """
        Pega o texto editado à esquerda e reconstrói as caixas de notas à direita.
        Tenta preservar as notas que já estavam selecionadas.
        """
        novas_linhas_texto = self.text_editor.get_text_lines()

        # Captura o estado atual dos combos
        notas_map = {}
        for cb, l_idx, s_idx in self.notes_editor.comboboxes:
            if l_idx not in notas_map: notas_map[l_idx] = []
            notas_map[l_idx].append(cb.currentText())

        notas_para_ui = []
        for i, txt in enumerate(novas_linhas_texto):
            sils = get_syllable_tokens(txt)
            old_notes = notas_map.get(i, [])

            # Ajusta tamanho
            new_notes = old_notes[:len(sils)]
            if len(new_notes) < len(sils):
                new_notes += ["SEMINIMA"] * (len(sils) - len(new_notes))

            notas_para_ui.append(new_notes)

        self.notes_editor.build_ui(novas_linhas_texto, notas_para_ui, self.app_colors)

    def guardar_dados_atuais(self):
        """
        Reconstrói a estrutura JSON detalhada a partir da UI.
        """
        linhas_novas = self.text_editor.get_text_lines()

        notas_map = {}
        for cb, l_idx, _ in self.notes_editor.comboboxes:
            if l_idx not in notas_map: notas_map[l_idx] = []
            notas_map[l_idx].append(cb.currentText())

        nova_estrofe = self.hino_data['estrofes'][self.estrofe_idx]
        nova_estrofe['linhas'] = [] # Limpa para reconstruir

        for i, txt_linha in enumerate(linhas_novas):
            txt_linha = txt_linha.strip()
            if not txt_linha: continue

            sils = get_syllable_tokens(txt_linha)
            cods = notas_map.get(i, ["SEMINIMA"]*len(sils))

            # Garante consistência
            if len(cods) < len(sils): cods += ["SEMINIMA"] * (len(sils) - len(cods))
            cods = cods[:len(sils)]

            # --- AQUI ESTÁ A LÓGICA DO JSON VERBOSE ---
            lista_silabas_json = []
            for j, silaba_txt in enumerate(sils):
                nota_nome = cods[j] # Já é o nome completo (ex: "SEMINIMA PONTUADA")

                # Lógica para tratar pausas/respirações onde texto é null
                texto_final = silaba_txt
                if "RESPIRACAO" in nota_nome or "PAUSA" in nota_nome:
                    texto_final = None 

                lista_silabas_json.append({
                    "texto": texto_final,
                    "nota": nota_nome
                })

            # Adiciona a linha no formato detalhado
            nova_estrofe['linhas'].append({
                "silabas": lista_silabas_json,
                # Mantemos também os campos auxiliares para facilitar leitura interna se necessário
                "texto_silabado": txt_linha, 
                "notas_codes": cods
            })

        self.hino_data['estrofes'][self.estrofe_idx] = nova_estrofe

    def navegar(self, direcao):
        self.guardar_dados_atuais()
        novo_idx = self.estrofe_idx + direcao

        # Permite avançar infinitamente para criar novas estrofes
        if novo_idx >= 0:
            self.estrofe_idx = novo_idx
            self.popular_interface()

    def replicar_ritmo_para_todos(self):
        self.guardar_dados_atuais()

        source_idx = self.estrofe_idx
        source_estrofe = self.hino_data['estrofes'][source_idx]
        source_tipo = source_estrofe.get('tipo', 'Estrofe')

        # Pega o padrão rítmico (lista de listas de notas)
        source_linhas = source_estrofe.get('linhas', [])
        padrao_ritmico = [l.get('notas_codes', []) for l in source_linhas]

        if not padrao_ritmico:
            QMessageBox.warning(self, "Aviso", "Estrofe atual não tem linhas para copiar.")
            return

        count = 0
        for i, estrofe in enumerate(self.hino_data['estrofes']):
            if i == source_idx: continue

            # Só replica se for do mesmo tipo (ex: não copia de Estrofe para Coro)
            if estrofe.get('tipo', 'Estrofe') == source_tipo:
                target_linhas = estrofe.get('linhas', [])

                # Só replica se tiver o mesmo número de linhas
                if len(target_linhas) == len(padrao_ritmico):
                    for j, linha in enumerate(target_linhas):
                        # Aplica as notas da origem na linha de destino
                        # Nota: isso pode dar conflito se o número de sílabas for diferente
                        # O ideal seria ajustar, mas aqui forçamos o ritmo
                        linha['notas_codes'] = list(padrao_ritmico[j])

                        # Precisamos reconstruir o objeto 'silabas' também para o JSON ficar consistente
                        # Isso é complexo pois depende do texto da estrofe destino.
                        # Simplificação: Apenas atualizamos 'notas_codes'. 
                        # O usuário terá que abrir a estrofe e salvar para regenerar o JSON detalhado corretamente.
                    count += 1

        QMessageBox.information(self, "Sucesso", f"Ritmo replicado para outras {count} estrofes do tipo '{source_tipo}'.\nNota: Verifique as outras estrofes para garantir que o texto encaixou no ritmo.")

    def salvar_em_disco(self):
        self.guardar_dados_atuais()
        try:
            # Salva como 1.json (apenas número) conforme preferência
            path = os.path.join(HINOS_FOLDER_PATH, f"{self.hino_num}.json")

            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.hino_data, f, indent=2, ensure_ascii=False)

            QMessageBox.information(self, "Sucesso", "Hino salvo com sucesso!")
            self.accept()
        except Exception as e:
            print(f"Erro salvar: {e}")
            QMessageBox.critical(self, "Erro", f"Falha ao salvar: {str(e)}")
