import pandas as pd
import unicodedata
from datetime import datetime

def normalize_text(text):
    if not isinstance(text, str):
        text = str(text)
    return " ".join(unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("ascii").lower().split())

def parse_valor(valor):
    if pd.isna(valor):
        return 0.0
    valor = str(valor).strip().replace("R$", "").replace(" ", "")
    if "." in valor and "," in valor:
        valor = valor.replace(".", "").replace(",", ".")
    elif "," in valor:
        valor = valor.replace(",", ".")
    elif "." in valor:
        partes = valor.split(".")
        if len(partes[-1]) > 2:
            valor = valor.replace(".", "")
    try:
        return float(valor)
    except:
        return 0.0

# Dicionário com contas padrão
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

def importar_arquivo(path_arquivo, conta_corrente, base_path, mapa_depara, tipo):
    mapa = {}

    # Carrega base de fornecedores
    if base_path:
        df_base = pd.read_excel(base_path) if base_path.endswith(".xlsx") else pd.read_csv(base_path)
        df_base.columns = [normalize_text(col) for col in df_base.columns]
        for _, row in df_base.iterrows():
            nome = normalize_text(row.get('fornecedor', ''))
            chave = nome.split()[0] if nome else ""
            mapa[chave] = str(row.get('codigo', ''))

    df = pd.read_csv(path_arquivo, delimiter=';', encoding='latin-1', header=0, dtype=str)
    df.columns = [normalize_text(col) for col in df.columns]
    df.dropna(subset=[df.columns[0]], inplace=True)

    lancamentos = []
    conciliacao_movimentos = []

    for _, row in df.iterrows():
        try:
            data_raw = row.get("datamovimento", "")
            valormovimento = parse_valor(row.get("valormovimento", 0))

            # ✅ Proteção contra explosão de registros
            if isinstance(valormovimento, (int, float)) and valormovimento != 0:
                data_conc = pd.to_datetime(data_raw, format="%Y-%m-%d", errors="coerce")
                if not pd.isna(data_conc):
                    conciliacao_movimentos.append({
                        "data": data_conc.date(),
                        "valor": float(valormovimento),
                        "tipo": "C" if valormovimento > 0 else "D"
                    })
                continue  # ← evita inclusão indevida em 'lancamentos'

            valorentrada = parse_valor(row.get("valorentrada", 0))
            valorsaida = parse_valor(row.get("valorsaida", 0))
            historico = row.get("fornecedor_observacao", "")
            if not data_raw or (valorentrada == 0 and valorsaida == 0):
                continue

            data = pd.to_datetime(data_raw, errors="coerce")
            if pd.isna(data):
                continue
            data = data.date()

            hist_norm = normalize_text(historico)
            chave = hist_norm.split()[0] if hist_norm else ""

            doc_norm = hist_norm
            if hist_norm in mapa_depara:
                deb = mapa_depara[hist_norm]
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
            elif 'nd' in doc_norm.strip().split():
                deb = CONTAS_PADRAO["nd"]
            else:
                deb = mapa.get(chave, CONTAS_PADRAO["desconhecido"])

            if valorentrada > 0:
                tipo_lanc = "C"
                valor = valorentrada
                conta_debito = conta_corrente
                conta_credito = CONTAS_PADRAO["entrada_credito_padrao"]
            elif valorsaida > 0:
                tipo_lanc = "D"
                valor = valorsaida
                conta_debito = deb
                conta_credito = conta_corrente
            else:
                continue

            lancamentos.append({
                "data": data,
                "descricao": historico.strip().upper(),
                "valor": float(valor),
                "conta_debito": conta_debito,
                "conta_credito": conta_credito,
                "tipo": tipo_lanc
            })

        except Exception as e:
            print(f"⚠️ Erro ao processar linha: {e}")
            continue

    print(f"✅ Total de lançamentos contábeis: {len(lancamentos)}")
    print(f"✅ Total de movimentos para conciliação: {len(conciliacao_movimentos)}")

    return lancamentos, conciliacao_movimentos


def conciliar_entradas(transacoes_entrada, extrato_banco):
    if not transacoes_entrada or extrato_banco.empty:
        return pd.DataFrame()
    
    print(f"📥 Entradas da empresa: {len(transacoes_entrada)}")
    print(f"🏦 Entradas do banco  : {len(extrato_banco)}")

    df_empresa = pd.DataFrame(transacoes_entrada)
    df_banco = extrato_banco.copy()

    df_empresa["data"] = pd.to_datetime(df_empresa["data"], errors="coerce", dayfirst=True)
    df_banco["data"] = pd.to_datetime(df_banco["data"], errors="coerce", dayfirst=True)
    df_empresa = df_empresa.dropna(subset=["data"])
    df_banco = df_banco.dropna(subset=["data"])
    print("→ Empresa tipo C:", (df_empresa["tipo"] == "C").sum())
    print("→ Banco tipo C  :", (df_banco["tipo"] == "C").sum())


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
    resumo["diferenca"] = (resumo["total_relatorio"] - resumo["total_bancos"]).round(2)
    resumo["status_conciliacao"] = resumo["diferenca"].apply(lambda d: "OK" if abs(d) < 0.01 else "Analisar")

    return resumo.reset_index()