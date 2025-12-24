import os
import cv2
import numpy as np
from paddleocr import PaddleOCR
from PIL import Image, ImageDraw, ImageFont 
import logging
import csv

logging.getLogger("ppocr").setLevel(logging.WARNING)

# --- Função de Desenho para OCR (corrigida para evitar erro de cvtColor) ---
def desenhar_resultados(image, boxes, txts, scores, font_path='arial.ttf'):
    # Garantir que image seja uma imagem PIL
    if isinstance(image, np.ndarray):
        image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype(font_path, 20)
    except IOError:
        font = ImageFont.load_default()

    for box, txt, score in zip(boxes, txts, scores):
        if score > 0.6:
            if isinstance(box, np.ndarray):
                box = box.tolist()
            poligono = [tuple([int(pt[0]), int(pt[1])]) for pt in box]
            draw.polygon(poligono, outline="red")
            ponto_texto = poligono[0] 
            draw.text((ponto_texto[0], ponto_texto[1] - 25), f"{txt}", fill="red", font=font)

    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

# --- Função Desenhar Linhas Detectadas ---
def desenhar_linhas_detectadas(image, barras_duplas):
    for barra in barras_duplas:
        coords = barra['coords']
        # Desenhar a primeira linha
        x1, y1 = coords[0]
        x2, y2 = coords[1]
        cv2.line(image, (x1, y1), (x2, y2), (0, 0, 255), 2)  # Linha vermelha

        # Desenhar a segunda linha
        x1_next, y1_next = coords[2]
        x2_next, y2_next = coords[3]
        cv2.line(image, (x1_next, y1_next), (x2_next, y2_next), (0, 0, 255), 2)  # Linha vermelha

        # Desenhar texto '[BARRA_DUPLA]' no centro
        center_x = barra['cx']
        center_y = barra['cy']
        cv2.putText(image, '[BARRA_DUPLA]', (center_x, center_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)

    return image

# --- Função Atualizada: Detectar barras duplas (||) com debug visual completo e melhoria para imagens escaneadas ---
def detectar_barras_duplas(image, min_length=10, max_gap=15, max_dist_dupla=25, threshold_block_size=9, threshold_c=1):
    # Converter para cinza e blur
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    cv2.imwrite('debug_gray.png', gray)  # Debug: imagem em cinza

    blurred = cv2.medianBlur(gray, 5)  # Median blur para reduzir ruido em escaneadas
    cv2.imwrite('debug_blurred.png', blurred)  # Debug: imagem borrada

    # Threshold adaptativo para imagens escaneadas
    adaptive = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, threshold_block_size, threshold_c)
    cv2.imwrite('debug_adaptive.png', adaptive)  # Debug: threshold adaptativo

    # Dilation para conectar linhas interrompidas
    kernel = np.ones((5, 1), np.uint8)  # Kernel vertical para linhas verticais
    dilated = cv2.dilate(adaptive, kernel, iterations=2)
    cv2.imwrite('debug_dilated.png', dilated)  # Debug: dilatação

    # Detecção de bordas com Canny no dilatado
    edges = cv2.Canny(dilated, 5, 50)
    cv2.imwrite('debug_edges.png', edges)  # Debug: imagem de bordas

    # Detecção de linhas com HoughLinesP
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 15, minLineLength=min_length, maxLineGap=max_gap)

    # Debug: desenhar todas as linhas detectadas em uma imagem separada
    debug_lines_img = image.copy()
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            cv2.line(debug_lines_img, (x1, y1), (x2, y2), (0, 255, 0), 2)  # Linhas verdes
    cv2.imwrite('debug_all_lines.png', debug_lines_img)  # Debug: todas as linhas detectadas

    barras_duplas = []
    if lines is not None:
        lines = sorted(lines, key=lambda line: line[0][0])  # Ordenar por X1
        i = 0
        while i < len(lines) - 1:
            x1, y1, x2, y2 = lines[i][0]
            x1_next, y1_next, x2_next, y2_next = lines[i+1][0]

            # Verificar se são verticais
            is_vertical = abs(y2 - y1) > abs(x2 - x1) * 3 and abs(y2_next - y1_next) > abs(x2_next - x1_next) * 3
            dist = abs(x1_next - x1)
            overlap_y = max(0, min(y2, y2_next) - max(y1, y1_next)) > min_length / 2

            if is_vertical and dist < max_dist_dupla and overlap_y:
                # É uma barra dupla
                center_x = int((x1 + x1_next) / 2)
                center_y = int((y1 + y2 + y1_next + y2_next) / 4)
                coords = [[x1, y1], [x2, y2], [x1_next, y1_next], [x2_next, y2_next]]
                barras_duplas.append({'txt': '[BARRA_DUPLA]', 'conf': 1.0, 'cx': center_x, 'cy': center_y, 'coords': coords})
                print(f"Barra Dupla detectada: Centro X={center_x}, Y={center_y}")
                i += 2
            else:
                i += 1

    return barras_duplas

# --- Configuração ---
img_path = r'C:\Users\psoares\pyNestle\Private\Hinario_Digital\musicos_imagens_cortadas\5.png'
csv_path = r'C:\Users\psoares\pyNestle\Private\resultado_ocr5.csv' 
font_path = r'C:\Windows\Fonts\arial.ttf' 

print("Iniciando PaddleOCR...")
ocr = PaddleOCR(use_angle_cls=True, lang='fr') 

if not os.path.exists(img_path):
    print(f"ERRO: Imagem não encontrada: {img_path}")
else:
    print(f"Processando imagem...")
    image_cv = cv2.imread(img_path)
    full_result = ocr.ocr(img_path)

    if full_result and len(full_result) > 0:
        dados = full_result[0]
        
        txts = dados.get('rec_texts', [])
        scores = dados.get('rec_scores', [])
        boxes = dados.get('dt_polys', []) 

        print(f"\n--- Salvando {len(txts)} itens de texto em CSV ---")
        
        # --- DETECTAR BARRAS DUPLAS (com debug visual completo) ---
        barras_duplas = detectar_barras_duplas(image_cv, min_length=10, max_gap=15, max_dist_dupla=25, threshold_block_size=9, threshold_c=1)

        # --- BLOCO DE EXPORTAÇÃO CSV ---
        with open(csv_path, mode='w', newline='', encoding='utf-8-sig') as arquivo_csv:
            writer = csv.writer(arquivo_csv, delimiter=';')

            # Cabeçalho do CSV
            writer.writerow(['Texto', 'Confianca', 'Centro_X', 'Centro_Y', 'Coords_Completas'])

            # Salvar textos do OCR
            for t, s, box in zip(txts, scores, boxes):
                if s > 0.6:
                    pts = np.array(box)
                    center_x = int(np.mean(pts[:, 0]))
                    center_y = int(np.mean(pts[:, 1]))
                    writer.writerow([t, f"{s:.4f}", center_x, center_y, box.tolist()])

            # Salvar barras duplas
            for barra in barras_duplas:
                writer.writerow([barra['txt'], f"{barra['conf']:.4f}", barra['cx'], barra['cy'], barra['coords']])

            print(f"\nSucesso! Arquivo CSV gerado em: {csv_path}")

        # --- DESENHAR LINHAS DETECTADAS NA IMAGEM ---
        image_cv = desenhar_linhas_detectadas(image_cv, barras_duplas)

        # Mostra a imagem final
        if len(boxes) > 0:
            img_resultado = desenhar_resultados(image_cv, boxes, txts, scores, font_path=font_path)
            cv2.imwrite('debug_final.png', img_resultado)  # Salva a imagem final para debug
            cv2.imshow("Resultado Final", img_resultado)
            print("\nPressione qualquer tecla na janela da imagem para fechar...")
            cv2.waitKey(0) 
            cv2.destroyAllWindows()
    else:
        print("Nenhum resultado retornado.")