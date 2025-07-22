import os
import pandas as pd
from datetime import datetime
from tkinter import filedialog, messagebox
from PIL import Image
from services.config import caminho_area_de_trabalho
from services.depara import carregar_depara, normalize_text


def identificar_categoria(historico: str) -> str:
    texto = historico.lower()

    if "entre contas" in texto or "transferência entre contas" in texto or "movimentação entre contas" in texto:
        return "Transferência Interna"
    elif "Pix" in texto:
        return "Pix"
    elif "Ted" in texto or "crédito em conta" in texto:
        return "TED"
    elif "cartão" in texto or "compra" in texto:
        return "Cartão"
    elif "boleto" in texto:
        return "Boleto"
    elif "tarifa" in texto or "mensal" in texto or "relac" in texto or "cobrança" in texto:
        return "Tarifa"
    elif "transferência" in texto:
        return "Transferência"
    elif "recebimento" in texto or "fornecedor" in texto or "receita" in texto:
        return "Recebimento"
    elif "pagto" in texto or "débito" in texto or "doc" in texto:
        return "Pagamento"
    else:
        return "Outros"


def salvar_resultados(transacoes, nome_base="extrato", incluir_data=True, salvar_txt=False):
    if transacoes is None or (isinstance(transacoes, pd.DataFrame) and transacoes.empty):
        return
    
    df = pd.DataFrame(transacoes)

    if "categoria" not in df.columns and "historico" in df.columns:
        df["categoria"] = df["historico"].apply(identificar_categoria)
    
    data_hoje = datetime.today().strftime("%Y-%m-%d")
    sufixo = f"_{data_hoje}" if incluir_data else ""
    caminho_base = os.path.join(caminho_area_de_trabalho(), f"{nome_base}{sufixo}")

    try:
        caminho_excel = caminho_base + ".xlsx"
        df.to_excel(caminho_excel, index=False)

        if salvar_txt and "valor" in df.columns:
            caminho_txt = caminho_base + ".txt"
            with open(caminho_txt, "w", encoding="utf-8") as f:
                for _, row in df.iterrows():
                    try:
                        data_fmt = datetime.strptime(str(row["data"]), "%Y-%m-%d").strftime("%d%m%Y")
                    except:
                        data_fmt = row["data"]

                    descricao_formatada = str(row.get("descricao", "Extrato bancário")).replace('"', "'")
                    conta_debito = row.get("conta_debito", "99999")
                    conta_credito = row.get("conta_credito", "99999")
                    linha = f'{data_fmt},{conta_debito},{conta_credito},{abs(row["valor"]):2f},350,"{descricao_formatada}"\n'
                    f.write(linha)
        
        messagebox.showinfo(
            "Arquivos salvos com sucesso!",
            f"Foram gerados:\n\n{os.path.basename(caminho_excel)}"
            + (f"\n{os.path.basename(caminho_txt)}" if salvar_txt else "") +
            f"\n\nNa sua área de trabalho."
        )

    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao salvar arquivos:\n{e}")


def gerar_resumo_diario(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or not all(col in df.columns for col in ["data", "valor", "tipo", "banco"]):
        return pd.DataFrame()
    
    df = df.copy()
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0)

    resumo = df.groupby(["data", "banco", "tipo"])["valor"].sum().reset_index()
    resumo["coluna"] = resumo.apply(
        lambda row: f"{row['banco']}_{'creditos' if row['tipo'] == 'C' else 'debitos'}", axis=1
    )
    resultado = resumo.pivot_table(index="data", columns="coluna", values="valor", fill_value=0).reset_index()
    return resultado

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


def gerar_txt_a_partir_do_excel(caminho_depara, func_salvar=salvar_resultados):
    try:
        caminho_planilha = filedialog.askopenfilename(
            title="Selecionar planilha Excel",
            filetypes=[("Arquivos Excel", "*.xlsx")]
        )
        if not caminho_planilha:
            return
        if not os.path.exists(caminho_planilha):
            messagebox.showerror("Erro", "O arquivo Excel não foi encontrado.")
            return

        df = pd.read_excel(caminho_planilha)
        if df.empty:
            messagebox.showerror("Erro", "O arquivo Excel está vazio.")
            return

        mapa = carregar_depara(caminho_depara)

        if "descricao" in df.columns and "conta_debito" in df.columns:
            for i, row in df.iterrows():
                desc = str(row["descricao"])
                conta_atual = str(row["conta_debito"])
                fornecedor = desc.split("-")[0].strip().lower()
                fornecedor_normalizado = normalize_text(fornecedor)
                conta_nova = mapa.get(fornecedor_normalizado)
                if conta_nova and conta_nova != conta_atual:
                    df.at[i, "conta_debito"] = conta_nova

        func_salvar(df.to_dict(orient="records"), nome_base="relatorio_empresa", incluir_data=False, salvar_txt=True)

    except Exception as e:
        messagebox.showerror("Erro", f"Ocorreu um erro ao gerar o TXT:\n{e}")