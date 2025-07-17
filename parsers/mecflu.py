import pandas as pd
import unicodedata
from datetime import datetime

def normalize_text(text):
    if not isinstance(text, str):
        text = str(text)
    return " ".join(unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("ascii").lower().split())

def parse_valor(valor):
    valor = str(valor).replace("R$", "").replace("-", "").strip().replace(" ", "")
    valor = valor.replace(".", "").replace(",", ".") if "," in valor else valor
    try:
        return float(valor)
    except:
        return 0.0

# Contas contábeis padrão
CONTAS_PADRAO = {
    "cartao": "1737",
    "juros": "4701",
    "tarifa": "4698",
    "CPFL": "4477",
    "salario": "1634",
    "holerite": "1634",
    "estagio": "1634",  
    "seguro": "1744",
    "desconhecido": "4951",
    "nd": "4582",
    "prolabore": "1635",
    "entrada_credito_padrao": "142"
}

def importar_arquivo(path_arquivo, tipo, conta_corrente, base_path, mapa_depara):
    mapa = {}

    # Carrega base de fornecedores (se SAIDA)
    if tipo == 'SAIDA' and base_path:
        df_base = pd.read_excel(base_path) if base_path.endswith(".xlsx") else pd.read_csv(base_path)
        df_base.columns = [normalize_text(col) for col in df_base.columns]
        for _, row in df_base.iterrows():
            nome = normalize_text(row.get('fornecedor', ''))
            chave = nome.split()[0] if nome else ""
            mapa[chave] = str(row.get('codigo', ''))

    # Lê o relatório da empresa
    df = pd.read_csv(path_arquivo, delimiter=';', encoding='latin-1', header=1)
    df.columns = [normalize_text(c.lower()) for c in df.columns]
    df.dropna(subset=[df.columns[0]], inplace=True)

    lancamentos = []
    conciliacao = []

    for _, row in df.iterrows():
        try:
            part = row.get('fornecedor', row.get('cliente', ''))
            doc = row.get('documento', '')
            hist = row.get('historico', '')
            obs = row.get('obs', '')

            data_raw = (
                row.get('data de pagamento') or
                row.get('pagamento') or
                row.get('data') or ''
            )
            try:
                data = pd.to_datetime(data_raw, dayfirst=True).date()
            except:
                continue

            valor = parse_valor(row.get('valor pago', row.get('valor', '0')))
            if not data or not part or valor == 0:
                continue

            hist_final = normalize_text(f"{part} - {doc} - {hist} - {obs}").upper()

            if tipo == 'SAIDA':
                doc_norm = normalize_text(f"{part} - {doc}").lower()
                nome_norm = normalize_text(part)
                chave = nome_norm.split()[0] if nome_norm else ""

                if nome_norm in mapa_depara:
                    deb = mapa_depara[nome_norm]
                elif 'cartao' in doc_norm or 'credito' in doc_norm:
                    deb = CONTAS_PADRAO['cartao']
                elif 'juros' in doc_norm:
                    deb = CONTAS_PADRAO["juros"]
                elif 'tarifa' in doc_norm:
                    deb = CONTAS_PADRAO["tarifa"]
                elif 'salario' in doc_norm or 'holerite' in doc_norm or 'estagio' in doc_norm:
                    deb = CONTAS_PADRAO["salario"]
                elif 'prolabore' in doc_norm or 'pro-labore' in doc_norm:
                    deb = CONTAS_PADRAO["prolabore"]
                elif 'seguro' in doc_norm:
                    deb = CONTAS_PADRAO["seguro"]
                elif 'energia' in doc_norm:
                    deb = CONTAS_PADRAO["CPFL"]
                elif doc_norm.strip() in ['nd', 'n.d', 'n.d.']:
                    deb = CONTAS_PADRAO["nd"]
                else:
                    deb = mapa.get(chave, CONTAS_PADRAO["desconhecido"])

                cred = conta_corrente
                valor = -abs(valor)
                tipo_mov = "D"

            elif tipo == 'ENTRADA':
                deb = conta_corrente
                cred = CONTAS_PADRAO["entrada_credito_padrao"]
                tipo_mov = "C"
            else:
                continue

            lancamentos.append({
                "data": data,
                "descricao": hist_final,
                "valor": valor,
                "conta_debito": deb,
                "conta_credito": cred,
                "tipo": tipo_mov
            })

            conciliacao.append({
                "data": data,
                "valor": abs(valor),
                "tipo": tipo_mov
            })

        except:
            continue

        

    return lancamentos, conciliacao


def conciliar_entradas(transacoes_entrada, extrato_banco):
    if not transacoes_entrada or extrato_banco.empty:
        return pd.DataFrame()
    

    df_empresa = pd.DataFrame(transacoes_entrada)
    df_banco = extrato_banco.copy()

    df_empresa["data"] = pd.to_datetime(df_empresa["data"], errors="coerce", dayfirst=True)
    df_banco["data"] = pd.to_datetime(df_banco["data"], errors="coerce", dayfirst=True)
    df_empresa = df_empresa.dropna(subset=["data"])
    df_banco = df_banco.dropna(subset=["data"])


    empresa_agg = df_empresa[df_empresa["tipo"] == "C"].groupby("data")["valor"].sum().rename("total_relatorio")
    banco_agg = df_banco[df_banco["tipo"] == "C"].groupby(["data", "banco"])["valor"].sum().unstack(fill_value=0)
    banco_agg.columns = [f"{col}_extrato" for col in banco_agg.columns]

    resumo = pd.concat([empresa_agg, banco_agg], axis=1).fillna(0)
    resumo["total_bancos"] = resumo.filter(like="_extrato").sum(axis=1)
    resumo["diferenca"] = (resumo["total_relatorio"] - resumo["total_bancos"]).round(2)
    resumo["status_conciliacao"] = resumo["diferenca"].apply(lambda d: "OK" if abs(d) < 0.01 else "Analisar")

    return resumo.reset_index()

def conciliar_saidas(transacoes_saida, extrato_banco):
    if not transacoes_saida or extrato_banco.empty:
        return pd.DataFrame()

    df_empresa = pd.DataFrame(transacoes_saida)
    df_banco = extrato_banco.copy()

    df_empresa["data"] = pd.to_datetime(df_empresa["data"], errors="coerce", dayfirst=True)
    df_banco["data"] = pd.to_datetime(df_banco["data"], errors="coerce", dayfirst=True)
    df_empresa = df_empresa.dropna(subset=["data"])
    df_banco = df_banco.dropna(subset=["data"])

    empresa_agg = df_empresa[df_empresa["tipo"] == "D"].groupby("data")["valor"].sum().rename("total_relatorio")
    banco_agg = df_banco[df_banco["tipo"] == "D"].groupby(["data", "banco"])["valor"].sum().unstack(fill_value=0)
    banco_agg.columns = [f"{col}_extrato" for col in banco_agg.columns]

    resumo = pd.concat([empresa_agg, banco_agg], axis=1).fillna(0)
    resumo["total_bancos"] = resumo.filter(like="_extrato").sum(axis=1)
    resumo["diferenca"] = (resumo["total_bancos"] + resumo["total_relatorio"]).round(2)
    resumo["status_conciliacao"] = resumo["diferenca"].apply(lambda d: "OK" if abs(d) < 0.01 else "Analisar")

    return resumo.reset_index()
