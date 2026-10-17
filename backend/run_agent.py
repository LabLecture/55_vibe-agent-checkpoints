"""뉴스 크롤링 도구와 글자 수 도구를 쥔 에이전트가 도구를 골라 쓰고, 그 흐름을 표로 남긴다."""
import os
import sys
import time
from pathlib import Path

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

# 2-2 뉴스 스크립트의 크롤링 도구와 표 도우미를 고치지 않고 가져다 쓴다
from run_news import BASE_URL, FAIL_PREFIX, cell, naver_news_crawl

OUT_PATH = Path("/app/out/agent_run.md")
NEWS_URL = "https://n.news.naver.com/mnews/article/018/0006389647"

QUESTIONS = [
    f"이 뉴스 기사를 요약하고 요약한 내용과 글자수를 알려줘: {NEWS_URL}",
]

SYSTEM_PROMPT = (
    "당신은 뉴스 분석 전문가입니다. 제공된 도구를 사용해 뉴스를 크롤링하고, "
    "그 내용을 요약한 뒤 원문과 요약문의 글자 수를 비교하여 보고하세요. "
    "모든 답변은 한국어로 작성합니다."
)

TRACE_CHARS = 80  # 콘솔에 찍을 인자·결과 앞부분 글자 수
ANSWER_CHARS = 200  # 표에 남길 최종 답 앞부분 글자 수 (기사 본문 전체는 남기지 않는다)


@tool
def get_word_length(text: str) -> int:
    """텍스트의 글자 수(길이)를 반환합니다."""
    return len(text)


TOOLS = [naver_news_crawl, get_word_length]


def text_of(content) -> str:
    # 메시지 content 가 글자열이 아니면(조각 목록 등) 글자열로 바꾼다
    return content if isinstance(content, str) else str(content)


def main() -> None:
    model = os.environ.get("LLM_MODEL")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not model:
        sys.exit("환경 변수 LLM_MODEL 이 없습니다.")
    if not api_key:
        sys.exit("환경 변수 OPENROUTER_API_KEY 가 없습니다.")

    llm = ChatOpenAI(model=model, base_url=BASE_URL, api_key=api_key, max_retries=0)
    agent = create_agent(model=llm, tools=TOOLS, system_prompt=SYSTEM_PROMPT).with_retry(
        stop_after_attempt=2  # 막히면 한 번만 다시 보낸다
    )

    header = [
        "# 에이전트 도구 선택 확인 (뉴스 크롤링 + 글자 수)",
        "",
        f"모델: {model}",
        "",
        "| 질문 | 도구 순서 | 도구가 센 글자 수 | 최종 답 앞 200자 | 걸린 초 | 상태 "
        "| 도구 결과 줄이 있는가 | 도구 이름이 둘 다인가 | 글자 수가 도구 값인가 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    lines = []

    for q in QUESTIONS:
        start = time.monotonic()
        try:
            result = agent.invoke({"messages": [{"role": "user", "content": q}]})
            messages, error = result["messages"], ""
        except Exception as e:  # 두 번 다 막히면 오류 원문을 그대로 남긴다
            messages, error = [], f"{type(e).__name__}: {e}"
        sec = time.monotonic() - start

        print(f"=== {q}")
        order, lengths, answer, crawl_failed = [], [], "", False
        # 돌아온 messages 를 차례대로 읽어 도구 호출과 결과를 적는다
        for m in messages:
            if isinstance(m, AIMessage) and m.tool_calls:
                for c in m.tool_calls:
                    order.append(c["name"])
                    print(f"[호출] {c['name']} · {str(c['args'])[:TRACE_CHARS]}")
            elif isinstance(m, ToolMessage):
                out = text_of(m.content)
                print(f"[결과] {m.name} · {out[:TRACE_CHARS]}")
                if m.name == get_word_length.name:
                    lengths.append(out)
                elif m.name == naver_news_crawl.name and out.startswith(FAIL_PREFIX):
                    crawl_failed = True
            elif isinstance(m, AIMessage):
                answer = text_of(m.content)  # 도구 호출 없는 마지막 AI 메시지가 최종 답

        if error:
            status, answer = "호출 실패", error
        elif not order:
            status = "도구 호출 없음"
        elif crawl_failed:
            status = "크롤링 실패"
        else:
            status = "완료"

        print(f"[최종 답] {answer[:ANSWER_CHARS]}")
        print(f"=== ({sec:.1f}초) {status}")
        row = [q, " → ".join(order) or "(없음)", "; ".join(lengths), answer[:ANSWER_CHARS]]
        lines.append(
            f"| {' | '.join(cell(x) for x in row)} | {sec:.1f} | {status} |  |  |  |"
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
