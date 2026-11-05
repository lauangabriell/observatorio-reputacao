"""Assuntos por regras lexicais; não infere sentimento por aspecto ou empresa."""
import re
import unicodedata
from collections import Counter

REGRAS = {
    "Atendimento": r"\b(atendimento|atendente[s]?|suporte|sac|ouvidoria|chat)\b",
    "Aplicativo": r"\b(app|aplicativo[s]?|aplicacao|travando|trava|bug[s]?|login|atualizacao)\b",
    "Cartão e limite": r"\b(cartao|cartoes|limite[s]?|fatura[s]?|credito|ultravioleta|nubank\s*\+)\b",
    "Juros e empréstimos": r"\b(juro[s]?|emprestimo[s]?|financiamento[s]?|consignado|divida[s]?)\b",
    "Investimentos e rendimento": r"\b(investimento[s]?|investir|rendimento[s]?|rende|render|cdi|cdb|caixinha[s]?|poupanca|dividendo[s]?|fgc)\b",
    "Transferências, Pix e saques": r"\b(pix|transferencia[s]?|transferir|transferi|saque[s]?|sacar|deposito[s]?|depositar)\b",
    "Tarifas e cobranças": r"\b(tarifa[s]?|taxa[s]?|anuidade|mensalidade[s]?|cobranca[s]?|cobrado[s]?|cobrar)\b",
    "Segurança e confiança": r"\b(golpe[s]?|fraude[s]?|seguranca|confianca|confio|confiavel|roubo|roubaram|roubando|falencia|faliu|falir)\b",
    "Conta e cadastro": r"\b(conta[s]?|cadastro|cadastrar|bloqueio|bloquead[oa]|encerramento|encerrar)\b",
}
OUTROS = "Outros / não identificado"


def identificar(texto):
    texto = unicodedata.normalize("NFKD", str(texto or "").casefold())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return [tema for tema, regra in REGRAS.items() if re.search(regra, texto)] or [OUTROS]


def ranking(registros):
    """Entrada já filtrada pelo painel; cada ID conta uma vez por assunto."""
    por_id = {}
    for r in registros:
        por_id.setdefault(r["comment_id"], set()).update(identificar(r["texto"]))
    contagem = Counter(tema for temas in por_id.values() for tema in temas)
    total = len(por_id)
    return [{"Assunto": tema, "Comentários": n, "Percentual": 100 * n / total}
            for tema, n in sorted(contagem.items(), key=lambda x: (-x[1], x[0]))]
