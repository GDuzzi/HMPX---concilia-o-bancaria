from abc import ABC
import pandas as pd
from datetime import datetime
import os


class BaseRelatorio(ABC):
    
    def gerar_relatorio_contabil(self, lancamentos: list[dict], destino: str, nome_arquivo: str = "lancamentos_contabeis.xlsx"):
        """ Salva um Excel com os lançamentos contábeis da empresa"""
        if not lancamentos:
            return
        
        df = pd.DataFrame(lancamentos)

        caminho = os.path.join(destino, nome_arquivo)
        os.makedirs(destino, exist_ok=True)

        try:
            df.to_excel(caminho, index=False)
        except Exception as e:
            raise RuntimeError(f"Erro ao salvar o arquivo: {e}")
    
    def gerar_arquivo_txt(self, lancamentos: list[dict], destino: str, nome_arquivo: str = "lancamentos_contabeis.txt"):
        """ Salva um TXT com os lançamentos contábeis no layout padrão (Questor)"""

        if not lancamentos:
            return
        
        caminho = os.path.join(destino, nome_arquivo)
        os.makedirs(destino, exist_ok=True)

        try:
            with(open(caminho, "w", encoding="utf-8")) as f:
                for row in lancamentos:
                    try:
                        data_raw = row.get("data")
                        if isinstance(data_raw, str):
                            data_fmt = datetime.strptime(data_raw, "%Y-%m-%d").strftime("%d%m%Y")
                        else:
                            data_fmt = data_raw.strftime("%d%m%Y")
                    except:
                        data_fmt = str(row.get("data", ""))
                    

                    descricao = str(row.get("descricao", "Lançamento contábil")).replace('"', "'")
                    conta_debito = row.get("conta_debito", "99999")
                    conta_credito = row.get("conta_credito", "99999")
                    valor = abs(row.get("valor", 0.0))

                    linha = f'{data_fmt},{conta_debito},{conta_credito},{valor:2f},350,"{descricao}"\n'
                    f.write(linha)
        except Exception as e:
            raise RuntimeError(f"Erro ao salvar o arquivo: {e}")

    def gerar_relatorio_conciliacao(self, entradas: pd.DataFrame, saidas: pd.DataFrame, destino: str, banco: str):
            """ Gera um único arquivo Excel por banco, com duas abas:
            - 'Entradas' (DataFrame de conciliação de entradas)
            - 'Saídas' (DataFrame de conciliação de saídas)"""

            if entradas.empty and saidas.empty:
                return
            
            os.makedirs(destino, exist_ok=True)

            nome_arquivo = f"conciliacao_{banco.lower()}.xlsx"
            caminho = os.path.join(destino, nome_arquivo)

            try:
                with pd.ExcelWriter(caminho, engine='xlsxwriter') as writer:
                    if not entradas.empty:
                        entradas.to_excel(writer, index=False, sheet_name="Entradas")
                    if not saidas.empty:
                        saidas.to_excel(writer, index=False, sheet_name="Saídas")
            except Exception as e:
                raise RuntimeError(f"Erro ao salvar o arquivo: {e}")