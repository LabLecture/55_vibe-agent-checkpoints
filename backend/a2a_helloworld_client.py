"""Hello World A2A 서버를 자식 프로세스로 띄워 카드를 읽고 「hi」 메시지 하나를 보낸 뒤 표로 남긴다."""
import asyncio
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import MessageSendParams, SendMessageRequest
from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH, PREV_AGENT_CARD_WELL_KNOWN_PATH

# 2-2 의 도우미를 고치지 않고 가져다 쓴다
from run_news import cell

OUT_PATH = Path("/app/out/a2a_helloworld.md")
SERVER_PATH = Path(__file__).resolve().parent / "a2a_helloworld_server.py"
BASE = "http://localhost:9999"
CARD_PATHS = [PREV_AGENT_CARD_WELL_KNOWN_PATH, AGENT_CARD_WELL_KNOWN_PATH]
WAIT_SEC = 20  # 서버가 뜨기를 기다릴 최대 초
QUESTION = "hi"


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


async def run_once(proc: subprocess.Popen, rec: dict) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        await wait_ready(client, proc)

        # 두 카드 주소(옛 주소 · 지금 주소)의 상태 코드
        for path in CARD_PATHS:
            code = (await client.get(BASE + path)).status_code
            rec["codes"].append((path, str(code)))
            print(f"[카드 주소] {path} · {code}")

        card = await A2ACardResolver(httpx_client=client, base_url=BASE).get_agent_card()
        rec["card"] = card
        print(f"[카드] {card.name} · {card.description}")

        a2a = A2AClient(httpx_client=client, agent_card=card)
        message = {"role": "user", "parts": [{"kind": "text", "text": QUESTION}], "messageId": uuid4().hex}
        request = SendMessageRequest(id=str(uuid4()), params=MessageSendParams(message=message))
        for attempt in range(2):  # 막히면 한 번만 다시 보낸다
            try:
                resp = await a2a.send_message(request)
                break
            except Exception as e:
                print(f"[다시 보냄] {type(e).__name__}: {e}")
                if attempt:
                    raise

        result = getattr(resp.root, "result", None)
        if result is None:  # JSON-RPC 오류 응답
            raise RuntimeError(f"오류 응답: {resp.root.error}")
        rec["kind"] = result.kind
        rec["answer"] = "".join(p.root.text for p in getattr(result, "parts", []) if getattr(p.root, "text", None))
        print(f"[답] {rec['kind']} · {rec['answer']}")


def main() -> None:
    # 막혀도 그때까지 모은 것으로 표를 쓴다
    rec = {"codes": [], "card": None, "kind": "", "answer": ""}
    error = ""
    start = time.monotonic()
    # 같은 상자 안 파이썬으로 서버 스크립트를 띄운다
    proc = subprocess.Popen([sys.executable, str(SERVER_PATH)])
    try:
        asyncio.run(run_once(proc, rec))
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
    sec = time.monotonic() - start
    status = "호출 실패" if error else "완료"
    print(f"=== ({sec:.1f}초) {status}")

    lines = [
        "# A2A Hello World 한 바퀴 (카드 읽기 → 메시지 보내기)",
        "",
        f"걸린 초: {sec:.1f} · 상태: {status}",
        "",
        "## 카드 주소",
        "",
        "| 카드 주소 | 상태 코드 |",
        "|---|---|",
    ]
    lines += [f"| {cell(p)} | {c} |" for p, c in rec["codes"]]
    card = rec["card"]
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
        "## 메시지",
        "",
        "| 보낸 말 | 답 종류(kind) | 답 글 | 걸린 초 |",
        "|---|---|---|---|",
        f"| {cell(QUESTION)} | {cell(rec['kind'])} | {cell(rec['answer'])} | {sec:.1f} |",
    ]
    if error:
        lines += ["", f"오류: {cell(error)}"]
    lines += [
        "",
        "## 사람이 확인",
        "",
        "| 사람이 확인 | 결과 |",
        "|---|---|",
        "| 카드만 보고 이 에이전트가 무엇을 하는지 말할 수 있나 |  |",
    ]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"표 저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
