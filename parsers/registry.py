import importlib

def get_empresa(nome_empresa: str):
    """Retorna a classe Parser da empresa, localizada em parsers/<empresa>/parser.py"""
    nome_formatado = nome_empresa.strip().lower().replace(" ", "_")
    try:
        modulo = importlib.import_module(f"parsers.{nome_formatado}.parser")
        return getattr(modulo, "Parser")  # <- extrai a classe Parser do módulo
    except (ModuleNotFoundError, AttributeError) as e:
        raise ImportError(f"Erro ao carregar Parser da empresa '{nome_empresa}': {e}")
