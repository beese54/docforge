// docforge Console: tiny client. Every state-changing request carries the launch token in a header.
(function () {
  const token = document.querySelector('meta[name="docforge-token"]')?.content || "";

  function toast(message, kind) {
    const el = document.getElementById("toast");
    if (!el) return;
    el.textContent = message;
    el.className = kind || "";
    el.hidden = false;
    clearTimeout(el._t);
    el._t = setTimeout(() => { el.hidden = true; }, 4000);
  }

  async function post(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json", "x-docforge-token": token },
      body: JSON.stringify(body || {}),
      credentials: "same-origin",
    });
    let data = {};
    try { data = await res.json(); } catch (_) { /* empty body */ }
    if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
    return data;
  }

  function collect(el) {
    // data-json maps body keys to input selectors, e.g. {"path": "#repo-path"}.
    const spec = el.dataset.json ? JSON.parse(el.dataset.json) : {};
    const body = el.dataset.body ? JSON.parse(el.dataset.body) : {};
    for (const [key, sel] of Object.entries(spec)) {
      const input = document.querySelector(sel);
      if (!input) continue;
      body[key] = input.type === "checkbox" ? input.checked : input.value;
    }
    return body;
  }

  async function run(el) {
    if (el.dataset.confirm && !window.confirm(el.dataset.confirm)) return;
    const busy = el.tagName === "FORM" ? el.querySelector("button[type=submit]") : el;
    if (busy) busy.disabled = true;
    try {
      const data = await post(el.dataset.action, collect(el));
      if (el.hasAttribute("data-go") && data.go) { window.location.href = data.go; return; }
      toast(data.message || "Done", "ok");
      if (el.hasAttribute("data-reload")) setTimeout(() => window.location.reload(), 400);
    } catch (err) {
      toast(err.message, "bad");
    } finally {
      if (busy) busy.disabled = false;
    }
  }

  document.addEventListener("submit", (e) => {
    const form = e.target.closest("form[data-action]");
    if (!form) return;
    e.preventDefault();
    run(form);
  });
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn || btn.closest("form[data-action]")) return;
    e.preventDefault();
    run(btn);
  });

  // Live log streaming (Server-Sent Events) for agent runs and red-team runs.
  window.docforgeStream = function (url, logEl, onDone) {
    const src = new EventSource(url);
    src.addEventListener("line", (e) => {
      const line = document.createElement("div");
      const msg = JSON.parse(e.data);
      line.className = "ln " + (msg.kind || "");
      line.textContent = msg.text;
      logEl.appendChild(line);
      logEl.scrollTop = logEl.scrollHeight;
    });
    src.addEventListener("done", (e) => {
      src.close();
      if (onDone) onDone(JSON.parse(e.data));
    });
    src.onerror = () => { src.close(); toast("Stream ended", "bad"); };
    return src;
  };
  window.docforgePost = post;
  window.docforgeToast = toast;
})();
