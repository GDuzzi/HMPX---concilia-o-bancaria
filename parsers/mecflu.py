# parsers/mecflu.py

import pandas as pd
import os
import unicodedata
from datetime import datetime

def normalize_text(text):
    if not isinstance(text, str): text = str(text)
    return " ".join(unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("ascii").lower().split())

def parse_valor(valor):
    valor = str(valor).replace("R$", "").replace("-", "").strip().replace(" ", "")
    valor = valor.replace(".", "").replace(",", ".") if "," in valor else valor
    try: return float(valor)
    except: return 0.0

def importar_arquivo(path_arquivo, tipo, conta_corrente, base_path, mapa_depara):
    mapa = {}
    if tipo == 'SAIDA' and base_path:
        df_base = pd.read_excel(base_path) if base_path.endswith(".xlsx") else pd.read_csv(base_path)
        df_base.columns = [normalize_text(col) for col in df_base.columns]
        for _, row in df_base.iterrows():
            nome = normalize_text(row['fornecedor'])
            chave = nome.split()[0] if nome else ""
            mapa[chave] = str(row['codigo'])

    df = pd.read_csv(path_arquivo, delimiter=';', encoding='latin-1', header=1)
    df.columns = [normalize_text(c) for c in df.columns]
    df.dropna(subset=[df.columns[0]], inplace=True)

    lancamentos = []
    for _, row in df.iterrows():
        try:
            part = row.get('fornecedor', row.get('cliente', ''))
            doc = row.get('documento', '')
            hist = row.get('historico', '')
            obs = row.get('obs', '')
            data = row.get('data de pagamento', row.get('data', ''))
            valor = parse_valor(row.get('valor pago', row.get('valor', '0')))

            if not data or not part or valor == 0:
                continue

            hist_final = normalize_text(f"{part} - {doc} - {hist} - {obs}").upper()

            if tipo == 'SAIDA':
                doc_norm = normalize_text(doc)
                nome_norm = normalize_text(part)

                if nome_norm in mapa_depara:
                    deb = mapa_depara[nome_norm]
                elif 'cartao' in doc_norm and 'credito' in doc_norm: deb = '1737'
                elif 'juros' in doc_norm: deb = '4701'
                elif 'tarifa' in doc_norm: deb = '4698'
                elif 'salario' in doc_norm or 'holerite' in doc_norm: deb = '1634'
                elif 'seguro' in doc_norm: deb = '1744'
                elif doc_norm == 'nd': deb = 123
                else:
                    chave = nome_norm.split()[0] if nome_norm else ""
                    deb = mapa.get(chave)

                cred = conta_corrente
                valor *= -1

            elif tipo == 'ENTRADA':
                deb = conta_corrente
                cred = 1234
            else:
                continue

            lancamentos.append({
                "data": data,
                "descricao": hist_final,
                "valor": valor,
                "conta_debito": deb,
                "conta_credito": cred,
                "tipo": "D" if tipo == "SAIDA" else "C"
            })
        except:
            continue

    return lancamentos
