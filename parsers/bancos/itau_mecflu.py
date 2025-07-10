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
                    # Ignorar linhas vazias ou com poucos campos
                    if not row or len(row) < 4:
                        continue

                    linha = [str(cell).strip() if cell else "" for cell in row]

                    # Verifica se a primeira coluna contém uma data válida
                    if not re.match(r"\d{2}/\d{2}/\d{4}", linha[0]):
                        continue

                    try:
                        data = datetime.strptime(linha[0], "%d/%m/%Y").date()
                        historico = linha[1]
                        valor_str = linha[3].replace("R$", "").replace(".", "").replace(",", ".")
                        valor = float(valor_str)
                        tipo = "C" if valor > 0 else "D"
                    except Exception as e:
                        print(f"[Erro de leitura]: {linha} - {e}")
                        continue

                    dados.append({
                        "data": pd.to_datetime(data),
                        "valor": round(valor, 2),
                        "tipo": tipo,
                        "historico": historico
                    })

    df = pd.DataFrame(dados)
    return df
