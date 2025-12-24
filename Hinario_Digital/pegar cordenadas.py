import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk

class CropEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Descobridor de Coordenadas (Tamanho Real)")
        self.root.geometry("1200x800")
        
        # Frame para os controles no topo
        top_frame = tk.Frame(root)
        top_frame.pack(side="top", fill="x", pady=5)
        
        btn = tk.Button(top_frame, text="Carregar Imagem", command=self.load_image, bg="#dddddd")
        btn.pack()
        
        # Frame principal para Canvas e Scrollbars
        main_frame = tk.Frame(root)
        main_frame.pack(fill="both", expand=True)

        # Configuração do Canvas e Scrollbars
        self.canvas = tk.Canvas(main_frame, cursor="cross", bg="grey")
        
        self.v_scroll = tk.Scrollbar(main_frame, orient="vertical", command=self.canvas.yview)
        self.h_scroll = tk.Scrollbar(main_frame, orient="horizontal", command=self.canvas.xview)
        
        self.canvas.configure(yscrollcommand=self.v_scroll.set, xscrollcommand=self.h_scroll.set)
        
        # Grid layout para colocar as barras nos cantos certos
        self.v_scroll.pack(side="right", fill="y")
        self.h_scroll.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        self.start_x = None
        self.start_y = None
        self.rect = None
        self.image = None
        self.tk_image = None

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

    def load_image(self):
        path = filedialog.askopenfilename(filetypes=[("Imagens", "*.png;*.jpg;*.jpeg")])
        if not path: return
        
        # Abre a imagem e NÃO redimensiona
        self.image = Image.open(path)
        self.tk_image = ImageTk.PhotoImage(self.image)
        
        # Configura o tamanho da área de rolagem para o tamanho real da imagem
        self.canvas.config(scrollregion=(0, 0, self.image.width, self.image.height))
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)
        
        print(f"Imagem carregada: {self.image.width}x{self.image.height} pixels.")

    def on_button_press(self, event):
        # canvasx e canvasy convertem a posição do mouse na tela para a posição real na imagem (considerando o scroll)
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="red", width=3)

    def on_move_press(self, event):
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)
        
        # Ordena coordenadas e converte para Inteiro (pixels não podem ser decimais)
        x1, x2 = sorted([int(self.start_x), int(end_x)])
        y1, y2 = sorted([int(self.start_y), int(end_y)])
        
        print("\n" + "="*40)
        print("COPIE ESTES NÚMEROS PARA O SEU CÓDIGO:")
        print(f"({x1}, {y1}, {x2}, {y2})")
        print("="*40)

if __name__ == "__main__":
    root = tk.Tk()
    app = CropEditor(root)
    root.mainloop()