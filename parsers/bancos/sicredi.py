import pdfplumber
import pandas as pd
from datetime import datetime
import re

def importar_extrato_santander(path_pdf: str) -> pd.DataFrame:
    dados = []
    valor_regex = re.compile(r"-?\d{1,3}(?:\.\d{3})*,\d{2}")

    with pdfplumber.open(path_pdf) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            texto = page.extract_text()
            if not texto:
                continue

            for linha in texto.split('\n'):
                linha = linha.strip()
                if not re.match(r"^\d{2}/\d{2}/\d{4}", linha):
                    continue

                partes = linha.split(maxsplit=1)
                if len(partes) < 2:
                    continue

                data_str, resto = partes
                try:
                    data = datetime.strptime(data_str, "%d/%m/%Y").date()
                except ValueError:
                    continue

                match_valor = valor_regex.findall(resto)
                if not match_valor:
                    continue

                valor_str = match_valor[-1]
                try:
                    valor = float(valor_str.replace('.', '').replace(',', '.'))
                    tipo = 'C' if valor > 0 else 'D'
                    historico = resto.replace(valor_str, '').strip()

                    dados.append({
                        "data": data,
                        "historico": historico,
                        "valor": round(valor, 2),
                        "tipo": tipo
                    })
                except:
                    continue

        # Fallback: se nenhum lançamento foi extraído por texto, tentar por tabela
        if not dados:
            ultima_pagina = pdf.pages[-1]
            tables = ultima_pagina.extract_tables()
            for table in tables:
                for row in table:
                    try:
                        if len(row) < 4:
                            continue
                        data_str = row[0].strip()
                        historico = row[1].strip()
                        valor_str = row[3].strip()

                        if not re.match(r"\d{2}/\d{2}/\d{4}", data_str):
                            continue

                        data = datetime.strptime(data_str, "%d/%m/%Y").date()
                        valor = float(valor_str.replace('.', '').replace(',', '.'))
                        tipo = 'C' if valor > 0 else 'D'

                        dados.append({
                            "data": data,
                            "historico": historico,
                            "valor": round(valor, 2),
                            "tipo": tipo
                        })
                    except:
                        continue

    return pd.DataFrame(dados)
