import customtkinter as ctk
from tkinter import filedialog, messagebox
import json
import os
import importlib
import pandas as pd
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageTk
import threading
from customtkinter import CTkImage
import unicodedata
import sys
import os
from gui.tela_depara import abrir_tela_depara

def recurso_path(rel_path):
    """Resolve caminho para arquivos estáticos, compatível com PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, rel_path)
    return os.path.join(os.path.abspath("."), rel_path)

CAMINHO_CONFIG = recurso_path(os.path.join("config", "empresas.json"))
# CAMINHO_DEPARA = os.path.join("config", "DE-PARA.xlsx")
CAMINHO_DEPARA = r"\\192.168.10.1\hmpx$\Contabil\Controles Internos\__BEATRIZ\projeto\DE-PARA (1).xlsx"
CAMINHO_BASE_FORNECEDORES = recurso_path(os.path.join("config", "Base_Fornecedores.xlsx"))


def caminho_area_de_trabalho():
    return str(Path.home() / "Desktop")

def identificar_categoria(historico: str) -> str:
    texto = historico.lower()

    if "entre contas" in texto or "transferência entre contas" in texto or "movimentação entre contas" in texto:
        return "Transferência Interna"
    elif "pix" in texto:
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
def normalize_text(text):
    if not isinstance(text, str):
        text = str(text)
    return " ".join(unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("ascii").lower().split())

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
        print(f"[DEBUG] Carregando DE-PARA a partir de: {CAMINHO_DEPARA}")
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
    
def gerar_txt_a_partir_do_excel():
    try:
        caminho_planilha = filedialog.askopenfilename(
            title="Selecionar planilha Excel",
            filetypes=[("Arquivos Excel", "*.xlsx")]
        )
        if not caminho_planilha:
            return
        if not os.path.exists(caminho_planilha):
            messagebox.showerror("Erro", "O arquivo relatorio_empresa.xlsx não foi encontrado na sua área de trabalho.")
            return

        df = pd.read_excel(caminho_planilha)
        if df.empty:
            messagebox.showerror("Erro", "O arquivo relatorio_empresa.xlsx está vazio.")
            return

        # Carregar DE-PARA
        mapa = carregar_depara()

        if "descricao" in df.columns and "conta_debito" in df.columns:
            for i, row in df.iterrows():
                desc = str(row["descricao"])
                conta_atual = str(row["conta_debito"])
                fornecedor = desc.split("-")[0].strip().lower()
                fornecedor_normalizado = normalize_text(fornecedor)
                conta_nova = mapa.get(fornecedor_normalizado)
                if conta_nova and conta_nova != conta_atual:
                    df.at[i, "conta_debito"] = conta_nova

        # Salva Excel atualizado e gera o TXT
        salvar_resultados(df.to_dict(orient="records"), nome_base="relatorio_empresa", incluir_data=False, salvar_txt=True)

    except Exception as e:
        messagebox.showerror("Erro", f"Ocorreu um erro ao gerar o TXT:\n{e}")

def remover_transferencias_entre_bancos(df_banco: pd.DataFrame) -> pd.DataFrame:
    if df_banco.empty or not all(col in df_banco.columns for col in ["data", "valor", "tipo", "banco"]):
        return df_banco

    df = df_banco.copy()
    df["data"] = pd.to_datetime(df["data"], errors="coerce", dayfirst=True)
    df = df.dropna(subset=["data"])
    df["valor_abs"] = df["valor"].abs()
    df["chave"] = df["data"].astype(str) + "_" + df["valor_abs"].astype(str)

    # Separa C e D
    creditos = df[df["tipo"] == "C"]
    debitos = df[df["tipo"] == "D"]

    # Encontra chaves que se repetem (mesma data e mesmo valor) entre créditos e débitos
    chaves_transferencia = set(creditos["chave"]).intersection(set(debitos["chave"]))

    # Remove linhas que têm essas chaves
    df_filtrado = df[~df["chave"].isin(chaves_transferencia)].drop(columns=["valor_abs", "chave"])
    return df_filtrado
    
def abrir_tela_parametros(id_empresa, nome_empresa):

    try:
        with open(CAMINHO_CONFIG, "r", encoding="utf-8") as f:
            config = json.load(f)[id_empresa]
    except:
        messagebox.showerror("Erro", f"Não foi possível carregar config da empresa '{id_empresa}'")
        return

    janela = ctk.CTkToplevel()
    def ao_fechar_janela():
        janela.destroy()
        app.deiconify()  # volta para a tela inicial

    janela.protocol("WM_DELETE_WINDOW", ao_fechar_janela)

    janela.protocol("WM_DELETE_WINDOW", ao_fechar_janela)
    janela.title(f"Importar Extrato - {nome_empresa}")
    janela.geometry("1280x520")

    frame = ctk.CTkFrame(janela, corner_radius=20)
    frame.pack(expand=True, padx=40, pady=40, fill="both")

    ctk.CTkLabel(frame, text="Importação e Conciliação de Extratos", font=("Arial", 20, "bold")).pack(pady=(20, 10))
    ctk.CTkLabel(frame, text=f"Empresa selecionada: {nome_empresa}", font=("Arial", 12)).pack(pady=(0, 25))

    conta_corrente_entry = ctk.CTkEntry(frame, placeholder_text="Conta Corrente (ex: 10201)", width=340)
    conta_corrente_entry.pack(pady=(0, 30))

    nome_parser_empresa = config["parser"]

    menu_frame = ctk.CTkFrame(frame, fg_color="transparent")
    menu_frame.pack(pady=(0, 25))

    banco_opcao = ctk.CTkOptionMenu(menu_frame, values=["banco_brasil", "sicredi", "caixa", "itau","santander", "mercado_pago"], width=340)
    banco_opcao.set("banco_brasil")
    banco_opcao.pack(pady=8)

    if nome_parser_empresa != "imperio":
        tipo_opcao = ctk.CTkOptionMenu(menu_frame, values=["SAIDA", "ENTRADA"], width=340)
        tipo_opcao.set("SAIDA")
        tipo_opcao.pack(pady=8)
    else:
        tipo_opcao = None

    parser_empresa = None
    transacoes_saida, transacoes_entrada, extratos_bancarios = [], [], []
    conciliacoes_entrada, conciliacoes_saida = [], []

    def importar_relatorios_empresa():
        caminhos_relatorios = filedialog.askopenfilenames(
            title="Selecionar Relatórios da Empresa",
            filetypes=[("Arquivos CSV", "*.csv"), ("Arquivos Excel", "*.xlsx"), ("Arquivos PDF", "*.pdf")]
        )
        if not caminhos_relatorios:
            return

        tipos = [tipo_opcao.get()] if tipo_opcao else [None]
        modo_automatico = tipo_opcao is None
        conta_corrente = conta_corrente_entry.get()
        mapa = carregar_depara()

        try:
            nome_parser_empresa = config["parser"]
            nonlocal parser_empresa
            parser_empresa = importlib.import_module(f"parsers.{nome_parser_empresa}")
            

            for tipo in tipos:
                for caminho in caminhos_relatorios:
                    transacoes, conciliacao = parser_empresa.importar_arquivo(
                        path_arquivo=caminho,
                        tipo=tipo,
                        conta_corrente=conta_corrente,
                        base_path=CAMINHO_BASE_FORNECEDORES,
                        mapa_depara=mapa
                    )
                    if modo_automatico:
                        for t in transacoes:
                            (transacoes_saida if t["tipo"] == "D" else transacoes_entrada).append(t)
                        for c in conciliacao:
                            (conciliacoes_saida if c["tipo"] == "D" else conciliacoes_entrada).append(c)
                    else:
                        (transacoes_saida if tipo == "SAIDA" else transacoes_entrada).extend(transacoes)
                        (conciliacoes_saida if tipo == "SAIDA" else conciliacoes_entrada).extend(conciliacao)
            messagebox.showinfo("Sucesso", "Relatórios importados com sucesso.")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao importar relatórios:\n{e}")

    def importar_extrato():
        caminho_extrato = filedialog.askopenfilename(title="Selecionar Extrato Bancário (PDF)", filetypes=[("Arquivos PDF", "*.pdf")])
        if not caminho_extrato:
            return
        banco_selecionado = banco_opcao.get()
        try:
            parser_banco = importlib.import_module(f"parsers.bancos.{banco_selecionado}")
            extrato = parser_banco.importar_extrato(caminho_extrato)
            extrato["banco"] = banco_selecionado
            if extrato.empty:
                messagebox.showwarning("Aviso", f"O extrato do banco {banco_selecionado} está vazio.")
                return
            extratos_bancarios.append(extrato)
            messagebox.showinfo("Sucesso", f"Extrato de {banco_selecionado} adicionado.")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao importar extrato:\n{e}")

    def processar_tudo():
        if not extratos_bancarios:
            messagebox.showerror("Erro", "Nenhum extrato bancário foi importado.")
            return
        if not transacoes_saida and not transacoes_entrada:
            messagebox.showerror("Erro", "Importe pelo menos um relatório de SAÍDA ou ENTRADA.")
            return
        try:
            extrato_banco = pd.concat(extratos_bancarios, ignore_index=True)
            if nome_parser_empresa == "mecflu":
                extrato_banco = remover_transferencias_entre_bancos(extrato_banco)

            nome_limpo = normalize_text(nome_empresa).replace(" ", "_")
            conta_corrente = conta_corrente_entry.get().strip()
            nome_base = f"{nome_limpo}_{conta_corrente}"


            todas_transacoes_empresa = transacoes_saida + transacoes_entrada
            salvar_resultados(todas_transacoes_empresa, nome_base=f"Empresa_{nome_base}", salvar_txt=True)
            
            movimentos_entrada = [mov for mov in conciliacoes_entrada if mov["tipo"] == "C"]
            movimentos_saida = [mov for mov in conciliacoes_saida if mov["tipo"] == "D"]
            resumo_saida = parser_empresa.conciliar_saidas(movimentos_saida, extrato_banco)

            salvar_resultados(resumo_saida, nome_base=f"Saida_{nome_base}")

            resumo_entrada = parser_empresa.conciliar_entradas(movimentos_entrada, extrato_banco)

            salvar_resultados(resumo_entrada, nome_base=f"Entrada_{nome_base}")

        except Exception as e:
            messagebox.showerror("Erro", f"Erro no processamento:\n{e}")
    def resetar_dados():
        nonlocal transacoes_saida, transacoes_entrada, extratos_bancarios
        nonlocal conciliacoes_entrada, conciliacoes_saida
        transacoes_saida.clear()
        transacoes_entrada.clear()
        extratos_bancarios.clear()
        conciliacoes_entrada.clear()
        conciliacoes_saida.clear()
        messagebox.showinfo("Reset concluído", "Todos os dados foram apagados.")
    

    spinner_path = "static/img/spinner.gif"
    spinner_frames = []
    if os.path.exists(spinner_path):
        spinner_img = Image.open(recurso_path("static/img/spinner.gif"))
        try:
            while True:
                spinner_frames.append(CTkImage(spinner_img.copy(), size=(48, 48)))
                spinner_img.seek(len(spinner_frames))
        except EOFError:
            pass

    # Container central
    overlay_path = "static/img/overlay.png"  # imagem com transparência real

    spinner_container = ctk.CTkLabel(frame, text="", image=CTkImage(Image.open(recurso_path(overlay_path)), size=(200, 200)))
    spinner_container.place(relx=0.5, rely=2.50, anchor="center")

    # Adiciona spinner por cima
    if spinner_frames:
        spinner_label = ctk.CTkLabel(spinner_container, text="", image=spinner_frames[0])
        spinner_label.place(relx=0.5, rely=0.4, anchor="center")
    else:
        spinner_label = ctk.CTkLabel(spinner_container, text="Carregando...", font=("Arial", 12))
        spinner_label.place(relx=0.5, rely=0.5, anchor="center")

    spinner_text = ctk.CTkLabel(spinner_container, text="Processando, aguarde...", font=("Arial", 12))
    spinner_text.place(relx=0.5, rely=0.7, anchor="center")


    def animar_spinner(frame_idx=0):
        if not spinner_frames:
            return
        frame = spinner_frames[frame_idx % len(spinner_frames)]
        spinner_label.configure(image=frame)
        janela.after(80, animar_spinner, frame_idx + 1)

    def mostrar_loading():
        spinner_container.place(relx=0.5, rely=0.5, anchor="center")
        spinner_container.lift()
        animar_spinner()


    def ocultar_loading():
        spinner_container.place_forget()

    def executar_em_thread(func):
        def iniciar_processo():
            def run():
                try:
                    func()
                finally:
                    janela.after(0, ocultar_loading)
            threading.Thread(target=run, daemon=True).start()

        mostrar_loading()
        janela.after(200, iniciar_processo)  # Garante que o loading apareça antes de processar

    # === BOTÕES ===
    botoes_frame = ctk.CTkFrame(frame, fg_color="transparent")
    botoes_frame.pack(pady=10)
    botoes = [
        ("Importar Relatório da Empresa", lambda: executar_em_thread(importar_relatorios_empresa), "#ED8936", "#DD6B20"),
        ("Adicionar Extrato Bancário", lambda: executar_em_thread(importar_extrato), "#3182CE", "#225EA8"),
        ("Processar Tudo", lambda: executar_em_thread(processar_tudo), "#2F855A", "#276749")  ,
        ("Resetar Dados", lambda: executar_em_thread(resetar_dados), "#E53E3E", "#C53030")  # vermelho  
        ]
    for i, (texto, comando, cor, cor_hover) in enumerate(botoes):
        ctk.CTkButton(
            botoes_frame,
            text=texto,
            width=240,
            height=45,
            font=("Arial", 13, "bold"),
            fg_color=cor,
            hover_color=cor_hover,
            corner_radius=15,
            command=comando
        ).grid(row=0, column=i, padx=10)

def iniciar_aplicacao():
    global app
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

    app = ctk.CTk()
    app.title("Conciliador Bancário")
    app.geometry("1080x600")
    app.iconbitmap(recurso_path("static/img/Logo_HMPX_Padrao.ico"))

    # Frame centralizado
    frame = ctk.CTkFrame(app, corner_radius=20)
    frame.pack(expand=True, padx=40, pady=40, fill="both")

    # Logo
    if os.path.exists(recurso_path("static/img/Logo_HMPX_Padrao.png")):
        from PIL import Image
        logo_img = ctk.CTkImage(Image.open(recurso_path("static/img/Logo_HMPX_Padrao.png")), size=(300, 85))
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
        hover_color="#225EA8",
        text_color="white",
        command=confirmar_empresa
    ).pack(pady=10, anchor="center")  # margem superior maior

    # Botão: GERAR TXT DA PLANILHA (embaixo)
    ctk.CTkButton(
        master=frame,
        text="Gerar TXT da Planilha",
        height=48,
        width=220,
        font=("Arial", 13, "bold"),
        corner_radius=20,
        fg_color="#805AD5",            # roxo elegante
        hover_color="#6B46C1",
        text_color="white",
        command=gerar_txt_a_partir_do_excel
    ).pack(pady=10, anchor="center")  # margem inferior maior

    ctk.CTkButton(
        master=frame,
        text="Editar DE-PARA",
        height=48,
        width=220,
        font=("Arial", 13, "bold"),
        corner_radius=20,
        fg_color="#D69E2E",
        hover_color="#B7791F",
        text_color="white",
        command=lambda: abrir_tela_depara(app)
    ).pack(pady=10, anchor="center")  # Aproximação com o botão de cima

    # Rodapé
    ctk.CTkLabel(
        frame,
        text="HMPX Sistemas • Desenvolvido para uso interno",
        font=("Arial", 11),
        text_color="#4A5568"
    ).pack(side="bottom", pady=10)
    def ao_fechar():
        app.destroy()
        os._exit(0)  # Força a saída total do process

    app.protocol("WM_DELETE_WINDOW", ao_fechar)
    app.mainloop()
