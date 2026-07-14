 # workers.py - Otimizado com logs DETALHADOS para diagnosticar travamentos

from PyQt6.QtCore import QThread, pyqtSignal
from PIL import Image
import google.generativeai as genai
from core.logger import log_info, log_debug, log_error
import time

class GeminiWorker(QThread):
    """Worker thread para processar imagens com Gemini API"""

    finished_signal = pyqtSignal(str, bool, str)  # output_path, success, message
    progress_signal = pyqtSignal(str)  # Para atualizar status da barra

    def __init__(self, image_path, output_path, api_key):
        super().__init__()
        self.image_path = image_path
        self.output_path = output_path
        self.api_key = api_key
        log_debug(f"GeminiWorker inicializado: {image_path} -> {output_path}")

    def run(self):
        """Executa processamento em thread separada"""
        try:
            if not self.api_key:
                log_error("Chave API nao configurada")
                self.progress_signal.emit("Erro: Chave API nao configurada")
                self.finished_signal.emit("", False, "Chave API nao configurada.")
                return

            # ========== ETAPA 1: Configurar Gemini ==========
            self.progress_signal.emit("Etapa 1/5: Configurando Gemini...")
            log_info("Etapa 1: Configurando API Gemini")
            log_debug(f"API Key: {self.api_key[:20]}...")

            genai.configure(api_key=self.api_key)
            log_debug("API Gemini configurada com sucesso")

            model = genai.GenerativeModel('models/gemini-2.5-pro')
            log_debug("Modelo Gemini-2.5-Pro carregado")

            # ========== ETAPA 2: Carregar imagem ==========
            self.progress_signal.emit("Etapa 2/5: Carregando imagem...")
            log_info(f"Etapa 2: Abrindo imagem: {self.image_path}")

            pil_img = Image.open(self.image_path)
            log_debug(f"Imagem carregada com sucesso")
            log_debug(f"Tamanho da imagem: {pil_img.size}")
            log_debug(f"Formato: {pil_img.format}")

            # ========== ETAPA 3: Preparar prompt ==========
            self.progress_signal.emit("Etapa 3/5: Preparando prompt...")
            log_info("Etapa 3: Preparando prompt para Gemini")

            prompt = """You are a Sheet Music OCR expert. Your goal is to digitize the sheet music into JSON, capturing EVERY musical event.

### 1. NOTE-BY-NOTE EXTRACTION (CRITICAL):
- **DO NOT skip any symbol.** You must generate an entry for EVERY Note, Rest (Pausa), or Breathing Mark (Respiracao) found on the staff, reading from Left to Right.
- **The "Null" Rule:** If a Note or Rest has NO lyrics underneath it (e.g., it is a melisma extension, a tie, or a rest), you **MUST** output: `{ "texto": null, "nota": "NoteValue" }`.
- **Example:** After the word "dent" (Seminima Pontuada), if there is another Seminima Pontuada without text and then a Rest, output both as null text entries.

### 2. VERTICAL ALIGNMENT STRATEGY:
- Identify the note on the staff.
- Look vertically below it to find the lyrics for Verse 1, Verse 2, Verse 3.
- If no lyrics are found directly below a note, apply the "Null" Rule above.

### 3. STRUCTURE & TAGS:
- **Coro (Chorus):** Look for the label "CORO" (orange tag) or "Refrain".
- **Logic:** If the lyrics repeat the Title of the song, it is the Coro.
- Set `"tipo": "Coro"` and `"numero": null` for the Chorus section.
- **Estrofes:** Number them 1, 2, 3...

### 4. FORMATTING:
- **Liaisons (~):** "ne a" -> "ne~a".
- **Hyphens:** Only at end of syllables ("Maî -"). No leading hyphens.
- **Metadata:** Title, Author, Key (Tom), BPM, Compasso.

### 5. BPM CALCULATION:
- If BPM is not explicitly stated, infer it from the header notes.
- Example: If header shows 112 and 144, calculate BPM as average: (112+144)/2 = 128

### 6. HEADER:
- Extract Title, Author, Key (Tom), Language (Idioma) from the header.
- Extract BPM from the header if present, otherwise calculate as described in section 5.
- Extract Language (Idioma) based on the lyrics language.
- Extract tom: the musical key from the header (e.g., "Do Maior", "Fa Menor").

### OUTPUT JSON SCHEMA:
{
    "titulo": "String",
    "numero": Integer,
    "idioma": "String",
    "tom": "String",
    "autor": "String",
    "BPM": Integer,
    "compasso": "String",
    "estrofes": [
        {
            "numero": 1,
            "tipo": "Estrofe",
            "linhas": [
                {
                    "silabas": [
                        { "texto": "Qui", "nota": "Colcheia" },
                        { "texto": "sur", "nota": "Colcheia" }
                    ]
                }
            ]
        }
    ]
}
"""
            log_debug(f"Tamanho do prompt: {len(prompt)} caracteres")

            # ========== ETAPA 4: Enviar para Gemini ==========
            self.progress_signal.emit("Etapa 4/5: Enviando para Gemini (pode levar 30-60 segundos)...")
            log_info("Etapa 4: Enviando imagem para Gemini API")
            log_debug("Iniciando requisicao para Gemini...")

            start_time = time.time()
            log_debug(f"Hora de inicio: {start_time}")

            try:
                log_debug("Chamando model.generate_content()...")
                response = model.generate_content(
                    [prompt, pil_img],
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.1,
                        response_mime_type="application/json"
                    )
                )

                elapsed_time = time.time() - start_time
                log_info(f"Resposta recebida em {elapsed_time:.2f} segundos")
                log_debug(f"Tamanho da resposta: {len(response.text)} caracteres")

                # Verificar se resposta tem conteudo
                if not response.text:
                    log_error("Resposta vazia do Gemini")
                    self.progress_signal.emit("Erro: Resposta vazia do Gemini")
                    self.finished_signal.emit("", False, "Gemini retornou resposta vazia")
                    return

                log_debug(f"Primeiros 200 caracteres: {response.text[:200]}")

            except Exception as api_error:
                elapsed_time = time.time() - start_time
                log_error(f"Erro na chamada da API (tempo decorrido: {elapsed_time:.2f}s)", api_error)
                self.progress_signal.emit(f"Erro na API: {str(api_error)}")
                self.finished_signal.emit("", False, f"Erro na API Gemini: {str(api_error)}")
                return

            # ========== ETAPA 5: Salvar resultado ==========
            self.progress_signal.emit("Etapa 5/5: Salvando resultado...")
            log_info(f"Etapa 5: Salvando resposta em: {self.output_path}")

            try:
                with open(self.output_path, "w", encoding="utf-8") as f:
                    f.write(response.text)
                log_info(f"Arquivo salvo com sucesso: {self.output_path}")
                log_debug(f"Tamanho do arquivo: {len(response.text)} bytes")

            except Exception as save_error:
                log_error(f"Erro ao salvar arquivo", save_error)
                self.progress_signal.emit(f"Erro ao salvar: {str(save_error)}")
                self.finished_signal.emit("", False, f"Erro ao salvar resultado: {str(save_error)}")
                return

            log_info("Processamento Gemini concluido com sucesso!")
            self.progress_signal.emit("Concluido com sucesso!")
            self.finished_signal.emit(self.output_path, True, "Sucesso!")

        except Exception as error_msg:
            log_error(f"Erro geral no GeminiWorker", error_msg)
            self.progress_signal.emit(f"Erro: {str(error_msg)}")
            self.finished_signal.emit("", False, str(error_msg))
