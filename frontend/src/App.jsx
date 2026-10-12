import { useState } from "react";

// 브라우저가 직접 호출하므로 컨테이너 이름이 아닌 localhost 를 쓴다
const API_URL = "http://localhost:8001/chat";

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");

  const add = (role, text) =>
    setMessages((prev) => [...prev, { role, text }]);

  const send = async () => {
    const question = input.trim();
    if (!question) return; // 빈 입력은 무시
    add("user", question);
    setInput("");
    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      add("bot", data.answer);
    } catch (e) {
      add("error", `서버 호출 실패: ${e.message}`);
    }
  };

  return (
    <div className="chat">
      <div className="messages">
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            {m.text}
          </div>
        ))}
      </div>
      <div className="input-row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          // 한글 조합 중 Enter 는 전송하지 않는다
          onKeyDown={(e) => e.key === "Enter" && !e.nativeEvent.isComposing && send()}
          placeholder="메시지를 입력하세요"
        />
        <button onClick={send}>보내기</button>
      </div>
    </div>
  );
}
