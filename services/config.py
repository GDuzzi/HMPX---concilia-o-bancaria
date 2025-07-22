import os
import sys
import json
from pathlib import Path

def recurso_path(rel_path):
    """Resolve caminho para arquivos estáticos, compatível com PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, rel_path)
    return os.path.join(os.path.abspath("."), rel_path)

def caminho_area_de_trabalho():
    return str(Path.home() / "Desktop")

def carregar_empresa(caminho_config):
    with open(caminho_config, "r", encoding="utf-8") as f:
        dados = json.load(f)
    return {config["nome"]: id_ for id_, config in dados.items()}