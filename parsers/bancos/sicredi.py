import pdfplumber
import pandas as pd
from datetime import datetime
import re

def importar_extrato(path_pdf: str) -> pd.DataFrame:
    dados = []

    with pdfplumber.open(path_pdf) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or len(row) < 4:
                        continue

                    linha = [str(cell).strip() if cell else "" for cell in row]

                    if not re.match(r"\d{2}/\d{2}/\d{4}", linha[0]):
                        continue

                    data_br = linha[0]
                    try:
                        data_fmt = datetime.strptime(data_br, "%d/%m/%Y").date()
                    except:
                        continue

                    descricao = linha[1]
                    valor_bruto = linha[3].replace("R$", "").replace(".", "").replace(",", ".").replace(" ", "")
                    try:
                        valor = float(valor_bruto)
                    except:
                        continue

                    tipo = "C" if valor > 0 else "D"
                    dados.append({
                        "data": pd.to_datetime(data_fmt),
                        "valor": round(valor, 2),
                        "tipo": tipo,
                        "historico": descricao
                    })

    df = pd.DataFrame(dados)
    return df