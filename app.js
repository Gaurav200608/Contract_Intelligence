const API_BASE = window.location.origin;
let csrfToken = "";

const fileInput = document.getElementById("fileInput");
const chooseBtn = document.getElementById("chooseBtn");
const dropZone = document.getElementById("dropZone");

const uploadPage = document.getElementById("uploadPage");
const resultsPage = document.getElementById("resultsPage");

const loading = document.getElementById("loading");
const errorBox = document.getElementById("error");

const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
let dashboardReady = false;
let currentAnalysis = null;
let clauseRecords = [];
let riskRecords = [];
let complianceRecords = [];

const pageTitles = {
    overview: "Overview",
    "contract-analysis": "Contract Analysis",
    "clause-analysis": "Clause Analysis",
    "risk-analysis": "Risk Analysis",
    "compliance-analysis": "Compliance Analysis",
    "financial-impact": "Financial Impact",
    "negotiation-support": "Negotiation Support",
    "law-analysis": "Law Analysis"
};

function navigateTo(page, updateHistory = true) {
    const targetPage = Object.prototype.hasOwnProperty.call(pageTitles, page)
        ? page
        : "overview";
    if (updateHistory && window.location.hash !== `#${targetPage}`) {
        window.location.hash = targetPage;
        return;
    }

    document.querySelectorAll("[data-page-container]").forEach(section => {
        section.hidden = section.dataset.pageContainer !== targetPage;
    });
    document.querySelectorAll("[data-page]").forEach(link => {
        const active = link.dataset.page === targetPage;
        link.classList.toggle("active", active);
        if (active) {
            link.setAttribute("aria-current", "page");
        } else {
            link.removeAttribute("aria-current");
        }
    });
    document.getElementById("pageTitle").textContent = pageTitles[targetPage];
    document.getElementById("pageBreadcrumb").textContent = pageTitles[targetPage];
    document.getElementById("mainContent").scrollTop = 0;
    window.scrollTo({ top: 0, behavior: "auto" });
    closeSidebar();
}

function closeSidebar() {
    document.getElementById("sidebar").classList.remove("sidebar-open");
    document.getElementById("sidebarBackdrop").hidden = true;
    document.getElementById("sidebarToggle").setAttribute("aria-expanded", "false");
}

const savedSidebarState = localStorage.getItem("contract-intelligence-sidebar");
if (savedSidebarState === "collapsed") {
    document.body.classList.add("sidebar-collapsed");
}

function updateSidebarControl() {
    const collapsed = document.body.classList.contains("sidebar-collapsed");
    const button = document.getElementById("sidebarCollapse");
    button.setAttribute("aria-label", collapsed ? "Expand navigation" : "Collapse navigation");
    button.title = collapsed ? "Expand navigation" : "Collapse navigation";
    button.querySelector("span").textContent = collapsed ? "Expand sidebar" : "Collapse sidebar";
}

document.getElementById("sidebarCollapse").addEventListener("click", () => {
    const collapsed = document.body.classList.toggle("sidebar-collapsed");
    localStorage.setItem("contract-intelligence-sidebar", collapsed ? "collapsed" : "expanded");
    updateSidebarControl();
});
updateSidebarControl();

document.querySelectorAll("[data-page]").forEach(link => {
    link.addEventListener("click", event => {
        event.preventDefault();
        navigateTo(link.dataset.page);
    });
});
document.querySelectorAll("[data-navigate]").forEach(button => {
    button.addEventListener("click", () => navigateTo(button.dataset.navigate));
});
window.addEventListener("hashchange", () => {
    const hash = window.location.hash.slice(1);
    navigateTo(
        hash.startsWith("law-") ? "law-analysis" : hash,
        false
    );
});
document.getElementById("sidebarToggle").addEventListener("click", () => {
    const sidebar = document.getElementById("sidebar");
    const open = sidebar.classList.toggle("sidebar-open");
    document.getElementById("sidebarBackdrop").hidden = !open;
    document.getElementById("sidebarToggle").setAttribute("aria-expanded", String(open));
});
document.getElementById("sidebarBackdrop").addEventListener("click", closeSidebar);
document.getElementById("topbarUpload").addEventListener("click", () => navigateTo("contract-analysis"));
document.addEventListener("keydown", event => {
    if (event.key === "Escape") closeSidebar();
});

function activateLawTab(tabName, focusTab = false) {
    const tabs = [...document.querySelectorAll("[data-law-tab]")];
    const validTab = tabs.some(tab => tab.dataset.lawTab === tabName);
    const selectedTab = validTab ? tabName : "overview";
    tabs.forEach(tab => {
        const selected = tab.dataset.lawTab === selectedTab;
        tab.setAttribute("aria-selected", String(selected));
        tab.tabIndex = selected ? 0 : -1;
        if (selected && focusTab) tab.focus();
    });
    document.querySelectorAll("[data-law-panel]").forEach(panel => {
        panel.hidden = panel.dataset.lawPanel !== selectedTab;
    });
}

document.querySelectorAll("[data-law-tab]").forEach(tab => {
    tab.addEventListener("click", () => activateLawTab(tab.dataset.lawTab));
    tab.addEventListener("keydown", event => {
        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
        event.preventDefault();
        const tabs = [...document.querySelectorAll("[data-law-tab]")];
        const index = tabs.indexOf(tab);
        const nextIndex = event.key === "ArrowRight"
            ? (index + 1) % tabs.length
            : (index - 1 + tabs.length) % tabs.length;
        activateLawTab(tabs[nextIndex].dataset.lawTab, true);
    });
});
document.getElementById("lawJurisdictionOverview").addEventListener("change", event => {
    const selectedJurisdiction = event.target.value;
    const findingFilter = document.getElementById("lawJurisdictionFilter");
    findingFilter.value = [...findingFilter.options].some(option => option.value === selectedJurisdiction)
        ? selectedJurisdiction
        : "";
    renderLawFindingList();
    renderJurisdictionSummary();
});

navigateTo(window.location.hash.slice(1) || "overview", false);

chooseBtn.disabled = true;
fileInput.disabled = true;
document.getElementById("analyzeBtn").disabled = true;
let selectedFile = null;
let lawAnalysisRecord = null;


function showError(message) {

    errorBox.textContent = message;
    errorBox.hidden = false;

}


function hideError() {

    errorBox.hidden = true;
    errorBox.textContent = "";

}

let toastTimer;
function showToast(message) {
    const region = document.getElementById("toastRegion");
    region.textContent = message;
    region.classList.add("toast-visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => region.classList.remove("toast-visible"), 3200);
}

function selectContract(file) {
    if (!file) return;
    const lowerName = file.name.toLowerCase();
    if (!lowerName.endsWith(".pdf") && !lowerName.endsWith(".docx")) {
        selectedFile = null;
        document.getElementById("selectedFile").hidden = true;
        document.getElementById("analyzeBtn").disabled = true;
        showError("Only PDF and DOCX files are supported.");
        return;
    }
    if (file.size > 100 * 1024 * 1024) {
        selectedFile = null;
        document.getElementById("selectedFile").hidden = true;
        document.getElementById("analyzeBtn").disabled = true;
        showError("This file exceeds the 100 MB upload limit.");
        return;
    }

    selectedFile = file;
    hideError();
    document.getElementById("selectedFile").hidden = false;
    document.getElementById("selectedFileName").textContent = file.name;
    document.getElementById("selectedFileMeta").textContent =
        `${file.size ? `${(file.size / (1024 * 1024)).toFixed(2)} MB · ` : ""}${lowerName.endsWith(".pdf") ? "PDF document" : "Word document"} · ready to analyze`;
    document.getElementById("analyzeBtn").disabled = !dashboardReady;
    showToast("Contract selected. Review the filename, then start analysis.");
}

function clearSelectedContract() {
    if (loading.hidden === false) return;
    selectedFile = null;
    fileInput.value = "";
    document.getElementById("selectedFile").hidden = true;
    document.getElementById("selectedFileName").textContent = "";
    document.getElementById("selectedFileMeta").textContent = "";
    document.getElementById("analyzeBtn").disabled = true;
    hideError();
}


function setLoading(value) {

    loading.hidden = !value;
    chooseBtn.disabled = value;
    fileInput.disabled = value || !dashboardReady;
    document.getElementById("analyzeBtn").disabled = value || !selectedFile;
    document.getElementById("clearSelectedFile").disabled = value;
    if (value) {
        document.getElementById("lawLoading").hidden = false;
        document.getElementById("lawEmpty").hidden = true;
        document.getElementById("lawError").hidden = true;
        document.getElementById("lawContent").hidden = true;
    }

}

function escapeHTML(value) {
    const entities = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "\"": "&quot;",
        "'": "&#39;"
    };
    return String(value ?? "").replace(/[&<>"']/g, character => entities[character]);
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

function populateFilter(id, values, label) {
    const select = document.getElementById(id);
    const current = select.value;
    select.replaceChildren(new Option(label, ""));
    [...new Set(values.filter(Boolean))].sort().forEach(value => {
        select.add(new Option(value, value));
    });
    select.value = values.includes(current) ? current : "";
}


function renderCompliance(items) {

    const table =
        document.getElementById("complianceTable");

    table.innerHTML = "";

    const search = document.getElementById("complianceSearch").value.trim().toLowerCase();
    const status = document.getElementById("complianceStatusFilter").value;
    const matches = items.filter(item => {
        const searchable = [item.clause, item.status, item.risk, item.requirement, item.text]
            .join(" ").toLowerCase();
        return (!search || searchable.includes(search))
            && (!status || item.status === status);
    });
    const empty = document.getElementById("complianceEmpty");
    empty.hidden = matches.length > 0;
    empty.textContent = items.length
        ? "No contractual-term checks match these filters."
        : "No compliance checks were returned by the analysis engine.";
    matches.forEach(item => {

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

    const search = document.getElementById("clauseSearch").value.trim().toLowerCase();
    const category = document.getElementById("clauseCategoryFilter").value;
    const matches = items.filter(item => {
        const searchable = [item.type, item.title, item.text, item.reference, item.clause_reference]
            .join(" ").toLowerCase();
        return (!search || searchable.includes(search))
            && (!category || item.type === category);
    });
    const empty = document.getElementById("clausesEmpty");
    empty.hidden = matches.length > 0;
    empty.textContent = items.length
        ? "No clauses match these filters."
        : "No clauses were returned by the analysis engine.";
    matches.forEach((item, index) => {

        const card =
            document.createElement("article");

        card.className = "card";

        card.innerHTML = `
            <div class="card-top">
                <span class="number">
                    ${String(index + 1).padStart(2, "0")}
                </span>

                ${item.confidence !== undefined && item.confidence !== null
                    ? `<span class="confidence">TinyBERT · ${escapeHTML(item.confidence)}% confidence</span>`
                    : item.classification_method === "heuristic"
                        ? `<span class="confidence">Rule-based classification</span>`
                        : ""}
            </div>

            <h4>${escapeHTML(item.type || "Unknown")}</h4>

            <p class="muted">
                ${escapeHTML([item.title, item.reference || item.clause_reference].filter(Boolean).join(" · "))}
            </p>

            <details class="clause-evidence">
                <summary>View extracted clause</summary>
                <div class="evidence">${escapeHTML(item.text || "No clause text returned.")}</div>
            </details>
        `;

        container.appendChild(card);

    });

}


function renderExplanations(items) {

    const container =
        document.getElementById("explanations");

    container.innerHTML = "";

    const severity = document.getElementById("riskSeverityFilter").value;
    const category = document.getElementById("riskCategoryFilter").value;
    const matches = items.filter(item =>
        (!severity || item.risk === severity)
        && (!category || (item.category || item.clause) === category)
    );
    const empty = document.getElementById("riskEmpty");
    empty.hidden = matches.length > 0;
    empty.textContent = items.length
        ? "No risk findings match these filters."
        : "No risk explanations were returned by the analysis engine.";
    matches.forEach(item => {

        const card =
            document.createElement("article");

        card.className = "card";

        card.innerHTML = `
            <div class="card-top">
                <h4>${escapeHTML(item.clause || "Finding")}</h4>
                <span class="badge ${riskClass(item.risk)}">
                    ${escapeHTML(item.risk || "â€”")}
                </span>
            </div>

            <div class="info-block">
                <b>Why</b>
                <p>${escapeHTML(item.reason || "â€”")}</p>
            </div>

            <div class="info-block">
                <b>Impact</b>
                <p>${escapeHTML(item.impact || "â€”")}</p>
            </div>

            <div class="info-block">
                <b>Recommendation</b>
                <p>${escapeHTML(item.recommendation || "â€”")}</p>
            </div>
        `;

        container.appendChild(card);
        const evidence = clauseRecords.find(clause =>
            clause.type === item.clause || clause.title === item.clause
        );
        if (evidence?.text) {
            const details = document.createElement("details");
            lawText(details, "summary", "Supporting contract clause");
            lawText(details, "blockquote", evidence.text);
            card.appendChild(details);
        }

    });

}


function renderNegotiations(items) {

    const container =
        document.getElementById("negotiations");

    container.innerHTML = "";
    const empty = document.getElementById("negotiationsEmpty");
    empty.hidden = items.length > 0;
    empty.textContent = items.length
        ? ""
        : "No negotiation recommendations were returned by the analysis engine.";

    items.forEach(item => {

        const card =
            document.createElement("article");

        card.className = "card";

        card.innerHTML = `
            <div class="card-top">
                <h4>${escapeHTML(item.clause || "Negotiation Point")}</h4>

                <span class="badge ${riskClass(item.priority)}">
                    ${escapeHTML(item.priority || "Low")} Priority
                </span>
            </div>

            <div class="info-block">
                <b>Recommended Action</b>
                <p>${escapeHTML(item.suggestion || "â€”")}</p>
            </div>

            <div class="wording">
                <b>Suggested alternative wording · review draft</b>
                <p>${escapeHTML(item.suggested_wording || "No wording returned.")}</p>
            </div>
        `;

        const evidence = clauseRecords.find(clause =>
            clause.type === item.clause || clause.title === item.clause
        );
        if (evidence?.text) {
            const details = document.createElement("details");
            lawText(details, "summary", "Original contract clause");
            lawText(details, "blockquote", evidence.text);
            card.appendChild(details);
        }

        container.appendChild(card);

    });

}


let lawFindingRecords = [];


function lawText(parent, tagName, value, className) {
    const element = document.createElement(tagName);
    if (className) {
        element.className = className;
    }
    element.textContent = value || "Not identified in the uploaded text.";
    parent.appendChild(element);
    return element;
}


function lawField(parent, label, value) {
    const wrapper = document.createElement("div");
    wrapper.className = "law-field";
    lawText(wrapper, "b", label);
    lawText(wrapper, "p", value);
    parent.appendChild(wrapper);
}


function addFilterOptions(id, values) {
    const select = document.getElementById(id);
    const current = select.value;
    select.replaceChildren(new Option(`All ${id === "lawPartyFilter" ? "companies" : id === "lawJurisdictionFilter" ? "jurisdictions" : id === "lawTopicFilter" ? "topics" : "severities"}`, ""));
    [...new Set(values.filter(Boolean))].sort().forEach(value => {
        select.add(new Option(value, value));
    });
    select.value = values.includes(current) ? current : "";
}

function renderJurisdictionSummary() {
    const selector = document.getElementById("lawJurisdictionOverview");
    const selected = selector.value;
    const overview = lawAnalysisRecord?.overview || {};
    const governing = overview.governing_law || {};
    const dispute = overview.dispute_resolution || {};
    const jurisdictions = overview.potential_jurisdictions || [];
    const source = (lawAnalysisRecord?.legal_sources || []).find(item =>
        item.jurisdiction === selected
    );
    const selectedContext = jurisdictions.find(item => item.jurisdiction === selected);
    const summary = document.getElementById("lawCountrySummary");
    summary.replaceChildren();

    const title = selected || governing.region || governing.jurisdiction || "";
    if (title) {
        lawText(summary, "b", `${title} · `);
        const reason = selectedContext?.applicability_reason
            || (governing.jurisdiction === selected ? "express governing-law clause" : "");
        lawText(
            summary,
            "span",
            reason
                ? `Contract connection identified: ${reason.replaceAll("_", " ")}. This is not a determination that a particular statute applies.`
                : "A contract connection is identified. The available analysis does not confirm that specific local laws apply."
        );
        if (source) {
            const sourceCount = (source.sources || []).length;
            const operationalCount = (source.sources || []).filter(item =>
                item.connector_status === "operational"
            ).length;
            lawText(
                summary,
                "p",
                sourceCount
                    ? `${sourceCount} official source record${sourceCount === 1 ? "" : "s"} listed; ${operationalCount} live connector${operationalCount === 1 ? "" : "s"}. Registry coverage is not retrieval or a legal applicability determination.`
                    : "No official source metadata is registered for this jurisdiction."
            );
        }
    } else {
        lawText(
            summary,
            "span",
            "No country has been selected. The analysis lists only contract-supported connections; it does not imply that every supported country's laws apply."
        );
    }
    const disputeSummary = dispute.summary;
    if (disputeSummary) {
        lawText(summary, "p", `Dispute resolution: ${disputeSummary}`);
    }
}


function renderLawFindingList() {
    const search = document.getElementById("lawSearch").value.trim().toLowerCase();
    const party = document.getElementById("lawPartyFilter").value;
    const jurisdiction = document.getElementById("lawJurisdictionFilter").value;
    const topic = document.getElementById("lawTopicFilter").value;
    const severity = document.getElementById("lawSeverityFilter").value;
    const matches = lawFindingRecords.filter(item => {
        const searchable = [
            item.title, item.affected_party, item.affected_party_role,
            item.jurisdiction, item.contract_topic, item.applicability_reason,
            item.contract_clause_text, item.legal_explanation,
            item.potential_conflict, item.missing_protection,
            item.recommended_action
        ].join(" ").toLowerCase();
        return (!search || searchable.includes(search))
            && (!party || item.affected_party === party)
            && (!jurisdiction || item.jurisdiction === jurisdiction)
            && (!topic || item.contract_topic === topic)
            && (!severity || item.severity === severity);
    });
    const container = document.getElementById("lawFindings");
    container.replaceChildren();
    matches.forEach(item => {
        const card = document.createElement("details");
        card.className = "law-finding";
        const header = document.createElement("div");
        header.className = "law-finding-header";
        lawText(header, "h5", item.title);
        const severityBadge = document.createElement("span");
        severityBadge.className = `badge ${riskClass(item.severity)}`;
        severityBadge.textContent = item.severity;
        header.appendChild(severityBadge);
        const summary = document.createElement("summary");
        summary.appendChild(header);
        card.appendChild(summary);
        const detailContent = document.createElement("div");
        detailContent.className = "law-finding-content";

        const tags = document.createElement("div");
        tags.className = "law-tags";
        [
            item.affected_party && `Company: ${item.affected_party}`,
            item.affected_party_role && `Role: ${item.affected_party_role}`,
            item.jurisdiction && `Jurisdiction: ${item.jurisdiction}`,
            item.contract_topic && `Topic: ${item.contract_topic}`,
            `Evidence confidence: ${Math.round(Number(item.confidence || 0) * 100)}%`
        ].filter(Boolean).forEach(value => lawText(tags, "span", value, "law-tag"));
        detailContent.appendChild(tags);

        lawField(detailContent, "Why this jurisdiction may matter", item.applicability_reason);
        lawField(detailContent, "Plain-English assessment", item.legal_explanation);
        lawField(detailContent, "Legal boundary / uncertainty", item.legal_boundary);
        if (item.contract_clause_text) {
            const details = document.createElement("details");
            const summary = lawText(details, "summary", "Contract evidence");
            summary.tabIndex = 0;
            lawText(details, "blockquote", item.contract_clause_text);
            if (item.contract_clause_reference) {
                lawText(details, "small", `Reference: ${item.contract_clause_reference}`);
            }
            detailContent.appendChild(details);
        }
        if (item.potential_conflict) {
            lawField(detailContent, "Potential conflict to review", item.potential_conflict);
        }
        if (item.missing_protection) {
            lawField(detailContent, "Missing or unclear term", item.missing_protection);
        }
        lawField(detailContent, "Recommended action", item.recommended_action);
        lawField(
            detailContent,
            "Confidence / review status",
            `${Math.round(Number(item.confidence || 0) * 100)}% evidence confidence · ${item.requires_lawyer_review ? "professional review recommended" : "review status not flagged"}`
        );
        lawField(
            detailContent,
            "Legal source status",
            item.legal_provision_name
                ? `${item.legal_provision_name} (${displaySourceStatus(item.source_verification_status)})`
                : "No specific legal provision was verified for this finding."
        );
        if (item.official_source_url) {
            appendOfficialLink(detailContent, item.official_source_url, "Open official research portal");
        }
        card.appendChild(detailContent);
        container.appendChild(card);
    });
    document.getElementById("lawNoFindings").hidden = matches.length > 0;
}


function appendOfficialLink(parent, url, label) {
    try {
        const parsed = new URL(url);
        if (parsed.protocol !== "https:") {
            return;
        }
        const link = document.createElement("a");
        link.href = parsed.href;
        link.textContent = label;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        parent.appendChild(link);
    } catch {
        return;
    }
}

function displaySourceStatus(status) {
    const labels = {
        not_checked: "Not verified",
        not_attempted: "Not verified · not yet retrieved",
        portal_reachable_provision_not_verified: "Portal reachable · provision not verified",
        portal_unavailable_provision_not_verified: "Portal unavailable · provision not verified",
        verified: "Verified",
        retrieved: "Official text retrieved · applicability not verified",
        partial_failure: "Partial retrieval · review source errors",
        no_results: "No search results",
        not_applicable: "Not searched",
        not_searched_jurisdiction_not_identified: "Not searched · jurisdiction not identified",
        not_searched_no_contract_topic_evidence: "Not searched · no contract topic evidence",
        timeout: "Source request timed out",
        rate_limited: "Source rate limit reached",
        unavailable: "Source unavailable",
        stale_source_date: "Source version may be stale",
        retrieved_as_of_source_date_not_guaranteed_current: "Retrieved as of source date · currentness not guaranteed"
    };
    return labels[status] || status || "Not verified";
}

function renderLawAnalysis(analysis) {
    const loadingState = document.getElementById("lawLoading");
    const emptyState = document.getElementById("lawEmpty");
    const errorState = document.getElementById("lawError");
    const content = document.getElementById("lawContent");
    loadingState.hidden = true;
    errorState.hidden = true;
    content.hidden = true;
    emptyState.hidden = true;

    if (!analysis || typeof analysis !== "object") {
        errorState.textContent = "Law Analysis was not included in the API response. Existing non-legal analysis results remain available.";
        errorState.hidden = false;
        document.getElementById("lawAnalysisBadge").textContent = "Unavailable";
        return;
    }

    const overview = analysis.overview || {};
    const governing = overview.governing_law || {};
    const dispute = overview.dispute_resolution || {};
    const parties = overview.parties || [];
    const jurisdictions = overview.potential_jurisdictions || [];
    const uncertainties = overview.missing_or_uncertain_information || [];
    lawFindingRecords = analysis.findings || [];
    lawAnalysisRecord = analysis;

    const legalResearch = analysis.legal_research || {};
    if (!lawFindingRecords.length && !parties.length && !jurisdictions.length
        && !(legalResearch.documents || []).length) {
        emptyState.hidden = false;
    } else {
        content.hidden = false;
    }

    const badge = document.getElementById("lawAnalysisBadge");
    badge.textContent = "Review required";
    badge.className = "badge medium";
    if (analysis.analysis_status !== "complete_with_review_required") {
        badge.textContent = "Degraded analysis";
    }

    const overviewContainer = document.getElementById("lawOverview");
    overviewContainer.replaceChildren();
    const overviewCards = [
        ["Contract type", analysis.contract_type || "Not identified"],
        [
            "Express governing law",
            governing.clause_found
                ? `${governing.region || governing.jurisdiction || "Jurisdiction unresolved"} — stated in contract`
                : "Not identified in uploaded text"
        ],
        ["Dispute resolution", dispute.summary || "Not identified"],
        [
            "Potential jurisdictions",
            jurisdictions.length
                ? jurisdictions.map(item => `${item.region || item.jurisdiction} (${item.applicability_reason})`).join("\n")
                : "No jurisdiction supported by the extracted contract evidence"
        ],
        [
            "Transaction context",
            (overview.transaction_context || []).length
                ? overview.transaction_context.map(item => `${item.contract_topic}: ${item.contract_clause_text}`).join("\n\n")
                : "No services, payment, data-processing, or IP transaction evidence was identified."
        ],
        [
            "Uncertainties / missing information",
            uncertainties.length ? uncertainties.join("\n") : "No additional uncertainty was flagged by the extraction rules."
        ]
    ];
    overviewCards.forEach(([label, value]) => {
        const card = document.createElement("article");
        card.className = "law-overview-card";
        lawText(card, "span", label, "law-overview-label");
        lawText(card, "p", value);
        overviewContainer.appendChild(card);
    });
    if (governing.evidence) {
        const evidence = document.createElement("article");
        evidence.className = "law-overview-card law-overview-evidence";
        lawText(evidence, "span", "Governing-law clause evidence", "law-overview-label");
        lawText(evidence, "p", governing.evidence);
        overviewContainer.appendChild(evidence);
    }
    [...(dispute.court_jurisdiction_evidence || []), ...(dispute.arbitration_evidence || [])]
        .forEach((text, index) => {
            const evidence = document.createElement("article");
            evidence.className = "law-overview-card law-overview-evidence";
            lawText(evidence, "span", index === 0 ? "Dispute clause evidence" : "Additional dispute clause evidence", "law-overview-label");
            lawText(evidence, "p", text);
            overviewContainer.appendChild(evidence);
        });

    const companyContainer = document.getElementById("lawCompanies");
    companyContainer.replaceChildren();
    (analysis.company_analyses || []).forEach(company => {
        const card = document.createElement("article");
        card.className = "law-company-card";
        lawText(card, "h5", company.name || "Party not identified");
        lawText(card, "p", `${company.role || "Role not stated"} · ${company.country || "Country not identified"}`, "law-company-meta");
        if (company.country_evidence) {
            lawField(card, "Country evidence", company.country_evidence);
        }
        const obligations = company.contractual_obligations || [];
        lawField(
            card,
            "Contract terms and duties identified",
            obligations.length
                ? obligations.map(item => `${item.topic}: ${item.summary || item.contract_clause_text}`).join("\n\n")
                : "No company-specific contractual term was confidently attributed."
        );
        const statutory = company.potential_statutory_obligations || [];
        lawField(
            card,
            "Potential statutory considerations",
            statutory.length
                ? statutory.map(item => `${item.topic}: ${item.note}`).join("\n")
                : "No statutory obligation is asserted; applicability requires facts and legal review."
        );
        const rights = company.contractual_rights_and_restrictions || [];
        lawField(
            card,
            "Contractual rights and restrictions (evidence)",
            rights.length
                ? rights.map(item => `${item.topic}: ${item.contract_clause_text}`).join("\n\n")
                : "No additional rights/restrictions were confidently attributed."
        );
        lawField(card, "Rights and boundaries", (company.rights_and_boundaries || []).join("\n"));
        companyContainer.appendChild(card);
    });
    if (!companyContainer.children.length) {
        lawText(companyContainer, "p", "No company names and contractual roles could be confidently identified. The module will not infer them.");
    }

    addFilterOptions("lawPartyFilter", lawFindingRecords.map(item => item.affected_party));
    addFilterOptions("lawJurisdictionFilter", lawFindingRecords.map(item => item.jurisdiction));
    addFilterOptions("lawTopicFilter", lawFindingRecords.map(item => item.contract_topic));
    addFilterOptions("lawSeverityFilter", lawFindingRecords.map(item => item.severity));
    document.getElementById("lawSourceNotice").textContent =
        analysis.source_verification?.notice || "Retrieved legal text is evidence for review only; applicability is not established.";
    renderLawFindingList();

    const issueContainer = document.getElementById("lawIssues");
    issueContainer.replaceChildren();
    (analysis.issues_to_resolve || []).forEach(issue => {
        const item = document.createElement("article");
        item.className = "law-issue";
        lawText(item, "b", `${issue.severity || "Review"} · ${issue.title}`);
        lawText(item, "p", issue.recommended_action);
        issueContainer.appendChild(item);
    });
    if (!issueContainer.children.length) {
        lawText(issueContainer, "p", "No additional missing-term or conflict issue was identified by the extraction rules. This is not confirmation that the contract is complete.");
    }

    const sourceContainer = document.getElementById("lawSources");
    sourceContainer.replaceChildren();
    (analysis.legal_sources || []).forEach(record => {
        const section = document.createElement("article");
        section.className = "law-source";
        lawText(section, "h5", record.jurisdiction);
        lawText(section, "p", (record.regions || []).join(" · "));
        (record.sources || []).forEach(source => {
            const line = document.createElement("div");
            line.className = "law-source-item";
            appendOfficialLink(line, source.base_url || source.url, source.organization || source.name);
            lawText(line, "span", `Connector: ${source.connector_status || "manual_access_required"} · Retrieval: ${displaySourceStatus(source.retrieval_status || "not_attempted")}`);
            if (source.retrieval_method) lawText(line, "p", `Method: ${source.retrieval_method}`);
            if (source.coverage_limitations) lawText(line, "p", `Coverage: ${source.coverage_limitations}`);
            if (source.last_successful_retrieval_at) {
                lawText(line, "p", `Last successful retrieval: ${source.last_successful_retrieval_at}`);
            }
            if (source.last_error) lawText(line, "p", `Last source error: ${source.last_error}`);
            if (source.checked_at) {
                lawText(line, "span", `Portal checked at ${source.checked_at}; this does not verify a provision.`);
            }
            section.appendChild(line);
        });
        sourceContainer.appendChild(section);
    });
    if (!sourceContainer.children.length) {
        lawText(sourceContainer, "p", "No official source portal was selected because the contract did not provide a supported jurisdiction connection.");
    }

    const connectorContainer = document.getElementById("lawConnectors");
    connectorContainer.replaceChildren();
    (legalResearch.connectors || []).forEach(connector => {
        const card = document.createElement("article");
        card.className = "law-source";
        lawText(card, "h5", `${connector.organization} · ${connector.jurisdiction}`);
        lawText(card, "p", `Connector status: ${connector.connector_status} · Retrieval: ${displaySourceStatus(connector.retrieval_status)}`);
        if (connector.last_attempt_at) lawText(card, "p", `Last attempt: ${connector.last_attempt_at}`);
        if (connector.last_successful_retrieval_at) {
            lawText(card, "p", `Last successful retrieval: ${connector.last_successful_retrieval_at}`);
        }
        lawText(card, "p", `Persistent storage: ${connector.storage_status}`);
        lawText(card, "p", `Coverage: ${connector.coverage_limitations}`);
        if (connector.api_docs_url) appendOfficialLink(card, connector.api_docs_url, "Official API documentation");
        (connector.queries || []).forEach(query => {
            lawText(card, "p", `Search topic: ${query.contract_topic}; official-source query: ${query.query}`);
        });
        (connector.errors || []).forEach(error => {
            const message = typeof error === "string"
                ? error
                : `${error.status || "source_error"}: ${error.message || "No details returned."}${error.retry_after ? ` Retry-After: ${error.retry_after}` : ""}`;
            lawText(card, "p", `Source error: ${message}`);
        });
        connectorContainer.appendChild(card);
    });
    if (!connectorContainer.children.length) {
        lawText(connectorContainer, "p", "No live legal-source connector was selected for the contract evidence.");
    }

    const documentsContainer = document.getElementById("lawDocuments");
    documentsContainer.replaceChildren();
    (legalResearch.comparisons || []).forEach(comparison => {
        const card = document.createElement("article");
        card.className = "law-source law-document";
        lawText(card, "h5", comparison.legal_document_title);
        lawText(card, "p", `${comparison.legal_provision_reference} · ${comparison.contract_topic} · ${comparison.support_assessment.replaceAll("_", " ")}`);
        const sourceDocument = (legalResearch.documents || []).find(document =>
            document.provision_reference === comparison.legal_provision_reference
        );
        if (sourceDocument) {
            lawField(card, "Source and jurisdiction", `${sourceDocument.source_name} · ${sourceDocument.jurisdiction}`);
            lawField(card, "Instrument type and authority", `${sourceDocument.document_type} · ${sourceDocument.authority_status}`);
            lawField(card, "Effective/version dates", `Effective from: ${sourceDocument.effective_date || "not supplied"} · Version: ${sourceDocument.version_id} · Source as of: ${sourceDocument.source_as_of_date}`);
            lawField(card, "Retrieval and verification", `Retrieved: ${sourceDocument.retrieved_at} · Last verified: ${sourceDocument.last_verified_at} · ${displaySourceStatus(sourceDocument.currency_status)} · ${sourceDocument.verification_status}`);
            lawField(card, "Amendment/consolidation status", sourceDocument.amendment_repeal_status);
        }
        lawField(card, "Evidence-based relationship", comparison.explanation);
        lawField(card, "Contract excerpt", comparison.contract_excerpt);
        const legalText = document.createElement("details");
        lawText(legalText, "summary", "Show retrieved legal-source text");
        lawText(legalText, "blockquote", comparison.legal_excerpt);
        card.appendChild(legalText);
        lawField(card, "Facts still needed", (comparison.missing_facts || []).join("\n"));
        appendOfficialLink(
            card,
            comparison.official_source_url,
            sourceDocument && sourceDocument.source_id === "us_code"
                ? "Open official U.S. Code title XML download"
                : "Open exact official provision",
        );
        documentsContainer.appendChild(card);
    });
    if (!documentsContainer.children.length) {
        lawText(
            documentsContainer,
            "p",
            "No provision text was retrieved for this upload. Portal entries above are research starting points, not evidence that a specific law was checked."
        );
    }

    const jurisdictionSelect = document.getElementById("lawJurisdictionOverview");
    const previousJurisdiction = jurisdictionSelect.value;
    const supportedJurisdictions = [...new Set([
        ...jurisdictions.map(item => item.jurisdiction),
        ...(analysis.legal_sources || []).map(item => item.jurisdiction),
        ...parties.map(item => item.country)
    ].filter(Boolean))].sort();
    jurisdictionSelect.replaceChildren(new Option("All identified context", ""));
    supportedJurisdictions.forEach(value => jurisdictionSelect.add(new Option(value, value)));
    jurisdictionSelect.value = supportedJurisdictions.includes(previousJurisdiction)
        ? previousJurisdiction
        : "";
    renderJurisdictionSummary();
    activateLawTab("overview");
}

function displayValue(value) {
    if (value === null || value === undefined || value === "") {
        return "Not provided by analysis.";
    }
    if (Array.isArray(value)) {
        return value.length ? value.map(displayValue).join("; ") : "None returned.";
    }
    if (typeof value === "object") {
        return Object.entries(value)
            .map(([key, item]) => `${key.replaceAll("_", " ")}: ${displayValue(item)}`)
            .join(" · ");
    }
    return String(value);
}

function appendFinancialRecords(container, records, preferredFields, emptyMessage) {
    container.replaceChildren();
    const entries = Array.isArray(records) ? records : [];
    if (!entries.length && emptyMessage) {
        lawText(container, "p", emptyMessage, "empty-state");
    }
    entries.forEach(record => {
        const card = document.createElement("article");
        card.className = "financial-item";
        if (typeof record !== "object" || record === null) {
            lawText(card, "p", displayValue(record));
        } else {
            const title = record.category || record.type || record.clause || record.name || record.label;
            if (title) {
                lawText(card, "h4", title);
            }
            const shown = new Set();
            preferredFields.forEach(field => {
                if (record[field] !== undefined && record[field] !== null && record[field] !== "") {
                    lawField(card, field.replaceAll("_", " "), displayValue(record[field]));
                    shown.add(field);
                }
            });
            Object.entries(record).forEach(([field, value]) => {
                if (!shown.has(field) && field !== "category" && field !== "type"
                    && field !== "clause" && field !== "name" && field !== "label"
                    && value !== null && value !== undefined && value !== "") {
                    lawField(card, field.replaceAll("_", " "), displayValue(value));
                }
            });
        }
        container.appendChild(card);
    });
}

function renderFinancialImpact(financial) {
    const unavailable = document.getElementById("financialUnavailable");
    const content = document.getElementById("financialContent");
    if (!financial || typeof financial !== "object") {
        unavailable.textContent = "Financial impact results were not included in the API response.";
        unavailable.hidden = false;
        content.hidden = true;
        return;
    }

    unavailable.hidden = true;
    content.hidden = false;
    const currency = financial.exposure_currency || financial.contract_value?.currency;
    const amount = value => {
        if (value === null || value === undefined || value === "") return "Not calculated";
        const numeric = Number(value);
        return Number.isFinite(numeric)
            ? `${currency ? `${currency} ` : ""}${numeric.toLocaleString()}`
            : displayValue(value);
    };
    document.getElementById("financialRisk").textContent =
        financial.financial_risk || "Not provided";
    document.getElementById("financialRiskReason").textContent =
        financial.financial_risk_reason || "No explanation returned.";
    const contractValue = financial.contract_value;
    document.getElementById("financialContractValue").textContent =
        contractValue === null || contractValue === undefined
            ? "Not identified"
            : typeof contractValue === "object"
                ? contractValue.amount === null || contractValue.amount === undefined
                    ? displayValue(contractValue)
                    : `${contractValue.currency ? `${contractValue.currency} ` : ""}${Number(contractValue.amount).toLocaleString()}`
                : displayValue(contractValue);
    document.getElementById("financialExposure").textContent =
        amount(financial.total_calculated_exposure);
    document.getElementById("financialExposureRatio").textContent =
        financial.exposure_ratio === null || financial.exposure_ratio === undefined
            ? "No comparable ratio calculated"
        : `Exposure ratio: ${Number(financial.exposure_ratio) * 100}%`;
    document.getElementById("financialTermCount").textContent =
        financial.financial_terms_detected ?? (financial.items || []).length;

    const items = Array.isArray(financial.items) ? financial.items : [];
    document.getElementById("financialItemsEmpty").hidden = items.length > 0;
    appendFinancialRecords(
        document.getElementById("financialItems"),
        items,
        ["amounts", "percentages", "durations", "evidence", "party_context", "calculation_status", "calculated_exposure", "assumptions"],
        null
    );
    appendFinancialRecords(
        document.getElementById("financialCalculations"),
        [
            ...(Array.isArray(financial.calculations) ? financial.calculations : []),
            ...(Array.isArray(financial.scenarios) ? financial.scenarios : [])
        ],
        ["formula", "assumptions", "amount", "currency", "estimated_impact", "conditional", "note", "evidence", "basis"],
        "No calculations or scenarios were returned by the engine."
    );
    const limitations = [
        ...(financial.risk_factors || []),
        ...(financial.uncertainties || []),
        ...(financial.limitations || []),
        financial.analysis_method ? `Analysis method: ${financial.analysis_method}` : null
    ].filter(Boolean);
    appendFinancialRecords(
        document.getElementById("financialUncertainties"),
        limitations,
        ["source_text", "reason"],
        "No uncertainties or limitations were returned by the engine."
    );
}

function renderResults(data) {

    currentAnalysis = data;
    const contractType = data.contract_type?.category || "Other/Unknown";
    const warnings = data.warnings || [];
    const extraction = data.extraction_summary || {};
    const ocrPages = extraction.pages_ocr_processed || [];
    const extractionInfo = ocrPages.length
        ? `OCR processed page${ocrPages.length === 1 ? "" : "s"} ${ocrPages.join(", ")}`
        : `${extraction.method || "text"} extraction`;

    const fileName = data.filename || "Contract Analysis";
    document.getElementById("fileName").textContent = fileName;
    document.getElementById("topbarContractName").textContent = fileName;
    document.getElementById("recentContractName").textContent = fileName;
    document.getElementById("recentContractMeta").textContent =
        `${contractType} · latest analysis in this session`;
    document.getElementById("recentEmpty").hidden = true;
    document.getElementById("recentCurrent").hidden = false;
    document.getElementById("overviewContractType").textContent = contractType;
    document.getElementById("overviewDocumentStatus").textContent = "Analysis complete";
    document.getElementById("overviewDocumentStatus").className = "status-pill status-success";
    document.getElementById("overviewContractType").textContent = contractType;
    document.getElementById("overviewExtraction").textContent = extractionInfo;
    document.getElementById("overviewLegalCount").textContent =
        Array.isArray(data.legal_analysis?.findings) ? data.legal_analysis.findings.length : "Unavailable";
    const warningContainer = document.getElementById("analysisWarnings");
    warningContainer.replaceChildren();
    warnings.forEach(warning => lawText(warningContainer, "p", warning));
    warningContainer.hidden = warnings.length === 0;


    document.getElementById("fileInfo").textContent =
        `${data.text_length || 0} characters analyzed • Contract type: ${contractType} • ${extractionInfo}${warnings.length ? ` • ${warnings.join(" ")}` : ""}`;


    document.getElementById("overallRisk").textContent =
        data.risk?.overall_risk || "â€”";

    document.getElementById("overallRisk").className =
        `risk ${riskClass(data.risk?.overall_risk)}`;


    document.getElementById("riskScore").textContent =
        data.risk?.risk_score ?? "â€”";


    const riskModelAvailable = Boolean(
        data.risk?.model_prediction
        && data.risk.model_prediction !== "Unavailable"
    );
    document.getElementById("riskModel").textContent = riskModelAvailable
        ? `TinyBERT prediction: ${data.risk.model_prediction} · ${data.risk.confidence ?? "Not available"}% confidence`
        : "Rule-based risk score · TinyBERT prediction unavailable";


    const compliance =
        data.compliance || [];

    document.getElementById("compliance").textContent =
        compliance.length;


    const complianceModelAvailable = Boolean(
        data.compliance_prediction?.status
        && data.compliance_prediction.status !== "Unavailable"
    );
    document.getElementById("complianceModel").textContent = complianceModelAvailable
        ? `TinyBERT prediction: ${data.compliance_prediction.status} · ${data.compliance_prediction.confidence ?? "Not available"}% confidence`
        : "Rule-based term checks shown below · TinyBERT prediction unavailable";


    const clauses =
        data.clauses || [];


    document.getElementById("clauseCount").textContent =
        clauses.length;


    document.getElementById("textLength").textContent =
        `${(data.text_length || 0).toLocaleString()} characters`;

    document.getElementById("overviewDocumentStatus").title =
        `${clauses.length} clauses, ${compliance.length} contractual-term checks`;
    document.getElementById("extractionTitle").textContent = fileName;
    document.getElementById("extractionContractType").textContent = contractType;
    document.getElementById("extractionCharacters").textContent =
        `${(data.text_length || 0).toLocaleString()} characters`;
    document.getElementById("extractionMethod").textContent = extractionInfo;
    document.getElementById("extractionWarnings").textContent =
        warnings.length ? warnings.join(" ") : "No extraction warnings were returned.";

    document.getElementById("riskPageLevel").textContent = data.risk?.overall_risk || "Not available";
    document.getElementById("riskPageScore").textContent =
        data.risk?.risk_score === undefined ? "No score returned" : `Risk score: ${data.risk.risk_score}`;
    document.getElementById("riskPageModelLabel").textContent = riskModelAvailable
        ? "TinyBERT model prediction"
        : "Assessment basis";
    document.getElementById("riskPageModel").textContent = riskModelAvailable
        ? data.risk.model_prediction
        : "Rule-based";
    document.getElementById("riskPageConfidence").textContent = riskModelAvailable
        ? `Confidence: ${data.risk.confidence ?? "Not returned"}%`
        : "Overall risk above is scored from the contract-term checks.";

    clauseRecords = Array.isArray(clauses) ? clauses : [];
    complianceRecords = Array.isArray(compliance) ? compliance : [];
    riskRecords = Array.isArray(data.explanations) ? data.explanations : [];
    populateFilter("clauseCategoryFilter", clauseRecords.map(item => item.type), "All categories");
    populateFilter("complianceStatusFilter", complianceRecords.map(item => item.status), "All statuses");
    populateFilter("riskSeverityFilter", riskRecords.map(item => item.risk), "All severities");
    populateFilter("riskCategoryFilter", riskRecords.map(item => item.category || item.clause), "All categories");

    renderCompliance(compliance);

    renderClauses(clauses);

    renderExplanations(
        data.explanations || []
    );

    renderNegotiations(
        data.negotiation || []
    );

    renderLawAnalysis(data.legal_analysis);
    renderFinancialImpact(data.financial_impact);

    document.getElementById("rawOutput").textContent =
        JSON.stringify(data, null, 2);


    resultsPage.hidden = false;
    document.getElementById("analyzeBtn").textContent = "Analyze another contract";
    document.getElementById("extractionStatus").textContent = "Analysis complete";
    showToast("Contract analysis is ready.");

    navigateTo("overview");

}


async function analyzeContract(file) {

    hideError();

    if (!file) {
        return;
    }

    if (!dashboardReady || !csrfToken) {
        showError("Finishing secure sign-in. Please wait a moment and try again.");
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
                    credentials: "same-origin",
                    headers: {
                        "X-CSRF-Token": csrfToken
                    },
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
            if (response.status === 401) {
                window.location.replace("/login?expired=1");
                return;
            }

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
        if (currentAnalysis) {
            renderLawAnalysis(currentAnalysis.legal_analysis);
        } else {
            document.getElementById("lawLoading").hidden = true;
            document.getElementById("lawContent").hidden = true;
            document.getElementById("lawEmpty").hidden = false;
            document.getElementById("lawError").hidden = true;
            document.getElementById("lawAnalysisBadge").textContent = "Awaiting analysis";
        }

    } finally {

        setLoading(false);

    }

}


async function initializeDashboard() {
    statusText.textContent = "Checking backend...";
    statusDot.className = "";

    const response = await fetch(`${API_BASE}/api/auth/status`, {
        credentials: "same-origin",
        cache: "no-store"
    });
    if (!response.ok) {
        throw new Error("Could not verify your sign-in.");
    }

    const status = await response.json();
    if (!status.authenticated) {
        window.location.replace("/login");
        return;
    }

    csrfToken = status.csrf_token;
    document.getElementById("profileName").textContent =
        status.user?.username || "Signed in";
    dashboardReady = true;
    chooseBtn.disabled = false;
    fileInput.disabled = false;
    await checkBackend();
    setInterval(checkBackend, 10000);
}


document.getElementById("logoutBtn").addEventListener("click", async () => {
    const button = document.getElementById("logoutBtn");
    button.disabled = true;
    try {
        const response = await fetch(`${API_BASE}/api/auth/logout`, {
            method: "POST",
            credentials: "same-origin",
            headers: { "X-CSRF-Token": csrfToken }
        });
        if (response.status === 401) {
            window.location.replace("/login?expired=1");
            return;
        }
        if (!response.ok) {
            throw new Error("Sign out failed. Please try again.");
        }
        window.location.replace("/login");
    } catch (error) {
        button.disabled = false;
        showError(error.message || "Sign out failed. Please try again.");
    }
});


chooseBtn.addEventListener(
    "click",
    event => {

        event.stopPropagation();

        fileInput.click();

    }
);


dropZone.addEventListener(
    "click",
    event => {
        if (event.target.id !== "chooseBtn") fileInput.click();
    }
);

dropZone.addEventListener("keydown", event => {
    if (event.target !== dropZone || (event.key !== "Enter" && event.key !== " ")) return;
    event.preventDefault();
    fileInput.click();
});


fileInput.addEventListener(
    "change",
    () => {

        const file =
            fileInput.files[0];

        if (file) selectContract(file);
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

        if (file) selectContract(file);

    }
);

document.getElementById("analyzeBtn").addEventListener("click", () => {
    if (selectedFile) analyzeContract(selectedFile);
});
document.getElementById("clearSelectedFile").addEventListener("click", clearSelectedContract);


document.getElementById(
    "newContract"
).addEventListener(
    "click",
    () => {
        hideError();
        navigateTo("contract-analysis");
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


[
    "lawSearch",
    "lawPartyFilter",
    "lawJurisdictionFilter",
    "lawTopicFilter",
    "lawSeverityFilter"
].forEach(id => {
    document.getElementById(id).addEventListener("input", renderLawFindingList);
    document.getElementById(id).addEventListener("change", renderLawFindingList);
});

document.getElementById("clauseSearch").addEventListener("input", () => renderClauses(clauseRecords));
document.getElementById("clauseCategoryFilter").addEventListener("change", () => renderClauses(clauseRecords));
document.getElementById("riskSeverityFilter").addEventListener("change", () => renderExplanations(riskRecords));
document.getElementById("riskCategoryFilter").addEventListener("change", () => renderExplanations(riskRecords));
document.getElementById("complianceSearch").addEventListener("input", () => renderCompliance(complianceRecords));
document.getElementById("complianceStatusFilter").addEventListener("change", () => renderCompliance(complianceRecords));

initializeDashboard().catch(error => {
    statusDot.className = "offline";
    statusText.textContent = "Backend Offline";
    chooseBtn.disabled = true;
    fileInput.disabled = true;
    showError(error.message || "Could not initialize the dashboard.");
});
