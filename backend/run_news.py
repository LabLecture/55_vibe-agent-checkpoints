"""네이버 뉴스 크롤링 도구를 모델에 쥐여 주고, 모델이 고른 도구를 체인 안에서 실행해 표로 남긴다."""
import os
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from langchain_core.output_parsers.openai_tools import JsonOutputToolsParser
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

BASE_URL = "https://openrouter.ai/api/v1"
OUT_PATH = Path("/app/out/news_run.md")
NEWS_URL = "https://n.news.naver.com/mnews/article/008/0005427584"

QUESTIONS = [
    f"다음 뉴스 기사 내용을 크롤링해줘: {NEWS_URL}",
]

# 브라우저처럼 보이게 하는 User-Agent (없으면 막히는 경우가 있다)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}
CRAWL_TIMEOUT_SEC = 10
FAIL_PREFIX = "기사를 가져오지 못했습니다"
HEAD_CHARS = 200  # 표에 남길 본문 앞부분 글자 수 (본문 전체는 남기지 않는다)


@tool
def naver_news_crawl(news_url: str) -> str:
    """Crawls a 네이버 (naver.com) news article and returns the body content."""
    try:
        res = requests.get(news_url, headers=HEADERS, timeout=CRAWL_TIMEOUT_SEC)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        title = soup.select_one("h2#title_area")
        body = soup.select_one("div#contents")
        if title is None or body is None:
            return f"{FAIL_PREFIX}: h2#title_area 또는 div#contents 가 없습니다"
        # 제목과 본문을 빈 줄 하나로 잇는다 (표에서 이 빈 줄로 다시 나눈다)
        body_text = body.get_text("\n", strip=True)
        return f"{title.get_text(strip=True)}\n\n{body_text}"
    except Exception as e:  # 실패해도 멈추지 않고 실패 문장을 돌려준다
        return f"{FAIL_PREFIX}: {type(e).__name__}: {e}"


TOOLS = [naver_news_crawl]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}


def execute(calls: list[dict]) -> list[tuple[dict, str]]:
    """파서가 꺼낸 호출 목록을 type 으로 도구를 찾아 args 로 실행한다."""
    results = []
    for c in calls:
        t = TOOLS_BY_NAME.get(c["type"])
        if t is None:
            results.append((c, f"{FAIL_PREFIX}: KeyError: 없는 도구 {c['type']!r}"))
            continue
        results.append((c, t.invoke(c["args"])))
    return results


def cell(text: str) -> str:
    # 표가 깨지지 않게 | 와 줄바꿈을 바꾼다
    return str(text).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def main() -> None:
    model = os.environ.get("LLM_MODEL")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not model:
        sys.exit("환경 변수 LLM_MODEL 이 없습니다.")
    if not api_key:
        sys.exit("환경 변수 OPENROUTER_API_KEY 가 없습니다.")

    llm = ChatOpenAI(model=model, base_url=BASE_URL, api_key=api_key, max_retries=0)

    chain = (
        llm.bind_tools(TOOLS).with_retry(stop_after_attempt=2)  # 막히면 한 번만 다시 보낸다
        | JsonOutputToolsParser()  # [{"type": 도구 이름, "args": {...}}, ...]
        | RunnableLambda(execute)
    )

    header = [
        "# 네이버 뉴스 크롤링 도구 실행 확인",
        "",
        f"모델: {model}",
        "",
        "| 질문 | 실행 도구 | 전달 인자 | 제목 | 본문 앞 200자 | 본문 글자 수 | 걸린 초 | 상태 "
        "| 기사 제목과 같은가 | 본문이 기사 글인가 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    lines = []

    for q in QUESTIONS:
        start = time.monotonic()
        try:
            runs = chain.invoke(q)
            error = ""
        except Exception as e:  # 두 번 다 막히면 오류 원문을 그대로 남긴다
            runs, error = [], f"{type(e).__name__}: {e}"
        sec = time.monotonic() - start

        names, args, titles, heads, lengths = [], [], [], [], []
        for c, out in runs:
            names.append(c["type"])
            args.append(str(c["args"]))
            if out.startswith(FAIL_PREFIX):
                # 실패 문장은 본문 칸에 그대로 적는다
                titles.append("")
                heads.append(out)
                lengths.append("")
            else:
                title, _, body = out.partition("\n\n")
                titles.append(title)
                heads.append(body[:HEAD_CHARS])
                lengths.append(str(len(body)))

        if error:
            status, heads = "호출 실패", [error]
        elif not runs:
            status, names = "도구 호출 없음", ["(없음)"]
        elif any(out.startswith(FAIL_PREFIX) for _, out in runs):
            status = "크롤링 실패"
        else:
            status = "도구 실행"

        row = ["; ".join(x) for x in (names, args, titles, heads, lengths)]
        print(f"=== {q} ({sec:.1f}초) {status}: {row[0]} {row[1]} -> {row[2]} / {row[3]} ({row[4]}자)")
        lines.append(
            f"| {cell(q)} | {' | '.join(cell(x) for x in row)} | {sec:.1f} | {status} |  |  |"
        )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if OUT_PATH.exists():
        # 표가 있으면 앞 줄(사람이 매긴 칸 포함)은 두고 새 줄만 뒤에 더한다
        with OUT_PATH.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    else:
        OUT_PATH.write_text("\n".join(header + lines) + "\n", encoding="utf-8")
    print(f"표 저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
