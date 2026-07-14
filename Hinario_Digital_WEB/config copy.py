import sqlite3
import os

# --- CAMINHOS ---
# Ajuste o caminho conforme sua necessidade real
HINOS_FOLDER_PATH = os.path.normpath(r"C:\Users\pettt\Projects\HinarioDigital\Hinario_Digital\textos_corrigidos")
CONFIG_DB_FILE = 'config.db'

# --- CONSTANTES GLOBAIS ---
BPM_INICIAL = 60  # <--- ESTA LINHA ESTAVA FALTANDO

# --- CORES ---
COR_INICIAR = "#006400" 
COR_PERIGO = "#8B0000" 
COR_AUTO_SCALE = "#0050C0" 
COR_EDICAO = "#FF4500"
COR_BARRA_PADRAO = "#000080"

# --- VALORES PADRÃO ---
DEFAULT_PARAMS = {
    'bpm_step': 5,
    'fermata_factor': 1.5,
    'min_zoom': 12,
    'max_zoom': 150,
    'start_delay': 2,
    'strofe_delay': 3,
    'time_rc': 300,   # Respiração Curta
    'time_pc': 500,   # Pausa Curta
    'time_rl': 800,   # Respiração Longa
    'time_pl': 1000,  # Pausa Longa
    'editor_width': 1000,
    'editor_height': 800,
    'tamanho_fonte': 60,
    'espacamento_texto': 20,
    'cor_fundo_texto': "black",
    'cor_texto_normal': "white",
    'cor_destaque_karaoke': "#FFFF00",
    'cor_nota_normal': "#00BFFF",
    'cor_nota_destaque': "#32CD32",
    'cor_barra_navegacao': "#000080",
    'BPM_padrao': BPM_INICIAL
}

class ConfigManager:
    def __init__(self):
        self.iniciar_banco_config()

    def iniciar_banco_config(self):
        try:
            conn = sqlite3.connect(CONFIG_DB_FILE)
            conn.execute("CREATE TABLE IF NOT EXISTS configuracoes (chave TEXT PRIMARY KEY, valor TEXT)")
            conn.commit(); conn.close()
        except: pass
            
    def get(self, chave, tipo=str):
        val = None
        try:
            conn = sqlite3.connect(CONFIG_DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT valor FROM configuracoes WHERE chave = ?", (chave,))
            res = cursor.fetchone()
            conn.close()
            if res: val = res[0]
        except: pass
        
        if val is None:
            val = DEFAULT_PARAMS.get(chave)
            
        if val is not None:
            try:
                if tipo == int: return int(float(val))
                if tipo == float: return float(val)
                return str(val)
            except: pass
        return val
        
    def set(self, chave, valor):
        try:
            conn = sqlite3.connect(CONFIG_DB_FILE)
            conn.execute("INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES (?, ?)", (chave, str(valor)))
            conn.commit(); conn.close()
        except: pass

    def carregar_config(self, chave, padrao=None): 
        res = self.get(chave)
        return res if res is not None else padrao

    def salvar_config(self, chave, valor): 
        self.set(chave, valor)

# Instância global para ser usada nos outros arquivos
config_manager = ConfigManager()