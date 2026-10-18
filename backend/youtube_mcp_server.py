"""유튜브 자막을 가져오는 도구 하나를 내놓는 MCP 서버. stdio 로 돈다.

표준 출력은 클라이언트와 말하는 통로이므로 여기서는 아무것도 찍지 않는다.
"""
import re

from mcp.server.fastmcp import FastMCP
from youtube_transcript_api import NoTranscriptFound, YouTubeTranscriptApi

mcp = FastMCP("YouTube Summarizer")


def video_id_of(url: str) -> str:
    # watch?v= · youtu.be/ · shorts/ · embed/ 뒤의 11자리 영상 ID 를 뽑는다
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([\w-]{11})", url)
    if not m:
        raise ValueError(f"영상 ID 를 찾지 못함: {url}")
    return m.group(1)


@mcp.tool()
def get_youtube_transcript(video_url: str) -> str:
    """유튜브 URL을 입력받아 해당 영상의 자막 전체를 추출합니다."""
    try:
        transcripts = YouTubeTranscriptApi().list(video_id_of(video_url))
        try:
            # 한국어 자동 자막을 먼저 찾는다
            transcript = transcripts.find_generated_transcript(["ko"])
        except NoTranscriptFound:
            # 없으면 목록의 첫 자막
            transcript = next(iter(transcripts))
        # 조각들을 한 줄 글로 잇는다
        return " ".join(s.text for s in transcript.fetch())
    except Exception as e:  # 오류를 던지지 않고 글로 돌려준다
        return f"자막 추출 실패: {type(e).__name__}: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
