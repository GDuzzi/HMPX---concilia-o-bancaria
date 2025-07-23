from parsers.baseParser import ParserBase
from parsers.BaseRelatorio import BaseRelatorio
from parsers.BaseConciliacao import BaseConciliacao
import pandas as pd
from datetime import datetime
from rapidfuzz import process, fuzz
import unicodedata
import os
from services.config import recurso_path
from services.depara import carregar_depara

class Parser(ParserBase, BaseConciliacao, BaseRelatorio):

    CONTAS_PADRAO = {
        "cartao": "1737",
        "juros": "4701",
        "tarifa": "4698",
        "CPFL": "4477",
        "salario": "1634",
        "holerite": "1634",
        "estagio": "1634",
        "seguro": "1744",
        "desconhecido": "14010",
        "nd": "4582",
        "prolabore": "1635",
        "entrada_credito_padrao": "142"
    }

    def __init__(self):
        self.cache_fornecedor = {}
        self.fornecedor_index = []

    def parse_valor(self, valor):
        if pd.isna(valor):
            return 0.0
        valor = str(valor).strip().replace("R$", "").replace(" ", "")
        if "." in valor and "," in valor:
            valor = valor.replace(".", "").replace(",", ".")
        if "," in valor:  
            valor = valor.replace(",", ".")
        elif "." in valor:
            partes = valor.split(".")
            if len(partes[-1]) > 2:
                valor = valor.replace(".", "")
        try:
            return float(valor)
        except:
            return 0.0

    def importar_arquivo(self, arquivos: list[str]) -> dict:
        """Separa e importa os arquivos da empresa IMPÉRIO, agrupando por banco"""
        dados_por_banco = {}

        for path in arquivos:
            nome = os.path.basename(path).lower()

            if not nome.endswith(".csv") and not nome.endswith(".xlsx"):
                continue

            if "itau" in nome or "itaú" in nome:
                banco = "itau"
                conta_corrente = "25005"
            elif "santander" in nome:
                banco = "santander"
                conta_corrente = "25007"
            else:
                banco = "desconhecido"
                conta_corrente = "99999"


            if banco not in dados_por_banco:
                dados_por_banco[banco] = {
                    "entradas": [],
                    "saidas": [],
                    "extrato": pd.DataFrame(),
                    "lancamentos": []
                }

            base_path = recurso_path("config/Base_Fornecedores.xlsx")
            mapa = carregar_depara(recurso_path("config/DE-PARA.xlsx"))

            lancamentos, conciliacoes = self.importar_arquivo_relatorio(
                path,
                conta_corrente,
                base_path=base_path,
                mapa_depara=mapa,
                tipo=None  # Tipo não é mais baseado no nome do arquivo
            )

            dados_por_banco[banco]["lancamentos"].extend(lancamentos)
            for conc in conciliacoes:
                if conc["tipo"] == "C":
                    dados_por_banco[banco]["entradas"].append(conc)
                elif conc["tipo"] == "D":
                    dados_por_banco[banco]["saidas"].append(conc)

        return dados_por_banco

    def importar_arquivo_relatorio(self, path_arquivo, conta_corrente, base_path, mapa_depara, tipo):
        """Importa um relatório individual da empresa IMPÉRIO"""

        mapa_codigo = {}
        mapa_nome = {}

        if base_path:
            df_base = pd.read_excel(base_path) if base_path.endswith(".xlsx") else pd.read_csv(base_path)
            df_base.columns = [self.normalize_text(col) for col in df_base.columns]
            for _, row in df_base.iterrows():
                nome_original = str(row.get('fornecedor', '')).strip()
                nome_norm = self.normalize_text(nome_original)
                if nome_norm:
                    mapa_codigo[nome_norm] = str(row.get('codigo', ''))
                    mapa_nome[nome_norm] = nome_original

        try:
            df = pd.read_csv(path_arquivo, delimiter=";", encoding="latin1", header=0, dtype=str)
        except Exception as e:
            return [], []


        df.columns = [self.normalize_text(col) for col in df.columns]
        df.dropna(subset=[df.columns[0]], inplace=True)

        lancamentos = []
        conciliacao_movimentos = []

        if not self.cache_fornecedor:
            self.cache_fornecedor = {}
            self.fornecedor_index = list(mapa_codigo.keys())

        for _, row in df.iterrows():
            try:
                data_raw = row.get("datamovimento", "")
                valormovimento = self.parse_valor(row.get("valormovimento", 0))

                if isinstance(valormovimento, (int, float)) and valormovimento != 0:
                    data_conc = pd.to_datetime(data_raw, format="%Y-%m-%d", errors="coerce")
                    if not pd.isna(data_conc):
                        conciliacao_movimentos.append({
                            "data": data_conc.date(),
                            "valor": float(valormovimento),
                            "tipo": "C" if valormovimento > 0 else "D"
                        })
                    continue

                valorentrada = self.parse_valor(row.get("valorentrada", 0))
                valorsaida = self.parse_valor(row.get("valorsaida", 0))
                historico = row.get("fornecedor_observacao", "")
                if not data_raw or (valorentrada == 0 and valorsaida == 0 and valormovimento == 0):
                    continue

                data = pd.to_datetime(data_raw, errors="coerce")
                if pd.isna(data):
                    continue
                data = data.date()

                hist_norm = self.normalize_text(historico)
                cache_key = hist_norm

                if cache_key in self.cache_fornecedor:
                    fornecedor_nome, deb = self.cache_fornecedor[cache_key]
                else:
                    fornecedor_nome = ""
                    deb = self.CONTAS_PADRAO["desconhecido"]

                    if hist_norm in mapa_depara:
                        deb = mapa_depara[hist_norm]
                    elif hist_norm in mapa_codigo:
                        deb = mapa_codigo[hist_norm]
                        fornecedor_nome = mapa_nome[hist_norm]
                    else:
                        match = process.extractOne(
                            hist_norm,
                            self.fornecedor_index,
                            scorer=fuzz.ratio,
                            score_cutoff=88
                        )
                        if match:
                            melhor = match[0]
                            deb = mapa_codigo[melhor]
                            fornecedor_nome = mapa_nome[melhor]

                    self.cache_fornecedor[cache_key] = (fornecedor_nome, deb)

                if valorentrada > 0:
                    tipo_lanc = "C"
                    valor = valorentrada
                    conta_debito = conta_corrente
                    conta_credito = self.CONTAS_PADRAO["entrada_credito_padrao"]
                elif valorsaida > 0:
                    tipo_lanc = "D"
                    valor = valorsaida
                    conta_debito = deb
                    conta_credito = conta_corrente
                else:
                    continue

                lancamentos.append({
                    "data": data,
                    "descricao": historico.strip().upper(),
                    "valor": float(valor),
                    "conta_debito": conta_debito,
                    "conta_credito": conta_credito,
                    "tipo": tipo_lanc,
                    "fornecedor_nome": fornecedor_nome,
                })
            except Exception as e:
                continue

        return lancamentos, conciliacao_movimentos
