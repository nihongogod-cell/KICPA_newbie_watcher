import json
import os
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup


KICPA_URL = "https://www.kicpa.or.kr/home/jobOffrSrchNewGnrl/list.face"
STATE_FILE = Path("state.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    )
}


def fetch_posts():
    response = requests.get(
        KICPA_URL,
        headers=HEADERS,
        timeout=15,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    posts = []

    for a in soup.find_all("a"):
        onclick = a.get("onclick", "")

        if "fn_detail" not in onclick:
            continue

        match = re.search(
            r"fn_detail\(['\"]?(\d+)['\"]?\)",
            onclick,
        )

        if not match:
            continue

        post_id = match.group(1)
        title = a.get_text(" ", strip=True)

        posts.append({
            "id": post_id,
            "title": title,
        })

    return posts


def load_seen_ids():
    if not STATE_FILE.exists():
        return None

    with STATE_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    return set(data.get("seen_ids", []))


def save_seen_ids(posts):
    data = {
        "seen_ids": [post["id"] for post in posts]
    }

    with STATE_FILE.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
        )


def send_discord_notification(post):
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

    print(
        "Discord webhook env:",
        "PRESENT" if webhook_url else "MISSING"
    )

    if not webhook_url:
        raise RuntimeError(
            "DISCORD_WEBHOOK_URL 환경변수가 설정되지 않았습니다."
        )

    message = {
        "content": (
            "🚨 **KICPA 신규 채용공고**\n\n"
            f"**{post['title']}**\n\n"
            f"게시글 ID: `{post['id']}`\n"
            f"👉 {KICPA_URL}"
        )
    }

    response = requests.post(
        webhook_url,
        json=message,
        timeout=10,
    )

    print("Discord status:", response.status_code)

    response.raise_for_status()


def main():
    print("KICPA 게시판 확인 중...")

    posts = fetch_posts()

    print(f"현재 게시글 수: {len(posts)}")

    if not posts:
        raise RuntimeError(
            "게시글을 하나도 찾지 못했습니다. "
            "KICPA 페이지 구조가 변경되었을 수 있습니다."
        )

    seen_ids = load_seen_ids()

    # 최초 실행
    if seen_ids is None:
        save_seen_ids(posts)

        print(
            "최초 실행입니다. "
            "현재 게시글을 기준값으로 저장했습니다."
        )
        print("Discord 알림은 보내지 않습니다.")
        return

    new_posts = [
        post
        for post in posts
        if post["id"] not in seen_ids
    ]

    if not new_posts:
        print("새로운 게시글이 없습니다.")
        save_seen_ids(posts)
        return

    print(f"신규 게시글 발견: {len(new_posts)}건")

    # 목록은 최신순이므로 오래된 신규글부터 알림
    for post in reversed(new_posts):
        print(f"알림 전송: {post['title']}")
        send_discord_notification(post)

    save_seen_ids(posts)

    print("완료.")


if __name__ == "__main__":
    main()