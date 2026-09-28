const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function sendChatMessage(userId, conversationId, message) {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, conversation_id: conversationId, message }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Server error (${res.status}): ${detail}`);
  }
  return res.json(); // { conversation_id, reply }
}

export async function fetchHistory(userId, conversationId) {
  const res = await fetch(
    `${API_BASE}/conversations/${conversationId}/messages?user_id=${encodeURIComponent(userId)}`
  );
  if (!res.ok) return []; // conversation may not exist yet - that's fine, start fresh
  return res.json(); // [{ role, content, created_at }]
}
export async function adminLogin(password) {
  const res = await fetch(`${API_BASE}/admin/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Login failed (${res.status}): ${detail}`);
  }
  return res.json(); // { token }
}

export async function adminGetUsers(token) {
  const res = await fetch(`${API_BASE}/admin/users`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Failed to fetch users");
  return res.json();
}
export async function adminGetConversations(token, params = {}) {
  const query = new URLSearchParams(params).toString();
  const res = await fetch(`${API_BASE}/admin/conversations?${query}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Failed to fetch conversations");
  return res.json();
}

export async function adminGetConversationDetail(token, conversationId) {
  const res = await fetch(`${API_BASE}/admin/conversations/${conversationId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Failed to fetch conversation detail");
  return res.json();
}