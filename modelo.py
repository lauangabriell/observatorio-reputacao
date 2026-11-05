"""Treino e inferência locais do candidato balanceado do experimento 05."""
import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

CLASSES = ("negativo", "neutro", "positivo")


def treinar(conteudo_base):
    registros = json.loads(conteudo_base)["registros"]
    if len(registros) != 89 or len({r["comment_id"] for r in registros}) != 89:
        raise ValueError("A base aprovada precisa ter 89 IDs únicos.")
    if any(r["divisao"] != "treino" or r["historico_avaliacao01"] for r in registros):
        raise ValueError("A base inclui registros fora do treino aprovado.")
    if {r["rotulo_atual"] for r in registros} != set(CLASSES):
        raise ValueError("A base precisa conter as três classes previstas.")
    modelo = Pipeline([
        ("tfidf", TfidfVectorizer(lowercase=True, ngram_range=(1, 2))),
        ("classificador", LogisticRegression(max_iter=1000, random_state=42, class_weight="balanced")),
    ])
    modelo.fit([r["texto"] for r in registros], [r["rotulo_atual"] for r in registros])
    return modelo, {r["comment_id"] for r in registros}


def prever(modelo, textos):
    if not textos or any(not isinstance(t, str) or not t.strip() for t in textos):
        raise ValueError("Informe pelo menos um texto não vazio.")
    probabilidades = modelo.predict_proba(textos)
    classes = modelo.named_steps["classificador"].classes_
    return [
        {"sentimento": str(classes[int(p.argmax())]),
         "escore": float(p.max()),
         **{f"escore_{c}": float(v) for c, v in zip(classes, p)}}
        for p in probabilidades
    ]
