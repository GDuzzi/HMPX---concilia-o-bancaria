import pandas as pd
import unicodedata
from datetime import datetime
from rapidfuzz import process, fuzz

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
    mapa_codigo = {}
    mapa_nome = {}

    # Carrega base de fornecedores
    if base_path:
        df_base = pd.read_excel(base_path) if base_path.endswith(".xlsx") else pd.read_csv(base_path)
        df_base.columns = [normalize_text(col) for col in df_base.columns]
        for _, row in df_base.iterrows():
            nome_original = str(row.get('fornecedor', '')).strip()
            nome_norm = normalize_text(nome_original)
            if nome_norm:
                mapa_codigo[nome_norm] = str(row.get('codigo', ''))
                mapa_nome[nome_norm] = nome_original

    # Leitura do relatório (CSV com ; e latin-1)
    df = pd.read_csv(path_arquivo, delimiter=';', encoding='latin-1', header=0, dtype=str)
    df.columns = [normalize_text(col) for col in df.columns]
    df.dropna(subset=[df.columns[0]], inplace=True)

    lancamentos = []
    conciliacao_movimentos = []

    if not hasattr(importar_arquivo, "cache_fornecedor"):
        importar_arquivo.cache_fornecedor = {}
    if not hasattr(importar_arquivo, "fornecedor_index"):
        importar_arquivo.fornecedor_index = list(mapa_codigo.keys())

    for _, row in df.iterrows():
        try:
            data_raw = row.get("datamovimento", "")
            valormovimento = parse_valor(row.get("valormovimento", 0))

            if isinstance(valormovimento, (int, float)) and valormovimento != 0:
                data_conc = pd.to_datetime(data_raw, format="%Y-%m-%d", errors="coerce")
                if not pd.isna(data_conc):
                    conciliacao_movimentos.append({
                        "data": data_conc.date(),
                        "valor": float(valormovimento),
                        "tipo": "C" if valormovimento > 0 else "D"
                    })
                continue

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
            cache_key = hist_norm

            if cache_key in importar_arquivo.cache_fornecedor:
                fornecedor_nome, deb = importar_arquivo.cache_fornecedor[cache_key]
            else:
                fornecedor_nome = ""
                deb = CONTAS_PADRAO["desconhecido"]

                if hist_norm in mapa_depara:
                    deb = mapa_depara[hist_norm]
                elif hist_norm in mapa_codigo:
                    deb = mapa_codigo[hist_norm]
                    fornecedor_nome = mapa_nome[hist_norm]
                else:
                    match = process.extractOne(
                        hist_norm,
                        importar_arquivo.fornecedor_index,
                        scorer=fuzz.ratio,
                        score_cutoff=85
                    )
                    if match:
                        melhor = match[0]
                        deb = mapa_codigo[melhor]
                        fornecedor_nome = mapa_nome[melhor]

                importar_arquivo.cache_fornecedor[cache_key] = (fornecedor_nome, deb)

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
                "tipo": tipo_lanc,
                "fornecedor_nome": fornecedor_nome
            })

        except Exception as e:
            continue

    return lancamentos, conciliacao_movimentos

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
    resumo["diferenca"] = (resumo["total_relatorio"] - resumo["total_bancos"]).round(2)
    resumo["status_conciliacao"] = resumo["diferenca"].apply(lambda d: "OK" if abs(d) < 0.01 else "Analisar")

    return resumo.reset_index()