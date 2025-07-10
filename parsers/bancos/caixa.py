import pdfplumber
import pandas as pd
from datetime import datetime
import re

def importar_extrato(path_pdf: str) -> pd.DataFrame:
    dados = []

    with pdfplumber.open(path_pdf) as pdf:
        for page in pdf.pages:
            texto = page.extract_text()
            if not texto:
                continue

            linhas = texto.split("\n")
            for linha in linhas:
                # Match para linhas como "02/06/2025 000000 PREST EMP 6.512,41 D 433,13 C"
                match = re.match(r"(\d{2}/\d{2}/\d{4})\s+\d+\s+(.+?)\s+([\d.,]+)\s+([DC])\s+[\d.,]+\s+[DC]", linha)
                if not match:
                    continue

                data_str, historico, valor_str, tipo = match.groups()
                try:
                    data_fmt = datetime.strptime(data_str, "%d/%m/%Y").date()
                    valor = float(valor_str.replace(".", "").replace(",", "."))
                    if tipo == "D":
                        valor *= -1
                except:
                    continue

                dados.append({
                    "data": pd.to_datetime(data_fmt),
                    "valor": round(valor, 2),
                    "tipo": "C" if valor > 0 else "D",
                    "historico": historico.strip()
                })

    df = pd.DataFrame(dados)
    return df