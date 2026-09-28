import { useEffect, useRef, useState } from "react";
import { fetchHistory, sendChatMessage } from "./api.js";

const USERS = [
  { id: "U001", name: "Rahul Mehta" },
  { id: "U002", name: "Priya Shah" },
  { id: "U003", name: "Arjun Kapoor" },
  { id: "U004", name: "Neha Jain" },
];

function storageKey(userId) {
  return `portfolio-analyst:conversation:${userId}`;
}

export default function App() {
  const [userId, setUserId] = useState(USERS[0].id);
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const bottomRef = useRef(null);

  // When the selected user changes, load their saved conversation (if any).
  useEffect(() => {
    const saved = localStorage.getItem(storageKey(userId));
    setError(null);
    setMessages([]);
    if (saved) {
      const savedId = Number(saved);
      setConversationId(savedId);
      fetchHistory(userId, savedId).then((history) => {
        setMessages(history.map((m) => ({ role: m.role, content: m.content })));
      });
    } else {
      setConversationId(null);
    }
  }, [userId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function handleSend() {
    const text = input.trim();
    if (!text || sending) return;

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setSending(true);
    setError(null);

    try {
      const result = await sendChatMessage(userId, conversationId, text);
      setConversationId(result.conversation_id);
      localStorage.setItem(storageKey(userId), String(result.conversation_id));
      setMessages((prev) => [...prev, { role: "assistant", content: result.reply }]);
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleNewChat() {
    localStorage.removeItem(storageKey(userId));
    setConversationId(null);
    setMessages([]);
    setError(null);
  }

  const currentUser = USERS.find((u) => u.id === userId);

  return (
    <div className="phone">
      <div className="header">
        <div className="avatar">{currentUser.name.charAt(0)}</div>
        <div className="header-text">
          <div className="header-name">Portfolio Analyst</div>
          <div className="header-sub">chatting as {currentUser.name}</div>
        </div>
        <button className="new-chat" onClick={handleNewChat} title="Start a fresh conversation">
          New chat
        </button>
        <select className="user-select" value={userId} onChange={(e) => setUserId(e.target.value)}>
          {USERS.map((u) => (
            <option key={u.id} value={u.id}>
              {u.id} - {u.name}
            </option>
          ))}
        </select>
      </div>

      <div className="messages">
        {messages.length === 0 && !sending && (
          <div className="empty-hint">
            Say hello, or try: "What does my portfolio look like?"
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`bubble-row ${m.role === "user" ? "right" : "left"}`}>
            <div className={`bubble ${m.role === "user" ? "bubble-user" : "bubble-assistant"}`}>
              {m.content}
            </div>
          </div>
        ))}
        {sending && (
          <div className="bubble-row left">
            <div className="bubble bubble-assistant typing">Analyst is typing…</div>
          </div>
        )}
        {error && <div className="error-banner">{error}</div>}
        <div ref={bottomRef} />
      </div>

      <div className="input-row">
        <textarea
          className="input-box"
          placeholder="Message"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
        />
        <button className="send-button" onClick={handleSend} disabled={sending || !input.trim()}>
          ➤
        </button>
      </div>
    </div>
  );
}
