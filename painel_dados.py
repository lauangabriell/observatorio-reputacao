"""Leitura de coletas e inferência, sem chamadas de rede."""
import csv
import json
from pathlib import Path

from modelo import prever
from revisao import sinalizar


def fontes(root):
    return [root / "dados" / "comentarios.json", *sorted((root / "coleta/data/processed").glob("*/comments_for_nlp.csv"), reverse=True)]


def ler_fonte(caminho):
    caminho = Path(caminho)
    if caminho.suffix == ".json":
        registros = json.loads(caminho.read_text(encoding="utf-8"))
    else:
        with caminho.open(encoding="utf-8-sig", newline="") as f:
            registros = [{"comment_id": r["comment_id"], "company": r["company"],
                          "texto": r["text_clean"], "published_at": r.get("published_at", "")}
                         for r in csv.DictReader(f)]
    if not registros:
        return []
    ids = set()
    for r in registros:
        if not str(r.get("company", "")).strip() or not str(r.get("texto", "")).strip() or not r.get("comment_id"):
            raise ValueError("Coleta contém comentário sem empresa, texto ou ID")
        if r["comment_id"] in ids:
            raise ValueError("Coleta contém IDs repetidos")
        ids.add(r["comment_id"])
    return registros


def classificar(modelo, ids_treino, registros):
    if not registros:
        return []
    return [{**r, **p, **sinalizar(r["texto"], r["company"], p), "usado_no_treino": r["comment_id"] in ids_treino}
            for r, p in zip(registros, prever(modelo, [r["texto"] for r in registros]))]
