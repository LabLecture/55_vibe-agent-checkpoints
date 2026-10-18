"""유튜브 자막 MCP 서버를 stdio 로 띄워 도구를 모델에 묶고, 에이전트 루프(추론 → 행동 → 최종답변)를 손으로 한 바퀴 돌려 표로 남긴다."""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 2-2 · 2-3 의 도우미를 고치지 않고 가져다 쓴다
from run_agent import text_of
from run_news import BASE_URL, cell

OUT_PATH = Path("/app/out/youtube_mcp.md")
SERVER_PATH = Path(__file__).resolve().parent / "youtube_mcp_server.py"
HEAD = 80  # 돌아온 글 앞부분으로 보여 줄 글자 수
ANSWER_HEAD = 200  # 최종답변 앞부분으로 보여 줄 글자 수
NO_CALL = "도구를 호출하지 않고 답변했습니다"
SYSTEM = (
    "너는 유튜브 분석 전문가야. 사용자가 링크를 주면 무조건 'get_youtube_transcript' 도구를 사용해 "
    "자막을 먼저 가져와. 자막 데이터가 없으면 절대로 요약하지 말고 모른다고 답해."
)
QUESTION = "이 영상 한글로 요약해줘: https://www.youtube.com/watch?v=fToUPQ_WRaY"


def to_model_tool(t) -> dict:
    # 서버가 내놓은 도구 설명을 그대로 모델 도구 꼴(function)로 옮긴다
    return {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.inputSchema}}


def args_of(schema: dict) -> str:
    # inputSchema 의 인자를 "이름: 타입" 으로, 꼭 줘야 하는 인자는 (필수) 를 붙인다
    required = set(schema.get("required", []))
    return ", ".join(
        f"{k}: {v.get('type', '?')}" + (" (필수)" if k in required else "")
        for k, v in schema.get("properties", {}).items()
    )


async def run_once(llm, rec: dict) -> None:
    # 같은 상자 안 파이썬으로 서버 스크립트를 띄운다
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER_PATH)])
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        init = await session.initialize()
        rec["connect"] = (params.command, " ".join(params.args), init.serverInfo.name, init.serverInfo.version, init.protocolVersion)
        print(f"[연결] {' · '.join(rec['connect'])}")

        tools = (await session.list_tools()).tools
        rec["tools"] = [(t.name, t.description or "", args_of(t.inputSchema)) for t in tools]
        for row in rec["tools"]:
            print(f"[도구] {' · '.join(row)}")
        # 도구 설명을 손으로 다시 적지 않고 서버 것을 그대로 묶는다
        bound = llm.bind_tools([to_model_tool(t) for t in tools]).with_retry(stop_after_attempt=2)  # 막히면 한 번만 다시 보낸다

        # 추론: 모델이 도구 쪽지를 내는가
        messages = [SystemMessage(SYSTEM), HumanMessage(QUESTION)]
        ai = await bound.ainvoke(messages)
        messages.append(ai)
        if not ai.tool_calls:
            rec["answer"] = text_of(ai.content)
            print(f"[쪽지 없음] {NO_CALL}")
            return

        # 행동: 쪽지마다 서버에 보내고 돌아온 글을 ToolMessage 로 붙인다
        for c in ai.tool_calls:
            res = await session.call_tool(c["name"], c["args"])
            text = "".join(x.text for x in res.content if x.type == "text")
            messages.append(ToolMessage(content=text, name=c["name"], tool_call_id=c["id"]))
            # 자막 전체는 남기지 않고 길이와 앞부분만
            rec["calls"].append((c["name"], json.dumps(c["args"], ensure_ascii=False), str(len(text)), text[:HEAD], str(res.isError)))
            print(f"[쪽지] {' · '.join(rec['calls'][-1])}")

        # 최종답변: 돌아온 글을 쥐고 다시 묻는다
        final = await bound.ainvoke(messages)
        rec["answer"] = text_of(final.content)
        if final.tool_calls:  # 한 바퀴만 도므로 또 낸 쪽지는 표에 적어만 둔다
            rec["extra"] = ", ".join(c["name"] for c in final.tool_calls)


def main() -> None:
    model = os.environ.get("LLM_MODEL")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not model:
        sys.exit("환경 변수 LLM_MODEL 이 없습니다.")
    if not api_key:
        sys.exit("환경 변수 OPENROUTER_API_KEY 가 없습니다.")

    llm = ChatOpenAI(model=model, base_url=BASE_URL, api_key=api_key, max_retries=0)

    # 막혀도 그때까지 모은 것으로 표를 쓴다
    rec = {"connect": None, "tools": [], "calls": [], "answer": "", "extra": ""}
    error = ""
    start = time.monotonic()
    try:
        asyncio.run(run_once(llm, rec))
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        print(f"[실패] {error}")
    sec = time.monotonic() - start
    status = "호출 실패" if error else "완료"
    print(f"=== ({sec:.1f}초) {status}")
    print(f"[최종답변] {rec['answer'][:ANSWER_HEAD]}")

    lines = [
        "# MCP 유튜브 요약 한 바퀴 (추론 → 행동 → 최종답변)",
        "",
        f"모델: {model} · 걸린 초: {sec:.1f} · 상태: {status}",
        "",
        f"질문: {QUESTION}",
        "",
        "## 연결",
        "",
        "| 명령 | 인자 | 서버 이름 | 서버 판 | 프로토콜 판 |",
        "|---|---|---|---|---|",
    ]
    if rec["connect"]:
        lines.append(f"| {' | '.join(cell(x) for x in rec['connect'])} |")
    lines += [
        "",
        "## 서버가 내놓은 도구",
        "",
        "| 이름 | 설명 | 인자 |",
        "|---|---|---|",
    ]
    lines += [f"| {' | '.join(cell(x) for x in row)} |" for row in rec["tools"]]
    lines += ["", "## 쪽지 (추론 → 행동)", ""]
    if rec["calls"]:
        lines += [
            "| # | 도구 이름 | 인자 | 돌아온 글 길이 | 돌아온 글 앞부분 | isError |",
            "|---|---|---|---|---|---|",
        ]
        lines += [f"| {i} | {' | '.join(cell(x) for x in row)} |" for i, row in enumerate(rec["calls"], 1)]
    elif rec["answer"]:
        lines.append(NO_CALL)
    lines += ["", "## 최종답변", "", f"- 앞부분: {cell(rec['answer'][:ANSWER_HEAD])}"]
    if rec["extra"]:
        lines.append(f"- 최종답변에서 또 낸 쪽지 (한 바퀴라 부르지 않음): {rec['extra']}")
    if error:
        lines += ["", f"오류: {cell(error)}"]
    lines += [
        "",
        "## 사람이 확인",
        "",
        "| 사람이 확인 | 결과 |",
        "|---|---|",
        "| 요약의 말이 자막 글에 있나 |  |",
    ]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"표 저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
