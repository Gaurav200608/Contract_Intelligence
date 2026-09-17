<<<<<<< HEAD
﻿const API_BASE = "http://127.0.0.1:8000";

const fileInput = document.getElementById("fileInput");
const chooseBtn = document.getElementById("chooseBtn");
const dropZone = document.getElementById("dropZone");

const uploadPage = document.getElementById("uploadPage");
const resultsPage = document.getElementById("resultsPage");

const loading = document.getElementById("loading");
const errorBox = document.getElementById("error");

const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");


function showError(message) {

    errorBox.textContent = message;
    errorBox.hidden = false;

}


function hideError() {

    errorBox.hidden = true;
    errorBox.textContent = "";

}


function setLoading(value) {

    loading.hidden = !value;
    chooseBtn.disabled = value;

}


async function checkBackend() {

    try {

        const response =
            await fetch(`${API_BASE}/api/health`);

        if (!response.ok) {
            throw new Error();
        }

        statusDot.className = "online";
        statusText.textContent = "Backend Online";

    } catch {

        statusDot.className = "offline";
        statusText.textContent = "Backend Offline";

    }

}


function riskClass(value) {

    const text =
        String(value || "").toLowerCase();

    if (
        text.includes("high") ||
        text.includes("non-compliant")
    ) {
        return "high";
    }

    if (
        text.includes("medium") ||
        text.includes("review")
    ) {
        return "medium";
    }

    return "low";

}


function createBadge(value) {

    const span =
        document.createElement("span");

    span.className =
        `badge ${riskClass(value)}`;

    span.textContent =
        value || "â€”";

    return span;

}


function renderCompliance(items) {

    const table =
        document.getElementById("complianceTable");

    table.innerHTML = "";

    items.forEach(item => {

        const row =
            document.createElement("tr");

        const clause =
            document.createElement("td");

        clause.textContent =
            item.clause || "â€”";


        const status =
            document.createElement("td");

        status.appendChild(
            createBadge(item.status)
        );


        const risk =
            document.createElement("td");

        risk.appendChild(
            createBadge(item.risk)
        );


        const requirement =
            document.createElement("td");

        requirement.textContent =
            item.requirement || "â€”";


        const evidence =
            document.createElement("td");

        evidence.textContent =
            item.text ||
            "No evidence found.";


        row.append(
            clause,
            status,
            risk,
            requirement,
            evidence
        );

        table.appendChild(row);

    });

}


function renderClauses(items) {

    const container =
        document.getElementById("clauses");

    container.innerHTML = "";

    items.forEach((item, index) => {

        const card =
            document.createElement("article");

        card.className = "card";

        card.innerHTML = `
            <div class="card-top">
                <span class="number">
                    ${String(index + 1).padStart(2, "0")}
                </span>

                <span class="confidence">
                    ${item.confidence ?? 0}% confidence
                </span>
            </div>

            <h4>${item.type || "Unknown"}</h4>

            <p class="muted">
                ${item.title || ""}
            </p>

            <div class="evidence">
                ${item.text || "No clause text returned."}
            </div>
        `;

        container.appendChild(card);

    });

}


function renderExplanations(items) {

    const container =
        document.getElementById("explanations");

    container.innerHTML = "";

    items.forEach(item => {

        const card =
            document.createElement("article");

        card.className = "card";

        card.innerHTML = `
            <div class="card-top">
                <h4>${item.clause || "Finding"}</h4>
                <span class="badge ${riskClass(item.risk)}">
                    ${item.risk || "â€”"}
                </span>
            </div>

            <div class="info-block">
                <b>Why</b>
                <p>${item.reason || "â€”"}</p>
            </div>

            <div class="info-block">
                <b>Impact</b>
                <p>${item.impact || "â€”"}</p>
            </div>

            <div class="info-block">
                <b>Recommendation</b>
                <p>${item.recommendation || "â€”"}</p>
            </div>
        `;

        container.appendChild(card);

    });

}


function renderNegotiations(items) {

    const container =
        document.getElementById("negotiations");

    container.innerHTML = "";

    items.forEach(item => {

        const card =
            document.createElement("article");

        card.className = "card";

        card.innerHTML = `
            <div class="card-top">
                <h4>${item.clause || "Negotiation Point"}</h4>

                <span class="badge ${riskClass(item.priority)}">
                    ${item.priority || "Low"} Priority
                </span>
            </div>

            <div class="info-block">
                <b>Recommended Action</b>
                <p>${item.suggestion || "â€”"}</p>
            </div>

            <div class="wording">
                <b>Suggested Contract Wording</b>
                <p>${item.suggested_wording || "No wording returned."}</p>
            </div>
        `;

        container.appendChild(card);

    });

}


function renderResults(data) {

    document.getElementById("fileName").textContent =
        data.filename || "Contract Analysis";


    document.getElementById("fileInfo").textContent =
        `${data.text_length || 0} characters analyzed`;


    document.getElementById("overallRisk").textContent =
        data.risk?.overall_risk || "â€”";

    document.getElementById("overallRisk").className =
        `risk ${riskClass(data.risk?.overall_risk)}`;


    document.getElementById("riskScore").textContent =
        data.risk?.risk_score ?? "â€”";


    document.getElementById("riskModel").textContent =
        `Model: ${data.risk?.model_prediction || "â€”"} Â· ${data.risk?.confidence ?? "â€”"}%`;


    const compliance =
        data.compliance || [];

    const compliant =
        compliance.filter(
            x => String(x.status).toLowerCase() === "compliant"
        ).length;


    const percentage =
        compliance.length
            ? Math.round((compliant / compliance.length) * 100)
            : 0;


    document.getElementById("compliance").textContent =
        `${percentage}%`;


    document.getElementById("complianceModel").textContent =
        `Model: ${data.compliance_prediction?.status || "â€”"} Â· ${data.compliance_prediction?.confidence ?? "â€”"}%`;


    const clauses =
        data.clauses || [];


    document.getElementById("clauseCount").textContent =
        clauses.length;


    document.getElementById("textLength").textContent =
        `${(data.text_length || 0).toLocaleString()} characters`;


    renderCompliance(compliance);

    renderClauses(clauses);

    renderExplanations(
        data.explanations || []
    );

    renderNegotiations(
        data.negotiation || []
    );


    document.getElementById("rawOutput").textContent =
        JSON.stringify(data, null, 2);


    uploadPage.hidden = true;
    resultsPage.hidden = false;

    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });

}


async function analyzeContract(file) {

    hideError();

    if (!file) {
        return;
    }


    const name =
        file.name.toLowerCase();


    if (
        !name.endsWith(".pdf") &&
        !name.endsWith(".docx")
    ) {

        showError(
            "Only PDF and DOCX files are supported."
        );

        return;

    }


    setLoading(true);


    try {

        const formData =
            new FormData();

        formData.append(
            "file",
            file
        );


        const response =
            await fetch(
                `${API_BASE}/api/analyze`,
                {
                    method: "POST",
                    body: formData
                }
            );


        let data;

        try {

            data =
                await response.json();

        } catch {

            throw new Error(
                `Server returned HTTP ${response.status}`
            );

        }


        if (!response.ok) {

            throw new Error(
                data.detail ||
                `Analysis failed: HTTP ${response.status}`
            );

        }


        renderResults(data);


    } catch (error) {

        showError(
            error.message ||
            "Could not connect to the backend."
        );

    } finally {

        setLoading(false);

    }

}


chooseBtn.addEventListener(
    "click",
    event => {

        event.stopPropagation();

        fileInput.click();

    }
);


dropZone.addEventListener(
    "click",
    () => fileInput.click()
);


fileInput.addEventListener(
    "change",
    () => {

        const file =
            fileInput.files[0];

        if (file) {
            analyzeContract(file);
        }

        fileInput.value = "";

    }
);


dropZone.addEventListener(
    "dragover",
    event => {

        event.preventDefault();

        dropZone.classList.add("dragover");

    }
);


dropZone.addEventListener(
    "dragleave",
    () => {

        dropZone.classList.remove(
            "dragover"
        );

    }
);


dropZone.addEventListener(
    "drop",
    event => {

        event.preventDefault();

        dropZone.classList.remove(
            "dragover"
        );

        const file =
            event.dataTransfer.files[0];

        if (file) {
            analyzeContract(file);
        }

    }
);


document.getElementById(
    "newContract"
).addEventListener(
    "click",
    () => {

        resultsPage.hidden = true;
        uploadPage.hidden = false;

        window.scrollTo({
            top: 0,
            behavior: "smooth"
        });

    }
);


document.getElementById(
    "copyBtn"
).addEventListener(
    "click",
    async () => {

        const output =
            document.getElementById(
                "rawOutput"
            ).textContent;

        await navigator.clipboard.writeText(
            output
        );

        document.getElementById(
            "copyBtn"
        ).textContent = "Copied";

        setTimeout(
            () => {
                document.getElementById(
                    "copyBtn"
                ).textContent = "Copy JSON";
            },
            1500
        );

    }
);


checkBackend();

setInterval(
    checkBackend,
    10000
);
=======
(() => {
  "use strict";

  /* ---------------------------------------------------------------
     Config & persisted settings
  ------------------------------------------------------------------ */

  const MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024; // 100 MB — server enforces this too
  const ALLOWED_EXTENSIONS = [".pdf", ".docx"];
  const DEFAULT_API_BASE = "http://localhost:8000";
  const STORAGE_KEY = "contract-intelligence-settings";

  function loadSettings() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return { apiBase: DEFAULT_API_BASE, useDemo: true };
      const parsed = JSON.parse(raw);
      return {
        apiBase: typeof parsed.apiBase === "string" ? parsed.apiBase : DEFAULT_API_BASE,
        useDemo: typeof parsed.useDemo === "boolean" ? parsed.useDemo : true
      };
    } catch (_e) {
      return { apiBase: DEFAULT_API_BASE, useDemo: true };
    }
  }

  function saveSettings(settings) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    } catch (_e) {
      /* localStorage unavailable — settings just won't persist across reloads */
    }
  }

  let settings = loadSettings();

  function apiUrl(path) {
    const base = settings.apiBase.replace(/\/+$/, "");
    return `${base}${path}`;
  }

  /* ---------------------------------------------------------------
     Element refs
  ------------------------------------------------------------------ */

  const el = {
    modeFlag: document.getElementById("mode-flag"),
    intake: document.getElementById("intake"),
    workbench: document.getElementById("workbench"),
    dropzone: document.getElementById("dropzone"),
    fileInput: document.getElementById("file-input"),
    intakeError: document.getElementById("intake-error"),
    btnNewUpload: document.getElementById("btn-new-upload"),
    btnTryDemo: document.getElementById("btn-try-demo"),
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

    settingsPanel: document.getElementById("settings-panel"),
    btnSettings: document.getElementById("btn-settings"),
    btnCloseSettings: document.getElementById("btn-close-settings"),
    apiBaseInput: document.getElementById("api-base-input"),
    demoToggle: document.getElementById("demo-toggle"),
    btnSaveSettings: document.getElementById("btn-save-settings"),
    btnTestConnection: document.getElementById("btn-test-connection"),
    connectionStatus: document.getElementById("connection-status")
  };

  /* ---------------------------------------------------------------
     Settings panel
  ------------------------------------------------------------------ */

  function openSettings() {
    el.apiBaseInput.value = settings.apiBase;
    el.demoToggle.checked = settings.useDemo;
    el.connectionStatus.textContent = "";
    el.connectionStatus.className = "connection-status";
    el.settingsPanel.hidden = false;
  }

  function closeSettings() {
    el.settingsPanel.hidden = true;
  }

  function applyModeFlag() {
    el.modeFlag.textContent = settings.useDemo ? "Demo data" : `Live · ${settings.apiBase}`;
  }

  el.btnSettings.addEventListener("click", openSettings);
  el.btnCloseSettings.addEventListener("click", closeSettings);
  el.settingsPanel.addEventListener("click", (e) => {
    if (e.target === el.settingsPanel) closeSettings();
  });

  el.btnSaveSettings.addEventListener("click", () => {
    const apiBase = el.apiBaseInput.value.trim() || DEFAULT_API_BASE;
    settings = { apiBase, useDemo: el.demoToggle.checked };
    saveSettings(settings);
    applyModeFlag();
    closeSettings();
  });

  el.btnTestConnection.addEventListener("click", async () => {
    const apiBase = el.apiBaseInput.value.trim() || DEFAULT_API_BASE;
    el.connectionStatus.className = "connection-status pending";
    el.connectionStatus.textContent = "Checking…";
    try {
      const res = await fetch(`${apiBase.replace(/\/+$/, "")}/api/health`, {
        method: "GET"
      });
      if (res.ok) {
        el.connectionStatus.className = "connection-status ok";
        el.connectionStatus.textContent = "Connected";
      } else {
        el.connectionStatus.className = "connection-status fail";
        el.connectionStatus.textContent = `Backend responded ${res.status}`;
      }
    } catch (_err) {
      el.connectionStatus.className = "connection-status fail";
      el.connectionStatus.textContent = "Unreachable — check URL, CORS, or that the server is running";
    }
  });

  applyModeFlag();

  /* ---------------------------------------------------------------
     File intake
  ------------------------------------------------------------------ */

  function showIntakeError(message) {
    el.intakeError.textContent = message;
    el.intakeError.hidden = false;
  }

  function clearIntakeError() {
    el.intakeError.hidden = true;
    el.intakeError.textContent = "";
  }

  function validateFile(file) {
    const name = (file.name || "").toLowerCase();
    const hasAllowedExt = ALLOWED_EXTENSIONS.some((ext) => name.endsWith(ext));
    if (!hasAllowedExt) {
      return "Unsupported file type. Upload a .pdf or .docx contract.";
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
      return `File is ${sizeMb} MB, which is over the 100 MB limit.`;
    }
    if (file.size === 0) {
      return "That file is empty.";
    }
    return null;
  }

  el.dropzone.addEventListener("click", () => el.fileInput.click());
  el.dropzone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      el.fileInput.click();
    }
  });

  ["dragenter", "dragover"].forEach((evt) => {
    el.dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      el.dropzone.classList.add("dragover");
    });
  });
  ["dragleave", "drop"].forEach((evt) => {
    el.dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      el.dropzone.classList.remove("dragover");
    });
  });
  el.dropzone.addEventListener("drop", (e) => {
    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    if (file) handleFile(file);
  });

  el.fileInput.addEventListener("change", () => {
    const file = el.fileInput.files && el.fileInput.files[0];
    if (file) handleFile(file);
    el.fileInput.value = "";
  });

  el.btnNewUpload.addEventListener("click", () => showIntake());
  el.btnReanalyze.addEventListener("click", () => showIntake());
  el.btnTryDemo.addEventListener("click", () => {
    clearIntakeError();
    renderAnalysis(window.DEMO_ANALYSIS);
  });

  async function handleFile(file) {
    clearIntakeError();
    const problem = validateFile(file);
    if (problem) {
      showIntakeError(problem);
      return;
    }

    if (settings.useDemo) {
      // Demo mode: show the bundled sample analysis, but keep the
      // uploaded file's name so the workbench still feels attached
      // to what was dropped in.
      const demo = { ...window.DEMO_ANALYSIS, filename: file.name };
      renderAnalysis(demo);
      return;
    }

    setDropzoneBusy(true);
    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch(apiUrl("/api/analyze"), {
        method: "POST",
        body: formData
      });

      if (!res.ok) {
        let detail = `Request failed (${res.status})`;
        try {
          const body = await res.json();
          if (body && body.detail) detail = body.detail;
        } catch (_e) {
          /* ignore parse failure, use default message */
        }
        showIntakeError(detail);
        return;
      }

      const data = await res.json();
      renderAnalysis(data);
    } catch (_err) {
      showIntakeError(
        `Couldn't reach the backend at ${settings.apiBase}. Check API settings, or turn on demo data.`
      );
    } finally {
      setDropzoneBusy(false);
    }
  }

  function setDropzoneBusy(isBusy) {
    if (isBusy) {
      el.dropzone.querySelector(".dropzone-title").textContent = "Analyzing…";
      el.dropzone.querySelector(".dropzone-sub").textContent = "Parsing, classifying, and scoring the contract";
      el.dropzone.setAttribute("aria-busy", "true");
    } else {
      el.dropzone.querySelector(".dropzone-title").textContent = "Drag a contract here";
      el.dropzone.querySelector(".dropzone-sub").textContent = "or click to browse — PDF or DOCX, up to 100\u00a0MB";
      el.dropzone.removeAttribute("aria-busy");
    }
  }

  function showIntake() {
    el.workbench.hidden = true;
    el.intake.hidden = false;
    clearIntakeError();
  }

  /* ---------------------------------------------------------------
     Rendering
  ------------------------------------------------------------------ */

  function riskClass(risk) {
    const r = (risk || "").toLowerCase();
    if (r === "high" || r === "non-compliant") return "high";
    if (r === "medium" || r === "needs review") return "medium";
    return "low";
  }

  function renderAnalysis(data) {
    el.intake.hidden = true;
    el.workbench.hidden = false;

    const requiredCount = (data.compliance || []).length;
    const compliantCount = (data.compliance || []).filter((c) => c.status === "Compliant").length;

    el.wbFilename.textContent = data.filename || "Untitled contract";
    el.wbMeta.textContent =
      `${(data.clauses || []).length} clause${(data.clauses || []).length === 1 ? "" : "s"} detected · ` +
      `${compliantCount} of ${requiredCount} required terms present`;

    renderClauseIndex(data.compliance || []);
    renderFeed(data.explanations || [], data.compliance || []);
    renderRiskDial(data.risk || { overall_risk: "Low", risk_score: 0 });
    renderNegotiation(data.negotiation || []);

    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function renderClauseIndex(compliance) {
    el.clauseIndex.innerHTML = "";
    compliance.forEach((item, i) => {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.className = "clause-index-btn";
      btn.type = "button";
      btn.dataset.target = `clause-${i}`;

      const dot = document.createElement("span");
      dot.className = `clause-dot ${riskClass(item.risk)}`;

      const name = document.createElement("span");
      name.className = "clause-name";
      name.textContent = item.clause;

      btn.append(dot, name);
      btn.addEventListener("click", () => {
        const target = document.getElementById(`clause-${i}`);
        if (target) {
          target.scrollIntoView({ behavior: "smooth", block: "start" });
          document.querySelectorAll(".clause-index-btn").forEach((b) => b.classList.remove("active"));
          btn.classList.add("active");
        }
      });

      li.appendChild(btn);
      el.clauseIndex.appendChild(li);
    });
  }

  function renderFeed(explanations, compliance) {
    el.feedList.innerHTML = "";
    const complianceByClause = Object.fromEntries((compliance || []).map((c) => [c.clause, c]));

    explanations.forEach((item, i) => {
      const compl = complianceByClause[item.clause] || {};
      const card = document.createElement("article");
      card.className = "feed-card";
      card.id = `clause-${i}`;

      const head = document.createElement("div");
      head.className = "feed-card-head";

      const title = document.createElement("h3");
      title.className = "feed-card-title";
      title.textContent = item.clause;

      const badge = document.createElement("span");
      badge.className = `status-badge ${riskClass(item.risk)}`;
      badge.textContent = compl.status ? `${compl.status} · ${item.risk}` : item.risk;

      head.append(title, badge);

      const reason = document.createElement("p");
      reason.className = "feed-card-explanation";
      reason.textContent = item.reason;

      const grid = document.createElement("div");
      grid.className = "feed-card-grid";
      grid.appendChild(field("Impact", item.impact));
      grid.appendChild(field("Recommendation", item.recommendation));
      if (compl.text) {
        grid.appendChild(field("Contract text", compl.text, true));
      }

      card.append(head, reason, grid);
      el.feedList.appendChild(card);
    });
  }

  function field(label, value, isQuote) {
    const wrap = document.createElement("div");
    const lab = document.createElement("p");
    lab.className = "feed-field-label";
    lab.textContent = label.toUpperCase();
    const val = document.createElement("p");
    val.className = `feed-field-value${isQuote ? " quote" : ""}`;
    val.textContent = value;
    wrap.append(lab, val);
    return wrap;
  }

  function renderRiskDial(risk) {
    const cls = riskClass(risk.overall_risk);
    const colors = { high: "#A32C22", medium: "#96661A", low: "#2F6B4F" };
    const circumference = 251.3;

    // Risk score is unbounded upward (sum of weighted clause risks),
    // so clamp the dial's visual fill at a reasonable ceiling for display.
    const displayCeiling = 24;
    const fraction = Math.max(0, Math.min(1, risk.risk_score / displayCeiling));
    const offset = circumference * (1 - fraction);

    el.riskDialFill.setAttribute("stroke", colors[cls]);
    el.riskDialFill.style.strokeDashoffset = String(offset);

    el.riskScore.textContent = risk.risk_score;
    el.riskLabel.textContent = risk.overall_risk;
    el.riskLabel.style.color = colors[cls];
    el.riskNote.textContent =
      cls === "high"
        ? "Multiple required terms are missing or high-risk. Review before signing."
        : cls === "medium"
        ? "Some required terms need attention before this is ready to sign."
        : "Required terms are largely in place.";
  }

  function renderNegotiation(items) {
    el.negotiationList.innerHTML = "";
    if (!items.length) {
      const li = document.createElement("li");
      li.className = "negotiation-item";
      li.textContent = "No negotiation points — nothing missing or flagged.";
      el.negotiationList.appendChild(li);
      return;
    }

    items.forEach((item) => {
      const li = document.createElement("li");
      li.className = `negotiation-item priority-${(item.priority || "").toLowerCase()}`;

      const head = document.createElement("div");
      head.className = "negotiation-item-head";
      const clause = document.createElement("span");
      clause.className = "negotiation-item-clause";
      clause.textContent = item.clause;
      const priority = document.createElement("span");
      priority.className = "negotiation-item-priority";
      priority.textContent = item.priority;
      head.append(clause, priority);

      const suggestion = document.createElement("p");
      suggestion.className = "negotiation-item-suggestion";
      suggestion.textContent = item.suggestion;

      li.append(head, suggestion);
      el.negotiationList.appendChild(li);
    });
  }
})();
>>>>>>> 15b92ba76e4f02c8cc8e9c68848ebd3d980e6056
