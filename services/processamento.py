from tkinter import filedialog, messagebox
from services.config import caminho_area_de_trabalho
from gui.loading import abrir_tela_loading, fechar_tela_loading
from parsers.registry import get_empresa  # Corrigido para usar o registry correto
import os
import threading

def executar_em_thread(funcao):
    def wrapper(*args, **kwargs):
        abrir_tela_loading()
        threading.Thread(target=lambda: funcao(*args, **kwargs) or fechar_tela_loading()).start()
    return wrapper

@executar_em_thread
def processar_tudo(nome_empresa: str):
    try:
        if not nome_empresa:
            messagebox.showerror("Erro", "Nenhuma empresa foi selecionada.")
            return

        # 1. Carrega o parser da empresa
        modulo_empresa = get_empresa(nome_empresa)
        parser = modulo_empresa.parser.Parser()

        # 2. Seleciona a pasta com os arquivos
        pasta_arquivos = filedialog.askdirectory(title="Selecione a pasta com os arquivos da empresa")
        if not pasta_arquivos:
            return

        arquivos = [
            os.path.join(pasta_arquivos, f)
            for f in os.listdir(pasta_arquivos)
            if f.lower().endswith((".csv", ".xlsx", ".pdf"))
        ]
        if not arquivos:
            messagebox.showerror("Erro", "A pasta selecionada não contém arquivos válidos.")
            return

        # 3. Importa e organiza os dados por banco
        dados_por_banco = parser.importar_arquivos(arquivos)
        if not dados_por_banco:
            messagebox.showerror("Erro", "Nenhum dado foi importado.")
            return

        # 4. Executa a conciliação por banco
        conciliacoes = parser.conciliar(dados_por_banco)

        # 5. Gera os relatórios (contábil + conciliação)
        destino = caminho_area_de_trabalho()
        parser.gerar_relatorio_contabil(conciliacoes, destino)
        parser.gerar_relatorios_conciliacao(conciliacoes, destino)

        messagebox.showinfo("Sucesso", "Relatórios gerados com sucesso na área de trabalho!")

    except Exception as e:
        messagebox.showerror("Erro", f"Ocorreu um erro no processamento:\n\n{e}")
    finally:
        fechar_tela_loading()
