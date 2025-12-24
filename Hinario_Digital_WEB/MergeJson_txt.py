import json
import re
import os
import glob

# ===================== CONFIGURAÇÃO =====================
INPUT_FOLDER = r"C:\Users\psoares\pyNestle\Private\Hinario_Digital\json_notas"
OUTPUT_FOLDER = r"C:\Users\psoares\pyNestle\Private\Hinario_Digital\json_final"

# ===================== 1. LISTA DE NOTAS ACEITAS =====================
VALID_NOTES = [
    "SEMIBREVE", "MINIMA", "MINIMA PONTUADA",
    "SEMINIMA", "SEMINIMA PONTUADA",
    "COLCHEIA", "COLCHEIA PONTUADA",
    "SEMICOLCHEIA", "SEMICOLCHEIA PONTUADA",
    "RESPIRACAO CURTA", "RESPIRACAO LONGA",
    "PAUSA SEMIBREVE", "PAUSA MINIMA", 
    "PAUSA SEMINIMA", "PAUSA COLCHEIA", "PAUSA SEMICOLCHEIA",
    "FERMATA MINIMA", "FERMATA SEMINIMA", "FERMATA COLCHEIA"
]

# ===================== 2. ORDENAÇÃO VISUAL INTELIGENTE =====================
def sort_visually(raw_items):
    """
    Agrupa notas em linhas visuais (com tolerância de altura) 
    e ordena da esquerda para a direita dentro de cada linha.
    """
    if not raw_items: return []

    # 1. Ordena tudo puramente por Y para facilitar o agrupamento
    # Isso coloca as linhas em ordem, mas mistura o X dentro delas se estiverem desalinhadas
    pre_sorted = sorted(raw_items, key=lambda i: i['y'])

    final_sorted_list = []
    current_line_items = []
    
    # Pega o Y do primeiro item como referência da primeira linha
    line_y_ref = pre_sorted[0]['y']
    
    # Tolerância de altura para considerar "mesma linha" (80 pixels é seguro para pautas)
    Y_THRESHOLD = 80 

    for item in pre_sorted:
        # Se a nota está próxima verticalmente da referência, pertence à mesma linha
        if abs(item['y'] - line_y_ref) < Y_THRESHOLD:
            current_line_items.append(item)
        else:
            # A nota está muito longe, então é uma NOVA linha.
            # 1. Ordena a linha anterior por X (Esquerda -> Direita) e salva
            current_line_items.sort(key=lambda i: i['x'])
            final_sorted_list.extend(current_line_items)
            
            # 2. Começa a nova linha com o item atual
            current_line_items = [item]
            line_y_ref = item['y']

    # Não esquecer de adicionar a última linha processada
    if current_line_items:
        current_line_items.sort(key=lambda i: i['x'])
        final_sorted_list.extend(current_line_items)

    return final_sorted_list

def extract_melodies_from_editor(editor_json):
    raw_items = editor_json.get('notas', [])
    
    # APLICA A NOVA ORDENAÇÃO
    sorted_items = sort_visually(raw_items)

    melodies = {'Estrofe': [], 'Coro': []}
    current_section = 'Estrofe' 

    for item in sorted_items:
        tipo = item['tipo']
        
        # Estrutura
        if "TAG_" in tipo:
            if "CORO" in tipo: current_section = 'Coro'
            elif "VERSO" in tipo: current_section = 'Estrofe'
            continue

        # Notas
        if tipo in VALID_NOTES:
            melodies[current_section].append(tipo)
        elif "FERMATA" in tipo:
            melodies[current_section].append(tipo)

    # Limpeza preventiva (Auto-Fix)
    for sec in melodies:
        while melodies[sec] and ("RESPIRACAO" in melodies[sec][0] or "PAUSA" in melodies[sec][0]):
            removido = melodies[sec].pop(0)
            print(f"   [AUTO-FIX] Removido '{removido}' do início de {sec}")

    return melodies

# ===================== 3. PROCESSAMENTO DE TEXTO =====================
def processar_texto_tokenizado(texto):
    # 1. Tratamos os hifens para que fiquem isolados mas identificáveis
    # 2. Símbolos especiais removidos conforme solicitado anteriormente
    # 3. Pontuação grudada na palavra anterior
    # 4. Incluímos ~ e ' como parte da sílaba (ligação e apóstrofo considerados como uma única sílaba)
    
    # Regex que encontra palavras (podendo incluir ~ e ', com pontuação opcional) ou hifens isolados
    padrao = r"([\w\u00C0-\u00FF~']+[.,;?!:]*|-)"
    
    tokens_raw = re.findall(padrao, texto)
    lista_final = []
    
    for t in tokens_raw:
        if t.strip():
            lista_final.append(t)
            
    return lista_final

def parse_metadata_and_structure(text):
    lines = text.strip().split('\n')
    header = lines[0]
    
    title_m = re.search(r'Title: (.*?) \|', header)
    num_m = re.search(r'Number: (\d+)', header)
    bpm_m = re.search(r'Tempo: .*?(\d+)', header)
    time_m = re.search(r'Time Signature: ([\d/]+)', header)
    
    bpm = int(bpm_m.group(1)) if bpm_m else 60
    compasso = time_m.group(1) if time_m else "4/4"
    
    full_title = "Hino"
    if num_m and title_m:
        full_title = f"{num_m.group(1)}. {title_m.group(1).upper()}"

    blocks = []
    chunks = re.split(r'===\s*(.*?)\s*===', text)
    
    for i in range(1, len(chunks), 2):
        block_title = chunks[i].upper()
        content = chunks[i+1].strip()
        
        if "CHORUS" in block_title or "CORO" in block_title or "REFRAIN" in block_title:
            b_type = "Coro"
            b_num = 0
        else:
            b_type = "Estrofe"
            nums = re.findall(r'\d+', block_title)
            b_num = int(nums[0]) if nums else 1
            
        lines_clean = [l.strip() for l in content.split('\n') if l.strip()]
        
        lines_final = []
        for l in lines_clean:
            if "Title:" in l or "Author:" in l or "Time Signature:" in l:
                continue
            
            l_no_num = re.sub(r'^[\d\.\s\'"]+', '', l)
            if l_no_num:
                lines_final.append(l_no_num)
        
        blocks.append((b_type, b_num, lines_final))
        
    return full_title, bpm, compasso, blocks

# ===================== 4. SINCRONIZADOR =====================
def synchronize(editor_data, metadata_text):
    melodies_source = extract_melodies_from_editor(editor_data)
    title, bpm, compasso, text_blocks = parse_metadata_and_structure(metadata_text)
    
    json_estrofes = []
    
    for b_type, b_num, lines in text_blocks:
        raw_notes = melodies_source.get(b_type, [])
        if not raw_notes and b_type == 'Coro':
            raw_notes = melodies_source.get('Estrofe', [])
            
        note_cursor = 0
        total_notes = len(raw_notes)
        json_lines = []
        
        for text_line in lines:
            tokens = processar_texto_tokenizado(text_line)
            silabas = []
            
            i = 0
            while i < len(tokens):
                token = tokens[i]
                
                if token == "-":
                    # Grudar ao anterior, se existir
                    if silabas:
                        silabas[-1]["texto"] += "-"
                    i += 1
                    continue
                
                # Adicionar respirações/pausas/fermatas antes da sílaba
                while note_cursor < total_notes and ("RESPIRACAO" in raw_notes[note_cursor] or "PAUSA" in raw_notes[note_cursor] or "FERMATA" in raw_notes[note_cursor]):
                    nota = raw_notes[note_cursor]
                    silabas.append({"texto": "", "nota": nota})
                    note_cursor += 1
                
                # Atribuir nota à sílaba
                if note_cursor < total_notes:
                    nota = raw_notes[note_cursor]
                    silabas.append({"texto": token.replace("~", "‿"), "nota": nota})  # Substituição visual mantida
                    note_cursor += 1
                else:
                    silabas.append({"texto": token.replace("~", "‿"), "nota": "SEMINIMA"})
                
                i += 1
            
            # Após a última sílaba da linha, adicionar respirações/pausas/fermatas restantes (se houver) ao final da linha
            while note_cursor < total_notes and ("RESPIRACAO" in raw_notes[note_cursor] or "PAUSA" in raw_notes[note_cursor] or "FERMATA" in raw_notes[note_cursor]):
                nota = raw_notes[note_cursor]
                silabas.append({"texto": "", "nota": nota})
                note_cursor += 1
            
            json_lines.append({"silabas": silabas})
        
        # Se sobrar notas após todas as linhas (ex: pausas no final do bloco), adicionar uma linha extra vazia com elas
        if note_cursor < total_notes:
            silabas_extra = []
            while note_cursor < total_notes:
                nota = raw_notes[note_cursor]
                if "RESPIRACAO" in nota or "PAUSA" in nota or "FERMATA" in nota:
                    silabas_extra.append({"texto": "", "nota": nota})
                else:
                    # Nota normal sobrando sem sílaba: adicionar como vazia ou ignorar? Aqui adicionamos como vazia
                    silabas_extra.append({"texto": "", "nota": nota})
                note_cursor += 1
            if silabas_extra:
                json_lines.append({"silabas": silabas_extra})
        
        json_estrofes.append({
            "numero": b_num,
            "tipo": b_type,
            "linhas": json_lines
        })
        
    return {
        "titulo": title, "BPM": bpm, "compasso": compasso, "estrofes": json_estrofes
    }

# ===================== 5. EXECUÇÃO =====================
def process_batch():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    json_files = glob.glob(os.path.join(INPUT_FOLDER, "*.json"))
    
    if not json_files:
        print(f"Nenhum JSON encontrado em: {INPUT_FOLDER}")
        return

    print(f"Processando {len(json_files)} hinos (Ordenação Visual Inteligente)...")

    for json_path in json_files:
        filename = os.path.basename(json_path)
        base_name = os.path.splitext(filename)[0]
        txt_path = os.path.join(INPUT_FOLDER, base_name + ".txt")
        
        if not os.path.exists(txt_path):
            print(f"⚠️  TXT faltando para: {filename}")
            continue
            
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                editor_data = json.load(f)
            with open(txt_path, 'r', encoding='utf-8') as f:
                metadata_text = f.read()
                
            final_obj = synchronize(editor_data, metadata_text)
            
            output_path = os.path.join(OUTPUT_FOLDER, base_name + ".json")
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(final_obj, f, indent=4, ensure_ascii=False)
                
            print(f"✅ Gerado: {base_name}.json")
            
        except Exception as e:
            print(f"❌ Erro em {base_name}: {e}")

if __name__ == "__main__":
    process_batch()