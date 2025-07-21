import pdfplumber
import pandas as pd
import re
import unicodedata
from datetime import datetime

def normalize(text):
    if not isinstance(text, str):
        return text
    return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8").strip().lower()

def importar_extrato(pdf_path: str, conta_corrente: str, conta_titulos: str) -> pd.DataFrame:
    linhas = []

    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text()
            if texto:
                linhas.extend(texto.split("\n"))

    skip_keywords = [
        "detalhe dos movimentos", "data de geração", "você tem alguma dúvida?",
        "mercado pago instituição", "agência: conta:", "periodo:", "saldo inicial", "saldo final",
        "encontre nossos canais", "descrição", "id da operação", "valor", "saldo", "o nosso sac",
        "ligue para", "ouvidoria", "cnpj", "av. das nações unidas", "portal de ajuda", "www.mercadopago"
    ]
    skip_regex = re.compile(r"\d+/3|^data\s|^descrição\s|^id da operação|^valo", re.IGNORECASE)

    linhas_filtradas = [
        l.strip() for l in linhas
        if l.strip()
        and not any(kw in l.lower() for kw in skip_keywords)
        and not skip_regex.search(l.lower())
    ]

    # Agrupar transações por data
    transacoes_raw = []
    buffer = []
    for linha in linhas_filtradas:
        if re.match(r"\d{2}-\d{2}-\d{4}", linha):
            if buffer:
                transacoes_raw.append(" ".join(buffer))
            buffer = []
        buffer.append(linha)
    if buffer:
        transacoes_raw.append(" ".join(buffer))

    registros = []
    for entrada in transacoes_raw:
        match = re.match(r"(\d{2}-\d{2}-\d{4})\s+(.+?)\s+(\d{9,})\s+R\$ (.+?)\s+R\$ (.+)", entrada)
        if not match:
            match = re.match(r"(\d{2}-\d{2}-\d{4})\s+(.+?)(\d{9,})\s+R\$ (.+?)\s+R\$ (.+)", entrada)
        if not match:
            continue

        data_str, descricao, operacao_id, valor_str, _ = match.groups()
        try:
            data = datetime.strptime(data_str, "%d-%m-%Y").date()
            valor = float(valor_str.replace(".", "").replace(",", "."))
            historico = normalize(f"{descricao} - {operacao_id}")
            tipo = "C" if valor > 0 else "D"

            conta_debito = conta_titulos if tipo == "D" else conta_corrente
            conta_credito = conta_corrente if tipo == "D" else conta_titulos

            # Regras especiais
            desc_norm = normalize(descricao)
            mapa_especifico = {
                "transferencia pix enviada": "14008",  
                "debito por divida imposto interestadual": "5235", 
                "pagamento cartao de credito": "1737", 
                "iof": "4670",
                "debito por divida diferenca da aliquota (difal)": "5235"
            }

            for termo, conta_esp in mapa_especifico.items():
                if termo in desc_norm:
                    if tipo == "D":
                        conta_debito, conta_credito = conta_esp, conta_corrente
                    else:
                        conta_debito, conta_credito = conta_corrente, conta_esp
                    break

            registros.append({
                "data": data,
                "historico": historico,
                "valor": round(valor, 2),
                "tipo": tipo,
                "conta_debito": conta_debito,
                "conta_credito": conta_credito
            })
        except Exception as e:
            print(f"[Mercado Pago] Erro ao processar: {entrada} -> {e}")

    return pd.DataFrame(registros)
