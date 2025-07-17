import pdfplumber
import pandas as pd
from datetime import datetime
import re
import unicodedata

def normalizar(texto: str) -> str:
    if not isinstance(texto, str):
        texto = str(texto)
    texto = unicodedata.normalize("NFD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    texto = re.sub(r"\s+", "", texto)  # remove todos os espaços
    return texto.lower()

def importar_extrato(path_pdf: str) -> pd.DataFrame:
    import pdfplumber
    import pandas as pd
    from datetime import datetime
    import re

    dados = []

    with pdfplumber.open(path_pdf) as pdf:
        for page_index, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            print(f"Página {page_index + 1}: {len(tables)} tabelas encontradas.")

            for table_index, table in enumerate(tables):
                if not table or len(table) < 2:
                    continue

                header = [cell.strip().lower() if cell else "" for cell in table[0]]
                if any("data" in h for h in header) and any("valor" in h for h in header):
                    print(f">>> Tabela de extrato identificada: página {page_index+1}, tabela {table_index+1}")
                    
                    for row_index, row in enumerate(table[1:], start=1):
                        try:
                            data_raw = row[0].strip() if row[0] else ""
                            historico = row[2].strip() if len(row) > 2 and row[2] else ""
                            valor_raw = row[4].strip() if len(row) > 4 and row[4] else ""

                            if not re.match(r"\d{2}/\d{2}/\d{4}", data_raw):
                                continue

                            data = datetime.strptime(data_raw, "%d/%m/%Y").date()
                            valor = float(valor_raw.replace(".", "").replace(",", "."))
                            tipo = "C" if valor > 0 else "D"

                            if "saldo" in historico.lower():
                                continue

                            dados.append({
                                "data": data,
                                "valor": round(abs(valor), 2),
                                "tipo": tipo,
                                "historico": historico
                            })

                        except Exception as e:
                            print(f"[Erro linha {row_index}] {e}")
                            continue

    df = pd.DataFrame(dados)
    print(f"Total de lançamentos importados: {len(df)}")
    return df
