import customtkinter as ctk
from tkinter import filedialog, messagebox
import json
import os
import importlib
import pandas as pd
from datetime import datetime

CAMINHO_CONFIG = os.path.join("config", "empresas.json")
CAMINHO_DEPARA = os.path.join("config", "DE-PARA.xlsx")
CAMINHO_BASE_FORNECEDORES = os.path.join("config", "Base_Fornecedores.xlsx")

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

def salvar_resultados(transacoes, janela_pai):
    if not transacoes or len(transacoes) == 0:
        messagebox.showwarning("Aviso", "Nenhuma transação para exportar.")
        return

    df = pd.DataFrame(transacoes)

    caminho_base = filedialog.asksaveasfilename(
        title="Salvar Arquivos",
        defaultextension=".xlsx",
        filetypes=[("Excel", "*.xlsx")],
        initialfile="lancamentos_conciliacao"
    )

    if not caminho_base:
        return

    try:
        # Salva Excel
        df.to_excel(caminho_base, index=False)

        # Salva TXT
        caminho_txt = caminho_base.replace(".xlsx", ".txt")
        with open(caminho_txt, "w", encoding="utf-8") as f:
            for _, row in df.iterrows():
                try:
                    data_fmt = datetime.strptime(str(row["data"]), "%Y-%m-%d").strftime("%d%m%Y")
                except:
                    data_fmt = row["data"]

                descricao_formatada = str(row["descricao"]).replace('"', "'")
                linha = f'{data_fmt},{row["conta_debito"]},{row["conta_credito"]},{abs(row["valor"]):.2f},350,"{descricao_formatada}"\n'
                f.write(linha)

        messagebox.showinfo("Sucesso", "Arquivos gerados com sucesso!")

    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao salvar arquivos:\n{e}")

def abrir_tela_parametros(id_empresa, nome_empresa):
    try:
        with open(CAMINHO_CONFIG, "r", encoding="utf-8") as f:
            config = json.load(f)[id_empresa]
    except:
        messagebox.showerror("Erro", f"Não foi possível carregar config da empresa '{id_empresa}'")
        return

    janela = ctk.CTkToplevel()
    janela.title(f"Importar Extrato - {nome_empresa}")
    janela.geometry("800x500")

    ctk.CTkLabel(janela, text=f"Parâmetros para {nome_empresa}", font=("Arial", 16)).pack(pady=10)

    conta_corrente_entry = ctk.CTkEntry(janela, placeholder_text="Conta Corrente (ex: 10201)")
    conta_corrente_entry.pack(pady=10)

    conta_fornecedores_entry = ctk.CTkEntry(janela, placeholder_text="Conta Fornecedores (ex: 14008)")
    conta_fornecedores_entry.pack(pady=10)

    conta_clientes_entry = ctk.CTkEntry(janela, placeholder_text="Conta Clientes (ex: 12001)")
    conta_clientes_entry.pack(pady=10)

    tipo_opcao = ctk.CTkOptionMenu(janela, values=["SAIDA", "ENTRADA"])
    tipo_opcao.set("SAIDA")
    tipo_opcao.pack(pady=10)

    def executar_importacao():
        caminho_arquivo = filedialog.askopenfilename(title="Selecionar Extrato CSV", filetypes=[("Arquivos CSV", "*.csv")])
        if not caminho_arquivo:
            return

        conta_corrente = conta_corrente_entry.get()
        conta_fornecedor = conta_fornecedores_entry.get()
        conta_cliente = conta_clientes_entry.get()
        tipo = tipo_opcao.get()
        mapa = carregar_depara()

        try:
            nome_parser = config["parser"]
            parser_modulo = importlib.import_module(f"parsers.{nome_parser}")
            transacoes = parser_modulo.importar_arquivo(
                path_arquivo=caminho_arquivo,
                tipo=tipo,
                conta_corrente=conta_corrente,
                conta_fornecedor=conta_fornecedor,
                conta_cliente=conta_cliente,
                base_path=CAMINHO_BASE_FORNECEDORES,
                mapa_depara=mapa
            )
        except Exception as e:
            messagebox.showerror("Erro ao processar", f"Erro no parser:\n{e}")
            return

        if not transacoes:
            messagebox.showinfo("Resultado", "Nenhuma transação encontrada.")
            return

        salvar_resultados(transacoes, janela)

    ctk.CTkButton(janela, text="Selecionar e Importar Extrato", command=executar_importacao).pack(pady=20)

def iniciar_aplicacao():
    global app  # <--- isso permite usar app.withdraw() depois
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

    app = ctk.CTk()
    app.title("Conciliador Bancário")
    app.geometry("600x300")

    empresas_dict = carregar_empresa()
    nomes_empresas = list(empresas_dict.keys())

    label = ctk.CTkLabel(app, text="Selecione uma empresa", font=("Arial", 16))
    label.pack(pady=20)

    combo = ctk.CTkComboBox(app, values=nomes_empresas, width=300)
    combo.pack(pady=10)

    def confirmar_empresa():
        nome = combo.get()
        if not nome:
            messagebox.showerror("Erro", "Selecione uma empresa.")
            return
        id_empresa = empresas_dict[nome]
        abrir_tela_parametros(id_empresa, nome)
        app.withdraw()  # <-- substitui o app.destroy()

    ctk.CTkButton(app, text="Continuar", command=confirmar_empresa).pack(pady=20)

    app.mainloop()
