# test.py → OCR + correção fácil + título + scroll + fundo preto
from manim import *
import os
from PIL import Image
import pytesseract

# ===================== CONFIGURAÇÃO =====================
BPM = 94                                   # ← Mude o BPM do hino
NUMERO = 1                                 # ← número do hino (1, 2, 3...)
PASTA_IMAGENS = "imagens"
PASTA_TEXTOS = "textos_corrigidos"         # ← pasta onde vai salvar os .txt
# =======================================================

# Cria a pasta se não existir
os.makedirs(PASTA_TEXTOS, exist_ok=True)
arquivo_txt = os.path.join(PASTA_TEXTOS, f"hino_{NUMERO:03d}.txt")
caminho_imagem = os.path.join(PASTA_IMAGENS, f"{NUMERO}.PNG")

class HinoKaraoke(Scene):
    def construct(self):
        self.camera.background_color = BLACK
        beat = 60.0 / BPM

        # === PASSO 1: Extrai OCR da imagem ===
        print(f"\nExtraindo texto do hino {NUMERO}...")
        raw_text = pytesseract.image_to_string(Image.open(caminho_imagem), lang='fra')
        print("\n" + "="*60)
        print("TEXTO EXTRAÍDO AUTOMATICAMENTE:")
        print("="*60)
        print(raw_text)
        print("="*60)

        # === PASSO 2: Carrega texto corrigido se já existir ===
        if os.path.exists(arquivo_txt):
            with open(arquivo_txt, "r", encoding="utf-8") as f:
                texto_final = f.read().strip()
            print(f"Texto corrigido carregado de: {arquivo_txt}")
        else:
            # Primeira vez → salva o OCR bruto pra você corrigir
            with open(arquivo_txt, "w", encoding="utf-8") as f:
                f.write(raw_text.strip())
            print(f"\nTexto bruto salvo em: {arquivo_txt}")
            print("ABRA esse arquivo, corrija o que precisar (inclusive adicione o título no topo), salve e rode de novo.")
            print("Na próxima execução ele já usa a versão corrigida!")
            input("\nPressione ENTER após corrigir o arquivo para continuar gerando o vídeo...")
            with open(arquivo_txt, "r", encoding="utf-8") as f:
                texto_final = f.read().strip()

        print("\nTexto que será usado no vídeo:\n")
        print(texto_final)

        # === PASSO 3: Divide em palavras mantendo quebras de linha ===
        words = []
        for linha in texto_final.split("\n"):
            linha = linha.strip()
            if not linha:
                words.append("\n")
                continue
            import re
            partes = re.findall(r"[\w'+’\-]+|[.,!?;:()\"]", linha)
            words.extend(partes)
            words.append("\n")

        # === PASSO 4: Cria o texto na tela ===
        todas_linhas = VGroup()
        linha_atual = VGroup()
        y_pos = 4

        objetos_texto = []  # para animar o destaque

        for item in words:
            if item == "\n":
                linha_atual.arrange(RIGHT, buff=0.45).move_to(UP * y_pos)
                todas_linhas.add(linha_atual)
                linha_atual = VGroup()
                y_pos -= 1.15
            else:
                t = Text(item, font_size=58, color=WHITE)
                linha_atual.add(t)
                objetos_texto.append(t)

        if len(linha_atual) > 0:
            linha_atual.arrange(RIGHT, buff=0.45).move_to(UP * y_pos)
            todas_linhas.add(linha_atual)

        todas_linhas.arrange(DOWN, buff=0.8).move_to(UP * 6)
        self.add(todas_linhas)

        # === PASSO 5: Destaque + scroll automático ===
        for texto in objetos_texto:
            self.play(
                texto.animate.set_color(YELLOW).scale(1.35),
                run_time=beat * 0.9,
                rate_func=there_and_back
            )
            self.play(
                texto.animate.set_color(WHITE).scale(1/1.35),
                run_time=beat * 0.1
            )

        # Scroll suave para mostrar tudo
        self.play(todas_linhas.animate.shift(DOWN * 22), run_time=len(objetos_texto)*beat*0.75, rate_func=linear)
        self.wait(3)

# RODE COM:
# manim -pqh test.py HinoKaraoke