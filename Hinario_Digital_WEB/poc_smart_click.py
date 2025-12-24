import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog

# --- MAPEAMENTO DE NOTAS ---
NOTAS_MAPA = {
    -5: 'Si (Agudo)', -4: 'La (Agudo)', -3: 'Sol (Agudo)', -2: 'Fa (Agudo)', -1: 'Mi (Agudo)',
    0: 'Fa (5a Linha)', 1: 'Mi (4o Espaco)', 
    2: 'Re (4a Linha)', 3: 'Do (3o Espaco)', 
    4: 'Si (3a Linha)', 5: 'La (2o Espaco)', 
    6: 'Sol (2a Linha)', 7: 'Fa (1o Espaco)', 
    8: 'Mi (1a Linha)', 9: 'Re (Grave)', 
    10: 'Do (Grave)'
}

# Variáveis de Estado
estado_zoom = False # False = Vendo img original, True = Vendo janela de zoom
img_original = None
img_zoom_crop = None
offset_zoom = (0, 0) # Para saber onde o recorte estava na imagem original

def selecionar_arquivo():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    return filedialog.askopenfilename()

def carregar_imagem(caminho):
    try:
        with open(caminho, "rb") as s:
            n = np.asarray(bytearray(s.read()), dtype=np.uint8)
            return cv2.imdecode(n, cv2.IMREAD_COLOR)
    except: return None

# --- ALGORITMO DE ALTURA (MANTIDO) ---
def identificar_altura(img_gray, y_global):
    h, w = img_gray.shape
    # Morfologia para apagar notas e deixar linhas
    _, binaria = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    linhas_img = cv2.morphologyEx(binaria, cv2.MORPH_OPEN, kernel)
    
    # Projeção horizontal perto do clique
    y1, y2 = max(0, y_global-100), min(h, y_global+100)
    fatia = linhas_img[y1:y2, :]
    proj = cv2.reduce(fatia, 1, cv2.REDUCE_AVG, dtype=cv2.CV_32F).flatten()
    
    linhas_y = []
    pular = 0
    for i, val in enumerate(proj):
        if pular > 0: pular -= 1; continue
        if val > 5:
            linhas_y.append(y1 + i)
            pular = 5
            
    if len(linhas_y) < 5: return "Pauta Nao Achada", []
    
    # Pega as 5 linhas mais proximas
    linhas_y.sort(key=lambda ly: abs(ly - y_global))
    pentagrama = sorted(linhas_y[:5])
    
    # Calcula Nota
    espaco = np.mean(np.diff(pentagrama))
    linha_topo = pentagrama[0]
    degraus = round((y_global - linha_topo) / (espaco / 2.0))
    nota = NOTAS_MAPA.get(degraus, "Outra")
    return nota, pentagrama

# --- ALGORITMO DE RITMO (HIERARQUIA DE CONTORNOS) ---
def identificar_ritmo(img_gray, x_global, y_global, linhas_pauta):
    if not linhas_pauta: return "Indefinido"
    
    # 1. Recorte local para analise (ROI)
    espaco = np.mean(np.diff(linhas_pauta))
    tamanho_box = int(espaco * 4) # Olha uma area de 4 espaços
    h, w = img_gray.shape
    
    x1 = max(0, x_global - tamanho_box)
    x2 = min(w, x_global + tamanho_box)
    y1 = max(0, y_global - tamanho_box)
    y2 = min(h, y_global + tamanho_box)
    
    roi = img_gray[y1:y2, x1:x2]
    
    # 2. Detecção de Contornos com Hierarquia
    # Inverte (Notas brancas, fundo preto)
    _, binaria = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # RETR_CCOMP acha contornos e organiza em dois niveis (Pai e Filho)
    # Se uma nota tem um buraco, ela terá um contorno Pai (cabeça) e um Filho (o buraco)
    contornos, hierarquia = cv2.findContours(binaria, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    
    if contornos is None or len(contornos) == 0:
        return "Erro (Vazio)"
        
    # Achar qual contorno o usuário clicou (o mais proximo do centro do ROI)
    centro_roi_x = x_global - x1
    centro_roi_y = y_global - y1
    
    melhor_cnt = None
    min_dist = 9999
    idx_melhor = -1
    
    for i, cnt in enumerate(contornos):
        # Testa se o ponto clicado está DENTRO do contorno
        dist = cv2.pointPolygonTest(cnt, (centro_roi_x, centro_roi_y), True)
        # pointPolygonTest retorna positivo se dentro, negativo se fora.
        # Queremos o maior valor positivo (mais "dentro") ou o mais próximo de 0
        
        # Filtro de tamanho (ignorar sujeira)
        area = cv2.contourArea(cnt)
        if area < 50: continue 

        # Distancia do centro de massa do contorno ate o clique
        M = cv2.moments(cnt)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            d = np.hypot(cx - centro_roi_x, cy - centro_roi_y)
            if d < min_dist:
                min_dist = d
                melhor_cnt = cnt
                idx_melhor = i
    
    if idx_melhor == -1: return "Nao detectou forma"
    
    # 3. Análise Hierárquica (O Segredo da Minima)
    # hierarchy estrutura: [Next, Previous, First_Child, Parent]
    # Se First_Child != -1, significa que esse contorno tem um buraco dentro!
    tem_buraco = hierarquia[0][idx_melhor][2] != -1
    
    # Pegar Bounding Box para analisar Haste/Bandeira
    bx, by, bw, bh = cv2.boundingRect(melhor_cnt)
    aspect_ratio = bw / bh
    
    # --- CLASSIFICAÇÃO FINAL ---
    tipo = ""
    
    if tem_buraco:
        # Se tem buraco, só pode ser Minima ou Semibreve
        # Semibreve não tem haste (altura ~= largura)
        if bh > bw * 1.5: 
            tipo = "Minima (Vazada)"
        else:
            tipo = "Semibreve ou Minima"
    else:
        # Se NÃO tem buraco, é cabeça preta (Seminima ou Colcheia)
        # Diferencia pela largura da bandeira
        largura_haste_esperada = espaco * 0.4
        
        if bw > espaco * 1.2: # Se a largura total for grande
            tipo = "Colcheia (Bandeira/Barra)"
        else:
            tipo = "Seminima"
            
    return tipo

# --- INTERAÇÃO (MOUSE) ---
def mouse_callback(event, x, y, flags, param):
    global estado_zoom, img_zoom_crop, offset_zoom, img_original
    
    if event == cv2.EVENT_LBUTTONDOWN:
        
        # --- PASSO 1: ZOOM (Se clicou na imagem principal) ---
        if not estado_zoom:
            print(f"Gerando zoom na regiao {x}, {y}...")
            h, w = img_original.shape[:2]
            
            # Tamanho da janela de zoom (ex: 100x100 px da original)
            tamanho_lupa = 60 
            x1 = max(0, x - tamanho_lupa)
            y1 = max(0, y - tamanho_lupa)
            x2 = min(w, x + tamanho_lupa)
            y2 = min(h, y + tamanho_lupa)
            
            # Recorta e guarda o offset
            crop = img_original[y1:y2, x1:x2]
            offset_zoom = (x1, y1)
            
            # Aumenta o recorte (Zoom visual 5x)
            img_zoom_crop = cv2.resize(crop, None, fx=5, fy=5, interpolation=cv2.INTER_NEAREST)
            
            estado_zoom = True
            cv2.imshow("PASSO 2: CLIQUE PRECISO NA NOTA", img_zoom_crop)
            cv2.setMouseCallback("PASSO 2: CLIQUE PRECISO NA NOTA", mouse_zoom_callback)
            print(">> Janela de Zoom aberta. CLIQUE NA NOTA NELA.")
            
def mouse_zoom_callback(event, x, y, flags, param):
    global offset_zoom, img_original, estado_zoom, img_zoom_crop
    
    if event == cv2.EVENT_LBUTTONDOWN:
        # --- PASSO 2: ANÁLISE (Se clicou na janela de zoom) ---
        
        # Converter coordenada do zoom volta para original
        # Como demos zoom de 5x:
        x_real = int(x / 5) + offset_zoom[0]
        y_real = int(y / 5) + offset_zoom[1]
        
        print(f"Analisando pixel real: {x_real}, {y_real}")
        
        gray = cv2.cvtColor(img_original, cv2.COLOR_BGR2GRAY)
        
        # Identificações
        nota, pentagrama = identificar_altura(gray, y_real)
        ritmo = identificar_ritmo(gray, x_real, y_real, pentagrama)
        
        # Desenhar Resultado na janela de Zoom para feedback imediato
        img_res = img_zoom_crop.copy()
        cv2.circle(img_res, (x, y), 5, (0,0,255), -1) # Onde vc clicou
        
        # Texto
        texto = f"{nota}"
        texto2 = f"{ritmo}"
        
        cv2.rectangle(img_res, (0,0), (600, 60), (0,0,0), -1)
        cv2.putText(img_res, texto, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,255), 2)
        cv2.putText(img_res, texto2, (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
        
        cv2.imshow("PASSO 2: CLIQUE PRECISO NA NOTA", img_res)
        
        # Se quiser fechar o zoom após o clique, descomente abaixo:
        # estado_zoom = False
        # cv2.destroyWindow("PASSO 2: CLIQUE PRECISO NA NOTA")

def main():
    global img_original
    caminho = selecionar_arquivo()
    if not caminho: return
    img_original = carregar_imagem(caminho)
    
    # Redimensiona para caber na tela a visão geral
    h, w = img_original.shape[:2]
    fator = 1.0
    if w > 1000: fator = 1000/w
    img_view = cv2.resize(img_original, None, fx=fator, fy=fator)
    
    janela_main = "PASSO 1: Clique na regiao (Geral)"
    cv2.namedWindow(janela_main)
    # Callback especial que lida com a escala da visualização
    cv2.setMouseCallback(janela_main, lambda e,x,y,f,p: mouse_callback(e, int(x/fator), int(y/fator), f, p))
    
    print("=== MODO ZOOM ATIVADO ===")
    print("1. Clique na imagem geral onde quer olhar.")
    print("2. Uma janela 'LUPA' vai abrir.")
    print("3. Na lupa, clique EXATAMENTE no centro da cabeça da nota.")
    
    cv2.imshow(janela_main, img_view)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()