import requests
import urllib3
import os
import glob

# Desabilita aviso de certificado (rede corporativa Nestlé)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def png_to_svg_vectorizer_ai(input_png, output_svg=None, api_id=None, api_secret=None):
    if output_svg is None:
        output_svg = input_png.replace(".png", "_vectorizer.svg")

    url = "https://vectorizer.ai/api/v1/vectorize"
    
    files = {'image': open(input_png, 'rb')}
    data = {}  # Sem 'mode' para produção paga (ativa full automaticamente)

    # Autenticação CORRETA: (ID, SECRET)
    auth = (api_id, api_secret)
    
    print("Enviando para vectorizer.ai (modo produção - sem watermark)...")
    response = requests.post(
        url,
        files=files,
        data=data,
        auth=auth,
        verify=False,  # Contorna SSL/proxy da Nestlé
        timeout=90
    )
    
    if response.status_code == 200:
        with open(output_svg, "wb") as f:
            f.write(response.content)
        print("SUCESSO! SVG gerado em modo produção (sem watermark).")
        print("Arquivo salvo em:", output_svg)
        # Abre no navegador (Windows)
        os.startfile(output_svg)
    else:
        print("Erro:", response.status_code)
        print(response.text)
        print("Dica: Verifique API_ID e API_SECRET no dashboard. Se 401, adicione crédito.")

# RODA AQUI – APENAS 1 PÁGINA PARA TESTAR
png_to_svg_vectorizer_ai(
    r"C:\Users\psoares\pyNestle\Private\Hinario_Digital\teste\1.png",
    r"C:\Users\psoares\pyNestle\Private\Hinario_Digital\teste\1_full_vectorizer.svg",
    api_id='vkrbfzhlvfcipvd',
    api_secret='dtao3rkcs4h9pvd8bujlpn1a6bv2so8glko4ar029gi1meb30klu'
)