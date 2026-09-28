import { useEffect, useState } from "react";
import {
  adminGetConversationDetail,
  adminGetConversations,
  adminGetUsers,
  adminLogin,
} from "./api.js";

const TOKEN_KEY = "portfolio-analyst:admin-token";

function fmtInr(n) {
  if (n === null || n === undefined) return "—";
  return `₹${(n / 10000000).toFixed(2)} Cr`;
}

function LoginScreen({ onLoggedIn }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const { token } = await adminLogin(password);
      sessionStorage.setItem(TOKEN_KEY, token);
      onLoggedIn(token);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="admin-login">
      <form className="admin-login-card" onSubmit={handleSubmit}>
        <h1>Admin Access</h1>
        <p className="admin-login-sub">Portfolio Analyst — business dashboard</p>
        <input
          type="password"
          placeholder="Admin password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoFocus
        />
        <button type="submit" disabled={loading || !password}>
          {loading ? "Checking…" : "Enter"}
        </button>
        {error && <div className="admin-error">{error}</div>}
      </form>
    </div>
  );
}

function UsersPanel({ token }) {
  const [users, setUsers] = useState([]);

  useEffect(() => {
    adminGetUsers(token).then(setUsers).catch(() => {});
  }, [token]);

  return (
    <table className="admin-table">
      <thead>
        <tr>
          <th>User</th>
          <th>City</th>
          <th>Properties</th>
          <th>Total Value</th>
        </tr>
      </thead>
      <tbody>
        {users.map((u) => (
          <tr key={u.user_id}>
            <td>{u.name} <span className="dim">({u.user_id})</span></td>
            <td>{u.city}</td>
            <td>{u.property_count}</td>
            <td>{fmtInr(u.total_value_inr)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ConversationDetailPanel({ token, conversationId }) {
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    if (!conversationId) return;
    setDetail(null);
    adminGetConversationDetail(token, conversationId).then(setDetail).catch(() => {});
  }, [token, conversationId]);

  if (!conversationId) {
    return <div className="admin-empty">Select a conversation to inspect it.</div>;
  }
  if (!detail) return <div className="admin-empty">Loading…</div>;

  return (
    <div className="transcript">
      {detail.needs_attention && (
        <div className="attention-banner">⚠ Needs attention: {detail.attention_reason}</div>
      )}
      {detail.messages.map((m, i) => (
        <div key={i} className={`transcript-message role-${m.role}`}>
          <div className="transcript-role">{m.role}</div>
          <div className="transcript-content">{m.content}</div>
          {m.tool_calls.length > 0 && (
            <div className="log-block">
              {m.tool_calls.map((tc, j) => (
                <div key={j} className={`log-line ${tc.success ? "" : "log-error"}`}>
                  🔧 <b>{tc.tool_name}</b>({tc.arguments_json}) → {tc.latency_ms}ms
                  {!tc.success && <div className="log-error-detail">Error: {tc.error}</div>}
                </div>
              ))}
            </div>
          )}
          {m.model_calls.length > 0 && (
            <div className="log-block">
              {m.model_calls.map((mc, j) => (
                <div key={j} className="log-line log-model">
                  🧠 {mc.model} — {mc.latency_ms}ms
                  {mc.prompt_tokens != null && ` — ${mc.prompt_tokens}+${mc.completion_tokens} tokens`}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function ConversationsPanel({ token }) {
  const [conversations, setConversations] = useState([]);
  const [onlyAttention, setOnlyAttention] = useState(false);
  const [selectedId, setSelectedId] = useState(null);

  function load() {
    adminGetConversations(token, { needsAttention: onlyAttention || undefined })
      .then(setConversations)
      .catch(() => {});
  }

  useEffect(load, [token, onlyAttention]);

  return (
    <div className="conversations-layout">
      <div className="conversations-list">
        <label className="attention-filter">
          <input
            type="checkbox"
            checked={onlyAttention}
            onChange={(e) => setOnlyAttention(e.target.checked)}
          />
          Needs attention only
        </label>
        {conversations.map((c) => (
          <div
            key={c.id}
            className={`conversation-row ${c.id === selectedId ? "selected" : ""} ${c.needs_attention ? "flagged" : ""}`}
            onClick={() => setSelectedId(c.id)}
          >
            <div className="conversation-row-top">
              <b>#{c.id} — {c.user_name || c.user_id}</b>
              {c.needs_attention && <span className="flag-dot" title={c.attention_reason}>⚠</span>}
            </div>
            <div className="conversation-preview">{c.last_message_preview || "(no messages yet)"}</div>
            <div className="conversation-meta">{c.message_count} messages</div>
          </div>
        ))}
        {conversations.length === 0 && <div className="admin-empty">No conversations found.</div>}
      </div>
      <div className="conversation-detail">
        <ConversationDetailPanel token={token} conversationId={selectedId} />
      </div>
    </div>
  );
}

export default function AdminApp() {
  const [token, setToken] = useState(sessionStorage.getItem(TOKEN_KEY));
  const [tab, setTab] = useState("conversations");

  function handleLogout() {
    sessionStorage.removeItem(TOKEN_KEY);
    setToken(null);
  }

  if (!token) {
    return <LoginScreen onLoggedIn={setToken} />;
  }

  return (
    <div className="admin-shell">
      <div className="admin-topbar">
        <div className="admin-title">Portfolio Analyst — Admin</div>
        <div className="admin-tabs">
          <button className={tab === "conversations" ? "active" : ""} onClick={() => setTab("conversations")}>
            Conversations
          </button>
          <button className={tab === "users" ? "active" : ""} onClick={() => setTab("users")}>
            Users
          </button>
        </div>
        <button className="admin-logout" onClick={handleLogout}>Log out</button>
      </div>
      <div className="admin-body">
        {tab === "conversations" ? <ConversationsPanel token={token} /> : <UsersPanel token={token} />}
      </div>
    </div>
  );
}
