const state = {
  conversationId: Number(localStorage.getItem("jarvisConversationId")) || null,
  sending: false,
};

const elements = {
  form: document.querySelector("#chat-form"),
  input: document.querySelector("#message-input"),
  send: document.querySelector("#send-button"),
  messages: document.querySelector("#messages"),
  welcome: document.querySelector("#welcome"),
  list: document.querySelector("#conversation-list"),
  title: document.querySelector("#conversation-title"),
  sidebar: document.querySelector("#sidebar"),
  backdrop: document.querySelector("#backdrop"),
  statusDot: document.querySelector("#status-dot"),
  statusText: document.querySelector("#status-text"),
};

async function request(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `요청 실패 (${response.status})`);
  }
  return response.status === 204 ? null : response.json();
}

function addMessage(role, content, pending = false) {
  elements.welcome?.remove();
  const row = document.createElement("article");
  row.className = `message ${role}${pending ? " pending" : ""}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = content;
  row.appendChild(bubble);
  elements.messages.appendChild(row);
  elements.messages.scrollTop = elements.messages.scrollHeight;
  return row;
}

async function loadConversations() {
  const items = await request("/conversations");
  elements.list.replaceChildren();
  items.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `conversation-item${item.id === state.conversationId ? " active" : ""}`;
    button.textContent = item.title || `대화 ${item.id}`;
    button.addEventListener("click", () => selectConversation(item));
    elements.list.appendChild(button);
  });
}

async function selectConversation(item) {
  state.conversationId = item.id;
  localStorage.setItem("jarvisConversationId", String(item.id));
  elements.title.textContent = item.title || `대화 ${item.id}`;
  elements.messages.replaceChildren();
  const messages = await request(`/conversations/${item.id}/messages`);
  messages.forEach((message) => addMessage(message.role, message.content));
  closeSidebar();
  await loadConversations();
}

function newConversation() {
  state.conversationId = null;
  localStorage.removeItem("jarvisConversationId");
  elements.title.textContent = "새 대화";
  elements.messages.replaceChildren();
  const intro = document.createElement("div");
  intro.className = "welcome";
  intro.id = "welcome";
  intro.innerHTML = '<div class="welcome-mark">J</div><p class="eyebrow">READY</p><h2>새 대화를 시작합니다.</h2><p>아래 입력창에 편하게 말씀해 주세요.</p>';
  elements.messages.appendChild(intro);
  closeSidebar();
  loadConversations().catch(() => {});
  elements.input.focus();
}

async function sendMessage(message) {
  if (!message || state.sending) return;
  state.sending = true;
  elements.send.disabled = true;
  addMessage("user", message);
  const pending = addMessage("assistant", "생각하고 있습니다…", true);
  try {
    const payload = { message };
    if (state.conversationId) payload.conversation_id = state.conversationId;
    const result = await request("/chat", { method: "POST", body: JSON.stringify(payload) });
    state.conversationId = result.conversation_id;
    localStorage.setItem("jarvisConversationId", String(result.conversation_id));
    pending.querySelector(".bubble").textContent = result.reply;
    pending.classList.remove("pending");
    await loadConversations();
  } catch (error) {
    pending.querySelector(".bubble").textContent = `오류: ${error.message}`;
    pending.classList.remove("pending");
  } finally {
    state.sending = false;
    elements.send.disabled = false;
    elements.input.focus();
  }
}

function closeSidebar() {
  elements.sidebar.classList.remove("open");
  elements.backdrop.classList.remove("open");
}

elements.form.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = elements.input.value.trim();
  if (!message) return;
  elements.input.value = "";
  elements.input.style.height = "auto";
  sendMessage(message);
});
elements.input.addEventListener("input", () => {
  elements.input.style.height = "auto";
  elements.input.style.height = `${Math.min(elements.input.scrollHeight, 150)}px`;
});
elements.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.form.requestSubmit();
  }
});
document.querySelector("#new-chat").addEventListener("click", newConversation);
document.querySelector("#reset-button").addEventListener("click", newConversation);
document.querySelector("#menu-button").addEventListener("click", () => {
  elements.sidebar.classList.add("open");
  elements.backdrop.classList.add("open");
});
elements.backdrop.addEventListener("click", closeSidebar);
document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => sendMessage(button.dataset.prompt));
});

async function initialize() {
  try {
    await request("/ready");
    elements.statusDot.classList.add("online");
    elements.statusText.textContent = "JARVIS 연결됨";
    const conversations = await request("/conversations");
    await loadConversations();
    const active = conversations.find((item) => item.id === state.conversationId);
    if (active) await selectConversation(active);
  } catch (error) {
    elements.statusText.textContent = "서버 연결 필요";
  }
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/static/sw.js");
}

initialize();
