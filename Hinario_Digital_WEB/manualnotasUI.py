import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw
import json
import os
from functools import partial

# ====================== CONFIGURAÇÃO ======================
# Ajuste os caminhos se necessário
IMG_FOLDER = r"C:\Users\psoares\pyNestle\Private\Hinario_Digital\teste"
JSON_FOLDER = r"C:\Users\psoares\pyNestle\Private\Hinario_Digital\json_notas"
ICONS_FOLDER = r"C:\Users\psoares\pyNestle\Private\Notas_Musicais"

os.makedirs(JSON_FOLDER, exist_ok=True)

# ====================== SISTEMA DE CACHE (OTIMIZAÇÃO) ======================
icon_cache = {}

def limpar_cache_se_necessario():
    if len(icon_cache) > 500:
        icon_cache.clear()

# ====================== TOOLTIP ======================
class ToolTip:
    def __init__(self, widget):
        self.widget = widget
        self.tipwindow = None

    def showtip(self, text):
        if self.tipwindow or not text: return
        x = self.widget.winfo_rootx() + 27
        y = self.widget.winfo_rooty() + 27
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(1)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=text, bg="#ffffe0", relief="solid", borderwidth=1,
                 font=("Tahoma", 8)).pack(ipadx=1)

    def hidetip(self):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None

def criar_tooltip(widget, text):
    tt = ToolTip(widget)
    widget.bind('<Enter>', lambda e: tt.showtip(text))
    widget.bind('<Leave>', lambda e: tt.hidetip())

# ====================== VARIÁVEIS GLOBAIS ======================
root = tk.Tk()
imagem_tk = None
imagem_original_pil = None
caminho_imagem_atual = ""
notas_ativas = {}
escala_zoom = 1.0
ferramenta_atual = "SEMINIMA"
botoes_ui = {}
nota_sendo_arrastada = None
ghost_image_tk = None

historico = []
historico_pos = -1
MAX_HIST = 50

SNAP_ATIVO = tk.BooleanVar(value=True)
PASSO_SNAP = 20

VALORES_NOTAS = [
    "SEMIBREVE", "MINIMA", "MINIMA PONTUADA",
    "SEMINIMA", "SEMINIMA PONTUADA",
    "COLCHEIA", "COLCHEIA PONTUADA",
    "SEMICOLCHEIA", "SEMICOLCHEIA PONTUADA",
    "RESPIRACAO CURTA", "RESPIRACAO LONGA",
    "PAUSA COLCHEIA", "PAUSA SEMIBREVE", "PAUSA SEMICOLCHEIA", "PAUSA SEMINIMA",
    "FERMATA MINIMA", "FERMATA COLCHEIA", "FERMATA SEMINIMA"
]

# ====================== CARREGAMENTO DE ÍCONES ======================
def criar_icone_fallback(texto):
    img = Image.new('RGB', (40, 40), color='#ecf0f1')
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 39, 39], outline="#bdc3c7")
    palavras = texto.split()
    abrev = palavras[0][0] + "." + palavras[1][:3] if len(palavras) > 1 else texto[:4]
    d.text((5, 12), abrev, fill="black")
    return ImageTk.PhotoImage(img)

def carregar_icone_nota(tipo, escala=1.0):
    # Usa cache para evitar leitura de disco repetitiva
    chave_cache = (tipo, escala)
    if chave_cache in icon_cache:
        return icon_cache[chave_cache]

    caminho = os.path.join(ICONS_FOLDER, f"{tipo.replace(' ', '_')}.png")
    if not os.path.exists(caminho): return None
    
    try:
        img = Image.open(caminho)
        tam = max(5, int(40 * escala))
        # BILINEAR é rápido e suficiente
        img_resized = img.resize((tam, tam), Image.Resampling.BILINEAR)
        photo = ImageTk.PhotoImage(img_resized)
        
        icon_cache[chave_cache] = photo
        return photo
    except: 
        return None

def carregar_icone_ui(tipo):
    chave_cache = (tipo, "UI")
    if chave_cache in icon_cache:
        return icon_cache[chave_cache]

    caminho = os.path.join(ICONS_FOLDER, f"{tipo.replace(' ', '_')}.png")
    if os.path.exists(caminho):
        try:
            photo = ImageTk.PhotoImage(Image.open(caminho).resize((30, 30), Image.Resampling.BILINEAR))
            icon_cache[chave_cache] = photo
            return photo
        except: pass
    
    fallback = criar_icone_fallback(tipo)
    icon_cache[chave_cache] = fallback
    return fallback

# ====================== SELEÇÃO DE FERRAMENTA ======================
def selecionar_ferramenta(tipo_nota):
    global ferramenta_atual
    ferramenta_atual = tipo_nota
    
    for tipo, btn in botoes_ui.items():
        if tipo == tipo_nota:
            btn.config(bg="#f1c40f", relief="sunken")
        else:
            btn.config(bg="#ecf0f1", relief="raised")
    
    icone_grande = carregar_icone_ui(tipo_nota)
    if icone_grande:
        lbl_icone_atual.config(image=icone_grande)
        lbl_icone_atual.image = icone_grande
    else:
        lbl_icone_atual.config(image="", text="?", font=("Arial", 20), fg="white")
    
    lbl_nome_ferramenta.config(text=tipo_nota)
    atualizar_icone_ghost()

# ====================== HISTÓRICO ======================
def estado_atual():
    return [{"tipo": v["tipo"], "x": v["x"], "y": v["y"]} for v in notas_ativas.values()]

def salvar_estado():
    global historico_pos
    estado = estado_atual()
    historico[:] = historico[:historico_pos + 1]
    historico.append(estado)
    if len(historico) > MAX_HIST: historico.pop(0)
    historico_pos = len(historico) - 1
    atualizar_titulo()

def undo(e=None):
    global historico_pos
    if historico_pos > 0:
        historico_pos -= 1
        aplicar_estado(historico[historico_pos])

def redo(e=None):
    global historico_pos
    if historico_pos < len(historico) - 1:
        historico_pos += 1
        aplicar_estado(historico[historico_pos])

def aplicar_estado(lista):
    notas_ativas.clear()
    redesenhar_tudo_com_lista(lista)

# ====================== DESENHO ======================
def redesenhar_fundo():
    global imagem_tk
    if not imagem_original_pil: return
    w = int(imagem_original_pil.width * escala_zoom)
    h = int(imagem_original_pil.height * escala_zoom)
    
    imagem_tk = ImageTk.PhotoImage(imagem_original_pil.resize((w, h), Image.Resampling.BILINEAR))
    canvas.create_image(0, 0, anchor="nw", image=imagem_tk, tags="fundo")
    canvas.config(scrollregion=canvas.bbox("all"))

def redesenhar_tudo():
    redesenhar_tudo_com_lista(list(notas_ativas.values()))

def redesenhar_tudo_com_lista(lista_dados):
    # Limpa tudo e recria do zero (seguro e rápido com cache)
    limpar_cache_se_necessario()
    canvas.delete("all")
    redesenhar_fundo()
    
    # Limpa dicionário atual e recria baseado na lista
    notas_ativas.clear()
    for dados in lista_dados:
        criar_nota_visual(dados["x"], dados["y"], dados["tipo"])
    
    criar_ghost_inicial()
    atualizar_icone_ghost()
    atualizar_titulo()

def atualizar_zoom(fator):
    global escala_zoom
    novo = round(escala_zoom + fator, 1)
    if 0.2 <= novo <= 3.0:
        escala_zoom = novo
        lbl_zoom.config(text=f"{int(escala_zoom*100)}%")
        redesenhar_tudo()

# ====================== GHOST CURSOR ======================
def criar_ghost_inicial():
    if not canvas.find_withtag("ghost"):
        canvas.create_image(-100, -100, image=None, tags="ghost")

def atualizar_icone_ghost():
    global ghost_image_tk
    if 'canvas' not in globals() or not canvas: return
    if not ferramenta_atual: return
    
    icone = carregar_icone_nota(ferramenta_atual, escala_zoom)
    if icone:
        ghost_image_tk = icone
        try:
            if not canvas.find_withtag("ghost"):
                criar_ghost_inicial()
            canvas.itemconfig("ghost", image=ghost_image_tk)
            canvas.tag_raise("ghost")
        except: pass

def mover_ghost(event):
    if not caminho_imagem_atual: return
    x = canvas.canvasx(event.x)
    y = canvas.canvasy(event.y)
    canvas.coords("ghost", x, y)

def esconder_ghost(event):
    canvas.coords("ghost", -100, -100)

# ====================== NOTAS (FUNÇÃO CORRIGIDA) ======================
def criar_nota_visual(x_real, y_real, tipo):
    x_tela = x_real * escala_zoom
    y_tela = y_real * escala_zoom
    tamanho = 40 * escala_zoom
    metade = tamanho / 2

    # 1. Cria retângulo invisível para gerar ID
    img_id = canvas.create_rectangle(
        x_tela - metade, y_tela - metade,
        x_tela + metade, y_tela + metade,
        outline="", width=0, tags="nota"
    )
    
    # Cria Tag de Grupo Única
    tag_grupo = f"id_{img_id}"
    
    # Aplica tag no retângulo
    canvas.itemconfig(img_id, tags=("nota", tag_grupo))

    icone_grande_ref = carregar_icone_nota(tipo, escala_zoom)
    icone_pequeno = carregar_icone_nota(tipo, escala_zoom * 0.5)

    # 2. Marcador Vermelho (COM TAG DE GRUPO)
    distancia_x = 40 * escala_zoom 
    y_marcador = y_tela - distancia_x

    canvas.create_line(x_tela-5, y_marcador-5, x_tela+5, y_marcador+5, 
                       fill="red", width=2, tags=("nota", "marcador", tag_grupo))
    canvas.create_line(x_tela-5, y_marcador+5, x_tela+5, y_marcador-5, 
                       fill="red", width=2, tags=("nota", "marcador", tag_grupo))

    # 3. Ícone Pequeno (COM TAG DE GRUPO)
    if icone_pequeno:
        distancia_mini = 20 * escala_zoom
        y_mini = y_tela - distancia_mini
        canvas.create_image(x_tela, y_mini, image=icone_pequeno, 
                            tags=("nota", "icone_pequeno", tag_grupo))
    
    notas_ativas[img_id] = {
        "tipo": tipo,
        "x": x_real,
        "y": y_real,
        "highlight_id": img_id,
        "img_ref": icone_grande_ref, 
        "img_small_ref": icone_pequeno
    }
    return img_id

def aplicar_snap(x, y):
    if SNAP_ATIVO.get():
        x = round(x / PASSO_SNAP) * PASSO_SNAP
        y = round(y / PASSO_SNAP) * PASSO_SNAP
    return int(x), int(y)

# ====================== EVENTOS ======================
def clique_criar_rapido(event):
    global nota_sendo_arrastada
    x_canvas = canvas.canvasx(event.x)
    y_canvas = canvas.canvasy(event.y)

    itens = canvas.find_overlapping(x_canvas-5, y_canvas-5, x_canvas+5, y_canvas+5)
    for item in itens:
        if "nota" in canvas.gettags(item):
            iniciar_arraste(event)
            return

    if not caminho_imagem_atual or not ferramenta_atual: return
    x_real, y_real = aplicar_snap(x_canvas / escala_zoom, y_canvas / escala_zoom)
    salvar_estado()
    criar_nota_visual(x_real, y_real, ferramenta_atual)
    canvas.tag_raise("ghost")

def iniciar_arraste(event):
    global nota_sendo_arrastada
    x_canvas = canvas.canvasx(event.x)
    y_canvas = canvas.canvasy(event.y)
    
    item = canvas.find_closest(x_canvas, y_canvas)
    if not item: return
    tags = canvas.gettags(item[0])
    if "nota" not in tags: return
    
    for tag in tags:
        if tag.startswith("id_"):
            nota_sendo_arrastada = int(tag.split("_")[1])
            canvas.config(cursor="hand2")
            break

def arrastar(event):
    if not nota_sendo_arrastada: return
    x_real, y_real = aplicar_snap(canvas.canvasx(event.x) / escala_zoom, canvas.canvasy(event.y) / escala_zoom)
    
    antigo_x = notas_ativas[nota_sendo_arrastada]["x"]
    antigo_y = notas_ativas[nota_sendo_arrastada]["y"]
    
    dx = (x_real - antigo_x) * escala_zoom
    dy = (y_real - antigo_y) * escala_zoom
    
    # Move o GRUPO INTEIRO
    canvas.move(f"id_{nota_sendo_arrastada}", dx, dy)
    
    notas_ativas[nota_sendo_arrastada]["x"] = x_real
    notas_ativas[nota_sendo_arrastada]["y"] = y_real

def soltar(event):
    global nota_sendo_arrastada
    if nota_sendo_arrastada:
        salvar_estado()
    nota_sendo_arrastada = None
    canvas.config(cursor="")

def clique_editar_excluir(event):
    x_canvas = canvas.canvasx(event.x)
    y_canvas = canvas.canvasy(event.y)
    itens = canvas.find_overlapping(x_canvas-5, y_canvas-5, x_canvas+5, y_canvas+5)
    for item in itens:
        if "nota" in canvas.gettags(item):
            abrir_menu_contexto(event, item)
            break

def abrir_menu_contexto(event, item_clicado):
    for tag in canvas.gettags(item_clicado):
        if tag.startswith("id_"):
            nid = int(tag.split("_")[1])
            break
    else: return

    menu = tk.Menu(root, tearoff=0)
    nome = notas_ativas[nid]["tipo"]
    menu.add_command(label=f"Excluir ({nome})", command=lambda: excluir_nota(nid))
    menu.add_separator()
    menu.add_command(label=f"Trocar por '{ferramenta_atual}'", command=lambda: trocar_nota(nid))
    menu.post(event.x_root, event.y_root)

def excluir_nota(nid):
    if nid not in notas_ativas: return
    salvar_estado()
    # Deleta grupo inteiro
    canvas.delete(f"id_{nid}")
    notas_ativas.pop(nid, None)

def trocar_nota(nid):
    if nid not in notas_ativas: return
    salvar_estado()
    # Atualiza dados
    notas_ativas[nid]["tipo"] = ferramenta_atual
    # Redesenha tudo (seguro contra falhas visuais)
    redesenhar_tudo()

def tecla_delete_hover(event):
    x = canvas.canvasx(canvas.winfo_pointerx() - canvas.winfo_rootx())
    y = canvas.canvasy(canvas.winfo_pointery() - canvas.winfo_rooty())
    itens = canvas.find_overlapping(x-5, y-5, x+5, y+5)
    for item in itens:
        if "nota" in canvas.gettags(item):
            for tag in canvas.gettags(item):
                if tag.startswith("id_"):
                    nid = int(tag.split("_")[1])
                    excluir_nota(nid)
                    return

# ====================== HOVER ======================
def hover_enter(event):
    item = canvas.find_withtag("current")
    if not item: return
    for tag in canvas.gettags(item[0]):
        if tag.startswith("id_"):
            nid = int(tag.split("_")[1])
            if nid in notas_ativas:
                canvas.itemconfig(notas_ativas[nid]["highlight_id"], outline="yellow", width=2)
            break

def hover_leave(event):
    item = canvas.find_withtag("current")
    if not item: return
    for tag in canvas.gettags(item[0]):
        if tag.startswith("id_"):
            nid = int(tag.split("_")[1])
            if nid in notas_ativas:
                canvas.itemconfig(notas_ativas[nid]["highlight_id"], outline="", width=0)
            break

# ====================== ARQUIVO ======================
def atualizar_titulo():
    nome = os.path.basename(caminho_imagem_atual) if caminho_imagem_atual else "Sem imagem"
    root.title(f"Editor Musical – {nome} ({len(notas_ativas)} notas)")

def exibir_imagem_no_canvas(caminho):
    global imagem_original_pil, caminho_imagem_atual, escala_zoom
    try:
        imagem_original_pil = Image.open(caminho)
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao abrir imagem: {e}")
        return False
    
    escala_zoom = 1.0
    icon_cache.clear()
    lbl_zoom.config(text="100%")
    caminho_imagem_atual = caminho
    
    # Reseta tudo
    notas_ativas.clear()
    historico.clear()
    global historico_pos
    historico_pos = -1
    
    canvas.delete("all")
    criar_ghost_inicial()
    
    redesenhar_tudo()
    atualizar_titulo()
    return True

def selecionar_imagem():
    caminho = filedialog.askopenfilename(initialdir=IMG_FOLDER, filetypes=[("Imagens", "*.png;*.jpg;*.jpeg")])
    if caminho: exibir_imagem_no_canvas(caminho)

def salvar_json():
    if not notas_ativas or not caminho_imagem_atual: return
    dados = {"imagem_fundo": caminho_imagem_atual, "notas": estado_atual()}
    arq = filedialog.asksaveasfilename(initialdir=JSON_FOLDER, defaultextension=".json", filetypes=[("JSON", "*.json")])
    if arq:
        with open(arq, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=4, ensure_ascii=False)
        messagebox.showinfo("Salvo", "Projeto salvo com sucesso!")

def carregar_projeto():
    arq = filedialog.askopenfilename(initialdir=JSON_FOLDER, filetypes=[("JSON", "*.json")])
    if not arq: return
    try:
        with open(arq, "r", encoding="utf-8") as f:
            dados = json.load(f)
        img = dados.get("imagem_fundo", "")
        if not os.path.exists(img):
            img = filedialog.askopenfilename(title="Localize a imagem de fundo")
            if not img: return
        exibir_imagem_no_canvas(img)
        aplicar_estado(dados.get("notas", []))
        salvar_estado()
        messagebox.showinfo("Sucesso", "Projeto carregado!")
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao carregar: {e}")

def limpar_tudo():
    if messagebox.askyesno("Limpar", "Remover todas as notas?"):
        salvar_estado()
        notas_ativas.clear()
        redesenhar_tudo()

# ====================== INTERFACE ======================
root.title("Editor Musical Visual")
root.geometry("1600x1000")

# Barra superior
barra_top = tk.Frame(root, bg="#2c3e50", height=40)
barra_top.pack(fill="x", side="top")

tk.Button(barra_top, text="Nova Img", command=selecionar_imagem, bg="#2980b9", fg="white", font=("Arial", 9)).pack(side="left", padx=5, pady=5)
tk.Button(barra_top, text="Abrir", command=carregar_projeto, bg="#f39c12", fg="white", font=("Arial", 9)).pack(side="left", padx=5, pady=5)
tk.Button(barra_top, text="Salvar", command=salvar_json, bg="#27ae60", fg="white", font=("Arial", 9)).pack(side="left", padx=5, pady=5)
tk.Button(barra_top, text="Limpar", command=limpar_tudo, bg="#c0392b", fg="white", font=("Arial", 9)).pack(side="left", padx=5, pady=5)
tk.Button(barra_top, text="Undo (Ctrl+Z)", command=undo, bg="#7f8c8d", fg="white", font=("Arial", 9)).pack(side="left", padx=20, pady=5)

tk.Checkbutton(barra_top, text="Snap", variable=SNAP_ATIVO, bg="#2c3e50", fg="white", selectcolor="#34495e").pack(side="left", padx=10)

frame_zoom = tk.Frame(barra_top, bg="#2c3e50")
frame_zoom.pack(side="left", padx=10)
tk.Button(frame_zoom, text="-", command=lambda: atualizar_zoom(-0.1), width=3).pack(side="left")
lbl_zoom = tk.Label(frame_zoom, text="100%", fg="white", bg="#2c3e50", width=6)
lbl_zoom.pack(side="left")
tk.Button(frame_zoom, text="+", command=lambda: atualizar_zoom(0.1), width=3).pack(side="left")

# FEEDBACK VISUAL
frame_ferramenta = tk.Frame(barra_top, bg="#2c3e50")
frame_ferramenta.pack(side="left", padx=30)
lbl_icone_atual = tk.Label(frame_ferramenta, bg="#2c3e50", width=50, height=50)
lbl_icone_atual.pack(side="left")
lbl_nome_ferramenta = tk.Label(frame_ferramenta, text="SEMINIMA", fg="#f1c40f", bg="#2c3e50", font=("Arial", 11, "bold"))
lbl_nome_ferramenta.pack(side="left", padx=10)

lbl_coords = tk.Label(barra_top, text="x: ---- y: ----", fg="white", bg="#2c3e50")
lbl_coords.pack(side="right", padx=20)

# Paleta
frame_paleta = tk.Frame(root, bg="#ecf0f1", height=70)
frame_paleta.pack(fill="x", side="top")
canvas_paleta = tk.Canvas(frame_paleta, bg="#ecf0f1", height=60, highlightthickness=0)
scroll_paleta = tk.Scrollbar(frame_paleta, orient="horizontal", command=canvas_paleta.xview)
frame_botoes = tk.Frame(canvas_paleta, bg="#ecf0f1")
canvas_paleta.create_window((0, 0), window=frame_botoes, anchor="nw")
canvas_paleta.configure(xscrollcommand=scroll_paleta.set)
scroll_paleta.pack(side="bottom", fill="x")
canvas_paleta.pack(side="left", fill="both", expand=True)

for nota in VALORES_NOTAS:
    img_ui = carregar_icone_ui(nota)
    btn = tk.Button(
        frame_botoes, image=img_ui, width=40, height=40,
        bg="#ecf0f1", relief="raised",
        command=partial(selecionar_ferramenta, nota)
    )
    btn.image = img_ui
    btn.pack(side="left", padx=2, pady=5)
    criar_tooltip(btn, nota)
    botoes_ui[nota] = btn

frame_botoes.update_idletasks()
canvas_paleta.config(scrollregion=canvas_paleta.bbox("all"))

# Canvas principal
canvas = tk.Canvas(root, bg="#bdc3c7")
scroll_x = tk.Scrollbar(root, orient="horizontal", command=canvas.xview)
scroll_y = tk.Scrollbar(root, orient="vertical", command=canvas.yview)
canvas.configure(xscrollcommand=scroll_x.set, yscrollcommand=scroll_y.set)
scroll_x.pack(side="bottom", fill="x")
scroll_y.pack(side="right", fill="y")
canvas.pack(fill="both", expand=True)

criar_ghost_inicial()

# Eventos
canvas.bind("<ButtonPress-1>", clique_criar_rapido)
canvas.bind("<B1-Motion>", arrastar)
canvas.bind("<ButtonRelease-1>", soltar)
canvas.bind("<Button-3>", clique_editar_excluir)
canvas.bind("<Motion>", lambda e: [mover_ghost(e), lbl_coords.config(text=f"x: {int(canvas.canvasx(e.x)/escala_zoom):4d}  y: {int(canvas.canvasy(e.y)/escala_zoom):4d}")])
canvas.bind("<Leave>", esconder_ghost)

canvas.tag_bind("nota", "<Enter>", hover_enter)
canvas.tag_bind("nota", "<Leave>", hover_leave)

# Pan & Zoom
canvas.bind("<ButtonPress-2>", lambda e: canvas.scan_mark(e.x, e.y))
canvas.bind("<B2-Motion>", lambda e: canvas.scan_dragto(e.x, e.y, gain=1))

def _on_mousewheel(event):
    if not (event.state & 0x4):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")

canvas.bind_all("<MouseWheel>", _on_mousewheel)
root.bind("<Control-MouseWheel>", lambda e: atualizar_zoom(0.1 if e.delta > 0 else -0.1))

root.bind("<Control-z>", undo)
root.bind("<Control-y>", redo)
root.bind("<Delete>", tecla_delete_hover)

selecionar_ferramenta("SEMINIMA")

root.mainloop()