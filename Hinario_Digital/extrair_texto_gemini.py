import json
import re
import os

# ===================== CAMINHOS =====================
BASE_PATH = r'C:\Users\psoares\pyNestle\Private\Hinario_Digital'
DATA_FILE_RHYTHM = os.path.join(BASE_PATH, 'textos_corrigidos', '3_notas.txt')
DATA_FILE_TEXT = os.path.join(BASE_PATH, 'textos_corrigidos', 'hino_003.txt')
OUTPUT_FILE = os.path.join(BASE_PATH, 'textos_corrigidos', 'hino_003.json')

# ===================== CONFIGURAÇÕES =====================
BPM_PADRAO = 60
COMPASSO_PADRAO = "4/4"

# ===================== 1. LÊ RITMO (SEPARADO POR TIPO) =====================
def ler_ritmo_estruturado():
    """
    Lê o arquivo de notas e separa em dois grupos: 'Estrofe' e 'Coro'.
    Baseia-se em cabeçalhos no arquivo txt (ex: "Estrofes", "Coro").
    """
    dados = {'Estrofe': [], 'Coro': []}
    chave_atual = 'Estrofe' # Padrão inicial

    try:
        with open(DATA_FILE_RHYTHM, 'r', encoding='utf-8') as f:
            for linha in f:
                linha_limpa = linha.strip()
                if not linha_limpa: continue

                # Detecta cabeçalhos
                if 'coro' in linha_limpa.lower():
                    chave_atual = 'Coro'
                    continue
                elif 'estrofe' in linha_limpa.lower():
                    chave_atual = 'Estrofe'
                    continue
                
                # Se não for cabeçalho, é linha de nota
                dados[chave_atual].append(linha_limpa)
                
        return dados
    except Exception as e:
        print(f"Erro ao ler notas: {e}")
        return {'Estrofe': [], 'Coro': []}

# ===================== 2. SEPARA ESTROFES E CORO =====================
def separar_estrofes_e_coro():
    """
    Lê o texto e identifica se o bloco é Estrofe (número) ou Coro (palavra Coro).
    Retorna uma lista de tuplas: (tipo, numero/nome, linhas)
    """
    try:
        with open(DATA_FILE_TEXT, 'r', encoding='utf-8') as f:
            linhas = [l.strip() for l in f.readlines() if l.strip()]
    except: return "Hino", []

    titulo = linhas[0]
    blocos = []
    
    bloco_atual_linhas = []
    bloco_atual_tipo = "Estrofe"
    bloco_atual_num = 1

    # Regex para identificar início: "1." ou "Coro."
    regex_inicio = re.compile(r'^(Coro|\d+)[\.\)]', re.IGNORECASE)

    for linha in linhas[1:]:
        match = regex_inicio.match(linha)
        
        if match:
            # Se já tinha um bloco sendo montado, salva ele antes de começar o novo
            if bloco_atual_linhas:
                blocos.append((bloco_atual_tipo, bloco_atual_num, bloco_atual_linhas))
                bloco_atual_linhas = []

            identificador = match.group(1) # Pega "1" ou "Coro"
            
            # Define o tipo do novo bloco
            if "coro" in identificador.lower():
                bloco_atual_tipo = "Coro"
                bloco_atual_num = 0 # Coro não precisa de número sequencial
            else:
                bloco_atual_tipo = "Estrofe"
                bloco_atual_num = int(identificador)
            
            # Limpa o marcador do texto (remove "1." ou "Coro.")
            texto_limpo = re.sub(r'^(Coro|\d+)[\.\)]\s*', '', linha).strip()
            if texto_limpo:
                bloco_atual_linhas.append(texto_limpo)
        else:
            # Continuação do bloco atual
            if linha:
                bloco_atual_linhas.append(linha)

    # Adiciona o último bloco que ficou pendente no loop
    if bloco_atual_linhas:
        blocos.append((bloco_atual_tipo, bloco_atual_num, bloco_atual_linhas))
    
    return titulo, blocos

# ===================== 3. PROCESSAMENTO DE TEXTO =====================
def processar_linha_texto(texto):
    # Regex: __ (pl), '' (rc), _ (pc), " (rl), - (hifen), espaços
    padrao = r'(__|\'\'|[_"\-]|\s+)'
    tokens_raw = re.split(padrao, texto)
    
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
            if token_limpo in simbolos_pausa:
                lista_final.append(token_limpo)
            else:
                # Limpa pontuação estranha, permite , . ; : ! ? ~
                limpo = re.sub(r'[^\w\',~\-.;:!?]', '', token)
                eh_pontuacao = token_limpo in [",", ";", ".", "!", "?", ":"]
                
                if eh_pontuacao:
                    if lista_final and lista_final[-1] not in simbolos_pausa:
                        lista_final[-1] += token_limpo
                elif limpo or token_limpo: 
                    lista_final.append(token)
    return lista_final

# ===================== 4. SINCRONIZAÇÃO INTELIGENTE =====================
def sincronizar(dicionario_ritmos, blocos_texto):
    json_estrofes = []
    
    print("\n--- INICIANDO PROCESSAMENTO ---")
    print(f"Compasso: {COMPASSO_PADRAO}")
    print("Modo: Seleção automática de notas (Estrofe vs Coro)")

    for tipo, numero, linhas_texto in blocos_texto:
        json_linhas = []
        
        # SELEÇÃO DO RITMO:
        # Se o bloco for "Estrofe", pega as notas de 'Estrofe'. Se "Coro", pega de 'Coro'.
        linhas_ritmo = dicionario_ritmos.get(tipo, [])
        
        if not linhas_ritmo:
            print(f"[AVISO] Não há notas definidas para o tipo '{tipo}'. Usando vazio.")
        
        total_linhas_notas = len(linhas_ritmo) if linhas_ritmo else 1
        idx_linha_nota_local = 0 

        print(f"Processando {tipo} {numero if numero > 0 else ''}...")

        for i, texto in enumerate(linhas_texto):
            # Lógica circular para notas
            if linhas_ritmo:
                linha_nota_str = linhas_ritmo[idx_linha_nota_local % total_linhas_notas]
                notas_arquivo = [n.strip() for n in linha_nota_str.split(',') if n.strip()]
            else:
                notas_arquivo = []
            
            idx_linha_nota_local += 1
            
            tokens_display = processar_linha_texto(texto)
            
            out_texto_silabado = []
            out_notas_codes = []
            idx_nota_arquivo = 0
            
            for token in tokens_display:
                t = token.strip()
                
                # Visual (Liaison ~ vira ‿)
                token_visual = t.replace("~", "‿") 
                out_texto_silabado.append(token_visual)
                
                # Pausas
                if t == "''": out_notas_codes.append("rc") 
                elif t == "_": out_notas_codes.append("pc") 
                elif t == '"': out_notas_codes.append("rl") 
                elif t == "__": out_notas_codes.append("pl") 
                
                # Notas Musicais
                else:
                    if idx_nota_arquivo < len(notas_arquivo):
                        # Pula pausas no arquivo de nota para priorizar texto
                        while idx_nota_arquivo < len(notas_arquivo) and notas_arquivo[idx_nota_arquivo].lower() in ['rc', 'rl', 'pc', 'pl']:
                            idx_nota_arquivo += 1
                        
                        if idx_nota_arquivo < len(notas_arquivo):
                            out_notas_codes.append(notas_arquivo[idx_nota_arquivo])
                            idx_nota_arquivo += 1
                        else:
                            out_notas_codes.append("sm") 
                    else:
                        out_notas_codes.append("sm") 

            json_linhas.append({
                "texto_silabado": " ".join(out_texto_silabado),
                "notas_codes": out_notas_codes
            })

        json_estrofes.append({
            "numero": numero, # Se for coro é 0
            "tipo": tipo,     # "Estrofe" ou "Coro"
            "linhas": json_linhas
        })

    return json_estrofes

# ===================== 5. VALIDAÇÃO =====================
def validar_resultado(json_data):
    print("\n" + "="*30)
    print("VALIDAÇÃO")
    erros = 0
    for estrofe in json_data['estrofes']:
        tipo = estrofe['tipo']
        num = estrofe['numero']
        for idx_l, linha in enumerate(estrofe['linhas']):
            tokens = linha['texto_silabado'].split(' ')
            notas = linha['notas_codes']
            if len(tokens) != len(notas):
                print(f"[ERRO] {tipo} {num} L{idx_l+1}: Texto={len(tokens)} vs Notas={len(notas)}")
                erros += 1
    if erros == 0: print("SUCESSO: Alinhamento perfeito.")
    else: print(f"ATENÇÃO: {erros} erros de alinhamento.")
    print("="*30 + "\n")

# ===================== 6. EXECUÇÃO =====================
if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    ritmos_dict = ler_ritmo_estruturado()
    titulo, blocos = separar_estrofes_e_coro()
    
    if ritmos_dict and blocos:
        resultado = sincronizar(ritmos_dict, blocos)
        
        json_final_obj = {
            "titulo": titulo,
            "BPM": BPM_PADRAO,
            "compasso": COMPASSO_PADRAO,
            "estrofes": resultado
        }
        
        validar_resultado(json_final_obj)
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(json_final_obj, f, indent=4, ensure_ascii=False)
        
        print(f"Arquivo salvo em: {OUTPUT_FILE}")
    else:
        print("ERRO: Verifique os arquivos de entrada.")