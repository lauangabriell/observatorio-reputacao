from __future__ import annotations

import csv
import json
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv()

API_KEY = os.getenv("YOUTUBE_API_KEY", "").strip()
COMPANY_NAME = os.getenv("COMPANY_NAME", "Nubank").strip()
SEARCH_QUERY = os.getenv("SEARCH_QUERY", COMPANY_NAME).strip()

aliases_env = os.getenv("COMPANY_ALIASES", "")
COMPANY_ALIASES = [
    COMPANY_NAME,
    *[x.strip() for x in aliases_env.split(",") if x.strip()],
]
COMPANY_ALIASES = list(dict.fromkeys(COMPANY_ALIASES))

SEARCH_CANDIDATES = min(max(int(os.getenv("SEARCH_CANDIDATES", "30")), 1), 50)
TOP_VIDEOS = max(int(os.getenv("TOP_VIDEOS", "5")), 1)
MAX_COMMENT_PAGES_PER_VIDEO = max(int(os.getenv("MAX_COMMENT_PAGES_PER_VIDEO", "2")), 0)
MAX_REPLY_PAGES_PER_THREAD = max(int(os.getenv("MAX_REPLY_PAGES_PER_THREAD", "2")), 0)
REGION_CODE = os.getenv("REGION_CODE", "BR").strip()
RELEVANCE_LANGUAGE = os.getenv("RELEVANCE_LANGUAGE", "pt").strip()
INCLUDE_VIDEO_CONTEXT_ONLY = os.getenv("INCLUDE_VIDEO_CONTEXT_ONLY", "false").lower() == "true"

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
COMMENT_THREADS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"
COMMENTS_URL = "https://www.googleapis.com/youtube/v3/comments"

ROOT_DIR = Path(__file__).resolve().parent


class YouTubeAPIError(Exception):
    def __init__(self, status_code: int, reason: str, message: str):
        self.status_code = status_code
        self.reason = reason
        self.message = message
        super().__init__(f"YouTube API {status_code} - {reason}: {message}")


def safe_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def clean_text(text: str) -> str:
    """Limpeza conservadora: preserva emojis, negações, pontuação e acentos."""
    if not text:
        return ""
    return " ".join(str(text).split()).strip()


def normalize_for_matching(text: str) -> str:
    """Normalização APENAS para detectar aliases/marca."""
    if not text:
        return ""
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


NORMALIZED_ALIASES = [normalize_for_matching(x) for x in COMPANY_ALIASES]


def contains_company_keyword(text: str) -> bool:
    normalized = normalize_for_matching(text)
    for alias in NORMALIZED_ALIASES:
        if not alias:
            continue
        pattern = rf"(?<!\w){re.escape(alias)}(?!\w)"
        if re.search(pattern, normalized):
            return True
    return False


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def append_jsonl(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def chunks(values: list[str], size: int = 50):
    for i in range(0, len(values), size):
        yield values[i:i + size]


def youtube_get(url: str, params: dict, attempts: int = 3) -> dict:
    if not API_KEY:
        raise RuntimeError("YOUTUBE_API_KEY não foi encontrada no .env.")

    request_params = dict(params)
    request_params["key"] = API_KEY

    for attempt in range(attempts):
        try:
            response = requests.get(url, params=request_params, timeout=30)
        except requests.RequestException as error:
            if attempt < attempts - 1:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Falha de conexão: {error}") from error

        if response.status_code == 200:
            return response.json()

        try:
            payload = response.json()
        except ValueError:
            payload = {}

        api_error = payload.get("error", {})
        errors = api_error.get("errors", [])
        reason = errors[0].get("reason", "") if errors else ""
        message = api_error.get("message", response.text[:300])

        if response.status_code in {429, 500, 502, 503, 504} and attempt < attempts - 1:
            time.sleep(2 ** attempt)
            continue

        raise YouTubeAPIError(response.status_code, reason, message)

    raise RuntimeError("Falha inesperada na API.")


def search_video_candidates(raw_dir: Path) -> list[dict]:
    params = {
        "part": "snippet",
        "q": SEARCH_QUERY,
        "type": "video",
        "maxResults": SEARCH_CANDIDATES,
        "order": "relevance",
    }
    if REGION_CODE:
        params["regionCode"] = REGION_CODE
    if RELEVANCE_LANGUAGE:
        params["relevanceLanguage"] = RELEVANCE_LANGUAGE

    data = youtube_get(SEARCH_URL, params)
    save_json(raw_dir / "01_search.json", data)

    candidates = []
    for position, item in enumerate(data.get("items", []), start=1):
        item_id = item.get("id", {})
        if item_id.get("kind") != "youtube#video":
            continue
        video_id = item_id.get("videoId")
        if video_id:
            candidates.append({"video_id": video_id, "search_rank": position})

    return candidates


def get_video_details(candidates: list[dict], raw_dir: Path) -> list[dict]:
    if not candidates:
        return []

    rank_by_id = {x["video_id"]: x["search_rank"] for x in candidates}
    video_ids = list(rank_by_id)
    videos = []
    raw_responses = []

    for group in chunks(video_ids, 50):
        data = youtube_get(
            VIDEOS_URL,
            {
                "part": "snippet,statistics",
                "id": ",".join(group),
            },
        )
        raw_responses.append(data)

        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            video_id = item.get("id", "")
            title = clean_text(snippet.get("title", ""))
            description = clean_text(snippet.get("description", ""))

            videos.append(
                {
                    "company": COMPANY_NAME,
                    "search_query": SEARCH_QUERY,
                    "video_id": video_id,
                    "search_rank": rank_by_id.get(video_id, 999999),
                    "title": title,
                    "channel_title": clean_text(snippet.get("channelTitle", "")),
                    "published_at": snippet.get("publishedAt", ""),
                    "view_count": safe_int(stats.get("viewCount")),
                    "comment_count": safe_int(stats.get("commentCount")),
                    "like_count": safe_int(stats.get("likeCount")),
                    "video_mentions_company_keyword": contains_company_keyword(
                        f"{title} {description}"
                    ),
                }
            )

    save_json(raw_dir / "02_videos.json", raw_responses)
    return videos


def publication_timestamp(value: str) -> float:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return 0.0


def select_best_videos(videos: list[dict]) -> list[dict]:
    """Critérios: comentários, recência, visualizações, posição da busca."""
    return sorted(
        videos,
        key=lambda v: (
            -v["comment_count"],
            -publication_timestamp(v["published_at"]),
            -v["view_count"],
            v["search_rank"],
        ),
    )[:TOP_VIDEOS]


def classify_relevance(
    text: str,
    comment_type: str,
    parent_has_keyword: bool,
    video_has_keyword: bool,
) -> tuple[str, bool]:
    direct = contains_company_keyword(text)

    if direct:
        return "direct_keyword", True
    if comment_type == "reply" and parent_has_keyword:
        return "parent_keyword_context", True
    if video_has_keyword:
        return "video_context_only", INCLUDE_VIDEO_CONTEXT_ONLY
    return "none", False


def build_comment_record(
    comment: dict,
    video: dict,
    comment_type: str,
    thread_id: str,
    parent_comment_id: str = "",
    parent_has_keyword: bool = False,
) -> dict:
    snippet = comment.get("snippet", {})
    text_raw = snippet.get("textDisplay", "") or ""
    text_clean = clean_text(text_raw)

    relevance_hint, include_for_nlp = classify_relevance(
        text_clean,
        comment_type,
        parent_has_keyword,
        bool(video.get("video_mentions_company_keyword")),
    )

    return {
        "company": COMPANY_NAME,
        "video_id": video["video_id"],
        "video_title": video["title"],
        "comment_id": comment.get("id", ""),
        "thread_id": thread_id,
        "comment_type": comment_type,
        "parent_comment_id": parent_comment_id,
        "text_raw": text_raw,
        "text_clean": text_clean,
        "like_count": safe_int(snippet.get("likeCount")),
        "published_at": snippet.get("publishedAt", ""),
        "updated_at": snippet.get("updatedAt", ""),
        "relevance_hint": relevance_hint,
        "include_for_nlp": include_for_nlp,
        "is_valid": bool(comment.get("id")) and bool(text_clean),
        "drop_reason": "" if (comment.get("id") and text_clean) else "missing_id_or_text",
    }


def collect_replies(
    video: dict,
    thread_id: str,
    top_comment: dict,
    total_reply_count: int,
    included_replies: list[dict],
    raw_comments_path: Path,
) -> list[dict]:
    if total_reply_count <= 0:
        return []

    top_id = top_comment.get("id", "")
    top_text = clean_text(top_comment.get("snippet", {}).get("textDisplay", ""))
    parent_has_keyword = contains_company_keyword(top_text)

    if total_reply_count <= len(included_replies):
        return [
            build_comment_record(
                reply,
                video,
                "reply",
                thread_id,
                parent_comment_id=top_id,
                parent_has_keyword=parent_has_keyword,
            )
            for reply in included_replies
        ]

    replies = []
    page_token = None
    page_number = 0

    while True:
        params = {
            "part": "snippet",
            "parentId": top_id,
            "maxResults": 100,
            "textFormat": "plainText",
        }
        if page_token:
            params["pageToken"] = page_token

        try:
            data = youtube_get(COMMENTS_URL, params)
        except YouTubeAPIError as error:
            print(f"[aviso] respostas de {top_id}: {error}")
            if not replies:
                replies = [
                    build_comment_record(
                        reply,
                        video,
                        "reply",
                        thread_id,
                        parent_comment_id=top_id,
                        parent_has_keyword=parent_has_keyword,
                    )
                    for reply in included_replies
                ]
            break

        page_number += 1
        append_jsonl(
            raw_comments_path,
            {
                "source": "comments.list",
                "video_id": video["video_id"],
                "parent_comment_id": top_id,
                "page": page_number,
                "payload": data,
            },
        )

        for reply in data.get("items", []):
            replies.append(
                build_comment_record(
                    reply,
                    video,
                    "reply",
                    thread_id,
                    parent_comment_id=top_id,
                    parent_has_keyword=parent_has_keyword,
                )
            )

        page_token = data.get("nextPageToken")
        if not page_token:
            break
        if MAX_REPLY_PAGES_PER_THREAD and page_number >= MAX_REPLY_PAGES_PER_THREAD:
            break

    return replies


def collect_video_comments(video: dict, raw_comments_path: Path) -> list[dict]:
    comments = []
    page_token = None
    page_number = 0

    while True:
        params = {
            "part": "snippet,replies",
            "videoId": video["video_id"],
            "maxResults": 100,
            "textFormat": "plainText",
            "order": "time",
        }
        if page_token:
            params["pageToken"] = page_token

        try:
            data = youtube_get(COMMENT_THREADS_URL, params)
        except YouTubeAPIError as error:
            if error.reason == "commentsDisabled":
                print(f"[aviso] comentários desativados: {video['title']}")
                return []
            raise

        page_number += 1
        append_jsonl(
            raw_comments_path,
            {
                "source": "commentThreads.list",
                "video_id": video["video_id"],
                "page": page_number,
                "payload": data,
            },
        )

        for thread in data.get("items", []):
            thread_id = thread.get("id", "")
            thread_snippet = thread.get("snippet", {})
            top_comment = thread_snippet.get("topLevelComment", {})

            top_record = build_comment_record(
                top_comment,
                video,
                "top_level",
                thread_id,
            )
            comments.append(top_record)

            total_reply_count = safe_int(thread_snippet.get("totalReplyCount"))
            included_replies = thread.get("replies", {}).get("comments", [])

            comments.extend(
                collect_replies(
                    video,
                    thread_id,
                    top_comment,
                    total_reply_count,
                    included_replies,
                    raw_comments_path,
                )
            )

        page_token = data.get("nextPageToken")
        if not page_token:
            break
        if MAX_COMMENT_PAGES_PER_VIDEO and page_number >= MAX_COMMENT_PAGES_PER_VIDEO:
            break

    return comments


def deduplicate_and_validate(comments: list[dict]) -> tuple[list[dict], list[dict]]:
    clean = []
    rejected = []
    seen_ids = set()

    for row in comments:
        comment_id = row.get("comment_id", "")

        if not row.get("is_valid"):
            rejected.append(row)
            continue

        if comment_id in seen_ids:
            rejected_row = dict(row)
            rejected_row["is_valid"] = False
            rejected_row["drop_reason"] = "duplicate_comment_id"
            rejected.append(rejected_row)
            continue

        seen_ids.add(comment_id)
        clean.append(row)

    return clean, rejected


VIDEO_COLUMNS = [
    "company",
    "search_query",
    "video_id",
    "search_rank",
    "title",
    "channel_title",
    "published_at",
    "view_count",
    "comment_count",
    "like_count",
    "video_mentions_company_keyword",
]

COMMENT_COLUMNS = [
    "company",
    "video_id",
    "video_title",
    "comment_id",
    "thread_id",
    "comment_type",
    "parent_comment_id",
    "text_raw",
    "text_clean",
    "like_count",
    "published_at",
    "updated_at",
    "relevance_hint",
    "include_for_nlp",
    "is_valid",
    "drop_reason",
]

NLP_COLUMNS = [
    "company",
    "video_id",
    "comment_id",
    "comment_type",
    "parent_comment_id",
    "text_clean",
    "relevance_hint",
    "published_at",
]


def run_etl() -> Path:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_dir = ROOT_DIR / "data" / "raw" / run_id
    processed_dir = ROOT_DIR / "data" / "processed" / run_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== ETL YouTube | {COMPANY_NAME} ===")

    candidates = search_video_candidates(raw_dir)
    if not candidates:
        raise RuntimeError("Nenhum vídeo candidato encontrado.")

    videos = get_video_details(candidates, raw_dir)
    selected_videos = select_best_videos(videos)

    write_csv(processed_dir / "videos_candidates.csv", videos, VIDEO_COLUMNS)
    write_csv(processed_dir / "videos_selected.csv", selected_videos, VIDEO_COLUMNS)

    raw_comments_path = raw_dir / "03_comments.jsonl"
    all_comments = []

    for idx, video in enumerate(selected_videos, start=1):
        print(f"[{idx}/{len(selected_videos)}] {video['title']}")
        if video["comment_count"] <= 0:
            continue
        all_comments.extend(collect_video_comments(video, raw_comments_path))

    clean_comments, rejected_comments = deduplicate_and_validate(all_comments)

    write_csv(processed_dir / "comments_clean.csv", clean_comments, COMMENT_COLUMNS)
    write_csv(processed_dir / "comments_rejected.csv", rejected_comments, COMMENT_COLUMNS)

    nlp_rows = [
        {column: row.get(column, "") for column in NLP_COLUMNS}
        for row in clean_comments
        if row.get("include_for_nlp")
    ]
    write_csv(processed_dir / "comments_for_nlp.csv", nlp_rows, NLP_COLUMNS)

    summary = {
        "run_id": run_id,
        "company": COMPANY_NAME,
        "search_query": SEARCH_QUERY,
        "candidate_videos": len(videos),
        "selected_videos": len(selected_videos),
        "comments_extracted": len(all_comments),
        "comments_clean": len(clean_comments),
        "comments_rejected": len(rejected_comments),
        "comments_for_nlp": len(nlp_rows),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    save_json(processed_dir / "summary.json", summary)

    print(f"ETL concluído: {processed_dir}")
    print(f"Comentários enviados ao NLP: {len(nlp_rows)}")
    return processed_dir


if __name__ == "__main__":
    run_etl()
