import customtkinter as ctk
from tkinter import filedialog, messagebox
import importlib
import pandas as pd
import threading
from PIL import Image
from customtkinter import CTkImage

from services.config import recurso_path, caminho_area_de_trabalho
from services.depara import carregar_depara
from services.processamento import (
    salvar_resultados,
    remover_transferencias_entre_bancos,
    gerar_txt_a_partir_do_excel,
    normalize_text
)

def abrir_tela_parametros(id_empresa, nome_empresa, app_ref):
    import json
    import os

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

    conta_corrente_entry = ctk.CTkEntry(frame, placeholder_text="Conta Corrente (ex: 10201)", width=340)
    conta_corrente_entry.pack(pady=(0, 30))

    nome_parser_empresa = config["parser"]

    menu_frame = ctk.CTkFrame(frame, fg_color="transparent")
    menu_frame.pack(pady=(0, 25))

    banco_opcao = ctk.CTkOptionMenu(menu_frame, values=["banco_brasil", "sicredi", "caixa", "itau", "santander", "mercado_pago"], width=340)
    banco_opcao.set("banco_brasil")
    banco_opcao.pack(pady=8)

    tipo_opcao = None
    if nome_parser_empresa != "imperio":
        tipo_opcao = ctk.CTkOptionMenu(menu_frame, values=["SAIDA", "ENTRADA"], width=340)
        tipo_opcao.set("SAIDA")
        tipo_opcao.pack(pady=8)

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
        mapa = carregar_depara(recurso_path("config/DE-PARA.xlsx"))

        try:
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
            extrato_banco = pd.concat(extratos_bancarios, ignore_index=True)
            if nome_parser_empresa == "mecflu":
                extrato_banco = remover_transferencias_entre_bancos(extrato_banco)

            nome_limpo = normalize_text(nome_empresa).replace(" ", "_")
            conta_corrente = conta_corrente_entry.get().strip()
            nome_base = f"{nome_limpo}_{conta_corrente}"

            todas_transacoes_empresa = transacoes_saida + transacoes_entrada
            salvar_resultados(todas_transacoes_empresa, nome_base=f"Empresa_{nome_base}", salvar_txt=True)

            resumo_saida = parser_empresa.conciliar_saidas(
                [mov for mov in conciliacoes_saida if mov["tipo"] == "D"],
                extrato_banco
            )
            salvar_resultados(resumo_saida, nome_base=f"Saida_{nome_base}")

            resumo_entrada = parser_empresa.conciliar_entradas(
                [mov for mov in conciliacoes_entrada if mov["tipo"] == "C"],
                extrato_banco
            )
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
