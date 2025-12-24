import json
import re
import os

# ===================== CAMINHOS (Não alterados) =====================
CONFIG_FILE = r'C:\Users\psoares\pyNestle\Private\Hinario_Digital\musicos_textos_corrigidos\config.txt'
DATA_FILE_RHYTHM = r'C:\Users\psoares\pyNestle\Private\Hinario_Digital\textos_corrigidos\1_notas.txt'
DATA_FILE_TEXT = r'C:\Users\psoares\pyNestle\Private\Hinario_Digital\textos_corrigidos\hino_001.txt'
OUTPUT_FILE = r'C:\Users\psoares\pyNestle\Private\Hinario_Digital\musicos_textos_corrigidos\hino_001_COMPLETO.json'

# ===================== 1. CARREGA CONFIG (Não alterado) =====================
def carregar_config():
    config = {'MAPA_DURACAO': {}, 'BPM': 61}
    
    # --- Lógica de leitura e parsing de CONFIG_FILE (mantida) ---
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            for linha in f:
                linha = linha.strip()
                if not linha or linha.startswith('#'):
                    continue
                if '#' in linha:
                    linha = linha.split('#', 1)[0].strip()
                if ':' not in linha:
                    continue
                    
                chave, valor_str = linha.split(':', 1)
                chave = chave.strip().lower()
                valor_str = valor_str.strip()
                
                try:
                    if chave == 'bpm':
                        config['BPM'] = int(valor_str)
                    elif chave == 'unidade_tempo' or chave == 'metro_inferior':
                        continue # Ignora
                    else:
                        config['MAPA_DURACAO'][chave] = float(valor_str)
                except ValueError:
                    print(f"Valor ignorado (não é número): {chave} = {valor_str}")
                    continue
    except FileNotFoundError:
        print(f"AVISO: Arquivo de configuração não encontrado em {CONFIG_FILE}. Usando valores padrão.")


    # Garante valores padrão
    defaults = {
        'sm': 1.0, 'm': 2.0, 'c': 0.5, 'sc': 0.25, 'Sm': 4.0,
        'cp': 0.75, 'rc': 0.0, 'rl': 0.0, '_fermata': 1.5
    }
    # Corrigi 'sb' para 'Sm' (Semibreve) para seguir o padrão do seu arquivo 1_notas.txt
    
    for k, v in defaults.items():
        # Usa o valor da configuração se existir, senão o default.
        if k == 'sb' and 'Sm' not in config['MAPA_DURACAO']:
            config['MAPA_DURACAO']['Sm'] = v
        elif k not in config['MAPA_DURACAO']:
            config['MAPA_DURACAO'][k] = v
    
    print("CONFIGURAÇÃO CARREGADA COM SUCESSO!")
    print(f"   BPM: {config['BPM']}")
    print(f"   Figuras carregadas: {list(config['MAPA_DURACAO'].keys())}")
    print("   Esta configuração será usada em TODAS as estrofes!\n")
    return config

# ===================== 2. LÊ RITMO (Não alterado) =====================
def ler_ritmo():
    # --- Lógica de leitura de DATA_FILE_RHYTHM (mantida) ---
    with open(DATA_FILE_RHYTHM, 'r', encoding='utf-8') as f:
        linhas = [l.strip().lower() for l in f if l.strip() and ',' in l]
    ritmo = [[s.strip() for s in linha.split(',') if s.strip()] for linha in linhas]
    print(f"Ritmo carregado: {len(ritmo)} linhas (repetirá para cada estrofe)")
    return ritmo

# ===================== 3. SEPARA ESTROFES (Não alterado) =====================
def separar_estrofes():
    # --- Lógica de leitura de DATA_FILE_TEXT (mantida) ---
    with open(DATA_FILE_TEXT, 'r', encoding='utf-8') as f:
        linhas = [l.strip() for l in f.readlines() if l.strip()]

    titulo = linhas[0]
    estrofes = []
    estrofe_atual = []
    numero = 1

    for linha in linhas[1:]:
        if re.match(r'^\d+[\.\)]', linha):
            if estrofe_atual:
                estrofes.append((numero, estrofe_atual))
                numero += 1
                estrofe_atual = []
        
        # Remove a numeração (se houver) e quebras de linha
        texto = re.sub(r'^\d+[\.\)]\s*', '', linha).strip()
        if texto:
            estrofe_atual.append(texto)

    if estrofe_atual:
        estrofes.append((numero, estrofe_atual))

    print(f"Título: {titulo}")
    print(f"Estrofes detectadas: {len(estrofes)} → {[n for n,_ in estrofes]}")
    return titulo, estrofes

# ===================== 4. SINCRONIZAÇÃO COM VALIDAÇÃO (MODIFICADA) =====================
def sincronizar(ritmo_base, estrofes, config):
    """
    Sincroniza o texto com o ritmo.
    MODIFICAÇÃO: Armazena o CÓDIGO DE NOTA no novo campo 'notas_codes', 
    em vez de milissegundos.
    """
    MAPA = config['MAPA_DURACAO']
    # Cálculo da duração base da semínima em ms (apenas para exibição de debug)
    ms_por_semiminima = (60 / config['BPM']) * 1000 
    json_estrofes = []
    idx_ritmo = 0

    print("\n" + "="*95)
    print("VALIDAÇÃO DETALHADA - NOTAS MUSICAIS SALVAS NO JSON")
    print("="*95)

    for num_estrofe, linhas_texto in estrofes:
        print(f"\n{'='*25} ESTROFE {num_estrofe} {'='*25}")
        json_linhas = []

        for i, texto in enumerate(linhas_texto, 1):
            
            # Pega a linha de ritmo correspondente (repetindo se necessário)
            simbolos = ritmo_base[idx_ritmo % len(ritmo_base)]
            idx_ritmo += 1

            # Divide o texto em sílabas/palavras (tokens que receberão nota)
            silabas = [s.strip('.,;:!?') for s in texto.replace('-', ' ').split() if s]
            out_silabas = []
            
            # 🟢 NOVO CAMPO: Armazenará os códigos de nota musical (sm, c, Sm, etc.)
            notas_codes = [] 
            j = 0 # Índice da sílaba/palavra

            print(f"   Linha {i}: \"{texto}\" (Sílabas esperadas: {len(silabas)})")

            # Itera sobre os símbolos do ritmo
            for simb in simbolos:
                base = simb.split('_')[0]
                fermata = '_fermata' in simb
                dur_rel = MAPA.get(base, 0.0)
                
                # --- Cálculo de MS para DEBUG/LOG APENAS ---
                if fermata:
                    dur_rel *= MAPA.get('_fermata', 1.5)
                ms_val = int(round(dur_rel * ms_por_semiminima))
                figura = simb.upper().replace('_FERMATA', '♪')
                
                # É uma nota (não pausa) E ainda há sílabas para consumir
                if dur_rel > 0 and j < len(silabas):
                    print(f"      OK  {silabas[j]:15} → {figura:10} = {ms_val:5}ms (NOTA: {simb})")
                    out_silabas.append(silabas[j])
                    
                    # 🟢 ARMAZENA O CÓDIGO DA NOTA (em minúsculas, como esperado)
                    notas_codes.append(simb) 
                    j += 1
                    
                # É uma nota (não pausa), mas não há mais sílabas (Excesso de notas)
                elif dur_rel > 0:
                    print(f"      ERRO EXCESSO → {figura:10} = {ms_val:5}ms (IGNORADO)")
                    # Não armazena código nem sílaba
                    out_silabas.append("") 
                    
                # É uma pausa (dur_rel == 0)
                else:
                    print(f"      Pausa → {figura:10} (IGNORADO)")
                    # Não armazena código nem sílaba
                    # A pausa musical não é sincronizada com texto, apenas notas.

            # AVISO: Sílabas soltas (faltou nota)
            while j < len(silabas):
                default_note = 'sm'
                print(f"      AVISO SÍLABA SOLTA → {silabas[j]} (USANDO {default_note.upper()})")
                out_silabas.append(silabas[j])
                
                # 🟢 Adiciona nota Semínima (sm) como padrão para sílabas sem ritmo
                notas_codes.append(default_note) 
                j += 1
            
            # 🟢 CRIA O OBJETO DA LINHA COM O NOVO CAMPO 'notas_codes'
            json_linhas.append({
                "texto_silabado": " ".join([s for s in out_silabas if s]), 
                "notas_codes": notas_codes
            })

        json_estrofes.append({"numero": num_estrofe, "linhas": json_linhas})

    print("\n" + "="*95)
    print(f"GLÓRIA A DEUS! {len(json_estrofes)} ESTROFES FORAM PROCESSADAS COM SUCESSO!")
    return json_estrofes

# ===================== 5. EXECUÇÃO =====================
if __name__ == "__main__":
    try:
        print("INICIANDO PROCESSAMENTO DO HINO 001\n")
        
        config = carregar_config()
        ritmo = ler_ritmo()
        titulo, estrofes = separar_estrofes()
        resultado = sincronizar(ritmo, estrofes, config)

        # 🟢 REMOVE 'tempo_unidade_ms' do JSON, pois o player fará o cálculo dinâmico.
        json_final = {
            "titulo": titulo,
            "BPM": config['BPM'],
            "unidade_metrica": "semínima",
            "estrofes": resultado
        }

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(json_final, f, indent=4, ensure_ascii=False)

        print(f"\nJSON GERADO COM SUCESSO!")
        print(f"Arquivo: {OUTPUT_FILE}")
        print("O campo 'notas_codes' garantirá o sincronismo dinâmico.")

    except Exception as e:
        print(f"\nERRO: {e}")
        import traceback
        traceback.print_exc()