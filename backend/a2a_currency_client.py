"""LangGraph 환전 A2A 서버(app/)를 자식 프로세스로 띄워 카드를 읽고, 한 번 묻기와 되묻는 대화를 보낸 뒤 표로 남긴다."""
import asyncio
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import MessageSendParams, SendStreamingMessageRequest
from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH

# 2-2 의 도우미를 고치지 않고 가져다 쓴다
from run_news import cell

OUT_PATH = Path("/app/out/a2a_currency.md")
SERVER_DIR = Path(__file__).resolve().parent  # 이 폴더에서 python -m app 으로 띄운다
LOG_PATH = Path("/tmp/a2a_currency_server.log")  # 서버 로그는 작업 폴더 밖에 둔다
BASE = "http://localhost:10000"
WAIT_SEC = 30  # 서버가 뜨기를 기다릴 최대 초
HTTP_TIMEOUT_SEC = 180  # 모델 호출이 여러 번 이어지므로 넉넉히 기다린다
# 도구가 부른 환율 주소는 서버 로그의 httpx 줄에서 잡는다
TOOL_URL_RE = re.compile(r"GET (https://api\.frankfurter\.dev/\S+)")


def text_of(parts) -> str:
    return "".join(p.root.text for p in parts or [] if getattr(p.root, "text", None))


async def wait_ready(client: httpx.AsyncClient, proc: subprocess.Popen) -> None:
    # 카드 주소가 답할 때까지 조금씩 기다린다
    deadline = time.monotonic() + WAIT_SEC
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"서버가 먼저 끝났습니다 (종료 코드 {proc.returncode})")
        try:
            await client.get(BASE + AGENT_CARD_WELL_KNOWN_PATH)
            return
        except httpx.TransportError:
            await asyncio.sleep(0.2)
    raise TimeoutError(f"서버가 {WAIT_SEC}초 안에 뜨지 않았습니다")


async def tool_rows(client: httpx.AsyncClient, log_from: int, label: str) -> list:
    # 이 말을 보낸 뒤 서버 로그에 찍힌 환율 주소를 같은 주소로 한 번 더 불러 환율 · 날짜를 얻는다
    # ponytail: 도구 결과는 A2A 메시지에 안 실려 다시 부른 값이다. 날이 바뀌는 순간이면 어긋날 수 있다
    log = LOG_PATH.read_text(encoding="utf-8", errors="replace")[log_from:]
    rows = []
    for url in TOOL_URL_RE.findall(log):
        try:
            data = (await client.get(url)).json()
            rows.append((label, url, str(data.get("rates", data)), str(data.get("date", ""))))
        except Exception as e:
            rows.append((label, url, f"{type(e).__name__}: {e}", ""))
    return rows


async def send(a2a: A2AClient, text: str, task_id: str | None = None, context_id: str | None = None) -> dict:
    # 스트리밍으로 보내 작업 상태가 바뀌는 차례를 모은다
    message = {"role": "user", "parts": [{"kind": "text", "text": text}], "messageId": uuid4().hex}
    if task_id:  # 되묻는 대화는 같은 작업 · 같은 대화로 이어 보낸다
        message["taskId"] = task_id
        message["contextId"] = context_id
    for attempt in range(2):  # 막히면 한 번만 다시 보낸다
        rec = {"text": text, "states": [], "task_id": "", "context_id": "", "status_msg": "", "artifact": ""}
        start = time.monotonic()
        try:
            request = SendStreamingMessageRequest(id=str(uuid4()), params=MessageSendParams(message=message))
            async for chunk in a2a.send_message_streaming(request):
                ev = getattr(chunk.root, "result", None)
                if ev is None:  # JSON-RPC 오류 응답
                    raise RuntimeError(f"오류 응답: {chunk.root.error}")
                if ev.kind == "task":
                    rec["task_id"], rec["context_id"] = ev.id, ev.context_id
                    rec["states"].append(ev.status.state.value)
                elif ev.kind == "status-update":
                    rec["task_id"], rec["context_id"] = ev.task_id, ev.context_id
                    rec["states"].append(ev.status.state.value)
                    if ev.status.message:
                        rec["status_msg"] = text_of(ev.status.message.parts)
                elif ev.kind == "artifact-update":
                    rec["artifact"] += text_of(ev.artifact.parts)
                elif ev.kind == "message":
                    rec["status_msg"] = text_of(ev.parts)
            break
        except Exception as e:
            print(f"[다시 보냄] {type(e).__name__}: {e}")
            if attempt:
                raise
    rec["sec"] = time.monotonic() - start
    rec["answer"] = rec["artifact"] or rec["status_msg"]
    print(f"[{text}] {' → '.join(rec['states'])} · {rec['answer']} ({rec['sec']:.1f}초)")
    return rec


async def run_once(proc: subprocess.Popen, out: dict) -> None:
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SEC) as client:
        await wait_ready(client, proc)

        card = await A2ACardResolver(httpx_client=client, base_url=BASE).get_agent_card()
        out["card"] = card
        print(f"[카드] {card.name} · {card.description}")
        a2a = A2AClient(httpx_client=client, agent_card=card)

        async def turn(label: str, text: str, task_id=None, context_id=None) -> dict:
            log_from = len(LOG_PATH.read_text(encoding="utf-8", errors="replace"))
            rec = await send(a2a, text, task_id, context_id)
            rec["label"] = label
            out["turns"].append(rec)
            out["tools"] += await tool_rows(client, log_from, label)
            return rec

        # 대화 A: 한 번에 다 주는 질문
        await turn("A", "How much is 100 USD in KRW?")
        # 대화 B: 새 대화로 통화를 빼고 물어 되묻게 한 뒤, 되물으면 같은 대화로 KRW 를 준다
        first = await turn("B-1", "How much is 100 USD?")
        if first["states"] and first["states"][-1] == "input-required":
            await turn("B-2", "KRW", first["task_id"], first["context_id"])
        else:
            out["note"] = f"B-1 이 되묻지 않음 (마지막 상태 {first['states'][-1] if first['states'] else '없음'}) · B-2 보내지 않음"
            print(f"[메모] {out['note']}")


def main() -> None:
    # 막혀도 그때까지 모은 것으로 표를 쓴다
    out = {"card": None, "turns": [], "tools": [], "note": ""}
    error = ""
    start = time.monotonic()
    # 같은 상자 안 파이썬으로 서버 패키지를 띄우고 로그는 파일로 받는다
    log = LOG_PATH.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "app"],
        cwd=SERVER_DIR,
        stdout=log,
        stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    try:
        asyncio.run(run_once(proc, out))
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        print(f"[실패] {error}")
    finally:
        # 다 쓰면 서버를 끈다
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        log.close()
    sec = time.monotonic() - start
    status = "호출 실패" if error else "완료"
    print(f"=== ({sec:.1f}초) {status}")

    lines = [
        "# A2A 환전 에이전트 (LangGraph) 한 바퀴 (카드 읽기 → 메시지 보내기 · 되묻기)",
        "",
        f"걸린 초: {sec:.1f} · 상태: {status} · 모델: {cell(os.environ.get('LLM_MODEL', ''))}",
    ]
    card = out["card"]
    if card:
        lines += [
            "",
            "## 카드",
            "",
            "| 이름 | 설명 | 판 | 주소 | 입력 | 출력 |",
            "|---|---|---|---|---|---|",
            f"| {cell(card.name)} | {cell(card.description)} | {cell(card.version)} | {cell(card.url)} "
            f"| {cell(', '.join(card.default_input_modes))} | {cell(', '.join(card.default_output_modes))} |",
            "",
            "## 스킬",
            "",
            "| id | 이름 | 설명 | 태그 | 예시 |",
            "|---|---|---|---|---|",
        ]
        lines += [
            f"| {cell(s.id)} | {cell(s.name)} | {cell(s.description)} | {cell(', '.join(s.tags))} | {cell(', '.join(s.examples or []))} |"
            for s in card.skills
        ]
        lines += ["", f"Capabilities: {cell(card.capabilities.model_dump(exclude_none=True))}"]
    lines += [
        "",
        "## 보낸 말",
        "",
        "| 대화 | 보낸 말 | task_id | context_id | 작업 상태 차례 | 최종 답 | 걸린 초 |",
        "|---|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {r['label']} | {cell(r['text'])} | {r['task_id'][:8]} | {r['context_id'][:8]} "
        f"| {cell(' → '.join(r['states']))} | {cell(r['answer'])} | {r['sec']:.1f} |"
        for r in out["turns"]
    ]
    lines += [
        "",
        "## 도구가 돌려준 환율",
        "",
        "서버 로그에서 도구가 부른 주소를 잡아 같은 주소를 한 번 더 부른 값이다.",
        "",
        "| 대화 | 도구 주소 | 환율 | 날짜 |",
        "|---|---|---|---|",
    ]
    lines += [f"| {lab} | {cell(url)} | {cell(rate)} | {cell(date)} |" for lab, url, rate, date in out["tools"]]
    if not out["tools"]:
        lines += ["| - | 도구 호출 없음 | | |"]
    if out["note"]:
        lines += ["", f"메모: {cell(out['note'])}"]
    if error:
        lines += ["", f"오류: {cell(error)}"]
    lines += [
        "",
        "## 사람이 확인",
        "",
        "| 사람이 확인 | 결과 |",
        "|---|---|",
        "| 대화 A 최종 답의 숫자가 도구가 돌려준 숫자(100 × 환율)와 같은가 |  |",
        "| 대화 B 최종 답의 숫자가 도구가 돌려준 숫자(100 × 환율)와 같은가 |  |",
    ]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"표 저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
