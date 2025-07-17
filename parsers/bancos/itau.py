import pdfplumber
import pandas as pd
from datetime import datetime
import re

def importar_extrato(path_pdf: str, nome_banco: str = "extrato") -> pd.DataFrame:
    dados = []
    meses = {
        "jan": "01", "fev": "02", "mar": "03", "abr": "04",
        "mai": "05", "jun": "06", "jul": "07", "ago": "08",
        "set": "09", "out": "10", "nov": "11", "dez": "12"
    }

    with pdfplumber.open(path_pdf) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            for t_idx, table in enumerate(tables):

                for row in table:
                    linha_concatenada = " | ".join([cell.strip() if cell else "" for cell in row])
                    # Tenta extrair: data, valor, e descrição de qualquer posição
                    match = re.search(r"(\d{2})\s*/\s*(\w{3}).*?(-?[\d.]+,\d{2})", linha_concatenada)
                    if not match:
                        continue

                    dia, mes_txt, valor_str = match.groups()
                    mes = meses.get(mes_txt.lower())
                    if not mes:
                        continue

                    try:
                        data = datetime.strptime(f"{dia}/{mes}/2025", "%d/%m/%Y").date()
                        valor = float(valor_str.replace(".", "").replace(",", "."))
                        tipo = "C" if valor > 0 else "D"
                    except Exception as e:
                        continue

                    # Usa primeira célula não vazia que não seja data ou valor como histórico
                    historico = next((c for c in row if c and not re.search(r"\d{2} / \w{3}", c) and not re.search(r"-?[\d.]+,\d{2}", c)), "").strip()

                    dados.append({
                        "data": pd.to_datetime(data),
                        "valor": round(valor, 2),
                        "tipo": tipo,
                        "historico": historico
                    })

    df = pd.DataFrame(dados)

    return df
