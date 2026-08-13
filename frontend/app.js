const API = "http://localhost:8000/api";

const state = {
  view: "home",           
  notebooks: [],
  currentNotebookId: null,
  currentNotebook: null,  
  messages: [],
  notes: [],
  activeMobilePane: "sources",
  pendingDangerAction: null,
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function formatDate(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

function fileIcon(filetype) {
  const map = { ".pdf": "PDF", ".txt": "TXT", ".csv": "CSV", ".ppt": "PPT", ".pptx": "PPT", ".docx": "DOC" };
  return map[filetype] || "?";
}

let loaderDepth = 0;

function showGlobalLoader(text, hint = "") {
  loaderDepth += 1;
  $("#global-loader-text").textContent = text;
  $("#global-loader-hint").textContent = hint;
  $("#global-loader").hidden = false;
  $("#btn-back-home").disabled = true;
  $("#btn-delete-notebook").disabled = true;
}

function hideGlobalLoader() {
  loaderDepth = Math.max(0, loaderDepth - 1);
  if (loaderDepth > 0) return;
  $("#global-loader").hidden = true;
  $("#btn-back-home").disabled = false;
  $("#btn-delete-notebook").disabled = false;
}

function showToast(message, isError = false) {
  const el = $("#toast");
  el.textContent = message;
  el.style.borderColor = isError ? "var(--ember)" : "var(--line)";
  el.hidden = false;
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => { el.hidden = true; }, 3200);
}

async function api(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: {
  ...(options.body && !(options.body instanceof FormData)
    ? { "Content-Type": "application/json" }
    : {}),
  ...(options.headers || {})
    },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {}
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

const postJSON = (path, body) => api(path, { method: "POST", body: JSON.stringify(body) });
const patchJSON = (path, body) => api(path, { method: "PATCH", body: JSON.stringify(body) });
const del = (path) => api(path, { method: "DELETE" });

function showView(view) {
  state.view = view;
  $("#view-home").hidden = view !== "home";
  $("#view-notebook").hidden = view !== "notebook";
}

async function loadHome() {
  showView("home");
  try {
    state.notebooks = await api("/notebooks");
  } catch (e) {
    showToast(`Couldn't load notebooks: ${e.message}`, true);
    state.notebooks = [];
  }
  renderHome();
}

function renderHome() {
  const grid = $("#notebook-grid");
  grid.querySelectorAll(".notebook-card:not(.notebook-card--new)").forEach((n) => n.remove());

  $("#home-empty-hint").hidden = state.notebooks.length > 0;

  for (const nb of state.notebooks) {
    const card = document.createElement("button");
    card.className = "notebook-card";
    const count = nb.source_count ?? 0;
    card.innerHTML = `
      <p class="notebook-card__name">${escapeHtml(nb.name)}</p>
      <div class="notebook-card__meta">
        <span>${count} source${count === 1 ? "" : "s"}</span>
        <span>${formatDate(nb.created_at)}</span>
      </div>`;
    card.addEventListener("click", () => openNotebook(nb.id));
    grid.appendChild(card);
  }
}

async function openNotebook(notebookId) {
  state.currentNotebookId = notebookId;
  showView("notebook");
  resetNotebookUI();

  try {
    const [notebook, messages, notes] = await Promise.all([
      api(`/notebooks/${notebookId}`),
      api(`/notebooks/${notebookId}/chat`),
      api(`/notebooks/${notebookId}/notes`),
    ]);
    state.currentNotebook = notebook;
    state.messages = messages;
    state.notes = notes;
    renderNotebook();
  } catch (e) {
    showToast(`Couldn't open notebook: ${e.message}`, true);
    loadHome();
  }
}

function resetNotebookUI() {
  $("#chat-log").innerHTML = "";
  $("#source-list").innerHTML = "";
  $("#note-list").innerHTML = "";
  $("#chat-loading").hidden = true;
  $("#composer-input").value = "";
}

function renderNotebook() {
  const nb = state.currentNotebook;
  $("#notebook-title").textContent = nb.name;
  renderSources();
  renderGuide();
  renderChat();
  renderNotes();
}

function renderSources() {
  const list = $("#source-list");
  list.innerHTML = "";
  const sources = state.currentNotebook.sources || [];
  $("#sources-empty-hint").hidden = sources.length > 0;

  for (const src of sources) {
    const li = document.createElement("li");
    li.className = "source-item";
    const statusClass = src.status === "failed" ? "is-failed" : src.status === "processing" ? "is-processing" : "";
    const statusText = src.status === "failed" ? (src.error || "Failed") :
                        src.status === "ready" ? `${src.num_chunks} chunks` : "Processing…";
    li.innerHTML = `
      <span class="source-item__icon">${fileIcon(src.filetype)}</span>
      <span class="source-item__body">
        <div class="source-item__name" title="${escapeHtml(src.filename)}">${escapeHtml(src.filename)}</div>
        <div class="source-item__status ${statusClass}">${escapeHtml(statusText)}</div>
      </span>
      <button class="source-item__remove" title="Remove source" aria-label="Remove source">✕</button>`;
    li.querySelector(".source-item__remove").addEventListener("click", () => confirmDeleteSource(src));
    list.appendChild(li);
  }
}

function confirmDeleteSource(src) {
  openConfirmModal({
    title: "Remove this source?",
    body: `"${src.filename}" and everything derived from it will be removed from this notebook.`,
    onConfirm: async () => {
      try {
        await del(`/notebooks/${state.currentNotebookId}/sources/${src.id}`);
        state.currentNotebook.sources = state.currentNotebook.sources.filter((s) => s.id !== src.id);
        renderSources();
        showToast("Source removed.");
      } catch (e) {
        showToast(`Couldn't remove source: ${e.message}`, true);
      }
    },
  });
}

async function uploadFiles(fileList) {
  const files = Array.from(fileList);
  if (!files.length) return;
  const tempSources = files.map((f) => ({
    id: `temp-${f.name}-${Date.now()}`,
    filename: f.name,
    filetype: `.${f.name.split(".").pop().toLowerCase()}`,
    status: "processing",
    num_chunks: 0,
  }));
  state.currentNotebook.sources.push(...tempSources);
  renderSources();

  const form = new FormData();
  files.forEach((f) => form.append("files", f));

  try {
    await api(`/notebooks/${state.currentNotebookId}/sources`, { method: "POST", body: form });
    const refreshed = await api(`/notebooks/${state.currentNotebookId}`);
    state.currentNotebook = refreshed;
    renderSources();
    renderGuide();
    showToast(files.length > 1 ? `${files.length} sources added.` : "Source added.");
  } catch (e) {
    state.currentNotebook.sources = state.currentNotebook.sources.filter(
      (s) => !tempSources.includes(s)
    );
    renderSources();
    showToast(`Upload failed: ${e.message}`, true);
  }
}

function renderGuide() {
  const nb = state.currentNotebook;
  const guide = $("#notebook-guide");
  const hasGuide = Boolean(nb.overview) || (nb.suggested_questions || []).length > 0;
  guide.hidden = !hasGuide || state.messages.length > 0;

  $("#notebook-overview").textContent = nb.overview || "";

  const box = $("#suggested-questions");
  box.innerHTML = "";
  for (const q of nb.suggested_questions || []) {
    const btn = document.createElement("button");
    btn.className = "suggested-question";
    btn.textContent = q;
    btn.addEventListener("click", () => {
      $("#composer-input").value = q;
      submitChat();
    });
    box.appendChild(btn);
  }
}

function renderMessageText(container, text, citations) {
  const parts = String(text).split(/(\[Source\s+\d+\])/gi);
  container.innerHTML = "";
  for (const part of parts) {
    const match = part.match(/\[Source\s+(\d+)\]/i);
    if (match) {
      const idx = parseInt(match[1], 10);
      const citation = citations?.find((c) => c.index === idx);
      const btn = document.createElement("button");
      btn.className = "footnote-mark";
      btn.type = "button";
      btn.textContent = idx;
      btn.addEventListener("click", (evt) => showFootnotePopover(evt, citation));
      container.appendChild(btn);
    } else if (part) {
      container.appendChild(document.createTextNode(part));
    }
  }
}

function renderChat() {
  const log = $("#chat-log");
  log.innerHTML = "";
  $("#chat-empty").hidden = state.messages.length > 0 || (state.currentNotebook.sources || []).length === 0;

  for (const msg of state.messages) {
    log.appendChild(buildMessageEl(msg));
  }
  renderGuide();
  scrollChatToBottom();
}

function buildMessageEl(msg) {
  const wrap = document.createElement("div");
  wrap.className = `msg msg--${msg.role === "user" ? "user" : "assistant"}`;

  const bubble = document.createElement("div");
  bubble.className = "msg__bubble";

  const textEl = document.createElement("p");
  textEl.className = "msg__text";
  bubble.appendChild(textEl);
  wrap.appendChild(bubble);

  if (msg.role === "user") {
    textEl.textContent = msg.content;
  } else {
    renderMessageText(textEl, msg.content, msg.citations);

    const actions = document.createElement("div");
    actions.className = "msg__actions";
    const saveBtn = document.createElement("button");
    saveBtn.className = "msg__action";
    saveBtn.type = "button";
    saveBtn.textContent = "Save to note";
    saveBtn.addEventListener("click", () => createNoteFromMessage(msg));
    actions.appendChild(saveBtn);
    wrap.appendChild(actions);
  }

  return wrap;
}

function scrollChatToBottom() {
  const scroll = $("#chat-scroll");
  scroll.scrollTop = scroll.scrollHeight;
}

async function submitChat() {
  const input = $("#composer-input");
  const message = input.value.trim();
  if (!message) return;

  if (!(state.currentNotebook.sources || []).some((s) => s.status === "ready")) {
    showToast("Add at least one source before chatting.", true);
    return;
  }

  input.value = "";
  autosizeComposer();
  $("#composer-send").disabled = true;

  const userMsg = { role: "user", content: message, citations: [] };
  state.messages.push(userMsg);
  $("#chat-empty").hidden = true;
  $("#notebook-guide").hidden = true;
  $("#chat-log").appendChild(buildMessageEl(userMsg));
  $("#chat-loading").hidden = false;
  scrollChatToBottom();

  try {
    const res = await postJSON(`/notebooks/${state.currentNotebookId}/chat`, { message });
    const assistantMsg = { role: "assistant", content: res.answer, citations: res.citations };
    state.messages.push(assistantMsg);
    $("#chat-loading").hidden = true;
    $("#chat-log").appendChild(buildMessageEl(assistantMsg));
    scrollChatToBottom();
  } catch (e) {
    $("#chat-loading").hidden = true;
    state.messages.pop();
    $("#chat-log").lastElementChild?.remove();
    showToast(`Couldn't get an answer: ${e.message}`, true);
    input.value = message;
  } finally {
    $("#composer-send").disabled = false;
  }
}

function autosizeComposer() {
  const el = $("#composer-input");
  el.style.height = "auto";
  el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
}

function showFootnotePopover(evt, citation) {
  const pop = $("#footnote-popover");
  if (!citation) {
    pop.hidden = true;
    return;
  }
  $("#footnote-popover-marker").textContent = `Source ${citation.index}`;
  $("#footnote-popover-filename").textContent = citation.filename;
  $("#footnote-popover-snippet").textContent = citation.snippet;

  pop.hidden = false;
  const rect = evt.target.getBoundingClientRect();
  const popRect = pop.getBoundingClientRect();
  let left = rect.left;
  let top = rect.bottom + 8;
  if (left + popRect.width > window.innerWidth - 16) left = window.innerWidth - popRect.width - 16;
  if (top + popRect.height > window.innerHeight - 16) top = rect.top - popRect.height - 8;
  pop.style.left = `${Math.max(16, left)}px`;
  pop.style.top = `${Math.max(16, top)}px`;
}

document.addEventListener("click", (evt) => {
  const pop = $("#footnote-popover");
  if (pop.hidden) return;
  if (!pop.contains(evt.target) && !evt.target.classList.contains("footnote-mark")) {
    pop.hidden = true;
  }
});

function renderNotes() {
  const list = $("#note-list");
  list.innerHTML = "";
  $("#notes-empty-hint").hidden = state.notes.length > 0;

  for (const note of state.notes) {
    const li = document.createElement("li");
    li.className = "note-card";
    li.innerHTML = `
      <button class="note-card__remove" title="Delete note" aria-label="Delete note">✕</button>
      <p class="note-card__title">${escapeHtml(note.title)}</p>
      <p class="note-card__content">${escapeHtml(note.content)}</p>`;
    li.querySelector(".note-card__remove").addEventListener("click", () => confirmDeleteNote(note));
    list.appendChild(li);
  }
}

function confirmDeleteNote(note) {
  openConfirmModal({
    title: "Delete this note?",
    body: `"${note.title}" will be permanently removed.`,
    onConfirm: async () => {
      try {
        await del(`/notebooks/${state.currentNotebookId}/notes/${note.id}`);
        state.notes = state.notes.filter((n) => n.id !== note.id);
        renderNotes();
      } catch (e) {
        showToast(`Couldn't delete note: ${e.message}`, true);
      }
    },
  });
}

async function createNoteFromMessage(msg) {
  const title = msg.content.slice(0, 60).split("\n")[0] || "Saved answer";
  try {
    const note = await postJSON(`/notebooks/${state.currentNotebookId}/notes`, {
      title,
      content: msg.content,
    });
    state.notes.push(note);
    renderNotes();
    showToast("Saved to notes.");
  } catch (e) {
    showToast(`Couldn't save note: ${e.message}`, true);
  }
}

function openModal(id) {
  $("#modal-backdrop").hidden = false;
  $$(".modal").forEach((m) => (m.hidden = m.id !== id));
}

function closeModals() {
  $("#modal-backdrop").hidden = true;
  state.pendingDangerAction = null;
}

function openConfirmModal({ title, body, onConfirm }) {
  $("#confirm-title").textContent = title;
  $("#confirm-body").textContent = body;
  state.pendingDangerAction = onConfirm;
  openModal("modal-confirm");
}

$("#modal-backdrop").addEventListener("click", (e) => {
  if (e.target === e.currentTarget) closeModals();
});
$$("[data-close-modal]").forEach((btn) => btn.addEventListener("click", closeModals));

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeModals();
});


$("#btn-new-notebook").addEventListener("click", () => {
  $("#new-notebook-name").value = "";
  openModal("modal-new-notebook");
  setTimeout(() => $("#new-notebook-name").focus(), 30);
});

$("#confirm-new-notebook").addEventListener("click", createNotebook);
$("#new-notebook-name").addEventListener("keydown", (e) => {
  if (e.key === "Enter") createNotebook();
});

async function createNotebook() {
  const name = $("#new-notebook-name").value.trim() || "Untitled notebook";
  try {
    const nb = await postJSON("/notebooks", { name });
    closeModals();
    await openNotebook(nb.id);
  } catch (e) {
    showToast(`Couldn't create notebook: ${e.message}`, true);
  }
}

$("#btn-back-home").addEventListener("click", loadHome);

$("#notebook-title").addEventListener("click", () => {
  const titleEl = $("#notebook-title");
  const input = $("#notebook-title-input");
  input.value = titleEl.textContent;
  titleEl.hidden = true;
  input.hidden = false;
  input.focus();
  input.select();
});

async function commitRename() {
  const titleEl = $("#notebook-title");
  const input = $("#notebook-title-input");
  const name = input.value.trim() || state.currentNotebook.name;
  input.hidden = true;
  titleEl.hidden = false;
  if (name === state.currentNotebook.name) return;
  titleEl.textContent = name;
  try {
    await patchJSON(`/notebooks/${state.currentNotebookId}`, { name });
    state.currentNotebook.name = name;
    const cached = state.notebooks.find((n) => n.id === state.currentNotebookId);
    if (cached) cached.name = name;
  } catch (e) {
    showToast(`Couldn't rename notebook: ${e.message}`, true);
  }
}

$("#notebook-title-input").addEventListener("blur", commitRename);
$("#notebook-title-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") $("#notebook-title-input").blur();
});

$("#btn-delete-notebook").addEventListener("click", () => {
  openConfirmModal({
    title: "Delete this notebook?",
    body: `"${state.currentNotebook.name}" and all its sources, chat history, and notes will be permanently deleted.`,
    onConfirm: async () => {
      try {
        await del(`/notebooks/${state.currentNotebookId}`);
        showToast("Notebook deleted.");
        loadHome();
      } catch (e) {
        showToast(`Couldn't delete notebook: ${e.message}`, true);
      }
    },
  });
});

$("#confirm-danger-action").addEventListener("click", async () => {
  const action = state.pendingDangerAction;
  closeModals();
  if (action) await action();
});


$("#btn-add-source").addEventListener("click", () => $("#file-input").click());
$("#file-input").addEventListener("change", (e) => {
  uploadFiles(e.target.files);
  e.target.value = "";
});

const dropzone = $("#dropzone");
["dragenter", "dragover"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("is-dragover");
  })
);
["dragleave", "drop"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("is-dragover");
  })
);
dropzone.addEventListener("drop", (e) => uploadFiles(e.dataTransfer.files));

$("#btn-add-note").addEventListener("click", () => {
  $("#new-note-title").value = "";
  $("#new-note-content").value = "";
  openModal("modal-new-note");
  setTimeout(() => $("#new-note-title").focus(), 30);
});

$("#confirm-new-note").addEventListener("click", async () => {
  const title = $("#new-note-title").value.trim() || "Untitled note";
  const content = $("#new-note-content").value.trim();
  if (!content) {
    showToast("Write something before saving.", true);
    return;
  }
  try {
    const note = await postJSON(`/notebooks/${state.currentNotebookId}/notes`, { title, content });
    state.notes.push(note);
    renderNotes();
    closeModals();
  } catch (e) {
    showToast(`Couldn't save note: ${e.message}`, true);
  }
});

$("#composer").addEventListener("submit", (e) => {
  e.preventDefault();
  submitChat();
});

$("#composer-input").addEventListener("input", autosizeComposer);
$("#composer-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    submitChat();
  }
});


$$(".tab-switch__btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const pane = btn.dataset.pane;
    state.activeMobilePane = pane;
    $$(".tab-switch__btn").forEach((b) => b.classList.toggle("is-active", b === btn));
    $$(".pane").forEach((p) => p.classList.toggle("is-active-mobile", p.dataset.pane === pane));
  });
});


loadHome();