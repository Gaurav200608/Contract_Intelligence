const API_BASE = "http://127.0.0.1:8000";

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
