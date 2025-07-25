from parsers.baseParser import ParserBase
from parsers.BaseRelatorio import BaseRelatorio
from parsers.BaseConciliacao import BaseConciliacao
from services.config import recurso_path
from services.depara import carregar_depara
from rapidfuzz import process, fuzz
import pandas as pd
import os



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

    MAPA_BANCOS = {
        "caixa economica matriz": ("caixa", "20"),
        "brasil filial": ("brasil filial", "25008"),
        "brasil matriz": ("brasil matriz", "25007"),
        "itau filial": ("itau filial", "25009"),
        "itau matriz": ("itau matriz", "25001"),
        "santander filial": ("santander filial", "25066"),
        "santander matriz": ("santander matriz", "25065"),
        "mercado pago filial": ("mercadolivre filial", "25016"),
        "mercado pago matriz": ("mercadolivre matriz", "25015"),
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

    def identificar_banco(self, banco_raw: str) -> tuple[str, str] | None:
        banco_raw = banco_raw.lower()

        chaves = {
            "caixa economica": ("caixa", "20"),
            "banco do brasil matriz": ("brasil matriz", "25007"),
            "banco do brasil filial": ("brasil filial", "25008"),
            "banco itaú matriz": ("itau matriz", "25001"),
            "banco itaú filial": ("itau filial", "25009"),
            "banco santander matriz": ("santander matriz", "25065"),
            "banco santander filial": ("santander filial", "25066"),
            "mercado pago matriz": ("mercadolivre matriz", "25015"),
            "mercado pago filial": ("mercadolivre filial", "25016"),
        }

        for chave, resultado in chaves.items():
            if chave in banco_raw:
                return resultado

        return None

    def importar_arquivo(self, arquivos: list[str]) -> dict:
        """Separa e importa os arquivos da empresa LM, agrupando por banco"""

        dados_por_banco = {}

        base_path = recurso_path("config/Base_Fornecedores.xlsx")
        mapa = carregar_depara(recurso_path("config/DE-PARA.xlsx"))

        for path in arquivos:
            nome = os.path.basename(path).lower()

            if not nome.endswith(".csv") and not nome.endswith(".xlsx"):
                continue

            try:
                if path.endswith(".csv"):
                    df = pd.read_csv(path, delimiter=";", encoding="utf-8-sig")
                else:
                    df = pd.read_excel(path)
            except Exception as e:
                continue



            df.columns = [col.lower().strip() for col in df.columns]

            if "banco" not in df.columns:
                continue

            for banco_raw, df_banco in df.groupby("banco"):
                banco_raw = str(banco_raw).strip().lower()
                banco_map = self.identificar_banco(banco_raw)

                if not banco_map:
                    continue

                nome_banco, conta_corrente = banco_map

                if nome_banco not in dados_por_banco:
                    dados_por_banco[nome_banco] = {
                        "entradas": [],
                        "saidas": [],
                        "extrato": pd.DataFrame(),
                        "lancamentos": []
                    }
                try:

                    lancamentos, conciliacoes = self.importar_arquivo_relatorio(
                        df_banco,
                        conta_corrente=conta_corrente,
                        base_path=base_path,
                        mapa_depara=mapa
                    )

                    dados_por_banco[nome_banco]["lancamentos"].extend(lancamentos)
                    for conc in conciliacoes:
                        if conc["tipo"] == "C":
                            dados_por_banco[nome_banco]["entradas"].append(conc)
                        elif conc["tipo"] == "D":
                            dados_por_banco[nome_banco]["saidas"].append(conc)

                except Exception as e:
                    continue

        return dados_por_banco
                    


    def importar_arquivo_relatorio(self, df, conta_corrente, base_path, mapa_depara):
        """Importa um DataFrame de relatório da empresa LM"""
        mapa_codigo = {}
        mapa_nome = {}

        # Normaliza as colunas do DataFrame (garante tudo em minúsculas)
        df.columns = [col.lower().strip() for col in df.columns]
        if base_path:
            df_base = pd.read_excel(base_path) if base_path.endswith(".xlsx") else pd.read_csv(base_path)
            df_base.columns = [self.normalize_text(col) for col in df_base.columns]
            for _, row in df_base.iterrows():
                nome_original = str(row.get('fornecedor', '')).strip()
                nome_norm = self.normalize_text(nome_original)
                if nome_norm:
                    mapa_codigo[nome_norm] = str(row.get('codigo', ''))
                    mapa_nome[nome_norm] = nome_original

        lancamentos = []
        conciliacao_movimentos = []

        if not self.cache_fornecedor:
            self.cache_fornecedor = {}
            self.fornecedor_index = list(mapa_codigo.keys())

        for _, row in df.iterrows():
            try:
                # ⬇️ Corrigido para usar nomes minúsculos
                data_raw = row.get("data", "")
                valor = self.parse_valor(row.get("valor", 0))
                tipo_mov = row.get("tipo", "").upper()
                historico_raw = row.get("cliente/fornecedor", "")
                historico = str(historico_raw).strip() if pd.notna(historico_raw) else "SEM HISTÓRICO"
                if not historico:
                    historico = "SEM HISTÓRICO"

                if not isinstance(valor, (int, float)) or valor == 0 or not data_raw:
                    continue

                data_conc = pd.to_datetime(data_raw, dayfirst=True, errors="coerce")
                if pd.isna(data_conc):
                    continue
                data = data_conc.date()

                # Adiciona à lista de conciliação
                if tipo_mov in ("C", "D"):
                    conciliacao_movimentos.append({
                        "data": data,
                        "valor": float(valor),
                        "tipo": tipo_mov
                    })

                valorentrada = valor if tipo_mov == "C" else 0
                valorsaida = valor if tipo_mov == "D" else 0
                if valorentrada == 0 and valorsaida == 0:
                    continue

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

                # Monta lançamento contábil
                if valorentrada > 0:
                    tipo_lanc = "C"
                    conta_debito = conta_corrente
                    conta_credito = self.CONTAS_PADRAO["entrada_credito_padrao"]
                    valor_lanc = valorentrada
                elif valorsaida > 0:
                    tipo_lanc = "D"
                    conta_debito = deb
                    conta_credito = conta_corrente
                    valor_lanc = valorsaida
                else:
                    continue

                lancamentos.append({
                    "data": data,
                    "descricao": historico.strip().upper(),
                    "valor": valor_lanc,
                    "tipo": tipo_lanc,
                    "conta_debito": conta_debito,
                    "conta_credito": conta_credito,
                    "fornecedor": fornecedor_nome
                })

            except Exception as e:
                continue

        return lancamentos, conciliacao_movimentos

            
