import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, simpledialog
from PIL import Image, ImageTk
from image_processor import ImageProcessor
import os
import json
import sys

# --- Função para acessar recursos embutidos (PyInstaller) ---
def resource_path(relative_path):
    """Retorna caminho absoluto, mesmo quando empacotado com PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# --- Configuração do arquivo ---
def get_config_path():
    if getattr(sys, 'frozen', False):
        # Quando está rodando como .exe
        base_path = os.path.dirname(sys.executable)
    else:
        # Quando roda via python main.py
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, "config.json")


CONFIG_FILE = get_config_path()
DEFAULT_IMAGES_PATH = resource_path("imagens")


# --- Inicializações ---
processor = ImageProcessor()
settings_window = None
file_window = None
fullscreen_mode = False
log_visible = False
last_folder = ""
last_image = ""


# --- Funções de log ---
def add_log(message):
    log_text.config(state="normal")
    log_text.insert("end", message + "\n")
    log_text.see("end")
    log_text.config(state="disabled")

def toggle_log():
    global log_visible
    if log_visible:
        log_frame.pack_forget()
        log_visible = False
        btn_log.config(text="Mostrar Log")
    else:
        log_frame.pack(side="bottom", fill="x", padx=5, pady=5)
        log_visible = True
        btn_log.config(text="Esconder Log")


# --- Configurações ---
def save_config():
    global last_folder, last_image
    folder = last_folder
    if 'entry_folder' in globals():
        try:
            folder = entry_folder.get()
        except tk.TclError:
            folder = last_folder
    last_folder = folder
    config = {
        "folder": folder,
        "image": last_image,
        "brightness": processor.beta,
        "contrast": processor.alpha,
        "zoom": processor.zoom,
        "invert": processor.inverted,
        "geometry": root.geometry()
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)
    add_log("💾 Configurações salvas.")

def load_config():
    global last_folder, last_image
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        processor.beta = config.get("brightness", 0)
        processor.alpha = config.get("contrast", 1.0)
        processor.zoom = config.get("zoom", 1.0)
        processor.inverted = config.get("invert", False)
        last_folder = config.get("folder", "")
        last_image = config.get("image", "")
        geometry = config.get("geometry")
        if geometry:
            root.geometry(geometry)
        add_log("📂 Configurações carregadas.")
        return last_folder
    else:
        # Se não houver config.json, usa pasta embutida
        last_folder = DEFAULT_IMAGES_PATH
        add_log("📂 Nenhuma configuração encontrada. Usando pasta integrada.")
        return last_folder


# --- Reset defaults ---
def reset_defaults():
    global last_folder, last_image
    processor.beta = 0
    processor.alpha = 1.0
    processor.zoom = 1.0
    processor.inverted = False
    last_folder = DEFAULT_IMAGES_PATH
    last_image = ""
    root.geometry("800x600")

    # Atualiza sliders
    if settings_window is not None and tk.Toplevel.winfo_exists(settings_window):
        for widget in settings_window.winfo_children():
            if isinstance(widget, tk.Scale):
                if "Brilho" in widget.cget("label"):
                    widget.set(processor.beta)
                elif "Contraste" in widget.cget("label"):
                    widget.set(processor.alpha)
                elif "Zoom" in widget.cget("label"):
                    widget.set(processor.zoom)

    update_display()
    add_log("♻️ Configurações restauradas para padrão.")


# --- Fechar aplicação ---
def on_close():
    save_config()
    root.destroy()


# --- Processamento ---
def load_image(filepath):
    processor.load_image(filepath)

    # Aplica brilho, contraste e zoom
    processor.set_brightness(processor.beta)
    processor.set_contrast(processor.alpha)
    processor.set_zoom(processor.zoom)

    # Aplica invert apenas se estiver True no JSON
    if processor.inverted:  
        processor.set_invert(True)

    auto_fit_image()
    update_display()
    add_log(f"✅ Imagem carregada: {filepath}")


def load_image_from_fields():
    global last_image
    folder = entry_folder.get()
    typed_name = entry_filename.get().strip()
    if not folder or not typed_name:
        add_log("⚠️ Nenhum diretório ou nome de arquivo informado.")
        return

    image_extensions = [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]
    all_files = os.listdir(folder)

    typed_root = os.path.splitext(typed_name)[0].lower()

    matching_files = [
        f for f in all_files
        if os.path.splitext(f)[0].lower() == typed_root
        and os.path.splitext(f)[1].lower() in image_extensions]

    if not matching_files:
        messagebox.showerror("Erro", f"Nenhum arquivo encontrado que comece com '{typed_name}'")
        add_log(f"❌ Nenhum arquivo encontrado para '{typed_name}'")
        return
    elif len(matching_files) > 1:
        choice = simpledialog.askstring(
            "Escolha o arquivo",
            f"Múltiplos arquivos encontrados:\n{', '.join(matching_files)}\nDigite o nome completo:"
        )
        if choice and choice in matching_files:
            filepath = os.path.join(folder, choice)
        else:
            add_log(f"⚠️ Nenhum arquivo selecionado entre múltiplos candidatos.")
            return
    else:
        filepath = os.path.join(folder, matching_files[0])

    last_image = os.path.basename(filepath)
    load_image(filepath)

def update_display():
    if processor.image is None:
        return
    processed = processor.apply_adjustments()
    mode = "L" if len(processed.shape) == 2 else "RGB"
    img = Image.fromarray(processed, mode=mode)
    imgtk = ImageTk.PhotoImage(image=img)
    display.config(image=imgtk)
    display.image = imgtk
    add_log("🔄 Imagem atualizada na tela.")

def update_brightness(val):
    processor.set_brightness(int(val))
    update_display()
    add_log(f"☀️ Brilho ajustado: {val}")

def update_contrast(val):
    processor.set_contrast(float(val))
    update_display()
    add_log(f"🎚️ Contraste ajustado: {val}")

def update_zoom(val):
    processor.set_zoom(float(val))
    update_display()
    add_log(f"🔍 Zoom ajustado: {val}")

def toggle_invert():
    processor.toggle_invert()
    update_display()
    add_log("🎨 Inversão de cores aplicada.")

def auto_fit_image(event=None):
    if processor.image is None:
        return
    display_frame.update_idletasks()
    frame_width = display_frame.winfo_width()
    frame_height = display_frame.winfo_height()
    if frame_width <= 1 or frame_height <= 1:
        return
    img_height, img_width = processor.image.shape[:2]
    scale_w = frame_width / img_width
    scale_h = frame_height / img_height
    scale = min(scale_w, scale_h)
    processor.set_zoom(scale)
    update_display()
    add_log(f"📐 Imagem ajustada automaticamente (zoom={scale:.2f})")


# --- Fullscreen ---
def toggle_fullscreen(event=None):
    global fullscreen_mode
    fullscreen_mode = not fullscreen_mode
    current_zoom = processor.zoom  # salva zoom atual

    if fullscreen_mode:
        control_frame.pack_forget()
        add_log("🖥️ Entrou no modo tela cheia.")
    else:
        control_frame.pack(side="bottom", fill="x", padx=5, pady=5)
        add_log("🖥️ Saiu do modo tela cheia.")

    # Reaplica zoom para não perder configurações
    processor.set_zoom(current_zoom)
    update_display()


# --- Zoom ---
def zoom_in(event=None):
    processor.set_zoom(min(processor.zoom + 0.1, 3.0))
    update_display()
    add_log(f"🔎 Zoom in → {processor.zoom:.1f}")

def zoom_out(event=None):
    processor.set_zoom(max(processor.zoom - 0.1, 0.5))
    update_display()
    add_log(f"🔎 Zoom out → {processor.zoom:.1f}")


# --- Configurações ---
def open_settings(event=None):
    global settings_window
    if settings_window is not None and tk.Toplevel.winfo_exists(settings_window):
        settings_window.lift()
        return

    settings_window = tk.Toplevel(root)
    settings_window.title("Configurações")
    settings_window.geometry("400x300")
    settings_window.resizable(False, False)

    tk.Label(settings_window, text="Brilho").pack()
    slider_brightness = tk.Scale(settings_window, from_=-100, to=100, orient="horizontal", command=update_brightness)
    slider_brightness.set(processor.beta)
    slider_brightness.pack(fill="x", padx=10, pady=5)

    tk.Label(settings_window, text="Contraste").pack()
    slider_contrast = tk.Scale(settings_window, from_=0.5, to=3.0, resolution=0.1, orient="horizontal", command=update_contrast)
    slider_contrast.set(processor.alpha)
    slider_contrast.pack(fill="x", padx=10, pady=5)

    tk.Label(settings_window, text="Zoom").pack()
    slider_zoom = tk.Scale(settings_window, from_=0.5, to=3.0, resolution=0.1, orient="horizontal", command=update_zoom)
    slider_zoom.set(processor.zoom)
    slider_zoom.pack(fill="x", padx=10, pady=5)

    btn_invert = tk.Button(settings_window, text="Inverter Cores", command=toggle_invert)
    btn_invert.pack(pady=10)

    settings_window.protocol("WM_DELETE_WINDOW", lambda: settings_window.destroy())
    add_log("⚙️ Configurações abertas.")


# --- Abrir arquivo ---
def open_file_menu(event=None):
    global file_window, entry_folder, entry_filename
    if file_window is not None and tk.Toplevel.winfo_exists(file_window):
        file_window.lift()
        return

    file_window = tk.Toplevel(root)
    file_window.title("Abrir Imagem")
    file_window.geometry("500x200")
    file_window.resizable(False, False)

    tk.Label(file_window, text="Diretório das Imagens:").pack()
    entry_folder = tk.Entry(file_window, width=50)
    entry_folder.pack()

    # Usa último diretório ou pasta integrada
    if last_folder:
        entry_folder.insert(0, last_folder)
    else:
        entry_folder.insert(0, DEFAULT_IMAGES_PATH)

    def browse_folder():
        folder = filedialog.askdirectory()
        if folder:
            entry_folder.delete(0, tk.END)
            entry_folder.insert(0, folder)
            save_config()
            add_log(f"📂 Pasta selecionada: {folder}")

    btn_browse_folder = tk.Button(file_window, text="Selecionar Pasta", command=browse_folder)
    btn_browse_folder.pack(pady=5)

    tk.Label(file_window, text="Nome da Imagem:").pack()
    entry_filename = tk.Entry(file_window, width=50)
    entry_filename.pack()
    entry_filename.bind("<Return>", lambda event: load_image_from_fields())

    btn_load = tk.Button(file_window, text="Carregar Imagem", command=load_image_from_fields)
    btn_load.pack(pady=10)

    file_window.protocol("WM_DELETE_WINDOW", lambda: file_window.destroy())
    add_log("📂 Janela de seleção de arquivo aberta.")


# --- Interface principal ---
root = tk.Tk()
root.title("Visualizador de Hinário")
root.geometry("800x600")
root.protocol("WM_DELETE_WINDOW", on_close)

# Frames
control_frame = tk.Frame(root)
control_frame.pack(side="bottom", fill="x", padx=5, pady=5)

display_frame = tk.Frame(root)
display_frame.pack(fill="both", expand=True)

# Botões
btn_file_menu = tk.Button(control_frame, text="Abrir Arquivo", command=open_file_menu)
btn_file_menu.pack(side="left", padx=5)

btn_settings = tk.Button(control_frame, text="Configurações", command=open_settings)
btn_settings.pack(side="left", padx=5)

btn_fullscreen = tk.Button(control_frame, text="Modo Tela Cheia", command=toggle_fullscreen)
btn_fullscreen.pack(side="left", padx=5)

btn_log = tk.Button(control_frame, text="Mostrar Log", command=toggle_log)
btn_log.pack(side="left", padx=5)

btn_auto_fit = tk.Button(control_frame, text="Auto Ajuste", command=auto_fit_image)
btn_auto_fit.pack(side="left", padx=5)

btn_save_config = tk.Button(control_frame, text="Salvar Configurações", command=save_config)
btn_save_config.pack(side="left", padx=5)

btn_reset = tk.Button(control_frame, text="Reset Defaults", command=reset_defaults)
btn_reset.pack(side="left", padx=5)

# Label para exibir imagem
display = tk.Label(display_frame)
display.pack(fill="both", expand=True)

# Frame de log
log_frame = tk.Frame(root)
log_text = scrolledtext.ScrolledText(log_frame, height=8, state="disabled")
log_text.pack(fill="both", expand=True)

# Atalhos
root.bind("<Control-s>", open_settings)
root.bind("<Control-o>", open_file_menu)
root.bind("<F11>", toggle_fullscreen)
root.bind("<Escape>", toggle_fullscreen)
root.bind("<Key-plus>", zoom_in)
root.bind("<KP_Add>", zoom_in)
root.bind("<Key-minus>", zoom_out)
root.bind("<KP_Subtract>", zoom_out)

# Carregar configurações automaticamente
last_folder = load_config()

# Se houver última imagem, tenta carregar automaticamente
if last_folder and last_image:
    filepath = os.path.join(last_folder, last_image)
    if os.path.exists(filepath):
        load_image(filepath)

add_log("🚀 Aplicação iniciada.")

root.mainloop()
