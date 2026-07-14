import os
import json
import re
from config import config_manager, HINOS_FOLDER_PATH

# --- CONSTANTES MUSICAIS ---
NOTE_DURATIONS_BASE = {
    "sm": 1.0, "m": 2.0, "c": 0.5, "sc": 0.25, "sb": 4.0, "cp": 0.75, 
    "rl": 0.0, "rc": 0.0, "pc": 0.0, "pl": 0.0 
}
NOTE_CODES = list(NOTE_DURATIONS_BASE.keys()) + [f"{k}_fermata" for k in NOTE_DURATIONS_BASE.keys() if k not in ["rl", "rc", "pc", "pl"]]

# --- FUNÇÕES ---

def get_syllable_tokens(text_line):
    """ Separa tokens (palavras e pausas). A vírgula é ignorada. """
    padrao = r'(__|\'\'|[_"\-]|\s+)'
    tokens_raw = re.split(padrao, text_line)
    lista_final = []
    for token in tokens_raw:
        if not token: continue
        token_limpo = token.strip()
        if token_limpo == '': pass
        elif token == '-':
            if lista_final: lista_final[-1] += "-"
            else: lista_final.append("-")
        else:
            simbolos_pausa = ["''", '"', "_", "__"]
            if token_limpo in simbolos_pausa: lista_final.append(token_limpo)
            else:
                limpo = re.sub(r'[^\w\',~\-.;:!?]', '', token) 
                if limpo or token_limpo in [",", ";", ".", "!", "?", ":"]: 
                    lista_final.append(token)
    return lista_final

def ler_arquivo_hino(num):
    for f in [f"hino_{num:03d}.json", f"hino_{num}.json"]:
        p = os.path.join(HINOS_FOLDER_PATH, f)
        if os.path.exists(p):
            try: 
                with open(p, 'r', encoding='utf-8') as file: return json.load(file)
            except: pass
    return None

def carregar_dados_json():
    if not os.path.exists(HINOS_FOLDER_PATH): 
        try: os.makedirs(HINOS_FOLDER_PATH)
        except: pass
        return 0
    max_n = 0
    pat = re.compile(r"^hino_(\d+)")
    for f in os.listdir(HINOS_FOLDER_PATH):
        m = pat.match(f)
        if m: max_n = max(max_n, int(m.group(1)))
    return max_n

def calcular_duracao_ms(code, bpm, unidade_bpm="sm"):
    if bpm <= 0: return 500
    nota_code = code.strip().lower()
    fermata = "_fermata" in nota_code
    if fermata: nota_code = nota_code.replace("_fermata", "")

    # Tempos fixos
    if nota_code == 'rc': return config_manager.get('time_rc', int) or 300
    if nota_code == 'pc': return config_manager.get('time_pc', int) or 500
    if nota_code == 'rl': return config_manager.get('time_rl', int) or 800
    if nota_code == 'pl': return config_manager.get('time_pl', int) or 1000

    # Cálculo matemático
    ms_por_batida = 60000 / bpm
    valor_base_unidade = NOTE_DURATIONS_BASE.get(unidade_bpm, 1.0)
    ms_seminima = ms_por_batida / valor_base_unidade
    fator_nota = NOTE_DURATIONS_BASE.get(nota_code, 1.0)
    ms = ms_seminima * fator_nota
    
    if fermata: ms *= config_manager.get('fermata_factor', float)
    
    return max(50, int(ms))