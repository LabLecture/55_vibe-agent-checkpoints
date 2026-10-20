"""서버 chat 주소만 불러 대본 세 턴과 틀린 요청 둘을 표로 남긴다.

python run_chat_api.py          다섯 요청을 차례로 보내 표를 새로 쓴다
python run_chat_api.py tools    표준 입력으로 받은 서버 로그에서 도구 시작 줄만 골라 표 아래에 더한다
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from run_graph import cell, turn

URL = "http://localhost:8001/chat"
OUT_PATH = Path("/app/out/chat_api.md")
TIMEOUT_SEC = 200  # 서버 전체 한도 180초보다 길게 기다린다


def post(body: dict) -> tuple[int, str, float]:
    # 한 번만 보내고 (상태 번호, 본문 원문, 걸린 초) 를 돌려준다. 오류가 나도 다시 보내지 않는다
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(URL, data, {"Content-Type": "application/json"})
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as res:
            status, text = res.status, res.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        status, text = e.code, e.read().decode("utf-8")
    except Exception as e:
        status, text = "-", repr(e)
    sec = time.monotonic() - start
    print(f"=== 상태 {status} ({sec:.1f}초) -> {text[:80]}")
    return status, text, sec


def reply(status, text: str) -> str:
    # 200 이면 response 칸 글, 아니면 본문 원문을 그대로 앞 챗봇 말로 쓴다
    if status == 200:
        return json.loads(text)["response"]
    return text


def main() -> None:
    q1, _ = turn(1)
    q2, _ = turn(2)
    q3, _ = turn(3)
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []  # (요청, 보낸 말 수, 상태, 글, 초, 사람 칸)

    m1 = [{"role": "user", "content": q1}]
    s, t, sec = post({"messages": m1})
    rows.append(("① 턴 1", len(m1), s, reply(s, t), sec, ""))
    a1 = reply(s, t)

    m2 = m1 + [{"role": "assistant", "content": a1}, {"role": "user", "content": q2}]
    s, t, sec = post({"messages": m2})
    rows.append(("② 턴 2", len(m2), s, reply(s, t), sec, ""))
    a2 = reply(s, t)

    m3 = m2 + [{"role": "assistant", "content": a2}, {"role": "user", "content": q3}]
    s, t, sec = post({"messages": m3})
    rows.append(("③ 턴 3", len(m3), s, reply(s, t), sec, ""))

    s, t, sec = post({"messages": []})
    rows.append(("④ 빈 목록", 0, s, t, sec, "-"))

    s, t, sec = post({"question": q1})
    rows.append(("⑤ 옛 화면 꼴 {question}", "-", s, t, sec, "-"))

    lines = [
        "# 서버 chat 주소 단독 (대본 세 턴 · 틀린 요청 둘)",
        "",
        f"모델: {os.environ.get('LLM_MODEL', '-')} · 주소: {URL} · 시작: {started}",
        "",
        "앞 챗봇 말은 대본 글이 아니라 서버가 실제로 돌려준 답을 이어 붙였다",
        "",
        "| 요청 | 보낸 말 수 | 상태 번호 | 돌려준 글 원문 | 걸린 초 | 대본 턴과 같은가 (사람) |",
        "|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {name} | {count} | {status} | {cell(text)} | {sec:.1f} | {human} |"
        for name, count, status, text, sec, human in rows
    ]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"표 저장: {OUT_PATH}")


def main_tools() -> None:
    # 서버 로그 가운데 _tool_start 가 든 줄만 표 아래에 더한다
    tool_starts = [line.rstrip() for line in sys.stdin if "_tool_start" in line]
    lines = ["", "## 서버 로그의 도구 시작 줄 (원문)", ""]
    lines += ["```", *tool_starts, "```"] if tool_starts else ["(도구 시작 줄 없음)"]
    with OUT_PATH.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"도구 시작 줄 {len(tool_starts)}개를 더함: {OUT_PATH}")


if __name__ == "__main__":
    main_tools() if sys.argv[1:] == ["tools"] else main()
