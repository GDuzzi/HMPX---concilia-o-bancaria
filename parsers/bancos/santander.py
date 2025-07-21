import pdfplumber
import pandas as pd
from datetime import datetime
import re
import unicodedata

def normalize(text):
    if not isinstance(text, str):
        return text
    return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8").strip()

def importar_extrato(pdf_path: str) -> pd.DataFrame:
    lancamentos = []
    padrao_linha = re.compile(
        r"^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(\d{3,}|[A-Z0-9/]+)?\s+(-?\d{1,3}(?:\.\d{3})*,\d{2})(?:\s+(-?\d{1,3}(?:\.\d{3})*,\d{2}))?$"
    )

    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text()
            if not texto:
                continue

            for linha in texto.split('\n'):
                linha = linha.strip()
                match = padrao_linha.match(linha)
                if match:
                    data_str, historico, documento, valor_str, saldo_str = match.groups()
                    try:
                        data = datetime.strptime(data_str, "%d/%m/%Y").date()
                        valor = float(valor_str.replace(".", "").replace(",", "."))
                        saldo = float(saldo_str.replace(".", "").replace(",", ".")) if saldo_str else None

                        lancamentos.append({
                            "data": data,
                            "historico": normalize(historico),
                            "documento": documento,
                            "valor": round(valor, 2),
                            "saldo": round(saldo, 2) if saldo is not None else None,
                            "tipo": "C" if valor > 0 else "D"
                        })
                    except Exception as e:
                        print(f"Erro ao processar linha: {linha} -> {e}")

    return pd.DataFrame(lancamentos)
