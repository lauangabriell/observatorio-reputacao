"""Coleta explícita por empresa; só execute para iniciar novas chamadas à API."""
import argparse
import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="Buscar vídeos e coletar comentários para uma empresa")
    parser.add_argument("--empresa", required=True)
    parser.add_argument("--busca", help="Por padrão, usa o nome da empresa")
    parser.add_argument("--aliases", default="", help="Variações inequívocas da marca, separadas por vírgulas")
    parser.add_argument("--videos", type=int, default=5)
    parser.add_argument("--excluir-videos", help="JSON com lista de IDs de vídeos já coletados")
    args = parser.parse_args()
    if not args.empresa.strip() or (args.busca is not None and not args.busca.strip()):
        parser.error("Empresa e busca precisam de texto não vazio")
    if not 1 <= args.videos <= 10:
        parser.error("Use entre 1 e 10 vídeos")
    load_dotenv(ROOT / ".env")
    if not os.getenv("YOUTUBE_API_KEY", "").strip():
        parser.error("Configure YOUTUBE_API_KEY no .env desta pasta")
    # Sobrescrever os três campos evita reaproveitar uma busca ou aliases de outra marca.
    os.environ["COMPANY_NAME"] = args.empresa.strip()
    os.environ["SEARCH_QUERY"] = (args.busca or args.empresa).strip()
    os.environ["COMPANY_ALIASES"] = args.aliases
    os.environ["TOP_VIDEOS"] = str(args.videos)
    os.environ["INCLUDE_VIDEO_CONTEXT_ONLY"] = "false"
    os.environ["MAX_COMMENT_PAGES_PER_VIDEO"] = "2"
    os.environ["MAX_REPLY_PAGES_PER_THREAD"] = "2"
    import coleta.etl_youtube as etl
    if args.excluir_videos:
        try:
            excluidos = json.loads(Path(args.excluir_videos).read_text(encoding="utf-8"))
            if not isinstance(excluidos, list) or not all(isinstance(x, str) for x in excluidos):
                raise ValueError("Lista de IDs inválida")
        except (ValueError, OSError):
            parser.error("Arquivo de exclusão de vídeos inválido")
        original = etl.select_best_videos
        etl.select_best_videos = lambda videos: original([v for v in videos if v["video_id"] not in set(excluidos)])
    try:
        pasta = etl.run_etl()
    except Exception:
        # Não exibir URL de requisição nem traceback que possa conter chave de API.
        print("Coleta interrompida. Confira chave, ativação da API, cota e conexão. Nenhum diagnóstico com credenciais será exibido.")
        raise SystemExit(1) from None
    print("Dados disponíveis no painel ao recarregar:", pasta)
    print("Coletar outra empresa não adapta os pesos nem valida o classificador para ela.")


if __name__ == "__main__":
    main()
