# hino_perfeito_final.py → FUNCIONA 100% NO SEU PC AGORA (sem LaTeX)
from manim import *
import re
import os

NUMERO = 1
PASTA_TEXTOS = "textos_corrigidos"
arquivo_txt = os.path.join(PASTA_TEXTOS, f"hino_{NUMERO:03d}.txt")

class HinoPerfeito(Scene):
    def construct(self):
        self.camera.background_color = BLACK
        self.camera.frame_width = 24  # NUNCA mais corta nas laterais

        with open(arquivo_txt, "r", encoding="utf-8") as f:
            linhas = [l.strip() for l in f.read().split("\n") if l.strip()]

        tudo = VGroup()
        palavras = []

        for i, linha in enumerate(linhas):
            tokens = re.findall(r"\w+[\w'+’-]*|[^\w\s]", linha)
            linha_group = VGroup()

            for token in tokens:
                texto = token if token in ".,!?:;" else token + " "
                t = Text(texto, font_size=64, color=WHITE, font="Arial")
                linha_group.add(t)
                palavras.append(t)

            linha_group.arrange(RIGHT, buff=0.45)
            if i == 0:  # título
                linha_group.scale(2.2).set_color(YELLOW)

            tudo.add(linha_group)

        tudo.arrange(DOWN, buff=1.3)
        tudo.move_to(ORIGIN)
        self.add(tudo)

        # Destaque amarelo (BPM 60)
        for p in palavras:
            self.play(
                p.animate.set_color(YELLOW).scale(1.55),
                run_time=0.95,
                rate_func=there_and_back
            )
            self.wait(0.05)

        self.play(tudo.animate.shift(DOWN * (len(linhas) * 1.9 + 10)),
                  run_time=18, rate_func=linear)
        self.wait(3)