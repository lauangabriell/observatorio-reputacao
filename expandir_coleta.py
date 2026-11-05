"""Coleta adicional limitada; não anota dados e não treina modelos."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
BUSCAS = ["Nubank atendimento", "Nubank cartao", "Nubank caixinhas", "Nubank aplicativo"]


def hash_texto(texto):
    return hashlib.sha256(" ".join(texto.casefold().split()).encode("utf-8")).hexdigest()


def ler_csv(p):
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    parser = argparse.ArgumentParser(description="Ampliar comentários do Nubank em até quatro buscas, sem anotar ou treinar")
    parser.add_argument("--meta", type=int, default=400, help="Parada entre buscas; não garante quantidade nem trunca a última coleta")
    args = parser.parse_args()
    if args.meta < 1:
        parser.error("A meta precisa ser positiva")
    historico = json.loads((ROOT / "dados/historico_coleta.json").read_text(encoding="utf-8"))
    vistos = set(historico["comment_ids"])
    videos = set(historico["video_ids"])
    hashes = set(historico["text_hashes"])
    processed = ROOT / "coleta/data/processed"
    for f in processed.glob("*/comments_clean.csv"):
        for r in ler_csv(f):
            vistos.add(r["comment_id"])
            videos.add(r["video_id"])
            hashes.add(hash_texto(r["text_clean"]))
    pasta = ROOT / "novas_coletas" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    pasta.mkdir(parents=True)
    novos, descartados, execucoes = [], [], []
    try:
        for busca in BUSCAS:
            if len(novos) >= args.meta:
                break
            exclusao = pasta / "videos_ja_conhecidos.json"
            exclusao.write_text(json.dumps(sorted(videos)), encoding="utf-8")
            antes = set(processed.glob("*/comments_clean.csv"))
            print(f"\nNova busca: {busca}. Novos candidatos até agora: {len(novos)}", flush=True)
            subprocess.run([sys.executable, str(ROOT / "coletar.py"), "--empresa", "Nubank", "--busca", busca,
                            "--aliases", "Nubank", "--videos", "5", "--excluir-videos", str(exclusao)], cwd=ROOT, check=True)
            arquivos = sorted(set(processed.glob("*/comments_clean.csv")) - antes)
            for f in arquivos:
                execucoes.append({"busca": busca, "pasta": str(f.parent.relative_to(ROOT))})
                selected = f.parent / "videos_selected.csv"
                if selected.exists():
                    videos.update(r["video_id"] for r in ler_csv(selected))
                rows = ler_csv(f)
                textos = {r["comment_id"]: r["text_raw"] for r in rows}
                for r in rows:
                    cid = r["comment_id"]
                    h = hash_texto(r["text_clean"])
                    motivo = None
                    if r.get("is_valid", "").lower() != "true":
                        motivo = "registro_invalido"
                    elif cid in vistos:
                        motivo = "id_ja_conhecido"
                    elif r.get("include_for_nlp", "").lower() != "true":
                        motivo = "fora_do_filtro_de_relevancia_lexical"
                    elif h in hashes:
                        motivo = "texto_repetido_normalizacao_conservadora"
                    if motivo:
                        descartados.append({"comment_id": cid, "motivo": motivo})
                    else:
                        novos.append({"comment_id": cid, "video_id": r["video_id"], "company": r["company"],
                                      "grupo_conversa": r["parent_comment_id"] or cid,
                                      "texto": r["text_raw"], "text_clean": r["text_clean"],
                                      "contexto_principal": textos.get(r["parent_comment_id"]),
                                      "published_at": r["published_at"], "busca_origem": busca,
                                      "relevance_hint": r["relevance_hint"], "rotulo": None,
                                      "divisao": None, "status": "aguardando_protocolo_e_anotacao"})
                    vistos.add(cid)
                    hashes.add(h)
    except subprocess.CalledProcessError:
        print("Uma busca falhou; os candidatos anteriores serão preservados.")
    finally:
        (pasta / "comentarios_novos.json").write_text(json.dumps(novos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (pasta / "relatorio_coleta.json").write_text(json.dumps({
            "empresa": "Nubank", "meta_entre_buscas": args.meta, "n_novos_candidatos": len(novos),
            "execucoes": execucoes, "descartes": descartados,
            "limites": ["amostra dirigida, não representativa", "quantidade depende da API", "relevância lexical não comprova alvo", "paráfrases não detectadas", "não anotados, sem divisão de treino ou teste", "nenhum treino realizado"]
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("\nArquivos preservados em:", pasta)
        print("Não coloque estes comentários no treino antes de definir e reservar a nova avaliação.")


if __name__ == "__main__":
    main()
