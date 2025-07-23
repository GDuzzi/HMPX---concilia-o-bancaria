import pandas as pd

def remover_transferencias_entre_bancos(df_banco: pd.DataFrame) -> pd.DataFrame:
    if df_banco.empty or not all(col in df_banco.columns for col in ["data", "valor", "tipo", "banco"]):
        return df_banco

    df = df_banco.copy()
    df["data"] = pd.to_datetime(df["data"], errors="coerce", dayfirst=True)
    df = df.dropna(subset=["data"])
    df["valor_abs"] = df["valor"].abs()
    df["chave"] = df["data"].astype(str) + "_" + df["valor_abs"].astype(str)

    creditos = df[df["tipo"] == "C"]
    debitos = df[df["tipo"] == "D"]
    chaves_transferencia = set(creditos["chave"]).intersection(set(debitos["chave"]))

    df_filtrado = df[~df["chave"].isin(chaves_transferencia)].drop(columns=["valor_abs", "chave"])
    return df_filtrado
