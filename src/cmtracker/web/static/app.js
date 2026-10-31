// Live status in the header; reloads the page once a check has finished.
(function () {
  const pill = document.getElementById("status-pill");
  if (!pill) return;
  const text = pill.querySelector(".text");
  const t = pill.dataset;
  const locale = t.lang === "de" ? "de-DE" : "en-GB";
  let wasBusy = pill.classList.contains("busy");
  const fmt = (iso) => iso ? new Date(iso).toLocaleTimeString(locale, {hour: "2-digit", minute: "2-digit"}) : "–";

  async function poll() {
    try {
      const r = await fetch("/api/status", {cache: "no-store"});
      if (!r.ok) return;
      const s = await r.json();
      const run = s.runner;
      if (!run) { pill.className = "status-pill off"; text.textContent = t.tView || ""; return; }
      const busy = run.busy;
      pill.className = "status-pill" + (busy ? " busy" : "") + (run.scheduling ? "" : " off");
      text.textContent = busy ? (run.current_task_label || t.tQueued)
        : run.scheduling ? (t.tNext || "{time}").replace("{time}", fmt(run.next_check_at)) : t.tOff;
      const editing = document.querySelector("form[data-dirty-guard]");
      if (wasBusy && !busy && !editing) location.reload();
      wasBusy = busy;
    } catch (e) { /* offline – try again next time */ }
  }
  setInterval(poll, wasBusy ? 2000 : 5000);
  if (wasBusy) poll();
})();

// Fields with a mode selector (default / any / selection): show or hide the value
document.querySelectorAll("[data-mode-select]").forEach((sel) => {
  const target = document.getElementById(sel.dataset.modeSelect);
  const update = () => { if (target) target.hidden = sel.value !== "custom"; };
  sel.addEventListener("change", update);
  update();
});

// Confirmation dialogs
document.querySelectorAll("form[data-confirm]").forEach((f) => {
  f.addEventListener("submit", (e) => { if (!confirm(f.dataset.confirm)) e.preventDefault(); });
});
