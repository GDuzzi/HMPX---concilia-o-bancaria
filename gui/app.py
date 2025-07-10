import customtkinter as ctk
from tkinter import filedialog, messagebox
import json
import os
import importlib
import pandas as pd
from datetime import datetime
from pathlib import Path

CAMINHO_CONFIG = os.path.join("config", "empresas.json")
CAMINHO_DEPARA = os.path.join("config", "DE-PARA.xlsx")
CAMINHO_BASE_FORNECEDORES = os.path.join("config", "Base_Fornecedores.xlsx")

def caminho_area_de_trabalho():
    return str(Path.home() / "Desktop")

def identificar_categoria(historico: str) -> str:
    texto = historico.lower()

    if "pix" in texto:
        return "Pix"
    elif "ted" in texto or "crédito em conta" in texto:
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
    
def gerar_resumo_diario(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or not all(col in df.columns for col in ["data", "valor", "tipo", "banco"]):
        return pd.DataFrame()

    df = df.copy()
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0)

    resumo = df.groupby(["data", "banco", "tipo"])["valor"].sum().reset_index()

    # Pivotar para ter colunas como banco_brasil_creditos, sicredi_debitos etc.
    resumo["coluna"] = resumo.apply(
        lambda row: f"{row['banco']}_{'creditos' if row['tipo'] == 'C' else 'debitos'}", axis=1
    )
    resultado = resumo.pivot_table(index="data", columns="coluna", values="valor", fill_value=0).reset_index()

    return resultado

def carregar_empresa():
    with open(CAMINHO_CONFIG, "r", encoding="utf-8") as f:
        dados = json.load(f)
    return {config["nome"]: id_ for id_, config in dados.items()}

def carregar_depara():
    mapa = {}
    try:
        df = pd.read_excel(CAMINHO_DEPARA)
        df.columns = [col.strip().lower() for col in df.columns]
        for _, row in df.iterrows():
            nome = str(row["nome"]).strip().lower()
            codigo = str(row["codigo"])
            mapa[nome] = codigo
    except:
        pass
    return mapa

def salvar_resultados(transacoes, nome_base="extrato", incluir_data=True, salvar_txt=False):
    if transacoes is None or (isinstance(transacoes, pd.DataFrame) and transacoes.empty):
        return

    df = pd.DataFrame(transacoes)

    # Adiciona categoria automática se for extrato
    if "categoria" not in df.columns and "historico" in df.columns:
        df["categoria"] = df["historico"].apply(identificar_categoria)

    data_hoje = datetime.today().strftime("%Y-%m-%d")
    sufixo = f"_{data_hoje}" if incluir_data else ""
    caminho_base = os.path.join(caminho_area_de_trabalho(), f"{nome_base}{sufixo}")

    try:
        # Salvar Excel
        caminho_excel = caminho_base + ".xlsx"
        df.to_excel(caminho_excel, index=False)

        # Salvar TXT apenas se solicitado e tiver coluna 'valor'
        if salvar_txt and "valor" in df.columns:
            caminho_txt = caminho_base + ".txt"
            with open(caminho_txt, "w", encoding="utf-8") as f:
                for _, row in df.iterrows():
                    try:
                        data_fmt = datetime.strptime(str(row["data"]), "%Y-%m-%d").strftime("%d%m%Y")
                    except:
                        data_fmt = row["data"]

                    descricao_formatada = str(row["descricao"]).replace('"', "'") if "descricao" in row else "Extrato Bancário"
                    conta_debito = row.get("conta_debito", "99999")
                    conta_credito = row.get("conta_credito", "99999")
                    linha = f'{data_fmt},{conta_debito},{conta_credito},{abs(row["valor"]):.2f},350,"{descricao_formatada}"\n'
                    f.write(linha)

        # Alerta
        messagebox.showinfo(
            "Arquivos salvos com sucesso!",
            f"Foram gerados:\n\n{os.path.basename(caminho_excel)}"
            + (f"\n{os.path.basename(caminho_txt)}" if salvar_txt else "") +
            f"\n\nNa sua área de trabalho."
        )

    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao salvar arquivos:\n{e}")
        return
    
def conciliar_saidas_por_data(df_empresa, df_banco) -> pd.DataFrame:
    if isinstance(df_empresa, list):
        df_empresa = pd.DataFrame(df_empresa)
    if isinstance(df_banco, list):
        df_banco = pd.DataFrame(df_banco)

    if df_empresa.empty or df_banco.empty:
        return pd.DataFrame()

    df_empresa["data"] = pd.to_datetime(df_empresa["data"], errors="coerce", dayfirst=True)
    df_banco["data"] = pd.to_datetime(df_banco["data"], errors="coerce", dayfirst=True)
    df_empresa = df_empresa.dropna(subset=["data"])
    df_banco = df_banco.dropna(subset=["data"])

    empresa_agg = df_empresa[df_empresa["tipo"] == "D"].groupby("data")["valor"].sum().rename("total_relatorio")
    banco_agg = df_banco[df_banco["tipo"] == "D"].groupby(["data", "banco"])["valor"].sum().unstack(fill_value=0)
    banco_agg.columns = [f"{col}_extrato" for col in banco_agg.columns]

    resumo = pd.concat([empresa_agg, banco_agg], axis=1).fillna(0)

    cols_bancos = [col for col in resumo.columns if col.endswith("_extrato")]
    resumo["total_bancos"] = resumo[cols_bancos].sum(axis=1)
    resumo["diferenca"] = resumo["total_relatorio"] - resumo["total_bancos"]

    # Apenas status da conciliação
    def status(dif):
        if pd.isna(dif) or abs(dif) < 0.01:
            return "OK"
        else:
            return "Analisar"

    resumo["diferenca"] = resumo["diferenca"].round(2)

    def status(dif):
        if pd.isna(dif) or abs(dif) < 0.01:
            return "OK"
        else:
            return "Analisar"

    resumo["status_conciliacao"] = resumo["diferenca"].apply(status)

    return resumo.reset_index()

    

def abrir_tela_parametros(id_empresa, nome_empresa):
    try:
        with open(CAMINHO_CONFIG, "r", encoding="utf-8") as f:
            config = json.load(f)[id_empresa]
    except:
        messagebox.showerror("Erro", f"Não foi possível carregar config da empresa '{id_empresa}'")
        return

    janela = ctk.CTkToplevel()
    janela.title(f"Importar Extrato - {nome_empresa}")
    janela.geometry("800x520")

    frame = ctk.CTkFrame(janela, corner_radius=20)
    frame.pack(expand=True, padx=40, pady=40, fill="both")

    # Título e nome da empresa
    ctk.CTkLabel(frame, text="Importação e Conciliação de Extratos", font=("Arial", 20, "bold")).pack(pady=(20, 10))
    ctk.CTkLabel(frame, text=f"Empresa selecionada: {nome_empresa}", font=("Arial", 12)).pack(pady=(0, 25))

    # Campo conta corrente (único campo manual)
    conta_corrente_entry = ctk.CTkEntry(frame, placeholder_text="Conta Corrente (ex: 10201)", width=340)
    conta_corrente_entry.pack(pady=(0, 30))

    # Menu de banco e tipo (empilhados)
    menu_frame = ctk.CTkFrame(frame, fg_color="transparent")
    menu_frame.pack(pady=(0, 25))

    banco_opcao = ctk.CTkOptionMenu(menu_frame, values=["banco_brasil", "sicredi", "caixa", "itau_mecflu"], width=340)
    banco_opcao.set("banco_brasil")
    banco_opcao.pack(pady=8)

    tipo_opcao = ctk.CTkOptionMenu(menu_frame, values=["SAIDA", "ENTRADA"], width=340)
    tipo_opcao.set("SAIDA")
    tipo_opcao.pack(pady=8)

    extratos_bancarios = []

    def importar_extrato():
        caminho_extrato = filedialog.askopenfilename(
            title="Selecionar Extrato Bancário (PDF)",
            filetypes=[("Arquivos PDF", "*.pdf")]
        )
        if not caminho_extrato:
            return

        banco_selecionado = banco_opcao.get()
        try:
            parser_banco = importlib.import_module(f"parsers.bancos.{banco_selecionado}")
            extrato = parser_banco.importar_extrato(caminho_extrato)
            extrato["banco"] = banco_selecionado
            extratos_bancarios.append(extrato)
            messagebox.showinfo("Sucesso", f"Extrato de {banco_selecionado} adicionado.")
            print(extrato)
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao importar extrato:\n{e}")

    def processar_tudo():
        caminho_relatorio = filedialog.askopenfilename(
            title="Selecionar Relatório da Empresa (CSV ou Excel)",
            filetypes=[("Arquivos CSV", "*.csv"), ("Arquivos Excel", "*.xlsx")]
        )
        if not caminho_relatorio:
            return

        if not extratos_bancarios:
            messagebox.showerror("Erro", "Nenhum extrato foi importado.")
            return

        conta_corrente = conta_corrente_entry.get()
        tipo = tipo_opcao.get()
        mapa = carregar_depara()

        try:
            nome_parser_empresa = config["parser"]
            parser_empresa = importlib.import_module(f"parsers.{nome_parser_empresa}")
            transacoes_empresa = parser_empresa.importar_arquivo(
                path_arquivo=caminho_relatorio,
                tipo=tipo,
                conta_corrente=conta_corrente,
                base_path=CAMINHO_BASE_FORNECEDORES,
                mapa_depara=mapa
            )

            extrato_banco = pd.concat(extratos_bancarios, ignore_index=True)
            extrato_credito = extrato_banco[extrato_banco["tipo"] == "C"]
            extrato_debito = extrato_banco[extrato_banco["tipo"] == "D"]

            salvar_resultados(transacoes_empresa, nome_base="relatorio_empresa", salvar_txt=True)
            salvar_resultados(extrato_credito, nome_base="extrato_creditos")
            salvar_resultados(extrato_debito, nome_base="extrato_debitos")
            resumo = gerar_resumo_diario(extrato_banco)
            salvar_resultados(resumo, nome_base="resumo_diario")

            resumo_conciliacao = conciliar_saidas_por_data(transacoes_empresa, extrato_banco)
            salvar_resultados(resumo_conciliacao, nome_base="conciliacao_por_saldo_saida")

        except Exception as e:
            messagebox.showerror("Erro", f"Erro no processamento:\n{e}")

    # Botões
    botoes_frame = ctk.CTkFrame(frame, fg_color="transparent")
    botoes_frame.pack(pady=10)

    ctk.CTkButton(botoes_frame, text="Adicionar Extrato Bancário", width=240, height=45, font=("Arial", 13, "bold"),
                  fg_color="#3182CE", hover_color="#225EA8", corner_radius=15, command=importar_extrato).pack(side="left", padx=20)

    ctk.CTkButton(botoes_frame, text="Processar Tudo", width=240, height=45, font=("Arial", 13, "bold"),
                  fg_color="#2F855A", hover_color="#276749", corner_radius=15, command=processar_tudo).pack(side="right", padx=20)

    # Rodapé
    ctk.CTkLabel(frame, text="HMPX Sistemas • Desenvolvido para uso interno", font=("Arial", 9)).pack(side="bottom", pady=10)

def iniciar_aplicacao():
    global app
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

    app = ctk.CTk()
    app.title("Conciliador Bancário")
    app.geometry("800x520")
    app.iconbitmap("static/img/Logo_HMPX_Padrao.ico")

    # Frame centralizado
    frame = ctk.CTkFrame(app, corner_radius=20)
    frame.pack(expand=True, padx=40, pady=40, fill="both")

    # Logo
    logo_path = "static/img/Logo_HMPX_Padrao.png"
    if os.path.exists(logo_path):
        from PIL import Image
        logo_img = ctk.CTkImage(Image.open(logo_path), size=(300, 85))
        ctk.CTkLabel(frame, image=logo_img, text="").pack(pady=(10, 10))

    # Título e instrução
    ctk.CTkLabel(frame, text="Conciliador Bancário", font=("Arial", 22, "bold")).pack(pady=(0, 6))
    ctk.CTkLabel(frame, text="Escolha a empresa para iniciar o processo de conciliação", font=("Arial", 15)).pack(pady=(0, 25))

    # Carregar empresas
    empresas_dict = carregar_empresa()
    nomes_empresas = list(empresas_dict.keys())

    # ComboBox mais suave e arredondado
    combo = ctk.CTkComboBox(
        master=frame,
        values=nomes_empresas,
        width=360,
        height=44,
        font=("Arial", 13),
        corner_radius=10,
        border_width=1,
        dropdown_font=("Arial", 12),
        fg_color="#FFFFFF",
        border_color="#CBD5E0",
        button_color="#E2E8F0",
        button_hover_color="#CBD5E0",
        text_color="#2D3748"
    )
    combo.pack(pady=10)

    # Função de confirmação
    def confirmar_empresa():
        nome = combo.get()
        if not nome or nome == "Selecione":
            messagebox.showerror("Erro", "Selecione uma empresa.")
            return
        id_empresa = empresas_dict[nome]
        abrir_tela_parametros(id_empresa, nome)
        app.withdraw()

    # Botão com visual mais moderno e arredondado
    ctk.CTkButton(
        master=frame,
        text="Iniciar Conciliação",
        height=48,
        width=220,
        font=("Arial", 14, "bold"),
        corner_radius=20,
        fg_color="#3182CE",           # azul profissional
        hover_color="#225EA8",        # hover mais escuro
        text_color="white",
        command=confirmar_empresa
    ).pack(pady=35)

    # Rodapé
    ctk.CTkLabel(
        frame,
        text="HMPX Sistemas • Desenvolvido para uso interno",
        font=("Arial", 11),
        text_color="#4A5568"
    ).pack(side="bottom", pady=10)

    app.mainloop()
