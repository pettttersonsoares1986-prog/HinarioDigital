import tkinter as tk
from tkinter import ttk, colorchooser
import os
import re
import json
import sqlite3
import sys
import traceback

# ===================== 1. CONFIGURAÇÃO E CONSTANTES =====================

# Caminho para a pasta dos hinos (AJUSTE CONFORME O SEU AMBIENTE!)
HINOS_FOLDER_PATH = os.path.normpath(r"C:\Users\psoares\pyNestle\Private\Hinario_Digital\textos_corrigidos")
CONFIG_DB_FILE = 'config.db'

# Padrões e Passos
BPM_INICIAL = 62
BPM_STEP = 5 
FERMATA_FACTOR = 1.5 
TAMANHO_PADRAO = 80 # Tamanho de fonte padrão
ESPACAMENTO_PADRAO = 20
MIN_ZOOM = 25
MAX_ZOOM = 130
STEP_ESPACAMENTO = 5

# Mapeamento de notas para fator de duração em relação à Semínima (1.0)
NOTE_DURATIONS_BASE = {
    "sm": 1.0,  # Semínima (referência de 1 tempo no BPM)
    "m": 2.0,   # Mínima (2 tempos)
    "c": 0.5,   # Colcheia (meio tempo)
    "sc": 0.25, # Semicolcheia (um quarto de tempo)
    "sb": 4.0,  # Semibreve (4 tempos)
    "cp": 0.75, # Colcheia pontuada (3/4 de tempo)
    "rl": 0.0,  # Pausa longa (tempo 0 para pular)
    "rc": 0.0,  # Pausa colcheia (tempo 0 para pular)
}

# NOVO: Lista completa de códigos de nota disponíveis para o Combobox
NOTE_CODES = list(NOTE_DURATIONS_BASE.keys()) + [
    f"{k}_fermata" for k in NOTE_DURATIONS_BASE.keys() if k not in ["rl", "rc"]
]


# Cores Padrão (Persistentes)
COR_NORMAL_PADRAO = "#000080"
COR_DESTAQUE_PADRAO = "#FFFF00"
COR_FUNDO_TEXTO_PADRAO = "black" 
COR_TEXTO_NORMAL_PADRAO = "white" 

# NOVO: Cores para os códigos das figuras musicais
COR_NOTA_NORMAL_PADRAO = "#00BFFF" 
COR_NOTA_DESTAQUE_PADRAO = "#32CD32" 

# Cores Padrão (Botões/Não Persistentes)
COR_INICIAR = "#006400" 
COR_PERIGO = "#8B0000" 
COR_FUNDO_CONFIG = "#222222" 
COR_AUTO_SCALE = "#0050C0" 
COR_EDICAO = "#FF4500" 

# ===================== 2. PERSISTÊNCIA (SQLite) =====================

class ConfigManager:
    """Gerencia a persistência das configurações no SQLite."""
    
    def iniciar_banco_config(self):
        """Cria a tabela de configuração se ela não existir."""
        try:
            conn = sqlite3.connect(CONFIG_DB_FILE)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS configuracoes (
                    chave TEXT PRIMARY KEY,
                    valor TEXT
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"ERRO ao iniciar o banco de dados de configuração: {e}")

    def carregar_config(self, chave, valor_padrao):
        """Carrega uma configuração do banco de dados ou retorna o valor padrão."""
        try:
            conn = sqlite3.connect(CONFIG_DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT valor FROM configuracoes WHERE chave = ?", (chave,))
            resultado = cursor.fetchone()
            conn.close()
            
            if resultado:
                valor_str = resultado[0]
                # Tenta converter para o tipo correto (int/float/str)
                try:
                    if '.' in valor_str:
                        return float(valor_str)
                    return int(valor_str)
                except ValueError:
                    return valor_str
            
        except Exception as e:
            # Em caso de erro (ex: DB corrompido), retorna o valor padrão
            pass
        return valor_padrao

    def salvar_config(self, chave, valor):
        """Salva uma configuração no banco de dados."""
        try:
            conn = sqlite3.connect(CONFIG_DB_FILE)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES (?, ?)
            """, (chave, str(valor)))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"ERRO ao salvar '{chave}': {e}")

# Inicializa o gerenciador de configuração
config_manager = ConfigManager()
config_manager.iniciar_banco_config()

# ===================== 3. VARIÁVEIS DE ESTADO GLOBAIS =====================

# Variáveis persistentes carregadas do DB
TAMANHO_FONTE_BASE = config_manager.carregar_config('tamanho_fonte', TAMANHO_PADRAO)
ESPACAMENTO_BASE = config_manager.carregar_config('espacamento_texto', ESPACAMENTO_PADRAO)
COR_NORMAL = config_manager.carregar_config('cor_barra_navegacao', COR_NORMAL_PADRAO)
COR_DESTAQUE = config_manager.carregar_config('cor_destaque_karaoke', COR_DESTAQUE_PADRAO)
COR_FUNDO_TEXTO = config_manager.carregar_config('cor_fundo_texto', COR_FUNDO_TEXTO_PADRAO)
COR_TEXTO_NORMAL = config_manager.carregar_config('cor_texto_normal', COR_TEXTO_NORMAL_PADRAO)
COR_NOTA_NORMAL = config_manager.carregar_config('cor_nota_normal', COR_NOTA_NORMAL_PADRAO)
COR_NOTA_DESTAQUE = config_manager.carregar_config('cor_nota_destaque', COR_NOTA_DESTAQUE_PADRAO)

# Variáveis de estado de execução
BPM = config_manager.carregar_config('BPM_padrao', BPM_INICIAL)
MAX_HINOS = 0
hino_data_atual = None
hino_atual = 0
timer = None
estrofe_atual_idx = 0
estrofes_texto = []
estrofes_info = [] 
palavras = [] 
palavra_indices = [] 
nota_indices = [] 
pos_atual = 0 
modo_edicao_ativo = False # VARIÁVEL DE ESTADO DE EDIÇÃO
notas_estrofes = []
duracoes_atuais_karaoke = []

# Referências de Widgets Tkinter
app = None
lbl_titulo = None
lbl_estrofe_info = None 
texto = None
texto_notas = None # Widget tk.Text (modo normal/karaokê)
content_frame = None # Frame pai que contém 'texto' e 'texto_notas' (ou 'edit_notes_frame')
edit_notes_frame = None # NOVO: Frame que conterá o editor de Comboboxes (dentro de um ScrollFrame)
comboboxes_notas_edicao = [] # NOVO: Lista de referências (StringVar, silaba, index_linha, index_nota)
bpm_display_label = None 
estrofe_entry = None
barra = None
btn_editar = None 
scroll_frame_parent = None # Referência ao frame pai que contém o Canvas e Scrollbar do editor

# ===================== 4. FUNÇÕES DE LÓGICA DE DADOS =====================

def _get_syllable_tokens(text_line):
    """Tokeniza a linha em sílabas/palavras para o karaokê."""
    return [m.group(0) for m in re.finditer(r"(\w+[\w'’-]*)", text_line, re.UNICODE)]

def ler_arquivo_hino(numero_hino):
    """Tenta ler o arquivo JSON do hino pelo número."""
    filenames_to_try = [f"hino_{numero_hino:03d}.json", f"hino_{numero_hino}.json"]
    for filename in filenames_to_try:
        file_path = os.path.join(HINOS_FOLDER_PATH, filename)
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Erro ao ler/parsear {file_path}: {e}")
                pass
    return None

def carregar_dados_json():
    """Escaneia a pasta para descobrir o número máximo de hinos."""
    global MAX_HINOS
    if not os.path.exists(HINOS_FOLDER_PATH):
        try: 
            os.makedirs(HINOS_FOLDER_PATH)
            return 0
        except OSError as e:
            print(f"Erro ao criar pasta de hinos: {e}")
            return 0
    try:
        max_num = 0
        hino_pattern = re.compile(r"^hino_(\d+)(_completo|_editado)?\.json$", re.IGNORECASE)
        for filename in os.listdir(HINOS_FOLDER_PATH):
            match = hino_pattern.match(filename)
            if match:
                hino_num = int(match.group(1))
                if hino_num > max_num: max_num = hino_num
        MAX_HINOS = max_num
        return MAX_HINOS
    except Exception as e:
        print(f"Erro ao escanear pasta de hinos: {e}")
        return 0

def calcular_duracao_ms(nota_code):
    """Calcula a duração da nota em milissegundos com base no BPM."""
    global BPM
    if BPM <= 0: return 500 
    
    quarter_note_ms = 60000 / BPM
    is_fermata = "_fermata" in nota_code.lower()
    base_note = nota_code.split('_')[0]
    fator = NOTE_DURATIONS_BASE.get(base_note.lower(), 1.0) 
    if is_fermata:
        fator *= FERMATA_FACTOR
    return int(quarter_note_ms * fator)

# ===================== 5. FUNÇÕES DE ATUALIZAÇÃO DA UI (VIEWS) =====================

def update_titulo(text, color):
    if lbl_titulo:
        lbl_titulo.config(text=text, fg=color)

def update_estrofe_label(text, color):
    if lbl_estrofe_info:
        lbl_estrofe_info.config(text=text, fg=color)

def update_bpm_display():
    if bpm_display_label:
        bpm_display_label.config(text=f"BPM: {BPM}") 

def update_estrofe_entry(estrofe_num):
    if estrofe_entry:
        estrofe_entry.delete(0, tk.END)
        estrofe_entry.insert(0, str(estrofe_num))

def update_text_content(text):
    """Atualiza o conteúdo principal do Text widget."""
    if texto:
        estado_original = texto.cget("state")
        texto.config(state="normal")
        texto.delete("1.0", "end")
        texto.insert("end", text)
        app.update_idletasks()
        texto.yview_moveto(0)
        texto.config(state=estado_original)

def update_notas_content(text):
    """Atualiza o conteúdo do widget de notas (apenas em modo normal/karaokê)."""
    global texto_notas
    if texto_notas:
        estado_original = texto_notas.cget("state")
        texto_notas.config(state="normal")
        texto_notas.delete("1.0", "end")
        texto_notas.insert("end", text)
        texto_notas.config(state=estado_original)


def apply_destaque_tag(start_index_text, length_text, start_index_nota, length_nota):
    """Aplica a tag de destaque à sílaba atual E à sua nota (apenas em modo normal/karaokê)."""
    
    # 1. Destaque do Texto Principal
    if texto:
        start_index_str = f"1.0 + {start_index_text}c"
        texto.tag_remove("destaque", "1.0", "end")
        texto.tag_add("destaque", start_index_str, f"{start_index_str} + {length_text}c")

    # 2. Destaque das Notas Musicais
    if texto_notas:
        start_index_str_nota = f"1.0 + {start_index_nota}c"
        texto_notas.tag_remove("destaque_nota", "1.0", "end")
        texto_notas.tag_add("destaque_nota", start_index_str_nota, f"{start_index_str_nota} + {length_nota}c")


def remove_destaque():
    """Remove todas as tags de destaque do texto E das notas."""
    if texto: texto.tag_remove("destaque", "1.0", "end")
    if texto_notas: texto_notas.tag_remove("destaque_nota", "1.0", "end")


def aplicar_cores_config():
    """Aplica as cores globais a todos os widgets relevantes."""
    global COR_FUNDO_TEXTO, COR_TEXTO_NORMAL, COR_DESTAQUE, COR_NORMAL, COR_NOTA_NORMAL, COR_NOTA_DESTAQUE
    
    if app: app.configure(bg=COR_FUNDO_TEXTO)
    if lbl_titulo: lbl_titulo.config(bg=COR_FUNDO_TEXTO, fg=COR_DESTAQUE)
    if lbl_estrofe_info: lbl_estrofe_info.config(bg=COR_FUNDO_TEXTO, fg=COR_DESTAQUE) 
    
    if texto:
        texto.config(bg=COR_FUNDO_TEXTO, fg=COR_TEXTO_NORMAL)
    
    if texto_notas:
        texto_notas.config(bg=COR_FUNDO_TEXTO, fg=COR_NOTA_NORMAL)
        texto_notas.tag_config("destaque_nota", foreground=COR_NOTA_DESTAQUE, font=("Courier New", 18, "bold")) 

    # Aplica as cores na barra de navegação
    if barra:
        barra.config(bg=COR_NORMAL)
        for widget in barra.winfo_children():
            if isinstance(widget, tk.Frame):
                widget.config(bg=COR_NORMAL)
                for sub_widget in widget.winfo_children():
                    if isinstance(sub_widget, tk.Frame): 
                        sub_widget.config(bg=COR_NORMAL)
                    elif isinstance(sub_widget, tk.Label):
                        sub_widget.config(bg=COR_NORMAL)
                    if isinstance(sub_widget, tk.Button) and sub_widget.cget('bg') not in (COR_INICIAR, COR_PERIGO, COR_AUTO_SCALE, COR_EDICAO):
                        sub_widget.config(bg=COR_NORMAL)
                        
    aplicar_zoom_config() 

def aplicar_espacamento_config():
    """Aplica o espaçamento vertical global no Text widget."""
    global ESPACAMENTO_BASE
    if texto:
        espacamento = ESPACAMENTO_BASE
        novo_spacing2 = max(5, espacamento // 2)
        estado_original = texto.cget("state")
        texto.config(state="normal")
        texto.config(spacing1=espacamento, spacing2=novo_spacing2, spacing3=espacamento)
        texto.config(state=estado_original)
    
    if texto_notas:
        # Garante que o widget de notas tenha espaçamento zero
        texto_notas.config(spacing1=0, spacing2=0, spacing3=0)


def aplicar_zoom_config(forcar_ajuste=False):
    """Aplica o zoom lendo o valor base, ou recalcula e aplica se forçado (auto-sizing)."""
    global TAMANHO_FONTE_BASE
    
    if not texto: return
    
    if not estrofes_texto or estrofe_atual_idx >= len(estrofes_texto):
        # Aplica o zoom base mesmo em caso de erro/sem estrofe
        fonte_base_aplicada = TAMANHO_FONTE_BASE
        texto.config(font=("Arial", fonte_base_aplicada, "bold"))
        texto.tag_config("destaque", foreground=COR_DESTAQUE, font=("Arial", min(MAX_ZOOM, int(fonte_base_aplicada * 1.5)), "bold"))
        return
    
    # Lógica de auto-ajuste (mantida)
    if forcar_ajuste:
        texto_original_display = estrofes_texto[estrofe_atual_idx]
        estado_original = texto.cget("state")
        texto.config(state="normal")
        texto.delete("1.0", "end")
        texto.insert("end", texto_original_display)
        app.update_idletasks() 
        
        try:
            # Pega a altura do widget de notas ou o editor de comboboxes
            global scroll_frame_parent
            if scroll_frame_parent and scroll_frame_parent.winfo_ismapped():
                 # Se estiver no modo edição, pega a altura do Frame do Scrollbar
                altura_notas_editor = scroll_frame_parent.winfo_height()
            elif texto_notas and texto_notas.winfo_ismapped():
                altura_notas_editor = texto_notas.winfo_height()
            else:
                altura_notas_editor = 40 # Fallback 

        except tk.TclError:
            altura_notas_editor = 40 

        altura_disponivel_para_texto = app.winfo_height() - lbl_titulo.winfo_height() - lbl_estrofe_info.winfo_height() - barra.winfo_height() - altura_notas_editor - 80 
        
        tamanho_fonte_ajustado = MIN_ZOOM
        fonte_teste = MAX_ZOOM
        
        while fonte_teste >= MIN_ZOOM:
            texto.config(font=("Arial", fonte_teste, "bold")) 
            texto.update_idletasks()
            bbox = texto.bbox("end-1c")
            
            if bbox is not None and bbox[3] <= altura_disponivel_para_texto:
                tamanho_fonte_ajustado = fonte_teste
                break
            fonte_teste -= 4
        
        TAMANHO_FONTE_BASE = tamanho_fonte_ajustado
        config_manager.salvar_config('tamanho_fonte', TAMANHO_FONTE_BASE)
        texto.config(state=estado_original)
        exibir_estrofe_atual(estrofe_atual_idx)
        return
        
    # Lógica de Aplicação (Para ajustes manuais e iniciais)
    fonte_base_aplicada = TAMANHO_FONTE_BASE
    estado_original = texto.cget("state") 
    texto.config(state="normal")
    texto.config(font=("Arial", fonte_base_aplicada, "bold"))
    texto.config(fg=COR_TEXTO_NORMAL)
    
    tamanho_destaque = min(MAX_ZOOM, int(fonte_base_aplicada * 1.5))
    texto.tag_config("destaque", foreground=COR_DESTAQUE, font=("Arial", tamanho_destaque, "bold"))
    texto.config(state=estado_original)
    

# ===================== 6. FUNÇÕES DE FLUXO E CONTROLE =====================

def create_text_notes_widget():
    """Cria o widget tk.Text para exibição das notas (modo normal/karaokê)."""
    global texto_notas, edit_notes_frame, content_frame, scroll_frame_parent
    
    # 1. Destrói o editor de comboboxes se ele existir
    if scroll_frame_parent:
         scroll_frame_parent.destroy() 
         scroll_frame_parent = None
         edit_notes_frame = None
        
    # 2. Cria ou verifica o widget de texto de notas
    if texto_notas is None:
        texto_notas = tk.Text(
            content_frame, 
            bg=COR_FUNDO_TEXTO, fg=COR_NOTA_NORMAL,
            font=("Courier New", 18, "bold"), wrap="none", bd=0, 
            highlightthickness=0, state="disabled", padx=120, height=2, cursor="arrow"
        )
        texto_notas.pack(fill="x", pady=(0, 20)) 
    else:
        # Garante que ele está visível se foi destruído e recriado
        texto_notas.pack(fill="x", pady=(0, 20)) 
    
    aplicar_cores_config()
    aplicar_espacamento_config()

def carregar_editor_combobox():
    """NOVO: Cria e preenche o frame com as sílabas/palavras e os Comboboxes de notas para edição."""
    global edit_notes_frame, comboboxes_notas_edicao, texto_notas, estrofe_atual_idx, hino_data_atual, content_frame, scroll_frame_parent
    
    print(f"DEBUG: Tentando carregar o editor de Combobox para estrofe {estrofe_atual_idx + 1}")
    
    # 1. Destrói o widget de texto de notas (se existir)
    if texto_notas:
        texto_notas.pack_forget() # Remove do layout
        
    comboboxes_notas_edicao = []
    
    # 2. Cria o Frame para o editor de comboboxes (Com Scrollbar)
    # Criamos um Frame pai dentro do content_frame para o Canvas+Scrollbar
    if scroll_frame_parent is None:
        scroll_frame_parent = tk.Frame(content_frame, bg=COR_FUNDO_TEXTO)
        scroll_frame_parent.pack(fill="both", expand=True, padx=120, pady=(0, 20)) 
    else:
        scroll_frame_parent.pack(fill="both", expand=True, padx=120, pady=(0, 20)) 
        for widget in scroll_frame_parent.winfo_children(): # Limpa widgets internos
             widget.destroy()

    canvas = tk.Canvas(scroll_frame_parent, bg=COR_FUNDO_TEXTO, highlightthickness=0)
    canvas.pack(side="left", fill="both", expand=True)

    scrollbar = ttk.Scrollbar(scroll_frame_parent, orient="vertical", command=canvas.yview)
    scrollbar.pack(side="right", fill="y")
    
    canvas.configure(yscrollcommand=scrollbar.set)
    
    # Frame interno onde os comboboxes serão colocados
    edit_notes_frame = tk.Frame(canvas, bg=COR_FUNDO_TEXTO)
    
    # Bind para ajustar a região de scroll
    def on_frame_configure(event):
        # Ajusta a largura do Canvas Window para o Frame do Scrollbar (que tem o tamanho certo)
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfig(canvas_window, width=scroll_frame_parent.winfo_width() - scrollbar.winfo_width() - 2) # -2px margin
        
    edit_notes_frame.bind("<Configure>", on_frame_configure)
    
    # Adiciona o frame interno ao canvas
    canvas_window = canvas.create_window((0, 0), window=edit_notes_frame, anchor="nw", width=1)
    
    # Bind para ajustar a largura do Canvas Window quando o parent Frame muda de tamanho
    scroll_frame_parent.bind("<Configure>", on_frame_configure)


    # 3. Lógica para popular as linhas do editor
    if hino_data_atual and 0 <= estrofe_atual_idx < len(hino_data_atual['estrofes']):
        estrofe_data = hino_data_atual['estrofes'][estrofe_atual_idx]
        
        count_comboboxes = 0
        
        for i, linha in enumerate(estrofe_data['linhas']):
            line_frame = tk.Frame(edit_notes_frame, bg=COR_FUNDO_TEXTO, pady=5)
            line_frame.pack(fill="x", padx=10) # Padding interno para a linha
            
            # Label de Linha (Opcional, para indicar a linha)
            tk.Label(line_frame, text=f"L{i+1}: ", bg=COR_FUNDO_TEXTO, fg="gray", font=("Arial", 12)).pack(side="left")
            
            silabas = _get_syllable_tokens(linha.get('texto_silabado', ''))
            notas_codes = linha.get('notas_codes', [])
            
            if not silabas:
                continue

            for j, silaba in enumerate(silabas):
                nota_code = notas_codes[j] if j < len(notas_codes) else "sm"
                
                # 1. Label da Sílaba (Fixo)
                # Adiciona um pequeno padding à direita do label para separar da combobox
                tk.Label(line_frame, text=f" {silaba} ", bg=COR_FUNDO_TEXTO, fg=COR_TEXTO_NORMAL, font=("Arial", 16, "bold")).pack(side="left", padx=(0, 2))
                
                # 2. Combobox da Nota (Editável)
                var = tk.StringVar(value=nota_code)
                combo = ttk.Combobox(line_frame, textvariable=var, values=NOTE_CODES, width=10, state="readonly", font=("Courier New", 12))
                combo.pack(side="left", padx=(0, 10))
                
                comboboxes_notas_edicao.append((var, silaba, i, j)) 
                count_comboboxes += 1

        print(f"DEBUG: {count_comboboxes} Comboboxes criados com sucesso.")
        
    # 4. Ajusta a área de scroll (força o canvas a recalcular o tamanho)
    edit_notes_frame.update_idletasks()
    canvas.config(scrollregion=canvas.bbox("all"))


def alternar_modo_edicao():
    """Alterna entre o modo de visualização (karaokê) e o modo de edição."""
    global modo_edicao_ativo, btn_editar, hino_data_atual
    
    parar_karaoke() 
    if not hino_data_atual: return
    
    modo_edicao_ativo = not modo_edicao_ativo
    
    if modo_edicao_ativo:
        # === ENTRA NO MODO EDIÇÃO ===
        btn_editar.config(text="SALVAR E SAIR", bg=COR_EDICAO, fg="white")
        update_titulo("MODO EDIÇÃO ATIVO — Edite as sílabas e notas", COR_EDICAO)

        # 1. Carrega todas as estrofes para edição no Text principal (para texto/sílabas)
        exibir_estrofe_atual(estrofe_atual_idx, suppress_note_widget_creation=True)
        # Libera edição do texto principal
        texto.config(state="normal", bg="#111111", insertbackground="white")

        # 2. Cria e carrega o editor de comboboxes (apenas para as notas da estrofe atual)
        carregar_editor_combobox() 

    else:
        # === SAI DO MODO EDIÇÃO (SALVA AUTOMATICAMENTE) ===
        salvar_hino_editado()
        
        # Desabilita edição e restaura estilos padrões do texto principal
        texto.config(state="disabled", bg=COR_FUNDO_TEXTO) 
        
        btn_editar.config(text="EDITAR ✏️", bg=COR_NORMAL, fg="white")
        
        # 3. Recria o widget de texto de notas (substituindo o editor de comboboxes)
        create_text_notes_widget() 

        # 4. Restaura exibição normal (apenas a estrofe atual)
        exibir_estrofe_atual(estrofe_atual_idx)
        update_titulo(hino_data_atual.get('titulo', f"Hino {hino_atual}"), COR_DESTAQUE)

def salvar_hino_editado():
    """Salva as alterações feitas no modo edição, lendo o texto principal e os comboboxes."""
    global hino_data_atual, hino_atual, estrofe_atual_idx, comboboxes_notas_edicao
    if not hino_data_atual:
        return

    texto_editado = texto.get("1.0", "end-1c")
    blocos_texto = [b.strip() for b in texto_editado.split("\n\n") if b.strip()]
    
    novo_hino = {"titulo": hino_data_atual.get("titulo", f"Hino {hino_atual}"), "estrofes": []}

    # 1. Monta a nova lista de notas a partir dos Comboboxes (somente para a estrofe atual)
    novas_notas_por_linha_atual = {}
    for var, silaba, idx_linha, idx_nota in comboboxes_notas_edicao:
        if idx_linha not in novas_notas_por_linha_atual:
            novas_notas_por_linha_atual[idx_linha] = []
        novas_notas_por_linha_atual[idx_linha].append(var.get())
    
    # 2. Reconstroi o JSON
    for i, bloco_texto in enumerate(blocos_texto):
        linhas_texto = [l.strip() for l in bloco_texto.split("\n") if l.strip()]
        
        tipo_estrofe_original = hino_data_atual.get("estrofes", [{}])[i].get("tipo", "Estrofe") if i < len(hino_data_atual.get("estrofes", [])) else "Estrofe"
        estrofe = {"numero": i+1, "tipo": tipo_estrofe_original, "linhas": []}
        
        for j, linha in enumerate(linhas_texto):
            silabas_na_linha = _get_syllable_tokens(linha)
            
            if i == estrofe_atual_idx:
                 # Esta é a estrofe que estava sendo editada com comboboxes
                 notas_codes = novas_notas_por_linha_atual.get(j, [])
            else:
                 # Outras estrofes: tenta usar as notas do JSON original (se o texto não mudou)
                 try:
                     original_linha = hino_data_atual['estrofes'][i]['linhas'][j]
                     original_silabas = _get_syllable_tokens(original_linha.get('texto_silabado', ''))
                     if len(original_silabas) == len(silabas_na_linha):
                         notas_codes = original_linha.get('notas_codes', ["sm"] * len(silabas_na_linha))
                     else:
                         # Se o número de sílabas mudou no texto, as notas antigas são inválidas.
                         notas_codes = ["sm"] * len(silabas_na_linha)
                 except (IndexError, KeyError):
                     notas_codes = ["sm"] * len(silabas_na_linha)

            # Garante consistência (no caso de notas incompletas ou excessivas)
            if len(silabas_na_linha) != len(notas_codes):
                 if len(silabas_na_linha) > len(notas_codes):
                    notas_codes += ["sm"] * (len(silabas_na_linha) - len(notas_codes))
                 else:
                    notas_codes = notas_codes[:len(silabas_na_linha)]

            estrofe["linhas"].append({"texto_silabado": linha, "notas_codes": notas_codes})

        novo_hino["estrofes"].append(estrofe)
        
    # 3. Salva o novo JSON
    caminho = os.path.join(HINOS_FOLDER_PATH, f"hino_{hino_atual:03d}.json")
    try:
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(novo_hino, f, ensure_ascii=False, indent=2)
        print(f"Hino {hino_atual} salvo com sucesso em {caminho}!")
        hino_data_atual = novo_hino
        # Recarregar o hino para atualizar estrofes_texto e notas_estrofes
        carregar_dados_json()
        carregar_hino(hino_atual, force_reload=True)
    except Exception as e:
        print(f"Erro ao salvar hino: {e}")

def carregar_hino(numero_desejado, force_reload=False):
    """Carrega o hino, atualiza o estado e a UI."""
    global hino_atual, hino_data_atual, BPM, estrofe_atual_idx, estrofes_texto, notas_estrofes, estrofes_info
    
    # Se já está carregado e não é forçado, não recarrega
    if hino_atual == numero_desejado and hino_data_atual is not None and not force_reload:
        exibir_estrofe_atual(0) 
        return
        
    if MAX_HINOS == 0:
        update_titulo("ERRO: SEM HINOS NA PASTA", COR_PERIGO)
        return
        
    if numero_desejado > MAX_HINOS: numero_desejado = 1
    elif numero_desejado < 1: numero_desejado = MAX_HINOS
        
    hino = ler_arquivo_hino(numero_desejado)
    if hino is None:
        update_titulo(f"Hino {numero_desejado:03d} NÃO ENCONTRADO", COR_PERIGO)
        return
        
    # 1. Atualiza o estado
    hino_atual = numero_desejado
    hino_data_atual = hino
    BPM = config_manager.carregar_config('BPM_padrao', hino.get("BPM", BPM_INICIAL))
    estrofe_atual_idx = 0
    parar_karaoke()

    # 2. Prepara dados para a exibição
    estrofes_texto = []
    notas_estrofes = []
    estrofes_info = [] 
    for estrofe in hino.get("estrofes", []):
        
        tipo_raw = estrofe.get("tipo", "Estrofe") 
        numero = estrofe.get("numero", 0) 
        tipo_completo = f"{tipo_raw.capitalize()} {numero}" if numero > 0 else tipo_raw.capitalize()
        
        estrofes_info.append({"numero": numero, "tipo": tipo_raw, "label": tipo_completo})
        
        estrofe_linhas_texto = [] 
        estrofe_notas_totais = [] 
        for linha in estrofe.get("linhas", []):
            texto_silabado = linha.get("texto_silabado", "").strip()
            if not texto_silabado: continue
            estrofe_linhas_texto.append(texto_silabado)
            
            silabas = _get_syllable_tokens(texto_silabado)
            notas_codes = linha.get("notas_codes", ["sm"] * len(silabas))
            
            if len(notas_codes) != len(silabas):
                if len(notas_codes) < len(silabas): 
                    notas_codes += ["sm"] * (len(silabas) - len(notas_codes))
                else: 
                    notas_codes = notas_codes[:len(silabas)]
                
            estrofe_notas_totais.extend(notas_codes)
            
        estrofes_texto.append("\n".join(estrofe_linhas_texto))
        notas_estrofes.append(estrofe_notas_totais)

    # 3. Notifica a UI sobre as mudanças
    titulo_display = hino.get('titulo', f"Hino {numero_desejado}")
    update_titulo(titulo_display, COR_DESTAQUE)

    update_bpm_display()
    update_estrofe_entry(1)
    
    aplicar_zoom_config(forcar_ajuste=True) 
    aplicar_espacamento_config()
    exibir_estrofe_atual(estrofe_atual_idx)


def exibir_estrofe_atual(index=None, suppress_note_widget_creation=False):
    """
    Prepara e exibe o texto da estrofe atual no widget.
    O flag `suppress_note_widget_creation` é usado ao entrar no modo edição.
    """
    global estrofe_atual_idx, palavras, palavra_indices, nota_indices, pos_atual, notas_estrofes, duracoes_atuais_karaoke
    
    karaoke_estava_ativo = timer is not None
    parar_karaoke() 

    if index is not None: estrofe_atual_idx = index
        
    if not estrofes_texto or estrofe_atual_idx >= len(estrofes_texto):
        if hino_data_atual:
             update_titulo(f"FIM DE {hino_data_atual.get('titulo', str(hino_atual))}", "#00FF00") 
        else:
            update_titulo("FIM", "#00FF00")
        update_estrofe_label("", COR_DESTAQUE) 
        if texto_notas: update_notas_content("") 
        return
        
    # 2. Atualiza o label da estrofe/coro
    if estrofes_info and 0 <= estrofe_atual_idx < len(estrofes_info):
        update_estrofe_label(estrofes_info[estrofe_atual_idx]["label"], COR_DESTAQUE)
    else:
        update_estrofe_label(f"Estrofe {estrofe_atual_idx + 1}", COR_DESTAQUE)
        
    # 3. Atualiza o texto principal (Todas as estrofes no modo edição, apenas a atual no modo normal)
    if modo_edicao_ativo:
        texto_display = "\n\n".join(estrofes_texto)
    else:
        texto_display = estrofes_texto[estrofe_atual_idx]
    
    update_text_content(texto_display)

    # 4. Processamento de notas (APENAS se não estiver no modo edição, ou se o widget existir)
    if not modo_edicao_ativo and not suppress_note_widget_creation:
        
        if texto_notas is None:
            create_text_notes_widget() # Garante que o widget Text está lá

        texto_estrofe = estrofes_texto[estrofe_atual_idx]
        
        # 5. Recalcula os dados de karaokê (Mantido da versão anterior, corrigida)
        palavras = []
        palavra_indices = []
        nota_indices = [] 
        
        notas_codes_originais = notas_estrofes[estrofe_atual_idx]
        duracoes_atuais_karaoke = [calcular_duracao_ms(code) for code in notas_codes_originais]  
        
        posicao_caractere_texto = 0 
        posicao_caractere_nota = 0 
        palavra_index_count = 0
        
        texto_notas_display = "" 
        
        for match in re.finditer(r"(\w+[\w'’-]*)|([^\w\s])|(\s+)", texto_estrofe, re.UNICODE):
            token = match.group(0)
            
            if match.group(1) is not None: 
                palavras.append(token)
                
                if palavra_index_count < len(duracoes_atuais_karaoke):
                    palavra_indices.append((posicao_caractere_texto, len(token)))
                    
                    nota_code = notas_codes_originais[palavra_index_count]
                    nota_para_display = nota_code.ljust(len(token)) 
                    texto_notas_display += nota_para_display
                    
                    nota_indices.append((posicao_caractere_nota, len(nota_code))) 
                    posicao_caractere_nota += len(nota_para_display)
                    
                    palavra_index_count += 1
                else:
                    espacos_vazios = " " * len(token)
                    texto_notas_display += espacos_vazios
                    posicao_caractere_nota += len(espacos_vazios)
                    
            elif match.group(2) is not None or match.group(3) is not None: 
                if '\n' in token:
                    texto_notas_display += '\n'
                    posicao_caractere_nota += 1 
                else:
                    espacos = " " * len(token)
                    texto_notas_display += espacos
                    posicao_caractere_nota += len(espacos)
                
            posicao_caractere_texto += len(token)
            
        # 6. Atualiza o widget das notas
        update_notas_content(texto_notas_display)
            
        # 7. Restaura o estado do karaokê
        if karaoke_estava_ativo:
            pos_para_destacar = min(pos_atual, len(palavras))
            
            if pos_para_destacar > 0:
                start_index_text, length_text = palavra_indices[pos_para_destacar - 1]
                start_index_nota, length_nota = nota_indices[pos_para_destacar - 1]
                apply_destaque_tag(start_index_text, length_text, start_index_nota, length_nota)
                
            if pos_para_destacar < len(palavras):
                pos_atual = pos_para_destacar
                destacar_palavra()
            else:
                pos_atual = 0
                remove_destaque()
        else:
            pos_atual = 0

def destacar_palavra():
    """Função recursiva para aplicar o destaque da sílaba/palavra."""
    global timer, pos_atual, estrofe_atual_idx
    
    if modo_edicao_ativo:
        parar_karaoke()
        return
    
    if pos_atual >= len(palavras):
        estrofe_atual_idx += 1
        parar_karaoke()
        timer = app.after(800, lambda: exibir_estrofe_atual(estrofe_atual_idx)) 
        return
    
    delay_ms = duracoes_atuais_karaoke[pos_atual] if pos_atual < len(duracoes_atuais_karaoke) else calcular_duracao_ms("sm")
        
    if delay_ms == 0:
        pos_atual += 1
        destacar_palavra() 
        return
        
    start_index_text, length_text = palavra_indices[pos_atual]
    start_index_nota, length_nota = nota_indices[pos_atual]
    
    apply_destaque_tag(start_index_text, length_text, start_index_nota, length_nota)
    
    pos_atual += 1
    timer = app.after(delay_ms, destacar_palavra)


def mudar_para_estrofe_manual(event=None):
    """Carrega e exibe a estrofe digitada na Entry, sem iniciar o karaokê."""
    global estrofe_entry, estrofe_atual_idx
    
    if not hino_data_atual or modo_edicao_ativo: return
    
    try:
        estrofe_num = int(estrofe_entry.get().strip())
        target_index = estrofe_num - 1
        
        if 0 <= target_index < len(estrofes_texto):
            estrofe_atual_idx = target_index
            update_estrofe_entry(estrofe_atual_idx + 1)
            parar_karaoke() 
            exibir_estrofe_atual(estrofe_atual_idx) 
            
            titulo_display = hino_data_atual.get('titulo', str(hino_atual))
            update_titulo(titulo_display, COR_DESTAQUE)

        else:
            update_titulo(f"Estrofe {estrofe_num} não existe.", COR_PERIGO)
            update_estrofe_entry(estrofe_atual_idx + 1)
            app.after(1500, lambda: update_titulo(hino_data_atual.get('titulo', str(hino_atual)), COR_DESTAQUE))
            return
            
    except ValueError:
        update_titulo("ENTRADA DE ESTROFE INVÁLIDA", COR_PERIGO)
        app.after(1500, lambda: update_titulo(hino_data_atual.get('titulo', str(hino_atual)), COR_DESTAQUE))

def iniciar_karaoke_da_estrofe():
    """Inicia o karaokê a partir da estrofe selecionada na Entry."""
    
    mudar_para_estrofe_manual() 

    if not hino_data_atual or modo_edicao_ativo: return
    
    if estrofe_atual_idx < len(estrofes_texto):
        global pos_atual
        pos_atual = 0
        destacar_palavra()

def parar_karaoke():
    """Para o temporizador e remove o destaque."""
    global timer
    if timer:
        app.after_cancel(timer)
        timer = None
    remove_destaque()

def ajustar_bpm(delta=0):
    """Ajusta o BPM global e atualiza a UI."""
    global BPM
    if delta != 0:
        BPM = max(30, BPM + delta)
    
    config_manager.salvar_config('BPM_padrao', BPM)
        
    update_bpm_display()
    
    if hino_data_atual:
        exibir_estrofe_atual(estrofe_atual_idx)

def ajustar_espacamento(delta=0):
    """Ajusta o espaçamento vertical global."""
    global ESPACAMENTO_BASE
    if delta == 0:
        ESPACAMENTO_BASE = ESPACAMENTO_PADRAO
    else:
        novo_espacamento = ESPACAMENTO_BASE + delta
        if 10 <= novo_espacamento <= 60:
            ESPACAMENTO_BASE = novo_espacamento
            config_manager.salvar_config('espacamento_texto', ESPACAMENTO_BASE)
    
    aplicar_espacamento_config()

def ajustar_zoom(delta=0):
    """Ajusta o tamanho da fonte base e notifica a UI para aplicar."""
    global TAMANHO_FONTE_BASE
    if delta != 0:
        novo_tamanho = TAMANHO_FONTE_BASE + delta
        if MIN_ZOOM <= novo_tamanho <= MAX_ZOOM:
            TAMANHO_FONTE_BASE = novo_tamanho
            config_manager.salvar_config('tamanho_fonte', TAMANHO_FONTE_BASE)
    
    aplicar_zoom_config()

def set_cor_config(key, color_code):
    """Atualiza a cor global e salva no DB."""
    global COR_NORMAL, COR_DESTAQUE, COR_FUNDO_TEXTO, COR_TEXTO_NORMAL, COR_NOTA_NORMAL, COR_NOTA_DESTAQUE
    
    if key == 'cor_barra_navegacao': COR_NORMAL = color_code
    elif key == 'cor_destaque_karaoke': COR_DESTAQUE = color_code
    elif key == 'cor_fundo_texto': COR_FUNDO_TEXTO = color_code
    elif key == 'cor_texto_normal': COR_TEXTO_NORMAL = color_code
    elif key == 'cor_nota_normal': COR_NOTA_NORMAL = color_code 
    elif key == 'cor_nota_destaque': COR_NOTA_DESTAQUE = color_code 
        
    config_manager.salvar_config(key, color_code)
    aplicar_cores_config()
    
# ===================== 7. TELA DE CONFIGURAÇÃO (TOPLEVEL) =====================

def abrir_tela_configuracao():
    """Cria e exibe a janela de configurações."""
    config_window = tk.Toplevel(app)
    config_window.title("Configurações Avançadas")
    config_window.geometry("800x700") 
    config_window.configure(bg=COR_FUNDO_CONFIG)
    config_window.transient(app) 
    
    main_frame = tk.Frame(config_window, padx=20, pady=20, bg=COR_FUNDO_CONFIG)
    main_frame.pack(expand=True, fill="both")
    config_notebook = ttk.Notebook(main_frame)
    config_notebook.pack(expand=True, fill="both")

    zoom_var = tk.IntVar(value=TAMANHO_FONTE_BASE)
    spacing_var = tk.IntVar(value=ESPACAMENTO_BASE)
    
    # --- Aba VISUAL / VELOCIDADE ---
    frame_visual = tk.Frame(config_notebook, bg=COR_FUNDO_CONFIG)
    config_notebook.add(frame_visual, text=" VISUAL / VELOCIDADE ")
    frame_visual.grid_columnconfigure(0, weight=1)
    frame_visual.grid_columnconfigure(1, weight=1)
    
    # Grupo BPM (Apenas display na tela de config)
    bpm_group = tk.LabelFrame(frame_visual, text="Velocidade (BPM)", font=("Arial", 14), fg="white", bg=COR_FUNDO_CONFIG, padx=10, pady=10)
    bpm_group.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
    
    bpm_display_config_label = tk.Label(bpm_group, text=f"BPM Atual: {BPM}", font=("Arial", 18, "bold"), fg=COR_DESTAQUE, bg=COR_FUNDO_CONFIG)
    bpm_display_config_label.pack(pady=10)
    
    def update_both_bpms(delta):
        ajustar_bpm(delta)
        bpm_display_config_label.config(text=f"BPM Atual: {BPM}") 

    tk.Button(bpm_group, text="BPM -5", command=lambda: update_both_bpms(-BPM_STEP), bg="#0050C0", fg="white").pack(side="left", padx=5)
    tk.Button(bpm_group, text="BPM +5", command=lambda: update_both_bpms(BPM_STEP), bg="#0050C0", fg="white").pack(side="left", padx=5)
    
    # Grupo Zoom
    zoom_group = tk.LabelFrame(frame_visual, text="Ajuste de Zoom", font=("Arial", 14), fg="white", bg=COR_FUNDO_CONFIG, padx=10, pady=10)
    zoom_group.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
    tk.Scale(zoom_group, variable=zoom_var, from_=MIN_ZOOM, to=MAX_ZOOM, orient="horizontal", length=250, bg=COR_FUNDO_CONFIG, fg="white", command=lambda v: ajustar_zoom(int(v) - TAMANHO_FONTE_BASE)).pack(pady=5)
    
    # Grupo Espaçamento
    spacing_group = tk.LabelFrame(frame_visual, text="Espaçamento Vertical", font=("Arial", 14), fg="white", bg=COR_FUNDO_CONFIG, padx=10, pady=10)
    spacing_group.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")
    tk.Scale(spacing_group, variable=spacing_var, from_=10, to=60, orient="horizontal", length=250, bg=COR_FUNDO_CONFIG, fg="white", command=lambda v: ajustar_espacamento(int(v) - ESPACAMENTO_BASE)).pack(pady=5)


    # Grupo Cores
    color_group = tk.LabelFrame(frame_visual, text="Cores", font=("Arial", 14), fg="white", bg=COR_FUNDO_CONFIG, padx=10, pady=10)
    color_group.grid(row=0, column=1, rowspan=3, padx=10, pady=10, sticky="nsew")
    
    cor_defs = [
        ('Cor de Fundo (Texto)', 'cor_fundo_texto', COR_FUNDO_TEXTO),
        ('Cor do Texto Normal', 'cor_texto_normal', COR_TEXTO_NORMAL),
        ('Cor do Destaque (Karaokê)', 'cor_destaque_karaoke', COR_DESTAQUE),
        ('Cor da Barra de Navegação', 'cor_barra_navegacao', COR_NORMAL),
        ('Cor Nota Normal (Azul)', 'cor_nota_normal', COR_NOTA_NORMAL), 
        ('Cor Nota Destaque (Verde)', 'cor_nota_destaque', COR_NOTA_DESTAQUE), 
    ]
    
    def selecionar_cor_ui(config_key, initial_color, widget_to_update, label_to_update=None):
        """Abre o seletor de cores, atualiza variáveis e aplica na UI."""
        current_color = label_to_update.cget("bg") if label_to_update else initial_color
        color_code = colorchooser.askcolor(current_color)[1]
        
        if color_code:
            set_cor_config(config_key, color_code)

            widget_to_update.config(bg=color_code)
            if label_to_update: label_to_update.config(text=color_code, bg=color_code)

    for text, key, initial_color in cor_defs:
        lbl = tk.Label(color_group, text=text, fg="white", bg=COR_FUNDO_CONFIG)
        lbl.pack(pady=(10, 2))
        frame_cor = tk.Frame(color_group, bg=COR_FUNDO_CONFIG)
        frame_cor.pack(pady=2)
        
        label_cor = tk.Label(frame_cor, text=config_manager.carregar_config(key, initial_color), 
                             bg=config_manager.carregar_config(key, initial_color), width=15)
        label_cor.pack(side="left", padx=5)
        
        btn_cor = tk.Button(frame_cor, text="Mudar", 
            command=lambda k=key, init_c=initial_color, l=label_cor: 
                selecionar_cor_ui(k, init_c, l, l))
        btn_cor.pack(side="left")

    tk.Button(config_window, text="FECHAR", font=("Arial", 20, "bold"), command=config_window.destroy, bg=COR_INICIAR, fg="white").pack(side="bottom", fill="x", pady=10, padx=20)


# ===================== 8. CONFIGURAÇÃO PRINCIPAL DA UI =====================

def setup_main_ui():
    """Configura e inicia a janela principal do Tkinter."""
    global app, lbl_titulo, lbl_estrofe_info, texto, barra, estrofe_entry, MAX_HINOS, bpm_display_label, btn_editar, content_frame
    
    app = tk.Tk()
    app.title("Hinário Digital - Karaokê JSON")
    app.configure(bg=COR_FUNDO_TEXTO)
    app.state('zoomed')
    app.update_idletasks()
    
    # 1. Barra Inferior
    barra = tk.Frame(app, bg=COR_NORMAL, height=55) 
    barra.pack(side="bottom", fill="x") 
    barra.pack_propagate(False)

    # 2. Título principal e Label Estrofe/Coro
    lbl_titulo = tk.Label(
        app, text="", bg=COR_FUNDO_TEXTO, fg=COR_DESTAQUE,
        font=("Arial", 40, "bold"), anchor="center"
    )
    lbl_titulo.pack(pady=(30, 0), fill="x") 

    lbl_estrofe_info = tk.Label(
        app, text="", bg=COR_FUNDO_TEXTO, fg=COR_DESTAQUE,
        font=("Arial", 24, "bold"), anchor="center"
    )
    lbl_estrofe_info.pack(pady=(5, 10), fill="x")
    
    # NOVO: Frame para conter o Texto e as Notas (Global)
    content_frame = tk.Frame(app, bg=COR_FUNDO_TEXTO)
    content_frame.pack(fill="both", expand=True)

    # 3. Área de Texto Principal
    texto = tk.Text(
        content_frame, bg=COR_FUNDO_TEXTO, fg=COR_TEXTO_NORMAL,
        font=("Arial", TAMANHO_FONTE_BASE, "bold"), wrap="word", bd=0, 
        highlightthickness=0, state="disabled", padx=120, cursor="arrow",
        yscrollcommand=lambda *args: None
    )
    texto.pack(fill="both", expand=True) 
    
    # 3.b Área de Notas Musicais: Criada por função auxiliar
    create_text_notes_widget() 


    # 4. Conteúdo da Barra de Navegação (Frames para organização)
    frame_nav = tk.Frame(barra, bg=COR_NORMAL)
    frame_nav.pack(fill="x", padx=5, pady=0) 
    
    frame_left = tk.Frame(frame_nav, bg=COR_NORMAL)
    frame_left.pack(side="left", fill="y", padx=5)
    
    frame_center = tk.Frame(frame_nav, bg=COR_NORMAL)
    frame_center.pack(side="left", fill="y", padx=5, expand=True) 

    frame_right = tk.Frame(frame_nav, bg=COR_NORMAL)
    frame_right.pack(side="right", fill="y", padx=5)

    # Elementos no frame_left (Navegação Hinos)
    tk.Button(frame_left, text="< Hino", bg=COR_NORMAL, fg="white", 
              command=lambda: carregar_hino(hino_atual - 1)).pack(side="left", padx=5, pady=0)
    tk.Button(frame_left, text="Hino >", bg=COR_NORMAL, fg="white", 
              command=lambda: carregar_hino(hino_atual + 1)).pack(side="left", padx=5, pady=0)

    # Elementos no frame_center (Controles de Karaoke)
    bpm_display_label = tk.Label(frame_center, text=f"BPM: {BPM}", 
                                 font=("Arial", 12, "bold"), fg=COR_DESTAQUE, bg=COR_NORMAL)
    bpm_display_label.pack(side="left", padx=10, pady=0)
    
    tk.Button(frame_center, text="BPM -", bg="#0050C0", fg="white", 
              command=lambda: ajustar_bpm(-BPM_STEP)).pack(side="left", padx=5, pady=0)
    tk.Button(frame_center, text="BPM +", bg="#0050C0", fg="white", 
              command=lambda: ajustar_bpm(BPM_STEP)).pack(side="left", padx=5, pady=0)
    
    tk.Label(frame_center, text="Estrofe:", fg="white", bg=COR_NORMAL).pack(side="left", padx=(10, 0), pady=0)
    estrofe_entry = tk.Entry(frame_center, width=4, font=("Arial", 14), justify='center')
    estrofe_entry.pack(side="left", pady=0)
    estrofe_entry.insert(0, "1")
    estrofe_entry.bind('<Return>', mudar_para_estrofe_manual) 
    
    tk.Button(frame_center, text="INICIAR", bg=COR_INICIAR, fg="white", 
              command=iniciar_karaoke_da_estrofe).pack(side="left", padx=10, pady=0)
    tk.Button(frame_center, text="PARAR", bg=COR_PERIGO, fg="white", 
              command=parar_karaoke).pack(side="left", padx=10, pady=0)
              
    tk.Button(frame_center, text="AUTO ZOOM 🔍", bg=COR_AUTO_SCALE, fg="white", 
              command=lambda: aplicar_zoom_config(forcar_ajuste=True)).pack(side="left", padx=10, pady=0) 

    # Elementos no frame_right (Configurações e Edição)
    
    btn_editar = tk.Button(frame_right, text="EDITAR ✏️", bg=COR_NORMAL, fg="white", 
              command=alternar_modo_edicao)
    btn_editar.pack(side="right", padx=10, pady=0)

    tk.Button(frame_right, text="Config", bg=COR_NORMAL, fg="white", 
              command=abrir_tela_configuracao).pack(side="right", padx=10, pady=0)
    
    aplicar_espacamento_config()
    aplicar_zoom_config()
    aplicar_cores_config() 
    
    # 5. Início do Carregamento
    MAX_HINOS = carregar_dados_json()
    if MAX_HINOS > 0:
        app.after(200, lambda: carregar_hino(1))
    else:
        update_titulo("NENHUM HINO ENCONTRADO", COR_PERIGO)
        
    app.mainloop()

# ===================== 9. PONTO DE ENTRADA =====================

if __name__ == "__main__":
    setup_main_ui()