/**
 * Contract Intelligence — frontend controller
 *
 * Owns the intake → workbench transition, talks to POST /api/analyze
 * when a backend base URL is configured, and falls back to the
 * bundled demo dataset (window.DEMO_ANALYSIS) otherwise. Renders the
 * clause index, analysis feed, risk dial, and negotiation rail from
 * whatever analysis object it's given, regardless of source.
 */

(function () {
  "use strict";

  const STORAGE_KEY = "contract-intel-settings";

  const state = {
    apiBase: "",
    useDemo: true,
    analysis: null,
  };

  // ---------------------------------------------------------------
  // DOM refs
  // ---------------------------------------------------------------

  const el = {
    intake: document.getElementById("intake"),
    workbench: document.getElementById("workbench"),
    modeFlag: document.getElementById("mode-flag"),

    dropzone: document.getElementById("dropzone"),
    fileInput: document.getElementById("file-input"),
    btnTryDemo: document.getElementById("btn-try-demo"),
    intakeError: document.getElementById("intake-error"),

    btnNewUpload: document.getElementById("btn-new-upload"),
    btnReanalyze: document.getElementById("btn-reanalyze"),

    wbFilename: document.getElementById("wb-filename"),
    wbMeta: document.getElementById("wb-meta"),

    clauseIndex: document.getElementById("clause-index"),
    feedList: document.getElementById("feed-list"),

    riskDialFill: document.getElementById("risk-dial-fill"),
    riskScore: document.getElementById("risk-score"),
    riskLabel: document.getElementById("risk-label"),
    riskNote: document.getElementById("risk-note"),

    negotiationList: document.getElementById("negotiation-list"),

    btnSettings: document.getElementById("btn-settings"),
    btnCloseSettings: document.getElementById("btn-close-settings"),
    settingsPanel: document.getElementById("settings-panel"),
    apiBaseInput: document.getElementById("api-base-input"),
    demoToggle: document.getElementById("demo-toggle"),
    btnSaveSettings: document.getElementById("btn-save-settings"),
  };

  const RISK_DIAL_CIRCUMFERENCE = 251.3; // matches the path's stroke-dasharray in the markup
  const RISK_MAX_SCORE = 24; // 8 required terms × weight 3 (High)

  // ---------------------------------------------------------------
  // Settings persistence
  // ---------------------------------------------------------------

  function loadSettings() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const saved = JSON.parse(raw);
      if (typeof saved.apiBase === "string") state.apiBase = saved.apiBase;
      if (typeof saved.useDemo === "boolean") state.useDemo = saved.useDemo;
    } catch (err) {
      // Corrupt or inaccessible storage — ignore and keep defaults.
    }
  }

  function saveSettings() {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ apiBase: state.apiBase, useDemo: state.useDemo })
      );
    } catch (err) {
      // Storage unavailable (private browsing, etc.) — settings just won't persist.
    }
  }

  function syncSettingsUI() {
    el.apiBaseInput.value = state.apiBase;
    el.demoToggle.checked = state.useDemo;
    el.modeFlag.textContent = state.useDemo
      ? "Demo data"
      : state.apiBase
      ? "Live backend"
      : "No backend set";
  }

  // ---------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------

  function riskClass(risk) {
    const r = (risk || "").toLowerCase();
    if (r === "high") return "high";
    if (r === "medium") return "medium";
    return "low";
  }

  function slugify(text) {
    return String(text)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/(^-|-$)/g, "");
  }

  function showError(message) {
    el.intakeError.textContent = message;
    el.intakeError.hidden = !message;
  }

  // ---------------------------------------------------------------
  // Intake ↔ workbench transition
  // ---------------------------------------------------------------

  function showIntake() {
    el.workbench.hidden = true;
    el.intake.hidden = false;
    showError("");
    el.fileInput.value = "";
  }

  function showWorkbench(analysis, filename) {
    state.analysis = analysis;
    el.intake.hidden = true;
    el.workbench.hidden = false;

    el.wbFilename.textContent = filename || analysis.filename || "Untitled contract";
    const clauseCount = (analysis.clauses || []).length;
    const requiredCount = (analysis.compliance || []).length;
    el.wbMeta.textContent = `${clauseCount} clause${clauseCount === 1 ? "" : "s"} detected · ${requiredCount} required term${requiredCount === 1 ? "" : "s"} checked`;

    renderClauseIndex(analysis.compliance || []);
    renderFeed(analysis.compliance || []);
    renderRiskDial(analysis.risk || {});
    renderNegotiation(analysis.negotiation || []);
  }

  // ---------------------------------------------------------------
  // Rendering
  // ---------------------------------------------------------------

  function renderClauseIndex(compliance) {
    el.clauseIndex.innerHTML = "";
    compliance.forEach((item, i) => {
      const id = `clause-${slugify(item.clause)}-${i}`;
      const li = document.createElement("li");

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "clause-index-btn";
      btn.dataset.target = id;
      btn.innerHTML = `
        <span class="clause-dot ${riskClass(item.risk)}" aria-hidden="true"></span>
        <span class="clause-name">${item.clause}</span>
      `;
      btn.addEventListener("click", () => focusClause(id, btn));

      li.appendChild(btn);
      el.clauseIndex.appendChild(li);
    });
  }

  function focusClause(id, activeBtn) {
    document
      .querySelectorAll(".clause-index-btn")
      .forEach((b) => b.classList.toggle("active", b === activeBtn));

    const card = document.getElementById(id);
    if (card) card.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderFeed(compliance) {
    el.feedList.innerHTML = "";
    compliance.forEach((item, i) => {
      const id = `clause-${slugify(item.clause)}-${i}`;
      const card = document.createElement("article");
      card.className = "feed-card";
      card.id = id;

      const excerptRow = item.text
        ? `<div>
             <p class="feed-field-label">Excerpt</p>
             <p class="feed-field-value quote">“${item.text}”</p>
           </div>`
        : "";

      card.innerHTML = `
        <div class="feed-card-head">
          <h3 class="feed-card-title">${item.clause}</h3>
          <span class="status-badge ${riskClass(item.risk)}">${item.status} · ${item.risk}</span>
        </div>
        <p class="feed-card-explanation">${item.explanation}</p>
        <div class="feed-card-grid">
          <div>
            <p class="feed-field-label">Requirement</p>
            <p class="feed-field-value">${item.requirement}</p>
          </div>
          ${excerptRow}
        </div>
      `;

      el.feedList.appendChild(card);
    });
  }

  function renderRiskDial(risk) {
    const score = typeof risk.risk_score === "number" ? risk.risk_score : 0;
    const label = risk.overall_risk || "—";
    const cls = riskClass(label);
    const colorVar = cls === "high" ? "var(--risk-high)" : cls === "medium" ? "var(--risk-medium)" : "var(--risk-low)";

    const fraction = Math.max(0, Math.min(1, score / RISK_MAX_SCORE));
    const offset = RISK_DIAL_CIRCUMFERENCE * (1 - fraction);

    el.riskDialFill.style.stroke = colorVar;
    // Force a reflow so the transition always animates from the previous value.
    el.riskDialFill.getBoundingClientRect();
    el.riskDialFill.setAttribute("stroke-dashoffset", String(offset));

    el.riskScore.textContent = String(score);
    el.riskLabel.textContent = label;
    el.riskLabel.style.color = colorVar;
    el.riskNote.textContent = `Score reflects weighted findings across all ${state.analysis?.compliance?.length ?? ""} required terms.`;
  }

  function renderNegotiation(negotiation) {
    el.negotiationList.innerHTML = "";
    negotiation.forEach((item) => {
      const li = document.createElement("li");
      li.className = `negotiation-item priority-${riskClass(item.priority)}`;
      li.innerHTML = `
        <div class="negotiation-item-head">
          <span class="negotiation-item-clause">${item.clause}</span>
          <span class="negotiation-item-priority">${item.priority}</span>
        </div>
        <p class="negotiation-item-suggestion">${item.suggestion}</p>
      `;
      el.negotiationList.appendChild(li);
    });
  }

  // ---------------------------------------------------------------
  // File handling
  // ---------------------------------------------------------------

  function isSupportedFile(file) {
    return /\.(pdf|docx)$/i.test(file.name);
  }

  async function handleFile(file) {
    showError("");

    if (!isSupportedFile(file)) {
      showError("Unsupported file type. Please upload a PDF or DOCX contract.");
      return;
    }

    if (state.useDemo || !state.apiBase) {
      // No backend configured, or demo mode is explicitly on — use the
      // bundled sample so the interface stays reviewable end to end.
      showWorkbench(window.DEMO_ANALYSIS, file.name);
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${state.apiBase.replace(/\/$/, "")}/api/analyze`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error(`Backend returned ${res.status}`);
      const analysis = await res.json();
      showWorkbench(analysis, file.name);
    } catch (err) {
      showError(
        `Couldn't reach the backend at ${state.apiBase} (${err.message}). Check API settings, or turn on demo data.`
      );
    }
  }

  function loadDemo() {
    showError("");
    showWorkbench(window.DEMO_ANALYSIS, window.DEMO_ANALYSIS.filename);
  }

  // ---------------------------------------------------------------
  // Event wiring
  // ---------------------------------------------------------------

  function initDropzone() {
    el.dropzone.addEventListener("click", () => el.fileInput.click());
    el.dropzone.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        el.fileInput.click();
      }
    });

    ["dragenter", "dragover"].forEach((evt) =>
      el.dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        el.dropzone.classList.add("dragover");
      })
    );
    ["dragleave", "drop"].forEach((evt) =>
      el.dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        el.dropzone.classList.remove("dragover");
      })
    );
    el.dropzone.addEventListener("drop", (e) => {
      const file = e.dataTransfer.files && e.dataTransfer.files[0];
      if (file) handleFile(file);
    });

    el.fileInput.addEventListener("change", (e) => {
      const file = e.target.files && e.target.files[0];
      if (file) handleFile(file);
    });
  }

  function initSettings() {
    el.btnSettings.addEventListener("click", () => {
      syncSettingsUI();
      el.settingsPanel.hidden = false;
    });
    el.btnCloseSettings.addEventListener("click", () => {
      el.settingsPanel.hidden = true;
    });
    el.settingsPanel.addEventListener("click", (e) => {
      if (e.target === el.settingsPanel) el.settingsPanel.hidden = true;
    });
    el.btnSaveSettings.addEventListener("click", () => {
      state.apiBase = el.apiBaseInput.value.trim();
      state.useDemo = el.demoToggle.checked;
      saveSettings();
      syncSettingsUI();
      el.settingsPanel.hidden = true;
    });
  }

  function init() {
    loadSettings();
    syncSettingsUI();

    initDropzone();
    initSettings();

    el.btnTryDemo.addEventListener("click", loadDemo);
    el.btnNewUpload.addEventListener("click", showIntake);
    el.btnReanalyze.addEventListener("click", showIntake);
  }

  document.addEventListener("DOMContentLoaded", init);
})();
