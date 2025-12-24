import json
import re
import os

# --- CONFIGURAÇÃO ---
PASTA_SAIDA = r"C:\Users\psoares\pyNestle\Private\Hinario_Digital\textos_corrigidos"
ARQUIVO_ENTRADA = "hino_.txt"

def processar_linha_texto(texto):
    """ Separa sílabas, mantendo pontuação e símbolos especiais """
    # Regex idêntico ao do Player
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
                limpo = re.sub(r'[^\w\',~\-.;:!?]', '', token) 
                if limpo or token_limpo in [",", ";", ".", "!", "?", ":"]: 
                    lista_final.append(token)
    return lista_final

def compilar_hino():
    if not os.path.exists(ARQUIVO_ENTRADA):
        print(f"Crie o arquivo '{ARQUIVO_ENTRADA}' com os dados do hino!")
        return

    with open(ARQUIVO_ENTRADA, 'r', encoding='utf-8') as f:
        linhas = f.readlines()

    hino_json = {
        "titulo": "",
        "BPM": 60,
        "compasso": "4/4",
        "unidade_bpm": "sm",
        "estrofes": []
    }

    ritmo_atual = []
    tipo_atual = "Estrofe"
    numero_atual = 1
    
    # Processamento
    modo = None # HEADER, RITMO, TEXTO
    
    for linha in linhas:
        linha = linha.strip()
        if not linha or linha.startswith("#"): continue # Ignora vazios e comentários

        # --- LEITURA DO CABEÇALHO ---
        if linha.startswith("TITULO:"): hino_json["titulo"] = linha.split(":", 1)[1].strip()
        elif linha.startswith("BPM:"): hino_json["BPM"] = int(linha.split(":")[1].strip())
        elif linha.startswith("COMPASSO:"): hino_json["compasso"] = linha.split(":")[1].strip()
        elif linha.startswith("UNIDADE:"): hino_json["unidade_bpm"] = linha.split(":")[1].strip()
        
        # --- DEFINIÇÃO DE BLOCOS ---
        elif linha.upper().startswith("ESTROFE"):
            modo = "TEXTO"
            tipo_atual = "Estrofe"
            try:
                numero_atual = int(re.search(r'\d+', linha).group())
            except: numero_atual = 1
            print(f"Processando Estrofe {numero_atual}...")

        elif linha.upper().startswith("CORO"):
            modo = "TEXTO"
            tipo_atual = "Coro"
            numero_atual = 0
            print(f"Processando Coro...")

        elif linha.startswith("RITMO:"):
            # Captura o padrão rítmico para usar nas próximas linhas
            notas_str = linha.split(":", 1)[1].strip()
            ritmo_atual = [n.strip() for n in notas_str.split(',') if n.strip()]
            print(f"   -> Ritmo capturado ({len(ritmo_atual)} notas)")

        # --- PROCESSAMENTO DO TEXTO ---
        elif modo == "TEXTO":
            # É uma linha da letra
            tokens = processar_linha_texto(linha)
            notas_linha = []
            
            # Aplica o ritmo salvo
            idx_nota = 0
            
            # Precisamos descobrir quantas notas REAIS (não pausa) essa linha precisa
            # O ritmo_atual pode conter varias linhas. 
            # Truque: Vamos consumir do ritmo_atual sequencialmente
            # Mas como saber onde começa?
            # SIMPLIFICAÇÃO: O usuário deve fornecer o ritmo LINHA A LINHA no txt ou
            # fornecer um ritmo longo que cubra tudo.
            # Vamos assumir que RITMO: define uma lista longa que reseta a cada bloco.
            
            # Melhor abordagem para o seu caso: 
            # O script vai tentar alinhar as notas do 'ritmo_atual' com as sílabas desta linha.
            # Mas o 'ritmo_atual' geralmente tem notas para a estrofe inteira.
            # Vamos criar um buffer de notas para o bloco atual.
            
            # Logica ajustada: O objeto estrofe é criado no inicio do bloco, 
            # e vamos preenchendo.
            
            # Encontra ou cria o bloco no JSON
            bloco_obj = None
            if hino_json["estrofes"] and \
               hino_json["estrofes"][-1]["tipo"] == tipo_atual and \
               hino_json["estrofes"][-1]["numero"] == numero_atual:
                bloco_obj = hino_json["estrofes"][-1]
            else:
                bloco_obj = {"numero": numero_atual, "tipo": tipo_atual, "linhas": []}
                hino_json["estrofes"].append(bloco_obj)
            
            # Calcula quantas notas já foram usadas neste bloco
            notas_usadas_no_bloco = 0
            for l in bloco_obj["linhas"]:
                # Conta apenas notas que não são pausa gerada pelo texto
                for n in l["notas_codes"]:
                     if n not in ["rc", "rl", "pc", "pl"]: # Se for nota musical
                         notas_usadas_no_bloco += 1
            
            out_notas = []
            
            for token in tokens:
                # Verifica se é pausa do texto
                if token == "''": out_notas.append("rc")
                elif token == "_": out_notas.append("pc")
                elif token == '"': out_notas.append("rl")
                elif token == "__": out_notas.append("pl")
                else:
                    # É sílaba musical
                    if notas_usadas_no_bloco < len(ritmo_atual):
                        nota = ritmo_atual[notas_usadas_no_bloco]
                        # Se a nota no ritmo for pausa, consome e adiciona
                        # Se for nota musical, adiciona
                        out_notas.append(nota)
                        if nota not in ["rc", "rl", "pc", "pl"]: # Avança se consumiu nota do buffer
                             notas_usadas_no_bloco += 1
                    else:
                        out_notas.append("sm") # Falta nota
            
            bloco_obj["linhas"].append({
                "texto_silabado": " ".join(tokens).replace("~", "‿"),
                "notas_codes": out_notas
            })

    # Salvar
    nome_arq = f"hino_{int(hino_json['titulo'].split('.')[0]):03d}.json"
    caminho_final = os.path.join(PASTA_SAIDA, nome_arq)
    
    with open(caminho_final, 'w', encoding='utf-8') as f:
        json.dump(hino_json, f, indent=4, ensure_ascii=False)
    
    print(f"\nGERADO COM SUCESSO: {caminho_final}")

if __name__ == "__main__":
    compilar_hino()