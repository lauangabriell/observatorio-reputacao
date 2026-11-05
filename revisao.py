"""Alertas operacionais: não resolvem sentimento por alvo nem calibram escores."""
import math
import re
import unicodedata

LIMIAR_MARGEM = 0.10  # provisório, não escolhido por acurácia ou validado estatisticamente
MARCAS = {
    "Nubank": ["nubank", "nu bank"], "Itaú": ["itau"], "iFood": ["ifood"],
    "Bradesco": ["bradesco"], "Santander": ["santander"], "Sofisa": ["sofisa"],
    "PicPay": ["picpay", "pic pay"], "Mercado Pago": ["mercado pago"],
    "C6": ["c6", "c6 bank"], "Inter": ["banco inter"],
    "Will": ["will bank", "banco will"], "Master": ["banco master"],
}


def normalizar(texto):
    t = unicodedata.normalize("NFKD", texto.casefold())
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).split())


def contem(texto, alias):
    return bool(re.search(r"(?<!\w)" + re.escape(normalizar(alias)) + r"(?!\w)", texto))


def sinalizar(texto, empresa, previsao, limiar=LIMIAR_MARGEM):
    if not 0 <= limiar <= 1:
        raise ValueError("Limiar de margem deve estar entre zero e um")
    escores = [float(previsao[f"escore_{c}"]) for c in ["positivo", "neutro", "negativo"]]
    if any(not math.isfinite(x) or not 0 <= x <= 1 for x in escores) or abs(sum(escores) - 1) > 1e-6:
        raise ValueError("Escores inválidos")
    normal = normalizar(texto)
    marcas = {nome for nome, aliases in MARCAS.items() if any(contem(normal, a) for a in aliases)}
    alvo = next((nome for nome, aliases in MARCAS.items() if normalizar(empresa) in [normalizar(nome), *[normalizar(a) for a in aliases]]), empresa)
    aliases_alvo = [empresa, *MARCAS.get(alvo, [])]
    alvo_detectado = any(contem(normal, a) for a in aliases_alvo)
    if alvo_detectado:
        marcas.add(alvo)
    margem = sorted(escores, reverse=True)[0] - sorted(escores, reverse=True)[1]
    motivos = []
    if margem < limiar:
        motivos.append("escores_proximos")
    if len(marcas) > 1:
        motivos.append("multiplas_empresas_detectadas")
    if not alvo_detectado:
        motivos.append("empresa_alvo_nao_detectada_no_texto")
    if re.search(r"\bretiro\b.{0,35}\b(disse|falei)\b", normal):
        motivos.append("possivel_referencia_a_fala_anterior")
    if normalizar(alvo) != "nubank":
        motivos.append("empresa_fora_do_dominio_avaliado")
    return {
        "previsao_texto": previsao["sentimento"],
        "sentimento_empresa": "nao_determinado_automaticamente",
        "revisao_necessaria": bool(motivos),
        "status_revisao": "revisao_necessaria" if motivos else "sem_alerta_heuristico",
        "motivos_revisao": "; ".join(motivos),
        "marcas_detectadas": "; ".join(sorted(marcas)),
        "margem_escores": margem,
        "limiar_margem": limiar,
    }
