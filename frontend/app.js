const API = "/api";

const state = {
  token: localStorage.getItem("dms_token") || null,
  user: JSON.parse(localStorage.getItem("dms_user") || "null"),
  fields: [],
  documents: [],
  currentDocId: null,
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.add("hidden"), 2800);
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.json);
  }
  const res = await fetch(`${API}${path}`, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}

function setSession(token, user) {
  state.token = token;
  state.user = user;
  localStorage.setItem("dms_token", token);
  localStorage.setItem("dms_user", JSON.stringify(user));
}

function clearSession() {
  state.token = null;
  state.user = null;
  localStorage.removeItem("dms_token");
  localStorage.removeItem("dms_user");
}

function showAuth() {
  $("#view-auth").classList.remove("hidden");
  $("#view-app").classList.add("hidden");
}

function showApp() {
  $("#view-auth").classList.add("hidden");
  $("#view-app").classList.remove("hidden");
  $("#user-chip").textContent = `${state.user.username} · ${state.user.division}`;
  $("#upload-division").textContent = state.user.division;
}

function route() {
  const hash = location.hash || "#/dashboard";
  const [path, param] = hash.replace(/^#\/?/, "").split("/");

  if (!state.token) {
    showAuth();
    return;
  }
  showApp();

  $$(".page").forEach((p) => p.classList.add("hidden"));
  $$(".nav a").forEach((a) => a.classList.toggle("active", a.dataset.nav === path));

  const titles = {
    dashboard: "Documents",
    detail: "Document Details",
    search: "Advanced Search",
    requests: "Access Requests",
    settings: "Admin / Settings",
  };

  if (path === "detail" && param) {
    $("#page-title").textContent = titles.detail;
    $("#page-detail").classList.remove("hidden");
    $("#open-upload").classList.add("hidden");
    loadDetail(param);
    return;
  }

  $("#open-upload").classList.toggle("hidden", path !== "dashboard");
  $("#page-title").textContent = titles[path] || "Documents";

  if (path === "search") {
    $("#page-search").classList.remove("hidden");
  } else if (path === "requests") {
    $("#page-requests").classList.remove("hidden");
    loadRequests();
  } else if (path === "settings") {
    $("#page-settings").classList.remove("hidden");
    loadFields();
  } else {
    $("#page-dashboard").classList.remove("hidden");
    loadDashboard();
  }
}

function metaChips(doc) {
  const chips = Object.entries(doc.metadata || {}).map(
    ([k, v]) => `<span class="chip">${escapeHtml(k)}: ${escapeHtml(String(v))}</span>`
  );
  if (doc.can_download) chips.push(`<span class="chip ok">Downloadable</span>`);
  else if (doc.access_pending) chips.push(`<span class="chip warn">Access pending</span>`);
  else if (!doc.same_division) chips.push(`<span class="chip warn">Request access</span>`);
  return chips.join("");
}

function renderDocCard(doc) {
  return `
    <article class="doc-card" data-id="${doc.id}">
      <h4>${escapeHtml(doc.filename)}</h4>
      <small>${escapeHtml(doc.division || "—")} · ${formatDate(doc.created_at)}</small>
      <div class="meta-chips">${metaChips(doc)}</div>
    </article>
  `;
}

async function loadDashboard() {
  await ensureFields();
  renderFilterControls();
  const params = new URLSearchParams();
  $$("#dashboard-filters select").forEach((sel) => {
    if (sel.value) params.set(sel.name, sel.value);
  });
  const qs = params.toString() ? `?${params}` : "";
  const data = await api(`/documents${qs}`);
  state.documents = data.documents || [];
  const list = $("#documents-list");
  list.innerHTML = state.documents.map(renderDocCard).join("");
  $("#documents-empty").classList.toggle("hidden", state.documents.length > 0);
  list.querySelectorAll(".doc-card").forEach((card) => {
    card.addEventListener("click", () => {
      location.hash = `#/detail/${card.dataset.id}`;
    });
  });
}

function renderFilterControls() {
  const box = $("#dashboard-filters");
  const filterable = state.fields.filter((f) => f.name !== "Division" || true);
  box.innerHTML = filterable
    .map(
      (f) => `
      <label>${escapeHtml(f.name)}
        <select name="${escapeHtml(f.name)}">
          <option value="">All</option>
          ${(f.options || []).map((o) => `<option value="${escapeHtml(o)}">${escapeHtml(o)}</option>`).join("")}
        </select>
      </label>`
    )
    .join("");
  box.querySelectorAll("select").forEach((sel) => {
    sel.addEventListener("change", () => loadDashboard().catch(showError));
  });
}

async function loadDetail(id) {
  state.currentDocId = id;
  const data = await api(`/documents/${id}`);
  const doc = data.document;
  const actions = [];
  if (doc.can_download) {
    actions.push(`<button type="button" class="btn primary" id="download-btn">Download</button>`);
  } else if (doc.access_pending) {
    actions.push(`<button type="button" class="btn ghost" disabled>Access request pending</button>`);
  } else {
    actions.push(`<button type="button" class="btn primary" id="request-btn">Request Access</button>`);
  }

  $("#detail-card").innerHTML = `
    <h3>${escapeHtml(doc.filename)}</h3>
    <p>${escapeHtml(doc.division)} · uploaded ${formatDate(doc.created_at)}</p>
    <div class="meta-chips">${metaChips(doc)}</div>
    <div class="detail-actions">${actions.join("")}</div>
    ${
      doc.ocr_text
        ? `<h4 style="margin:1.2rem 0 0.4rem">OCR / extracted text</h4><pre class="ocr-preview">${escapeHtml(doc.ocr_text)}</pre>`
        : doc.can_download
          ? `<p class="hint">No OCR text was extracted from this file.</p>`
          : ""
    }
  `;

  $("#download-btn")?.addEventListener("click", () => downloadDoc(id));
  $("#request-btn")?.addEventListener("click", async () => {
    try {
      await api("/access/request", { method: "POST", json: { doc_id: id } });
      toast("Access request sent");
      loadDetail(id);
    } catch (e) {
      showError(e);
    }
  });
}

async function downloadDoc(id) {
  const res = await fetch(`${API}/documents/${id}/download`, {
    headers: { Authorization: `Bearer ${state.token}` },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || "Download failed");
  }
  const blob = await res.blob();
  const dispo = res.headers.get("Content-Disposition") || "";
  const match = /filename="?([^"]+)"?/.exec(dispo);
  const name = match?.[1] || "document";
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

async function loadRequests() {
  const data = await api("/access/requests");
  const incoming = $("#incoming-requests");
  const outgoing = $("#outgoing-requests");

  incoming.innerHTML = (data.incoming || [])
    .map(
      (r) => `
      <div class="request-card">
        <strong>${escapeHtml(r.document?.filename || r.doc_id)}</strong>
        <div class="hint">From ${escapeHtml(r.requester?.username || "user")} (${escapeHtml(r.requester_division || "—")}) · ${escapeHtml(r.status)}</div>
        ${
          r.status === "pending"
            ? `<div class="actions">
                <button class="btn ok" data-approve="${r.id}">Approve</button>
                <button class="btn danger" data-reject="${r.id}">Reject</button>
              </div>`
            : ""
        }
      </div>`
    )
    .join("") || `<p class="empty">No incoming requests.</p>`;

  outgoing.innerHTML = (data.outgoing || [])
    .map(
      (r) => `
      <div class="request-card">
        <strong>${escapeHtml(r.document?.filename || r.doc_id)}</strong>
        <div class="hint">Status: ${escapeHtml(r.status)} · ${formatDate(r.created_at)}</div>
      </div>`
    )
    .join("") || `<p class="empty">You have not requested access yet.</p>`;

  incoming.querySelectorAll("[data-approve]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await api("/access/approve", { method: "POST", json: { request_id: btn.dataset.approve } });
        toast("Approved");
        loadRequests();
      } catch (e) {
        showError(e);
      }
    });
  });
  incoming.querySelectorAll("[data-reject]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await api("/access/reject", { method: "POST", json: { request_id: btn.dataset.reject } });
        toast("Rejected");
        loadRequests();
      } catch (e) {
        showError(e);
      }
    });
  });
}

async function ensureFields() {
  if (state.fields.length) return state.fields;
  const data = await api("/metadata/fields");
  state.fields = data.fields || [];
  return state.fields;
}

async function loadFields() {
  const data = await api("/metadata/fields");
  state.fields = data.fields || [];
  const list = $("#fields-list");
  list.innerHTML = state.fields
    .map(
      (f) => `
      <div class="field-card" data-id="${f.id}">
        <div class="head">
          <strong>${escapeHtml(f.name)}</strong>
          ${f.name !== "Division" ? `<button type="button" class="btn ghost" data-delete="${f.id}">Delete</button>` : ""}
        </div>
        <label>Options
          <input data-options="${f.id}" value="${escapeHtml((f.options || []).join(", "))}" />
        </label>
        <button type="button" class="btn primary" data-save="${f.id}">Save</button>
      </div>`
    )
    .join("");

  list.querySelectorAll("[data-save]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.save;
      const raw = list.querySelector(`[data-options="${id}"]`).value;
      const options = raw.split(",").map((s) => s.trim()).filter(Boolean);
      try {
        await api(`/metadata/fields/${id}`, { method: "PUT", json: { options } });
        toast("Field updated");
        state.fields = [];
        loadFields();
      } catch (e) {
        showError(e);
      }
    });
  });
  list.querySelectorAll("[data-delete]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!confirm("Delete this metadata field?")) return;
      try {
        await api(`/metadata/fields/${btn.dataset.delete}`, { method: "DELETE" });
        toast("Field deleted");
        state.fields = [];
        loadFields();
      } catch (e) {
        showError(e);
      }
    });
  });
}

function buildUploadFields() {
  const box = $("#upload-metadata-fields");
  const fields = state.fields.filter((f) => f.name !== "Division");
  box.innerHTML = fields
    .map(
      (f) => `
      <label>${escapeHtml(f.name)}
        <select name="meta_${escapeHtml(f.name)}">
          <option value="">—</option>
          ${(f.options || []).map((o) => `<option value="${escapeHtml(o)}">${escapeHtml(o)}</option>`).join("")}
        </select>
      </label>`
    )
    .join("");
}

async function loadDivisions() {
  const data = await api("/divisions");
  const sel = $("#signup-division");
  sel.innerHTML = (data.divisions || [])
    .map((d) => `<option value="${escapeHtml(d)}">${escapeHtml(d)}</option>`)
    .join("");
}

function escapeHtml(str) {
  return String(str ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function showError(err) {
  console.error(err);
  toast(err.message || String(err));
}

/* ---------- Event wiring ---------- */
$$("[data-auth-tab]").forEach((tab) => {
  tab.addEventListener("click", () => {
    $$("[data-auth-tab]").forEach((t) => t.classList.toggle("active", t === tab));
    const mode = tab.dataset.authTab;
    $("#login-form").classList.toggle("hidden", mode !== "login");
    $("#signup-form").classList.toggle("hidden", mode !== "signup");
    $("#auth-error").hidden = true;
  });
});

$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    const data = await api("/auth/login", {
      method: "POST",
      json: { username: fd.get("username"), password: fd.get("password") },
    });
    setSession(data.token, data.user);
    location.hash = "#/dashboard";
    route();
  } catch (err) {
    $("#auth-error").hidden = false;
    $("#auth-error").textContent = err.message;
  }
});

$("#signup-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  try {
    const data = await api("/auth/register", {
      method: "POST",
      json: {
        username: fd.get("username"),
        password: fd.get("password"),
        division: fd.get("division"),
      },
    });
    setSession(data.token, data.user);
    location.hash = "#/dashboard";
    route();
  } catch (err) {
    $("#auth-error").hidden = false;
    $("#auth-error").textContent = err.message;
  }
});

$("#logout-btn").addEventListener("click", () => {
  clearSession();
  location.hash = "#/login";
  route();
});

$("#open-upload").addEventListener("click", async () => {
  try {
    await ensureFields();
    buildUploadFields();
    $("#upload-error").hidden = true;
    $("#upload-dialog").showModal();
  } catch (e) {
    showError(e);
  }
});

$("#cancel-upload").addEventListener("click", () => $("#upload-dialog").close());

$("#upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fileInput = e.target.querySelector('input[type="file"]');
  if (!fileInput.files?.[0]) return;

  const metadata = { Division: state.user.division };
  e.target.querySelectorAll("select[name^='meta_']").forEach((sel) => {
    const key = sel.name.replace(/^meta_/, "");
    if (sel.value) metadata[key] = sel.value;
  });

  const body = new FormData();
  body.append("file", fileInput.files[0]);
  body.append("metadata", JSON.stringify(metadata));

  try {
    const res = await fetch(`${API}/documents/upload`, {
      method: "POST",
      headers: { Authorization: `Bearer ${state.token}` },
      body,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Upload failed");
    $("#upload-dialog").close();
    e.target.reset();
    toast("Document uploaded");
    loadDashboard();
  } catch (err) {
    $("#upload-error").hidden = false;
    $("#upload-error").textContent = err.message;
  }
});

$("#search-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = new FormData(e.target).get("q");
  try {
    const data = await api(`/search?q=${encodeURIComponent(q)}`);
    const list = $("#search-results");
    list.innerHTML = (data.results || []).map(renderDocCard).join("");
    $("#search-empty").classList.toggle("hidden", (data.results || []).length > 0);
    list.querySelectorAll(".doc-card").forEach((card) => {
      card.addEventListener("click", () => {
        location.hash = `#/detail/${card.dataset.id}`;
      });
    });
  } catch (err) {
    showError(err);
  }
});

$("#field-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const options = String(fd.get("options") || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  try {
    await api("/metadata/fields", {
      method: "POST",
      json: { name: fd.get("name"), options },
    });
    e.target.reset();
    state.fields = [];
    toast("Field added");
    loadFields();
  } catch (err) {
    showError(err);
  }
});

$("#back-to-docs").addEventListener("click", () => {
  location.hash = "#/dashboard";
});

window.addEventListener("hashchange", () => {
  route();
});

(async function init() {
  try {
    await loadDivisions();
  } catch {
    // Mongo may not be up yet; auth page still loads
  }

  if (state.token) {
    try {
      const me = await api("/auth/me");
      state.user = me.user;
      localStorage.setItem("dms_user", JSON.stringify(me.user));
    } catch {
      clearSession();
    }
  }
  route();
})();
