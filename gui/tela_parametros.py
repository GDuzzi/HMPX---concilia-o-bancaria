import customtkinter as ctk
from tkinter import filedialog, messagebox
import importlib
import pandas as pd
import threading
from PIL import Image
from customtkinter import CTkImage
from parsers.baseParser import ParserBase
from services.utils import remover_transferencias_entre_bancos
from parsers.registry import get_empresa
from services.config import recurso_path, caminho_area_de_trabalho
from services.depara import carregar_depara
from parsers.BaseConciliacao import BaseConciliacao
from parsers.BaseRelatorio import BaseRelatorio
from datetime import datetime




def abrir_tela_parametros(id_empresa, nome_empresa, app_ref):
    import json
    import os
    parser_class = get_empresa(id_empresa.upper())
    parser = parser_class()
    CAMINHO_CONFIG = recurso_path("config/empresas.json")
    CAMINHO_BASE_FORNECEDORES = recurso_path("config/Base_Fornecedores.xlsx")

    try:
        with open(CAMINHO_CONFIG, "r", encoding="utf-8") as f:
            config = json.load(f)[id_empresa]
    except:
        messagebox.showerror("Erro", f"Não foi possível carregar config da empresa '{id_empresa}'")
        return

    janela = ctk.CTkToplevel()
    janela.title(f"Importar Extrato - {nome_empresa}")
    janela.geometry("1280x520")

    def ao_fechar_janela():
        janela.destroy()
        app_ref.deiconify()

    janela.protocol("WM_DELETE_WINDOW", ao_fechar_janela)

    frame = ctk.CTkFrame(janela, corner_radius=20)
    frame.pack(expand=True, padx=40, pady=40, fill="both")

    ctk.CTkLabel(frame, text="Importação e Conciliação de Extratos", font=("Arial", 20, "bold")).pack(pady=(20, 10))
    ctk.CTkLabel(frame, text=f"Empresa selecionada: {nome_empresa}", font=("Arial", 12)).pack(pady=(0, 25))



    menu_frame = ctk.CTkFrame(frame, fg_color="transparent")
    menu_frame.pack(pady=(0, 25))

    banco_opcao = ctk.CTkOptionMenu(menu_frame, values=["banco_brasil", "sicredi", "caixa", "itau", "santander"], width=340)
    banco_opcao.set("banco_brasil")
    banco_opcao.pack(pady=8)

    tipo_opcao = None
    if id_empresa.lower() != "imperio":
        tipo_opcao = ctk.CTkOptionMenu(menu_frame, values=["SAIDA", "ENTRADA"], width=340)
        tipo_opcao.set("SAIDA")
        tipo_opcao.pack(pady=8)

    parser_empresa = None
    transacoes_saida, transacoes_entrada, extratos_bancarios = [], [], []
    conciliacoes_entrada, conciliacoes_saida = [], []
    lancamentos_empresa_por_banco = {}

    def importar_relatorios_empresa():
        caminhos_relatorios = filedialog.askopenfilenames(
            title="Selecionar Relatórios da Empresa",
            filetypes=[("Arquivos CSV", "*.csv"), ("Arquivos Excel", "*.xlsx"), ("Arquivos PDF", "*.pdf")]
        )
        if not caminhos_relatorios:
            return

        try:
            nonlocal parser_empresa, lancamentos_empresa_por_banco

            dados_por_banco = parser.importar_arquivo(caminhos_relatorios)

            for banco, dados in dados_por_banco.items():
                conciliacoes = dados["entradas"] + dados["saidas"]
                transacoes = dados["lancamentos"]

                for t in transacoes:
                    (transacoes_saida if t["tipo"] == "D" else transacoes_entrada).append(t)
                for c in conciliacoes:
                    (conciliacoes_saida if c["tipo"] == "D" else conciliacoes_entrada).append(c)

            # <-- Adicione esta parte -->
            lancamentos_empresa_por_banco = {
                banco: dados["lancamentos"]
                for banco, dados in dados_por_banco.items()
            }

            messagebox.showinfo("Sucesso", "Relatórios importados com sucesso.")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao importar relatórios:\n{e}")

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
            print("[DEBUG] Iniciando processamento completo")

            extrato_banco = pd.concat(extratos_bancarios, ignore_index=True)
            print(f"[DEBUG] Extrato bancário concatenado: {extrato_banco.shape}")

            if id_empresa.lower() == "mecflu":
                extrato_banco = remover_transferencias_entre_bancos(extrato_banco)
                print("[DEBUG] Remoção de transferências entre bancos aplicada (MECFLU)")


            nome_limpo = ParserBase.normalize_text(nome_empresa).replace(" ", "_")
            data_hoje = datetime.now().strftime("%Y-%m-%d")
            pasta_saida = os.path.join(caminho_area_de_trabalho(), f"{nome_limpo}_{data_hoje}")
            os.makedirs(pasta_saida, exist_ok=True)
            print(f"[DEBUG] Pasta de saída criada: {pasta_saida}")

            df_saida = pd.DataFrame(conciliacoes_saida)
            df_entrada = pd.DataFrame(conciliacoes_entrada)
            print(f"[DEBUG] Linhas em df_saida: {df_saida.shape[0]}")
            print(f"[DEBUG] Linhas em df_entrada: {df_entrada.shape[0]}")

            conciliacoes_por_banco_saida = []
            conciliacoes_por_banco_entrada = []

            # Assume que 'dados_por_banco' foi preenchido corretamente pelo parser durante a importação
            bancos_no_extrato = extrato_banco["banco"].dropna().unique()
            print(f"[DEBUG] Bancos encontrados no extrato: {bancos_no_extrato}")

            todos_lancamentos = []

            for banco in bancos_no_extrato:
                print(f"[DEBUG] Processando banco: {banco}")
                df_extrato_banco = extrato_banco[extrato_banco["banco"].str.lower() == banco.lower()]
                df_saida_banco = df_saida[df_saida["banco"].str.lower() == banco.lower()] if "banco" in df_saida.columns else df_saida
                df_entrada_banco = df_entrada[df_entrada["banco"].str.lower() == banco.lower()] if "banco" in df_entrada.columns else df_entrada

                conc_saida = BaseConciliacao().conciliar_saidas(df_saida_banco, df_extrato_banco, banco)
                conc_entrada = BaseConciliacao().conciliar_entradas(df_entrada_banco, df_extrato_banco, banco)

                if not conc_saida.empty:
                    conc_saida["banco"] = banco
                    conciliacoes_por_banco_saida.append(conc_saida)
                    print(f"[DEBUG] Conciliações de saída adicionadas para {banco}: {conc_saida.shape[0]} linhas")

                if not conc_entrada.empty:
                    conc_entrada["banco"] = banco
                    conciliacoes_por_banco_entrada.append(conc_entrada)
                    print(f"[DEBUG] Conciliações de entrada adicionadas para {banco}: {conc_entrada.shape[0]} linhas")

                # Salva o relatório de conciliação
                BaseRelatorio().gerar_relatorio_conciliacao(conc_entrada, conc_saida, pasta_saida, banco)
                print(f"[DEBUG] Relatório de conciliação salvo para banco: {banco}")

                # Pega os lançamentos contábeis da empresa, por banco
                if banco in lancamentos_empresa_por_banco:
                    todos_lancamentos.extend(lancamentos_empresa_por_banco[banco])

            # Gera os relatórios contábeis (Excel e TXT)
            if todos_lancamentos:
                print("[DEBUG] Total de lançamentos:", len(todos_lancamentos))
                print("[DEBUG] Exemplo de lançamento:", todos_lancamentos[0])
                campos_esperados = {'data', 'descricao', 'valor', 'conta_debito', 'conta_credito', 'tipo', 'fornecedor_nome'}
                for i, lanc in enumerate(todos_lancamentos):
                    if set(lanc.keys()) != campos_esperados:
                        print(f"[ERRO] Lançamento {i} com campos inesperados:", lanc.keys())

                relatorio = BaseRelatorio()
                relatorio.gerar_relatorio_contabil(lancamentos=todos_lancamentos, destino=pasta_saida)
                relatorio.gerar_arquivo_txt(lancamentos=todos_lancamentos, destino=pasta_saida)
                print(f"[DEBUG] Relatórios contábeis gerados: {len(todos_lancamentos)} lançamentos")

            messagebox.showinfo("Processamento concluído", f"Relatórios salvos em:\n{pasta_saida}")

        except Exception as e:
            print(f"[ERRO] Exceção durante processamento: {str(e)}")
            messagebox.showerror("Erro no processamento", str(e))


    def resetar_dados():
        nonlocal transacoes_saida, transacoes_entrada, extratos_bancarios
        nonlocal conciliacoes_entrada, conciliacoes_saida
        transacoes_saida.clear()
        transacoes_entrada.clear()
        extratos_bancarios.clear()
        conciliacoes_entrada.clear()
        conciliacoes_saida.clear()
        messagebox.showinfo("Reset concluído", "Todos os dados foram apagados.")

    # === LOADING/SPINNER ===
    spinner_frames = []
    spinner_path = recurso_path("static/img/spinner.gif")
    if os.path.exists(spinner_path):
        spinner_img = Image.open(spinner_path)
        try:
            while True:
                spinner_frames.append(CTkImage(spinner_img.copy(), size=(48, 48)))
                spinner_img.seek(len(spinner_frames))
        except EOFError:
            pass

    spinner_container = ctk.CTkLabel(frame, text="", image=CTkImage(Image.open(recurso_path("static/img/overlay.png")), size=(200, 200)))
    spinner_container.place(relx=0.5, rely=2.5, anchor="center")

    spinner_label = ctk.CTkLabel(spinner_container, text="", image=spinner_frames[0] if spinner_frames else None)
    spinner_label.place(relx=0.5, rely=0.4, anchor="center")

    spinner_text = ctk.CTkLabel(spinner_container, text="Processando, aguarde...", font=("Arial", 12))
    spinner_text.place(relx=0.5, rely=0.7, anchor="center")

    def animar_spinner(frame_idx=0):
        if spinner_frames:
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
        def iniciar():
            def run():
                try:
                    func()
                finally:
                    janela.after(0, ocultar_loading)
            threading.Thread(target=run, daemon=True).start()
        mostrar_loading()
        janela.after(200, iniciar)

    # === BOTÕES ===
    botoes_frame = ctk.CTkFrame(frame, fg_color="transparent")
    botoes_frame.pack(pady=10)
    botoes = [
        ("Importar Relatório da Empresa", lambda: executar_em_thread(importar_relatorios_empresa), "#ED8936", "#DD6B20"),
        ("Adicionar Extrato Bancário", lambda: executar_em_thread(importar_extrato), "#3182CE", "#225EA8"),
        ("Processar Tudo", lambda: executar_em_thread(processar_tudo), "#2F855A", "#276749"),
        ("Resetar Dados", lambda: executar_em_thread(resetar_dados), "#E53E3E", "#C53030"),
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
