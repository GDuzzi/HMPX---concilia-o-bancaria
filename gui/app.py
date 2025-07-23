import customtkinter as ctk
from tkinter import messagebox
from tkinter import filedialog
import os
import json
from PIL import Image
from services.config import recurso_path, carregar_empresa
from parsers.BaseRelatorio import BaseRelatorio
from gui.tela_depara import abrir_tela_depara
from gui.tela_parametros import abrir_tela_parametros

relatorio = BaseRelatorio()

def iniciar_aplicacao():
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
    logo_path = recurso_path("static/img/Logo_HMPX_Padrao.png")
    if os.path.exists(logo_path):
        logo_img = ctk.CTkImage(Image.open(logo_path), size=(300, 85))
        ctk.CTkLabel(frame, image=logo_img, text="").pack(pady=(10, 10))

    # Título e instrução
    ctk.CTkLabel(frame, text="Conciliador Bancário", font=("Arial", 22, "bold")).pack(pady=(0, 6))
    ctk.CTkLabel(frame, text="Escolha a empresa para iniciar o processo de conciliação", font=("Arial", 15)).pack(pady=(0, 25))

    # Carregar empresas
    CAMINHO_CONFIG = recurso_path("config/empresas.json")
    empresas_dict = carregar_empresa(CAMINHO_CONFIG)
    nomes_empresas = list(empresas_dict.keys())

    # ComboBox
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
        abrir_tela_parametros(id_empresa, nome, app)
        app.withdraw()

    def gerar_txt_a_partir_da_planilha():
        try:
            caminho = filedialog.askopenfilename(
                title="Selecione a planilha de lançamentos",
                filetypes=[("Planilhas Excel", "*.xlsx")]
            )
            if not caminho:
                return

            import pandas as pd
            df = pd.read_excel(caminho)
            if df.empty:
                messagebox.showerror("Erro", "O arquivo está vazio.")
                return

            lancamentos = df.to_dict(orient="records")
            destino = os.path.dirname(caminho)

            relatorio.gerar_arquivo_txt(lancamentos, destino)
            messagebox.showinfo("Sucesso", f"Arquivo TXT gerado na mesma pasta da planilha!")

        except Exception as e:
            messagebox.showerror("Erro", f"Ocorreu um erro ao gerar o TXT:\n{e}")
    
    # Botões
    botoes = [
        ("Iniciar Conciliação", confirmar_empresa, "#3182CE", "#225EA8"),
        ("Gerar TXT da Planilha", lambda: gerar_txt_a_partir_da_planilha(recurso_path("config/DE-PARA.xlsx")), "#805AD5", "#6B46C1"),
        ("Editar DE-PARA", lambda: abrir_tela_depara(app), "#D69E2E", "#B7791F")
    ]

    for texto, comando, cor, cor_hover in botoes:
        ctk.CTkButton(
            master=frame,
            text=texto,
            height=48,
            width=220,
            font=("Arial", 13, "bold"),
            corner_radius=20,
            fg_color=cor,
            hover_color=cor_hover,
            text_color="white",
            command=comando
        ).pack(pady=10, anchor="center")

    # Rodapé
    ctk.CTkLabel(
        frame,
        text="HMPX Sistemas • Desenvolvido para uso interno",
        font=("Arial", 11),
        text_color="#4A5568"
    ).pack(side="bottom", pady=10)

    # Encerramento forçado
    def ao_fechar():
        app.destroy()
        os._exit(0)

    app.protocol("WM_DELETE_WINDOW", ao_fechar)
    app.mainloop()


if __name__ == "__main__":
    iniciar_aplicacao()
