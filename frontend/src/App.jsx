import { useState } from "react";
import axios from "axios";
import "@chatscope/chat-ui-kit-styles/dist/default/styles.min.css";
import {
  MainContainer,
  ChatContainer,
  MessageList,
  Message,
  MessageInput,
  TypingIndicator,
} from "@chatscope/chat-ui-kit-react";

// 브라우저가 직접 호출하므로 컨테이너 이름이 아닌 localhost 를 쓴다
const API_URL = "http://localhost:8001/chat";

// 말풍선을 서버가 받는 {role, content} 로 바꾼다 (내 말 = user, 챗봇 말 = assistant)
const toApiMessages = (bubbles) =>
  bubbles.map((m) => ({
    role: m.direction === "outgoing" ? "user" : "assistant",
    content: m.content,
  }));

export default function App() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  const add = (direction, content, sender) =>
    setMessages((prev) => [
      ...prev,
      { direction, content, sentTime: new Date().toLocaleTimeString("ko-KR"), sender },
    ]);

  const onSend = async (innerHtml, textContent) => {
    const question = textContent.trim();
    if (!question) return; // 빈 입력은 무시
    add("outgoing", question, "나"); // [A] 내 말을 먼저 더한다
    setLoading(true);
    try {
      // messages 는 [A] 전 상태라 이번 말은 끝에 한 번만 붙는다
      const history = [...toApiMessages(messages), { role: "user", content: question }];
      const res = await axios.post(API_URL, { messages: history }); // [B]
      add("incoming", res.data.response, "챗봇"); // [C]
    } catch (e) {
      add("incoming", `서버 호출 실패: ${e.message}`, "챗봇");
    } finally {
      setLoading(false); // 성공·실패 모두 표시를 내리고 잠금을 푼다
    }
  };

  return (
    <div className="chat">
      <MainContainer>
        <ChatContainer>
          <MessageList
            typingIndicator={loading && <TypingIndicator content="답을 찾는 중" />}
          >
            {messages.map((m, i) => (
              <Message
                key={i}
                model={{
                  direction: m.direction,
                  sentTime: m.sentTime,
                  sender: m.sender,
                  position: "single",
                }}
              >
                {/* model.message 는 HTML 로 그려지므로 답은 글자 그대로 넣는다 */}
                <Message.TextContent text={m.content} />
              </Message>
            ))}
          </MessageList>
          <MessageInput
            placeholder="메시지를 입력하세요"
            onSend={onSend}
            disabled={loading}
            attachButton={false}
          />
        </ChatContainer>
      </MainContainer>
    </div>
  );
}
