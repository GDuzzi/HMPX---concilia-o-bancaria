import customtkinter as ctk
from PIL import Image, ImageTk
import os
import itertools
import threading
import time

tela_loading = None
executando = False

def recurso_path(rel_path):
    """Resolve caminho para arquivos estáticos, compatível com PyInstaller"""
    if hasattr(os, '_MEIPASS'):
        return os.path.join(os._MEIPASS, rel_path)
    return os.path.join(os.path.abspath("."), rel_path)

def animar_spinner(label, imagens):
    global executando
    i = 0
    while executando:
        imagem = imagens[i % len(imagens)]
        label.configure(image=imagem)
        i += 1
        time.sleep(0.1)

def abrir_tela_loading():
    global tela_loading, executando

    if tela_loading is not None:
        return

    tela_loading = ctk.CTkToplevel()
    tela_loading.title("Processando...")
    tela_loading.geometry("180x180")
    tela_loading.resizable(False, False)
    tela_loading.attributes("-topmost", True)
    tela_loading.overrideredirect(True)

    largura_tela = tela_loading.winfo_screenwidth()
    altura_tela = tela_loading.winfo_screenheight()
    largura_janela = 180
    altura_janela = 180
    pos_x = (largura_tela // 2) - (largura_janela // 2)
    pos_y = (altura_tela // 2) - (altura_janela // 2)
    tela_loading.geometry(f"{largura_janela}x{altura_janela}+{pos_x}+{pos_y}")

    caminho_spinner = recurso_path(os.path.join("img", "spinner"))
    arquivos = sorted([f for f in os.listdir(caminho_spinner) if f.endswith(".png")])
    imagens = [
        ImageTk.PhotoImage(Image.open(os.path.join(caminho_spinner, f)).resize((80, 80)))
        for f in arquivos
    ]

    label_spinner = ctk.CTkLabel(tela_loading, text="")
    label_spinner.pack(expand=True)

    executando = True
    threading.Thread(target=animar_spinner, args=(label_spinner, imagens), daemon=True).start()
    tela_loading.update()

def fechar_tela_loading():
    global tela_loading, executando
    executando = False
    if tela_loading is not None:
        tela_loading.destroy()
        tela_loading = None