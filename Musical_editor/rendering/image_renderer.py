# image_renderer.py - CORRIGIDO: Ordena por Y (linha), depois X (coluna)

import os
from PIL import Image, ImageDraw, ImageEnhance, ImageOps, ImageFont
from core.config import GLOBAL_CONFIG
from ui.graphics_items import NoteItem, LabelItem, HeaderBoxItem, TimeSigBoxItem
from core.logger import log_info, log_debug, log_error, log_warning

class ImageRenderer:
    def __init__(self, scene, image_paths):
        self.scene = scene
        self.image_paths = image_paths

    def render(self):
        """Renderiza preview da imagem final"""
        log_info("Iniciando renderizacao de preview")
        return self._render_internal(use_export_mode=False)

    def export_clean_sheet_with_crops(self):
        """Exporta folha limpa com recortes das silabas"""
        log_info("Iniciando exportacao de folha limpa")
        return self._render_internal(use_export_mode=True)

    def _render_internal(self, use_export_mode=False):
        """Logica interna compartilhada de renderizacao"""
        state = self.get_current_state()
        if not state:
            log_warning("Estado vazio, nada para renderizar")
            return None

        # Separar notas de headers/timesigs
        notes_and_tags = [item for item in state if item['type'] in ['NOTE', 'TAG']]

        if not notes_and_tags:
            log_warning("Nenhuma nota ou tag para renderizar")
            return None

        # ORDENAR: Agrupar por Y (linha), depois por X (coluna) dentro de cada linha
        notes_and_tags.sort(key=lambda n: n['y'])

        # Agrupar por linhas (Y similar)
        LINE_THRESHOLD = 80
        sorted_notes = []
        current_line = []

        if notes_and_tags:
            current_line.append(notes_and_tags[0])
            line_y_ref = notes_and_tags[0]['y']

            for i in range(1, len(notes_and_tags)):
                item = notes_and_tags[i]
                if abs(item['y'] - line_y_ref) < LINE_THRESHOLD:
                    current_line.append(item)
                else:
                    # Ordenar linha atual por X
                    current_line.sort(key=lambda n: n['x'])
                    sorted_notes.extend(current_line)
                    current_line = [item]
                    line_y_ref = item['y']

            # Ordenar ultima linha por X
            if current_line:
                current_line.sort(key=lambda n: n['x'])
                sorted_notes.extend(current_line)

        notes_and_tags = sorted_notes

        log_info("Notas ordenadas por Y (linha), depois X (coluna):")
        for idx, item in enumerate(notes_and_tags):
            log_debug(f"  {idx+1}. {item.get('t', 'N/A')} em Y={item.get('y', 0)}, X={item.get('x', 0)}")

        # Resto do codigo continua igual...
        PAGE_W = GLOBAL_CONFIG.get("PAGE_WIDTH", 2000)
        SPACING = GLOBAL_CONFIG.get("SPACING_NOTE", 160)
        CROP_W = GLOBAL_CONFIG.get("CROP_WIDTH", 60)
        CROP_H = GLOBAL_CONFIG.get("CROP_HEIGHT", 90)
        CROP_OFF_Y = GLOBAL_CONFIG.get("CROP_OFFSET_Y", 40)
        CROP_ZOOM = GLOBAL_CONFIG.get("CROP_ZOOM", 1.3)
        MARGIN_R = GLOBAL_CONFIG.get("RIGHT_MARGIN", 150)
        PAD_B = GLOBAL_CONFIG.get("BOTTOM_PADDING", 50)

        # Extrair retangulos especiais
        header_rect_coords = None
        timesig_rect_coords = None
        for item in self.scene.items():
            if isinstance(item, HeaderBoxItem):
                r = item.rect()
                p = item.pos()
                header_rect_coords = (p.x() + r.left(), p.y() + r.top(), p.x() + r.right(), p.y() + r.bottom())
            elif isinstance(item, TimeSigBoxItem):
                r = item.rect()
                p = item.pos()
                timesig_rect_coords = (p.x() + r.left(), p.y() + r.top(), p.x() + r.right(), p.y() + r.bottom())

        W, H = PAGE_W, max(4000, len(self.image_paths) * 4000)
        img_out = Image.new('RGB', (W, H), color='white')
        draw = ImageDraw.Draw(img_out)

        # Fontes
        try:
            font_note_name = ImageFont.truetype("arial.ttf", 18)
            font_tag = ImageFont.truetype("arial.ttf", 22)
        except:
            font_note_name = ImageFont.load_default()
            font_tag = ImageFont.load_default()

        # Carregar imagens
        source_images = []
        try:
            for path in self.image_paths:
                if os.path.exists(path):
                    src = Image.open(path).convert("RGBA")
                    source_images.append(src)
            log_debug(f"Imagens carregadas: {len(source_images)}")
        except Exception as e:
            log_error(f"Erro ao carregar imagens: {e}")
            return None

        if not source_images:
            log_error("Nenhuma imagem disponivel")
            return None

        # ---------------------------------------------------------
        # 1. CABECALHO
        # ---------------------------------------------------------
        header_height_pasted = 0
        if source_images and header_rect_coords:
            log_info("Processando cabecalho")
            first_img = source_images[0]
            hx1, hy1, hx2, hy2 = header_rect_coords
            hy1 = max(0, int(hy1))
            hy2 = min(first_img.height, int(hy2))
            hx1 = max(0, int(hx1))
            hx2 = min(first_img.width, int(hx2))

            if hy2 > hy1 and hx2 > hx1:
                header_crop = first_img.crop((hx1, hy1, hx2, hy2))
                new_hw = int(header_crop.width * CROP_ZOOM)
                new_hh = int(header_crop.height * CROP_ZOOM)
                header_crop = header_crop.resize((new_hw, new_hh), Image.Resampling.LANCZOS)
                enhancer = ImageEnhance.Contrast(header_crop)
                header_crop = enhancer.enhance(2.0)
                header_crop = ImageOps.grayscale(header_crop).convert("RGB")
                paste_x = int((W - new_hw) // 2)
                img_out.paste(header_crop, (paste_x, 0))
                header_height_pasted = new_hh
                log_debug(f"Cabecalho: {new_hw}x{new_hh}")

        start_y_offset = header_height_pasted + 100
        cursor_x = 100
        cursor_y_staff_center = start_y_offset
        row_height = 450
        current_y_ref = notes_and_tags[0]['y'] if notes_and_tags else 0

        # ---------------------------------------------------------
        # 2. COMPASSO
        # ---------------------------------------------------------
        if source_images and timesig_rect_coords:
            log_info("Processando compasso")
            first_img = source_images[0]
            tx1, ty1, tx2, ty2 = timesig_rect_coords
            tx1 = max(0, int(tx1))
            tx2 = min(first_img.width, int(tx2))
            ty1 = max(0, int(ty1))
            ty2 = min(first_img.height, int(ty2))

            if tx2 > tx1 and ty2 > ty1:
                ts_crop = first_img.crop((tx1, ty1, tx2, ty2))
                new_w = int(ts_crop.width * CROP_ZOOM)
                new_h = int(ts_crop.height * CROP_ZOOM)
                ts_crop = ts_crop.resize((new_w, new_h), Image.Resampling.LANCZOS)
                enhancer = ImageEnhance.Contrast(ts_crop)
                ts_crop = enhancer.enhance(2.0)
                ts_crop = ImageOps.grayscale(ts_crop).convert("RGB")
                dest_y_ts = int(cursor_y_staff_center - (new_h // 2))
                img_out.paste(ts_crop, (cursor_x, dest_y_ts))
                cursor_x += new_w + 50
                log_debug(f"Compasso: {new_w}x{new_h}")

        # ---------------------------------------------------------
        # 3. NOTAS E TAGS (ORDENADAS POR Y, DEPOIS X)
        # ---------------------------------------------------------
        for item in notes_and_tags:
            item_y = item['y']

            # Quebra de linha
            if item_y > current_y_ref + 150:
                cursor_y_staff_center += row_height
                cursor_x = 100
                current_y_ref = item_y

            if item['type'] == 'TAG':
                tag_text = item['t'].replace("TAG_", "")
                bg_color = "#3498db"
                if "CORO" in tag_text:
                    bg_color = "#e67e22"
                elif "FINAL" in tag_text:
                    bg_color = "#27ae60"
                elif "VERSO" in tag_text:
                    bg_color = "#2980b9"

                tag_w, tag_h = 100, 40
                tag_x1 = cursor_x
                tag_y1 = cursor_y_staff_center - 20
                tag_x2 = tag_x1 + tag_w
                tag_y2 = tag_y1 + tag_h

                draw.rectangle([tag_x1, tag_y1, tag_x2, tag_y2], fill=bg_color, outline=None)
                bbox = draw.textbbox((0, 0), tag_text, font=font_tag)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
                text_x = tag_x1 + (tag_w - text_w) / 2
                text_y = tag_y1 + (tag_h - text_h) / 2 - 2
                draw.text((text_x, text_y), tag_text, fill="white", font=font_tag)
                cursor_x += GLOBAL_CONFIG.get("SPACING_TAG", 220)
                log_debug(f"Tag '{tag_text}' adicionada")

            else:  # NOTE
                display_name = item['t'].replace("_", " ").title()
                try:
                    draw.text((cursor_x, cursor_y_staff_center - 70), display_name, fill="black", font=font_note_name, anchor="mb")
                except ValueError:
                    draw.text((cursor_x - 30, cursor_y_staff_center - 90), display_name, fill="black", font=font_note_name)

                # Recorte da silaba
                if not any(x in item['t'] for x in ["PAUSA", "RESPIRACAO"]):
                    local_w = item.get('cp', {}).get('w', CROP_W) if 'cp' in item else CROP_W
                    local_h = item.get('cp', {}).get('h', CROP_H) if 'cp' in item else CROP_H
                    local_y = item.get('cp', {}).get('y', CROP_OFF_Y) if 'cp' in item else CROP_OFF_Y

                    accumulated_y = 0
                    source_img_to_use = None
                    relative_y = 0

                    for src_img in source_images:
                        h = src_img.height
                        if accumulated_y <= item_y < (accumulated_y + h + 20):
                            source_img_to_use = src_img
                            relative_y = item_y - accumulated_y
                            break
                        accumulated_y += h + 20

                    if source_img_to_use:
                        crop_x1 = int(item['x'] - local_w // 2)
                        crop_y1 = int(relative_y + local_y)
                        crop_x2 = int(item['x'] + local_w // 2)
                        crop_y2 = int(relative_y + local_y + local_h)

                        crop_x1 = max(0, crop_x1)
                        crop_y1 = max(0, crop_y1)
                        crop_x2 = min(source_img_to_use.width, crop_x2)
                        crop_y2 = min(source_img_to_use.height, crop_y2)

                        if crop_x2 > crop_x1 and crop_y2 > crop_y1:
                            cropped_text = source_img_to_use.crop((crop_x1, crop_y1, crop_x2, crop_y2))
                            new_text_w = int(cropped_text.width * CROP_ZOOM)
                            new_text_h = int(cropped_text.height * CROP_ZOOM)
                            cropped_text = cropped_text.resize((new_text_w, new_text_h), Image.Resampling.LANCZOS)
                            enhancer = ImageEnhance.Contrast(cropped_text)
                            cropped_text = enhancer.enhance(1.5)
                            dest_x = int(cursor_x - (new_text_w // 2))
                            dest_y = int(cursor_y_staff_center + 65)
                            img_out.paste(cropped_text, (dest_x, dest_y))

                cursor_x += SPACING

            # Quebra de linha horizontal
            if cursor_x > W - MARGIN_R:
                cursor_x = 100
                cursor_y_staff_center += row_height

        # Cortar imagem
        img_inverted = ImageOps.invert(img_out.convert('RGB'))
        bbox = img_inverted.getbbox()
        if bbox:
            crop_h = min(H, bbox[3] + PAD_B)
            img_out = img_out.crop((0, 0, W, crop_h))

        log_info("Renderizacao concluida com sucesso")
        return img_out

    def get_current_state(self):
        """Retorna estado atual da cena"""
        raw = []
        for i in self.scene.items():
            if isinstance(i, (NoteItem, LabelItem)):
                d = {
                    'type': 'NOTE' if isinstance(i, NoteItem) else 'TAG',
                    't': i.tipo,
                    'x': i.x(),
                    'y': i.y()
                }
                if hasattr(i, 'custom_crop_params') and i.custom_crop_params:
                    d['cp'] = i.custom_crop_params
                raw.append(d)
            elif isinstance(i, HeaderBoxItem):
                r = i.rect()
                raw.append({
                    'type': 'HEADER',
                    'r': (i.x(), i.y(), i.x() + r.width(), i.y() + r.height()),
                    'x': i.x(),
                    'y': i.y()
                })
            elif isinstance(i, TimeSigBoxItem):
                r = i.rect()
                raw.append({
                    'type': 'TIME',
                    'r': (i.x(), i.y(), i.x() + r.width(), i.y() + r.height()),
                    'x': i.x(),
                    'y': i.y()
                })
        log_debug(f"Estado atual tem {len(raw)} itens")
        return raw
