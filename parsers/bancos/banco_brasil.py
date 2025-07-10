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
                    if not row or len(row) < 2:
                        continue

                    linha = [str(cell).strip() if cell else "" for cell in row]

                    if not re.match(r"\d{2}/\d{2}/\d{4}", linha[0]):
                        continue

                    data_br = linha[0]
                    try:
                        data_fmt = datetime.strptime(data_br, "%d/%m/%Y").date()
                    except:
                        continue

                    valor = None
                    tipo = ""
                    for campo in linha:
                        match = re.search(r"(\d{1,3}(?:\.\d{3})*,\d{2})([CD])", campo.replace(" ", ""))
                        if match:
                            valor_str, tipo = match.groups()
                            valor = float(valor_str.replace(".", "").replace(",", "."))
                            if tipo == "D":
                                valor *= -1
                            break

                    if valor is None:
                        continue

                    historico = " ".join(linha[1:-1])
                    historico = re.sub(r"\s{2,}", " ", historico).strip()

                    dados.append({
                        "data": pd.to_datetime(data_fmt),
                        "valor": round(valor, 2),
                        "tipo": tipo,
                        "historico": historico
                    })

    # Remove "Saldo Anterior" apenas se for o primeiro lançamento
    if dados and "saldo anterior" in dados[0]["historico"].lower():
        dados = dados[1:]

    df = pd.DataFrame(dados)

    # Separa por tipo
    df_credito = df[df["tipo"] == "C"]
    df_debito = df[df["tipo"] == "D"]

    # Salva os arquivos
    df_credito.to_excel("extrato_creditos.xlsx", index=False)
    df_debito.to_excel("extrato_debitos.xlsx", index=False)

    return df
