import pandas as pd
import unicodedata

def normalize_text(text):
    if not isinstance(text, str):
        text = str(text)
    return " ".join(
        unicodedata.normalize("NFD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
        .split()
    )

def carregar_depara(caminho_depara):
    mapa = {}

    try:
        df = pd.read_excel(caminho_depara)
        df.columns = [col.strip().lower() for col in df.columns]
        for _, row in df.iterrows():
            nome = str(row["nome"]).strip().lower()
            codigo = str(row["codigo"])
            nome_normalizado = normalize_text(nome)
            mapa[nome_normalizado] = codigo
    except Exception as e:
              print(f"[DEPARA] Erro ao carregar DE-PARA: {e}")
    return mapa 