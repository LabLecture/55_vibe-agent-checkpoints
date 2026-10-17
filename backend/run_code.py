"""모델에게 파이썬 코드를 짜게 하고, 체인 마지막 칸에서 그 코드를 바로 실행해 표로 남긴다."""
import os
import re
import sys
import time
from pathlib import Path

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_experimental.tools import PythonREPLTool
from langchain_experimental.utilities import PythonREPL
from langchain_openai import ChatOpenAI

BASE_URL = "https://openrouter.ai/api/v1"
OUT_PATH = Path("/app/out/code_run.md")

SYSTEM = (
    "You are Raymond Hettinger, an expert python programmer. "
    "Return only the raw python code. No explanation, no markdown blocks, no intro. "
    "Just the code itself."
)

QUESTIONS = [
    "로또 번호 생성기를 출력하는 코드를 작성하세요. "
    "1부터 45까지 숫자 중 6개를 중복없이 정렬하여 출력하세요.",
]

# 마크다운 코드 블록(```python ... ```) 안쪽만 잡는다
FENCE = re.compile(r"```[\w+-]*[ \t]*\n?(.*?)```", re.S)
# PythonREPL 은 예외를 잡아 repr(e) 글자로 돌려준다 (예: NameError("..."))
ERROR_RESULT = re.compile(r"^\w+(Error|Exception)\(")


def strip_fences(text: str) -> str:
    # 코드 블록 표시가 있으면 첫 블록 안쪽만, 없으면 글 그대로 쓴다
    m = FENCE.search(text)
    return (m.group(1) if m else text).strip()


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
    # __name__ 을 "__main__" 으로 넣어야 if __name__ == "__main__": 아래 코드가 돈다
    # locals 를 None 으로 두어 globals 하나만 쓴다 (나뉘면 함수 안에서 import 한 이름을 못 찾는다)
    repl = PythonREPLTool(
        python_repl=PythonREPL(_globals={"__name__": "__main__"}, _locals=None)
    )
    rows: list[dict] = []

    def write_table() -> None:
        lines = [
            "# 모델이 짠 코드 실행 확인",
            "",
            f"모델: {model}",
            "",
            "| 질문 | 짠 코드 원문 | 실행 결과 | 걸린 초 | 상태 | 6개인가 | 겹치지 않는가 | 정렬됐는가 |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for r in rows:
            lines.append(
                f"| {cell(r['q'])} | {cell(r['code'])} | {cell(r['result'])} "
                f"| {r['sec']} | {r['status']} |  |  |  |"
            )
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def run(code: str) -> str:
        # 실행하기 전에 짠 코드 원문부터 표에 적어 둔다
        rows[-1].update(code=code, status="실행 전")
        write_table()
        return repl.run(strip_fences(code))

    chain = (
        ChatPromptTemplate.from_messages([("system", SYSTEM), ("user", "{question}")])
        | llm.with_retry(stop_after_attempt=2)  # 막히면 한 번만 다시 보낸다
        | StrOutputParser()
        | RunnableLambda(run)
    )

    for q in QUESTIONS:
        rows.append({"q": q, "code": "", "result": "", "sec": "", "status": "호출 중"})
        start = time.monotonic()
        try:
            result = chain.invoke({"question": q})
            if not result.strip():
                status = "출력 없음"
            elif ERROR_RESULT.match(result.strip()):
                status = "실행 오류"
            else:
                status = "실행 성공"
        except Exception as e:  # 두 번 다 막히면 오류 원문을 그대로 남긴다
            result, status = f"{type(e).__name__}: {e}", "호출 실패"
        sec = time.monotonic() - start

        rows[-1].update(result=result, sec=f"{sec:.1f}", status=status)
        write_table()
        print(f"=== {q} ({sec:.1f}초) {status}\n--- 코드\n{rows[-1]['code']}\n--- 결과\n{result}")

    print(f"표 저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
