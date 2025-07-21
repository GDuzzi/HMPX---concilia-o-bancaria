import customtkinter as ctk
from tkinter import messagebox
import pandas as pd
import os

# CAMINHO_DEPARA = os.path.join("config", "DE-PARA.xlsx")
CAMINHO_DEPARA = r"\\192.168.10.1\hmpx$\Contabil\Controles Internos\__BEATRIZ\projeto\DE-PARA (1).xlsx"

def abrir_tela_depara(janela_anterior):
    janela_anterior.withdraw()  # Oculta a janela anterior

    janela_depara = ctk.CTkToplevel()
    janela_depara.title("Gerenciar DE-PARA")
    janela_depara.geometry("560x470")
    janela_depara.resizable(False, False)

    def fechar_janela():
        janela_depara.destroy()
        janela_anterior.deiconify()

    janela_depara.protocol("WM_DELETE_WINDOW", fechar_janela)

    # Frame principal
    frame = ctk.CTkFrame(master=janela_depara, corner_radius=20)
    frame.pack(padx=30, pady=30, fill="both", expand=True)

    # Título
    titulo = ctk.CTkLabel(frame, text="Adicionar novo DE-PARA", font=("Arial", 18, "bold"))
    titulo.pack(pady=(15, 20))

    # Entradas
    nome_entry = ctk.CTkEntry(frame, placeholder_text="Nome do fornecedor", height=40, width=300, corner_radius=10)
    nome_entry.pack(pady=(0, 10))

    codigo_entry = ctk.CTkEntry(frame, placeholder_text="Código contábil", height=40, width=300, corner_radius=10)
    codigo_entry.pack(pady=(0, 15))

    # Textbox de visualização
    resultado_box = ctk.CTkTextbox(frame, height=160, corner_radius=10, font=("Arial", 12))
    resultado_box.pack(padx=10, pady=(0, 20), fill="both", expand=True)

    def carregar_registros():
        resultado_box.delete("1.0", "end")
        try:
            if os.path.exists(CAMINHO_DEPARA):
                df = pd.read_excel(CAMINHO_DEPARA)
                df.columns = [col.strip().lower() for col in df.columns]
                df = df.dropna(how="all")

                for _, row in df.iterrows():
                    nome = str(row.get("nome", "")).strip()
                    codigo = str(row.get("codigo", "")).strip()

                    if not nome or not codigo:
                        continue

                    if codigo.endswith(".0"):
                        codigo = codigo[:-2]

                    resultado_box.insert("end", f"{nome} -> {codigo}\n")
            else:
                resultado_box.insert("end", "Arquivo DE-PARA não encontrado.")
        except Exception as e:
            resultado_box.insert("end", f"Erro ao carregar: {e}")

    def adicionar_registro():
        nome = nome_entry.get().strip()
        codigo = codigo_entry.get().strip()

        if not nome or not codigo:
            messagebox.showerror("Erro", "Preencha os dois campos.")
            return

        try:
            if os.path.exists(CAMINHO_DEPARA):
                df = pd.read_excel(CAMINHO_DEPARA)
                df.columns = [col.strip().lower() for col in df.columns]
            else:
                df = pd.DataFrame(columns=["nome", "codigo"])

            novo = pd.DataFrame([[nome, codigo]], columns=["nome", "codigo"])
            df = pd.concat([df, novo], ignore_index=True)
            df = df.dropna(subset=["nome", "codigo"])
            df.to_excel(CAMINHO_DEPARA, index=False)

            nome_entry.delete(0, "end")
            codigo_entry.delete(0, "end")
            carregar_registros()

            messagebox.showinfo("Sucesso", "Registro adicionado com sucesso.")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao salvar:\n{e}")

    # Botão
    botao_adicionar = ctk.CTkButton(
        master=frame,
        text="Adicionar",
        height=44,
        width=200,
        font=("Arial", 14, "bold"),
        corner_radius=12,
        fg_color="#3182CE",
        hover_color="#225EA8",
        text_color="white",
        command=adicionar_registro
    )
    botao_adicionar.pack(pady=(0, 10))

    carregar_registros()
    janela_depara.mainloop()
