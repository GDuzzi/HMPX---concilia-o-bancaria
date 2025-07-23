from abc import ABC
import pandas as pd

class BaseConciliacao(ABC):

    def conciliar_entradas(self, transacoes_entrada, extrato_banco: pd.DataFrame, banco: str) -> pd.DataFrame:
        """Concilia as ENTRADAS da empresa com os EXTRATOS do banco informado"""
        transacoes_entrada = pd.DataFrame(transacoes_entrada)
        if transacoes_entrada.empty or extrato_banco.empty:
            return pd.DataFrame()

        df_empresa = transacoes_entrada.copy()
        df_banco = extrato_banco.copy()

        df_banco = df_banco[df_banco["banco"].str.lower() == banco.lower()]

        df_empresa["data"] = pd.to_datetime(df_empresa["data"], errors="coerce", dayfirst=True)
        df_banco["data"] = pd.to_datetime(df_banco["data"], errors="coerce", dayfirst=True)

        df_empresa = df_empresa.dropna(subset=["data"])
        df_banco = df_banco.dropna(subset=["data"])

        empresa_agg = df_empresa[df_empresa["tipo"] == "C"].groupby("data")["valor"].sum().rename("total_relatorio")
        banco_agg = df_banco[df_banco["tipo"] == "C"].groupby("data")["valor"].sum().rename(f"{banco}_extrato")

        resumo = pd.concat([empresa_agg, banco_agg], axis=1).fillna(0)
        resumo["diferenca"] = (resumo["total_relatorio"] - resumo[f"{banco}_extrato"]).round(2)
        resumo["status_conciliacao"] = resumo["diferenca"].apply(lambda d: "OK" if abs(d) < 0.01 else "Analisar")

        return resumo.reset_index()

    def conciliar_saidas(self, transacoes_saida, extrato_banco: pd.DataFrame, banco: str) -> pd.DataFrame:
        """Concilia as SAÍDAS da empresa com os EXTRATOS do banco informado"""
        transacoes_saida = pd.DataFrame(transacoes_saida)
        if transacoes_saida.empty or extrato_banco.empty:
            return pd.DataFrame()

        df_empresa = transacoes_saida.copy()
        df_banco = extrato_banco.copy()

        df_banco = df_banco[df_banco["banco"].str.lower() == banco.lower()]

        df_empresa["data"] = pd.to_datetime(df_empresa["data"], errors="coerce", dayfirst=True)
        df_banco["data"] = pd.to_datetime(df_banco["data"], errors="coerce", dayfirst=True)

        df_empresa = df_empresa.dropna(subset=["data"])
        df_banco = df_banco.dropna(subset=["data"])

        empresa_agg = df_empresa[df_empresa["tipo"] == "D"].groupby("data")["valor"].sum().rename("total_relatorio")
        banco_agg = df_banco[df_banco["tipo"] == "D"].groupby("data")["valor"].sum().rename(f"{banco}_extrato")

        resumo = pd.concat([empresa_agg, banco_agg], axis=1).fillna(0)
        resumo["diferenca"] = (resumo["total_relatorio"] - resumo[f"{banco}_extrato"]).round(2)
        resumo["status_conciliacao"] = resumo["diferenca"].apply(lambda d: "OK" if abs(d) < 0.01 else "Analisar")

        return resumo.reset_index()
