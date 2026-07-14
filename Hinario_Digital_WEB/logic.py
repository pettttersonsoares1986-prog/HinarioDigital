import os
import json
import re
from config import config_manager, HINOS_FOLDER_PATH

# --- CONSTANTES DE ESTRUTURA (Para referência ou uso futuro) ---
TAGS_ESTRUTURA = ["TAG_VERSO", "TAG_CORO", "TAG_FINAL"]

# --- DEFINIÇÃO DE VALORES DE DURAÇÃO (Base: Seminima = 1.0) ---
# Aqui usamos EXATAMENTE os nomes que você forneceu.
NOTE_DURATIONS_BASE = {
    # Notas Simples
    "SEMIBREVE": 4.0,
    "MINIMA": 2.0,
    "SEMINIMA": 1.0,
    "COLCHEIA": 0.5,
    "SEMICOLCHEIA": 0.25,

    # Notas Pontuadas (Valor + 50%)
    "MINIMA PONTUADA": 3.0,
    "SEMINIMA PONTUADA": 1.5,
    "COLCHEIA PONTUADA": 0.75,
    "SEMICOLCHEIA PONTUADA": 0.375,

    # Pausas (Mesma duração das notas, mas som mudo)
    "PAUSA SEMIBREVE": 4.0,
    "PAUSA MINIMA": 2.0,
    "PAUSA SEMINIMA": 1.0,
    "PAUSA COLCHEIA": 0.5,
    "PAUSA SEMICOLCHEIA": 0.25,

    # Pausas Pontuadas
    "PAUSA SEMINIMA PONTUADA": 1.5,
    "PAUSA COLCHEIA PONTUADA": 0.75,
    "PAUSA SEMICOLCHEIA PONTUADA": 0.375,

    # Outros (Tempos fixos ou especiais)
    "RESPIRACAO CURTA": 0.0, # Tempo definido em config
    "RESPIRACAO LONGA": 0.0, # Tempo definido em config

    # Fermatas (Baseadas na nota original, o cálculo aplica o fator depois)
    "FERMATA MINIMA": 2.0,
    "FERMATA SEMINIMA": 1.0,
    "FERMATA COLCHEIA": 0.5
}

# Lista ordenada para aparecer nos ComboBoxes do Editor
NOTE_CODES = list(NOTE_DURATIONS_BASE.keys())

# --- FUNÇÕES ---

def get_syllable_tokens(text_line):
    """ Separa tokens (palavras e pausas). """
    if text_line is None: return []
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
                lista_final.append(token)
    return lista_final

def ler_arquivo_hino(numero):
    """
    Lê o JSON diretamente. Não precisa mais converter nada,
    pois o JSON já está no formato que o código entende.
    """
    caminho = os.path.join(HINOS_FOLDER_PATH, f"{numero}.json")

    # Fallback para formato antigo hino_001 se necessário
    if not os.path.exists(caminho):
        caminho_antigo = os.path.join(HINOS_FOLDER_PATH, f"hino_{numero:03d}.json")
        if os.path.exists(caminho_antigo):
            caminho = caminho_antigo
        else:
            return None

    try:
        with open(caminho, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Adaptação leve: Se o JSON vier com "silabas", transformamos para
        # listas planas (texto_silabado e notas_codes) para facilitar o Player/Editor,
        # mas mantendo os nomes originais ("SEMINIMA", etc).
        if 'estrofes' in data:
            for estrofe in data['estrofes']:
                linhas = estrofe.get('linhas', [])
                for linha in linhas:
                    if 'silabas' in linha:
                        # Extrai as listas planas
                        txts = []
                        notas = []
                        for s in linha['silabas']:
                            t = s.get('texto')
                            n = s.get('nota', 'SEMINIMA') # Default seguro

                            # Normaliza para Maiúsculas para garantir match com NOTE_DURATIONS_BASE
                            n = n.upper() 

                            if t is not None: txts.append(t)
                            notas.append(n)

                        # Reconstrói texto concatenado
                        texto_final = ""
                        for i, t in enumerate(txts):
                            texto_final += t
                            if i < len(txts) - 1 and not t.endswith('-'):
                                texto_final += " "

                        linha['texto_silabado'] = texto_final
                        linha['notas_codes'] = notas

        return data

    except Exception as e:
        print(f"Erro ao ler hino {numero}: {e}")
        return None

def calcular_duracao_ms(nota_nome, bpm, unidade_bpm="SEMINIMA"):
    """ Calcula duração em ms baseada no nome completo da nota. """
    if bpm <= 0: return 500

    nota_nome = nota_nome.upper() # Garante consistência

    # Tempos fixos (Respirações/Pausas específicas se configuradas)
    if "RESPIRACAO CURTA" in nota_nome: return config_manager.get('time_rc', int) or 300
    if "RESPIRACAO LONGA" in nota_nome: return config_manager.get('time_rl', int) or 800
    if "PAUSA CURTA" in nota_nome: return config_manager.get('time_pc', int) or 500 # Caso usem nomes antigos

    # Verifica se é Fermata para aplicar fator extra
    is_fermata = "FERMATA" in nota_nome

    # Pega a duração base do dicionário
    fator_nota = NOTE_DURATIONS_BASE.get(nota_nome, 1.0)

    # Cálculo matemático
    ms_por_batida = 60000 / bpm
    valor_base_unidade = NOTE_DURATIONS_BASE.get(unidade_bpm, 1.0)

    ms_seminima = ms_por_batida / valor_base_unidade
    ms = ms_seminima * fator_nota

    if is_fermata:
        ms *= config_manager.get('fermata_factor', float) or 2.0

    return max(50, int(ms))
