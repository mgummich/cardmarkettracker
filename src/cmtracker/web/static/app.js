// Live-Status in der Kopfzeile; lädt die Seite neu, sobald eine Prüfung fertig ist.
(function () {
  const pill = document.getElementById("status-pill");
  if (!pill) return;
  const text = pill.querySelector(".text");
  let wasBusy = pill.classList.contains("busy");
  const fmt = (iso) => iso ? new Date(iso).toLocaleTimeString("de-DE", {hour: "2-digit", minute: "2-digit"}) : "–";

  async function poll() {
    try {
      const r = await fetch("/api/status", {cache: "no-store"});
      if (!r.ok) return;
      const s = await r.json();
      const run = s.runner;
      if (!run) { pill.className = "status-pill off"; text.textContent = "nur Ansicht"; return; }
      const busy = run.busy;
      pill.className = "status-pill" + (busy ? " busy" : "") + (run.scheduling ? "" : " off");
      text.textContent = busy ? (run.current_task || "Auftrag wartet…")
        : run.scheduling ? "nächste Prüfung " + fmt(run.next_check_at) : "Zeitplan aus";
      const editing = document.querySelector("form[data-dirty-guard]");
      if (wasBusy && !busy && !editing) location.reload();
      wasBusy = busy;
    } catch (e) { /* offline – nächster Versuch */ }
  }
  setInterval(poll, wasBusy ? 2000 : 5000);
  if (wasBusy) poll();
})();

// Felder mit Modus-Auswahl (Standard / egal / Auswahl) ein-/ausblenden
document.querySelectorAll("[data-mode-select]").forEach((sel) => {
  const target = document.getElementById(sel.dataset.modeSelect);
  const update = () => { if (target) target.hidden = sel.value !== "custom"; };
  sel.addEventListener("change", update);
  update();
});

// Sicherheitsabfragen
document.querySelectorAll("form[data-confirm]").forEach((f) => {
  f.addEventListener("submit", (e) => { if (!confirm(f.dataset.confirm)) e.preventDefault(); });
});
