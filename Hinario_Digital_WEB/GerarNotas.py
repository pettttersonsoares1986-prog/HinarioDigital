# RODE ESSE CÓDIGO UMA VEZ SÓ — GERA AS 10 IMAGENS PNG PERFEITAS E LINDAS!
from PIL import Image, ImageDraw
import os

# PASTA PARA SALVAR AS IMAGENS
pasta = r"C:\Users\psoares\pyNestle\Private\Notas_Musicais"
os.makedirs(pasta, exist_ok=True)

def salvar_nota(nome, largura=70, altura=100):
    img = Image.new("RGBA", (largura, altura), (0,0,0,0))
    d = ImageDraw.Draw(img)

    # Centro da cabeça da nota
    cx, cy = largura // 2, altura - 28
    raio = 12
    haste_x = cx + 15
    haste_topo = cy - raio - 45

    if nome == "semibreve":
        d.ellipse([cx-raio, cy-raio, cx+raio, cy+raio], outline="black", width=3)

    elif nome == "minima":
        d.ellipse([cx-raio, cy-raio, cx+raio, cy+raio], outline="black", width=3)
        d.line([haste_x, cy-raio, haste_x, haste_topo], fill="black", width=5)

    elif nome == "minima_pontuada":
        d.ellipse([cx-raio, cy-raio, cx+raio, cy+raio], outline="black", width=3)
        d.line([haste_x, cy-raio, haste_x, haste_topo], fill="black", width=5)
        d.ellipse([cx+raio+10, cy-4, cx+raio+20, cy+4], fill="black")

    elif nome == "seminima":
        d.ellipse([cx-raio, cy-raio, cx+raio, cy+raio], fill="black")
        d.line([haste_x, cy-raio, haste_x, haste_topo], fill="black", width=5)

    elif nome == "seminima_pontuada":
        d.ellipse([cx-raio, cy-raio, cx+raio, cy+raio], fill="black")
        d.line([haste_x, cy-raio, haste_x, haste_topo], fill="black", width=5)
        d.ellipse([cx+raio+10, cy-4, cx+raio+20, cy+4], fill="black")

    elif nome == "colcheia":
        d.ellipse([cx-raio, cy-raio, cx+raio, cy+raio], fill="black")
        d.line([haste_x, cy-raio, haste_x, haste_topo], fill="black", width=5)
        d.polygon([
            (haste_x, haste_topo+18),
            (haste_x+28, haste_topo+6),
            (haste_x+22, haste_topo+22),
            (haste_x, haste_topo+30)
        ], fill="black")

    elif nome == "colcheia_pontuada":
        d.ellipse([cx-raio, cy-raio, cx+raio, cy+raio], fill="black")
        d.line([haste_x, cy-raio, haste_x, haste_topo], fill="black", width=5)
        d.polygon([
            (haste_x, haste_topo+18),
            (haste_x+28, haste_topo+6),
            (haste_x+22, haste_topo+22),
            (haste_x, haste_topo+30)
        ], fill="black")
        d.ellipse([cx+raio+10, cy-4, cx+raio+20, cy+4], fill="black")

    elif nome == "semicolcheia":
        d.ellipse([cx-raio, cy-raio, cx+raio, cy+raio], fill="black")
        d.line([haste_x, cy-raio, haste_x, haste_topo], fill="black", width=5)
        d.polygon([
            (haste_x, haste_topo+18),
            (haste_x+28, haste_topo+6),
            (haste_x+22, haste_topo+22),
            (haste_x, haste_topo+30)
        ], fill="black")
        d.polygon([
            (haste_x, haste_topo+32),
            (haste_x+28, haste_topo+20),
            (haste_x+22, haste_topo+36),
            (haste_x, haste_topo+44)
        ], fill="black")

    elif nome == "fusa":
        d.ellipse([cx-raio, cy-raio, cx+raio, cy+raio], fill="black")
        d.line([haste_x, cy-raio, haste_x, haste_topo], fill="black", width=5)
        for i in range(3):
            dy = haste_topo + 18 + i*14
            d.polygon([
                (haste_x, dy),
                (haste_x+28, dy-12),
                (haste_x+22, dy+2),
                (haste_x, dy+10)
            ], fill="black")

    elif nome == "semifusa":
        d.ellipse([cx-raio, cy-raio, cx+raio, cy+raio], fill="black")
        d.line([haste_x, cy-raio, haste_x, haste_topo], fill="black", width=5)
        for i in range(4):
            dy = haste_topo + 18 + i*12
            d.polygon([
                (haste_x, dy),
                (haste_x+28, dy-12),
                (haste_x+22, dy+2),
                (haste_x, dy+10)
            ], fill="black")

    # Salva
    arquivo = os.path.join(pasta, f"{nome}.png")
    img.save(arquivo, "PNG")
    print(f"Gerada: {arquivo}")

# GERA TODAS AS 10 IMAGENS PERFEITAS
print("GERANDO AS 10 IMAGENS PNG PERFEITAS DAS NOTAS MUSICAIS...")
for n in [
    "semibreve", "minima", "minima_pontuada",
    "seminima", "seminima_pontuada",
    "colcheia", "colcheia_pontuada",
    "semicolcheia", "fusa", "semifusa"
]:
    salvar_nota(n)

print("\nPRONTO! Todas as imagens PNG perfeitas estão salvas em:")
print(pasta)
os.startfile(pasta)  # abre a pasta