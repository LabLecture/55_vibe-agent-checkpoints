"""prompts/{이름}.md 를 읽어 <<이름>> 자리를 채우고 system 메시지로 붙인다 (LangManus prompts/template.py 꼴)."""
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from langchain_core.messages import SystemMessage

# 한국 시각 (+0900). 상자에 tzdata 가 없어도 되게 고정 시차를 쓴다
KST = timezone(timedelta(hours=9))


def apply_prompt_template(prompt_name: str, state: dict) -> list:
    text = (Path(__file__).parent / f"{prompt_name}.md").read_text(encoding="utf-8")
    values = {"CURRENT_TIME": datetime.now(KST).strftime("%a %b %d %Y %H:%M:%S %z"), **state}

    def fill(m: re.Match) -> str:
        # 목록 값은 「a, b」 꼴로 잇는다. { } 는 건드리지 않는다
        v = values[m.group(1)]
        return ", ".join(v) if isinstance(v, list) else str(v)

    return [SystemMessage(re.sub(r"<<(\w+)>>", fill, text))] + state["messages"]
