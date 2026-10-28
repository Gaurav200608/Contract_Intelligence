const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const test = require("node:test");

class MockElement {
    constructor(id = "") {
        this.id = id;
        this.disabled = false;
        this.hidden = false;
        this.value = "";
        this.files = [];
        this.children = [];
        this.listeners = {};
        this.className = "";
        this.dataset = {};
        this.attributes = {};
        this.classList = {
            add: name => {
                if (!this.className.split(/\s+/).includes(name)) {
                    this.className = `${this.className} ${name}`.trim();
                }
            },
            remove: name => {
                this.className = this.className.split(/\s+/).filter(item => item !== name).join(" ");
            },
            toggle: (name, force) => {
                const has = this.className.split(/\s+/).includes(name);
                const add = force === undefined ? !has : force;
                if (add) this.classList.add(name);
                else this.classList.remove(name);
                return add;
            },
            contains: name => this.className.split(/\s+/).includes(name)
        };
    }

    set innerHTML(value) {
        this._innerHTML = value;
        if (value === "") {
            this.children = [];
        }
    }

    get innerHTML() {
        return this._innerHTML || "";
    }

    get options() {
        return this.children;
    }

    addEventListener(name, handler) {
        this.listeners[name] = handler;
    }

    appendChild(child) {
        this.children.push(child);
        return child;
    }

    append(...children) {
        this.children.push(...children);
    }

    replaceChildren(...children) {
        this.children = children;
    }

    add(option) {
        this.children.push(option);
    }

    setAttribute(name, value) {
        this.attributes[name] = value;
    }

    removeAttribute(name) {
        delete this.attributes[name];
    }

    querySelector(selector) {
        if (selector === "span") {
            if (!this._span) this._span = new MockElement();
            return this._span;
        }
        return null;
    }

    focus() {}
    click() {}
}

const lawFinding = {
    finding_id: "fixture-finding",
    title: "Contractual data protection and transfers term identified",
    affected_party: "Example GmbH",
    affected_party_role: "Provider",
    jurisdiction: "Germany",
    contract_topic: "Data protection and transfers",
    contract_clause_text: "Provider processes personal data in India.",
    contract_clause_reference: null,
    applicability_reason: "Party incorporation and data location are stated.",
    legal_provision_name: null,
    legal_provision_reference: null,
    legal_explanation: "Contract text only; no statute is asserted.",
    legal_boundary: "Mandatory rules require fact-specific review.",
    potential_conflict: null,
    missing_protection: null,
    severity: "Medium",
    confidence: 0.76,
    recommended_action: "Confirm data flows with counsel.",
    official_source_url: "https://www.gesetze-im-internet.de/",
    source_verification_status: "not_checked",
    source_verified_at: null,
    requires_lawyer_review: true
};

function createHarness() {
    const html = fs.readFileSync("index.html", "utf8");
    const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
    const elements = new Map(ids.map(id => [id, new MockElement(id)]));
    const pages = [...html.matchAll(/<section\b[^>]*id="([^"]+)"[^>]*data-page-container="([^"]+)"/g)].map(match => {
        const element = elements.get(match[1]);
        element.dataset.pageContainer = match[2];
        return element;
    });
    const navLinks = [...html.matchAll(/<a\b[^>]*data-page="([^"]+)"/g)].map(match => {
        const link = new MockElement();
        link.dataset.page = match[1];
        return link;
    });
    const navigateButtons = [...html.matchAll(/<button\b[^>]*data-navigate="([^"]+)"/g)].map(match => {
        const button = new MockElement();
        button.dataset.navigate = match[1];
        return button;
    });
    const lawTabs = [...html.matchAll(/<button\b[^>]*data-law-tab="([^"]+)"/g)].map(match => {
        const button = new MockElement();
        button.dataset.lawTab = match[1];
        return button;
    });
    const lawPanels = [...html.matchAll(/<section\b[^>]*data-law-panel="([^"]+)"/g)].map(match => {
        const panel = new MockElement();
        panel.dataset.lawPanel = match[1];
        return panel;
    });
    const windowListeners = {};
    let hashValue = "";
    const location = { origin: "http://localhost:8000", replace() {} };
    Object.defineProperty(location, "hash", {
        get() { return hashValue; },
        set(value) { hashValue = value.startsWith("#") ? value : `#${value}`; }
    });
    const windowObject = {
        location,
        scrollTo() {},
        addEventListener(name, handler) {
            windowListeners[name] = handler;
        }
    };
    const body = new MockElement("body");
    const localStorage = {
        values: new Map(),
        getItem(key) { return this.values.get(key) || null; },
        setItem(key, value) { this.values.set(key, value); }
    };
    elements.get("sidebar").classList.remove = name => {
        elements.get("sidebar").className = elements.get("sidebar").className.split(/\s+/).filter(item => item !== name).join(" ");
    };
    elements.get("sidebar").classList.toggle = (name, force) => {
        const sidebar = elements.get("sidebar");
        const has = sidebar.className.split(/\s+/).includes(name);
        const add = force === undefined ? !has : force;
        if (add) sidebar.classList.add(name);
        else sidebar.classList.remove(name);
        return add;
    };
    let analysisPayload = {
        filename: "uploaded-contract.pdf",
        text_length: 100,
        contract_type: { category: "Service agreement" },
        clauses: [],
        compliance: [],
        risk: { overall_risk: "Low", risk_score: 1 },
        compliance_prediction: {},
        explanations: [],
        negotiation: [],
        financial_impact: {
            financial_risk: "Medium",
            financial_risk_reason: "A stated exposure requires review.",
            contract_value: { amount: 10000, currency: "USD" },
            total_calculated_exposure: 2500,
            exposure_currency: "USD",
            exposure_ratio: 0.25,
            financial_terms_detected: 1,
            items: [{
                term_type: "penalty",
                evidence: "A penalty of USD 2,500 applies.",
                amounts: [{ amount: 2500, currency: "USD" }],
                percentages: [],
                durations: [],
                party_context: "not explicit",
                calculation_status: "stated_amount",
                calculated_exposure: 2500,
                assumptions: []
            }],
            calculations: [],
            scenarios: [],
            risk_factors: [],
            uncertainties: [],
            limitations: ["Heuristic result; review the contract."],
            analysis_method: "Evidence-linked rules"
        },
        legal_analysis: {
            status: "informational",
            analysis_status: "complete_with_review_required",
            contract_type: "Service agreement",
            overview: {
                parties: [{
                    name: "Example GmbH",
                    role: "Provider",
                    country: "Germany",
                    country_evidence: "Example GmbH incorporated in Germany."
                }],
                governing_law: {
                    clause_found: true,
                    jurisdiction: "Germany",
                    evidence: "This Agreement is governed by German law."
                },
                dispute_resolution: {
                    summary: "Arbitration detected.",
                    court_jurisdiction_evidence: [],
                    arbitration_evidence: ["Arbitration seated in Berlin."]
                },
                potential_jurisdictions: [{
                    jurisdiction: "Germany",
                    region: null,
                    applicability_reason: "governing_law"
                }],
                missing_or_uncertain_information: []
            },
            company_analyses: [{
                name: "Example GmbH",
                role: "Provider",
                country: "Germany",
                country_evidence: "Example GmbH incorporated in Germany.",
                contractual_obligations: [{
                    topic: "Data protection and transfers",
                    contract_clause_text: lawFinding.contract_clause_text
                }],
                potential_statutory_obligations: [],
                rights_and_boundaries: ["Contract-only evidence."]
            }],
            findings: [lawFinding],
            issues_to_resolve: [],
            legal_sources: [{
                jurisdiction: "Germany",
                regions: ["Germany (national law)"],
                sources: [{
                    name: "Gesetze im Internet",
                    url: lawFinding.official_source_url,
                    verification_status: "not_checked"
                }]
            }],
            source_verification: {
                notice: "No legal provision is considered verified."
            }
        }
    };
    let holdAnalysis = false;
    let apiFailure = false;
    let releaseAnalysis;
    const fetchCalls = [];
    const context = {
        document: {
            getElementById(id) {
                if (!elements.has(id)) elements.set(id, new MockElement(id));
                return elements.get(id);
            },
            querySelectorAll(selector) {
                if (selector === "[data-page-container]") return pages;
                if (selector === "[data-page]") return navLinks;
                if (selector === "[data-navigate]") return navigateButtons;
                if (selector === "[data-law-tab]") return lawTabs;
                if (selector === "[data-law-panel]") return lawPanels;
                return [];
            },
            addEventListener() {},
            body,
            createElement() {
                return new MockElement();
            }
        },
        window: windowObject,
        localStorage,
        Option: class Option {
            constructor(text, value) {
                this.textContent = text;
                this.value = value;
            }
        },
        FormData: class FormData {
            append(key, value) {
                this[key] = value;
            }
        },
        fetch: async (url, options = {}) => {
            fetchCalls.push({ url, options });
            if (url.endsWith("/api/auth/status")) {
                return { ok: true, status: 200, json: async () => ({ authenticated: true, csrf_token: "csrf" }) };
            }
            if (url.endsWith("/api/health")) {
                return { ok: true, status: 200 };
            }
            if (url.endsWith("/api/analyze")) {
                if (holdAnalysis) {
                    await new Promise(resolve => {
                        releaseAnalysis = resolve;
                    });
                }
                if (apiFailure) {
                    return {
                        ok: false,
                        status: 422,
                        json: async () => ({ detail: "Document extraction failed." })
                    };
                }
                return { ok: true, status: 200, json: async () => analysisPayload };
            }
            throw new Error(`Unexpected request ${url}`);
        },
        setInterval() {},
        setTimeout() { return 1; },
        clearTimeout() {},
        console
    };
    vm.runInNewContext(
        fs.readFileSync("app.js", "utf8"),
        context,
        { filename: "app.js" }
    );
    return {
        elements,
        fetchCalls,
        navLinks,
        lawTabs,
        lawPanels,
        body,
        localStorage,
        pages,
        windowListeners,
        window: windowObject,
        setPayload(payload) {
            analysisPayload = payload;
        },
        failAnalysis() {
            apiFailure = true;
        },
        pauseAnalysis() {
            holdAnalysis = true;
        },
        resumeAnalysis(payload) {
            analysisPayload = payload || analysisPayload;
            holdAnalysis = false;
            releaseAnalysis();
        }
    };
}

function startAnalysis(harness, name, size = 1024) {
    const input = harness.elements.get("fileInput");
    input.files = [{ name, size }];
    input.listeners.change();
    assert.equal(harness.elements.get("selectedFile").hidden, false);
    assert.equal(harness.elements.get("analyzeBtn").disabled, false);
    harness.elements.get("analyzeBtn").listeners.click();
}

function textInTree(element) {
    return [
        element.textContent || "",
        ...element.children.flatMap(child => textInTree(child))
    ].join(" ");
}

test("uploaded API Law Analysis renders actual evidence, filters and official sources", async () => {
    const harness = createHarness();
    await new Promise(resolve => setTimeout(resolve, 0));
    startAnalysis(harness, "uploaded-contract.pdf");
    await new Promise(resolve => setTimeout(resolve, 10));

    const analysisCall = harness.fetchCalls.find(call => call.url.endsWith("/api/analyze"));
    assert.ok(analysisCall);
    assert.equal(analysisCall.options.method, "POST");
    assert.equal(analysisCall.options.headers["X-CSRF-Token"], "csrf");
    assert.equal(harness.elements.get("lawContent").hidden, false);
    assert.equal(harness.elements.get("lawFindings").children.length, 1);
    assert.equal(harness.elements.get("lawSources").children.length, 1);
    assert.equal(harness.elements.get("lawAnalysisBadge").textContent, "Review required");
    assert.equal(harness.elements.get("lawJurisdictionFilter").children.some(option => option.value === "Germany"), true);
    assert.equal(harness.elements.get("financialContent").hidden, false);
    assert.equal(harness.elements.get("financialContractValue").textContent, "USD 10,000");
    assert.equal(harness.elements.get("financialExposure").textContent, "USD 2,500");
    assert.equal(harness.elements.get("riskPageModelLabel").textContent, "Assessment basis");
    assert.equal(harness.elements.get("riskPageModel").textContent, "Rule-based");
    assert.match(harness.elements.get("riskPageConfidence").textContent, /contract-term checks/);
    assert.match(harness.elements.get("riskModel").textContent, /Rule-based risk score/);
    assert.match(harness.elements.get("complianceModel").textContent, /Rule-based term checks/);
    assert.equal(harness.elements.get("topbarContractName").textContent, "uploaded-contract.pdf");
    assert.equal(harness.window.location.hash, "#overview");
    assert.equal(harness.elements.get("recentCurrent").hidden, false);
    assert.equal(harness.elements.get("recentEmpty").hidden, true);
    assert.match(textInTree(harness.elements.get("lawSources")), /Not verified/);

    const jurisdiction = harness.elements.get("lawJurisdictionOverview");
    jurisdiction.value = "Germany";
    jurisdiction.listeners.change({ target: jurisdiction });
    assert.match(textInTree(harness.elements.get("lawCountrySummary")), /Germany/);
    assert.equal(harness.elements.get("lawJurisdictionFilter").value, "Germany");

    harness.elements.get("lawSearch").value = "not in this contract";
    harness.elements.get("lawSearch").listeners.input();
    assert.equal(harness.elements.get("lawFindings").children.length, 0);
    assert.equal(harness.elements.get("lawNoFindings").hidden, false);
});

test("retrieved source excerpts are rendered as text and retain official citation metadata", async () => {
    const harness = createHarness();
    await new Promise(resolve => setTimeout(resolve, 0));
    const sourceExcerpt = "<img src=x onerror=alert(1)> synthetic source text";
    harness.setPayload({
        filename: "uploaded-contract.pdf",
        clauses: [],
        compliance: [],
        risk: { overall_risk: "Low", risk_score: 1 },
        explanations: [],
        negotiation: [],
        financial_impact: {},
        legal_analysis: {
            analysis_status: "complete_with_review_required",
            contract_type: "Service agreement",
            overview: {
                parties: [],
                governing_law: {},
                dispute_resolution: {},
                potential_jurisdictions: [{
                    jurisdiction: "United States of America",
                    applicability_reason: "explicit contract mention"
                }],
                missing_or_uncertain_information: []
            },
            findings: [],
            company_analyses: [],
            issues_to_resolve: [],
            legal_sources: [],
            source_verification: {},
            legal_research: {
                status: "retrieved",
                connectors: [{
                    source_id: "us_ecfr",
                    organization: "Office of the Federal Register",
                    jurisdiction: "United States — federal",
                    connector_status: "operational",
                    retrieval_status: "retrieved",
                    queries: [{ contract_topic: "Data protection", query: "data privacy" }],
                    errors: [],
                    documents: [],
                    coverage_limitations: "Federal regulations only.",
                    storage_status: "available"
                }],
                documents: [{
                    source_id: "us_ecfr",
                    source_name: "Office of the Federal Register",
                    jurisdiction: "United States — federal",
                    document_type: "regulation",
                    authority_status: "Federal regulation; applicability not assessed.",
                    document_id: "45 CFR 164.520",
                    provision_reference: "45 CFR 164.520",
                    title: "Synthetic parser fixture section",
                    canonical_url: "https://www.ecfr.gov/current/title-45/section-164.520",
                    source_text: sourceExcerpt,
                    contract_topic: "Data protection",
                    contract_excerpt: "<script>contract-derived text</script>",
                    publication_date: null,
                    adoption_date: null,
                    entry_into_force_date: null,
                    effective_date: "2024-06-25",
                    version_id: "2026-10-23",
                    version_status: "current consolidated text",
                    source_as_of_date: "2026-10-23",
                    currency_status: "retrieved_as_of_source_date_not_guaranteed_current",
                    amendment_repeal_status: "not evaluated",
                    retrieved_at: "2026-10-28T00:00:00+00:00",
                    last_verified_at: "2026-10-28T00:00:00+00:00",
                    source_language: "en",
                    authenticity: "official source API",
                    verification_status: "official_text_retrieved; applicability_not_verified",
                    source_endpoint: "https://www.ecfr.gov/api/versioner/v1/full/2026-10-23/title-45.xml",
                    source_score: 10,
                    source_match_excerpt: "Synthetic search excerpt.",
                    provision_text_truncated: false
                }],
                comparisons: [{
                    contract_topic: "Data protection",
                    contract_excerpt: "<script>contract-derived text</script>",
                    contract_clause_reference: null,
                    legal_document_title: "Synthetic parser fixture section",
                    legal_provision_reference: "45 CFR 164.520",
                    legal_excerpt: sourceExcerpt,
                    official_source_url: "https://www.ecfr.gov/current/title-45/section-164.520",
                    relationship: "official_full_text_retrieved_as_a_search_candidate",
                    support_assessment: "insufficient_evidence",
                    explanation: "Search relevance only.",
                    missing_facts: ["Applicability has not been determined."]
                }],
                query_disclosure: {
                    contract_text_sent: false,
                    party_names_sent: false,
                    filename_sent: false
                },
                historical_law_status: "Contract effective date not established.",
                storage: { backend: "SQLite", status: "available", version_retention: "Versioned" },
                limitations: []
            }
        }
    });
    startAnalysis(harness, "uploaded-contract.pdf");
    await new Promise(resolve => setTimeout(resolve, 10));

    const content = harness.elements.get("lawDocuments");
    assert.equal(content.children.length, 1);
    assert.match(textInTree(content), /45 CFR 164\.520/);
    assert.match(textInTree(content), /2026-10-23/);
    assert.match(textInTree(content), /insufficient evidence/);
    assert.match(textInTree(content), /<img src=x onerror=alert\(1\)>/);
    assert.match(textInTree(content), /<script>contract-derived text<\/script>/);
    assert.equal(content.children[0].innerHTML, "");
});

test("contract intake waits for explicit confirmation and rejects unsupported files", async () => {
    const harness = createHarness();
    await new Promise(resolve => setTimeout(resolve, 0));
    const input = harness.elements.get("fileInput");
    input.files = [{ name: "notes.txt", size: 20 }];
    input.listeners.change();
    assert.equal(harness.elements.get("error").hidden, false);
    assert.match(harness.elements.get("error").textContent, /Only PDF and DOCX/);
    assert.equal(harness.fetchCalls.some(call => call.url.endsWith("/api/analyze")), false);

    input.files = [{ name: "large.pdf", size: 101 * 1024 * 1024 }];
    input.listeners.change();
    assert.match(harness.elements.get("error").textContent, /100 MB/);
    assert.equal(harness.fetchCalls.some(call => call.url.endsWith("/api/analyze")), false);

    input.files = [{ name: "selected.docx", size: 1000 }];
    input.listeners.change();
    assert.equal(harness.elements.get("selectedFileName").textContent, "selected.docx");
    assert.equal(harness.fetchCalls.some(call => call.url.endsWith("/api/analyze")), false);
});

test("sidebar routing keeps exactly one page visible and handles browser history navigation", async () => {
    const harness = createHarness();
    await new Promise(resolve => setTimeout(resolve, 0));
    assert.equal(harness.pages.filter(page => !page.hidden).length, 1);
    assert.equal(harness.pages.find(page => !page.hidden).dataset.pageContainer, "overview");

    const routeNames = [...new Set(harness.navLinks.map(link => link.dataset.page))];
    for (const route of routeNames) {
        harness.window.location.hash = `#${route}`;
        harness.windowListeners.hashchange();
        assert.equal(harness.pages.filter(page => !page.hidden).length, 1);
        assert.equal(harness.pages.find(page => !page.hidden).dataset.pageContainer, route);
        assert.equal(harness.navLinks.find(link => link.dataset.page === route).attributes["aria-current"], "page");
    }

    harness.window.location.hash = "#law-jurisdiction";
    harness.windowListeners.hashchange();
    assert.equal(harness.pages.filter(page => !page.hidden).length, 1);
    assert.equal(harness.pages.find(page => !page.hidden).dataset.pageContainer, "law-analysis");

    const lawTabs = harness.lawTabs;
    lawTabs[1].listeners.click();
    assert.equal(harness.lawPanels.find(panel => !panel.hidden).dataset.lawPanel, "companies");
    assert.equal(lawTabs[1].attributes["aria-selected"], "true");
    lawTabs[1].listeners.keydown({ key: "ArrowRight", preventDefault() {} });
    assert.equal(harness.lawPanels.find(panel => !panel.hidden).dataset.lawPanel, "findings");

    harness.elements.get("sidebarCollapse").listeners.click();
    assert.equal(harness.body.classList.contains("sidebar-collapsed"), true);
    assert.equal(harness.localStorage.getItem("contract-intelligence-sidebar"), "collapsed");
    harness.elements.get("sidebarCollapse").listeners.click();
    assert.equal(harness.body.classList.contains("sidebar-collapsed"), false);
});

test("clause, risk and compliance filters render only matching API records", async () => {
    const harness = createHarness();
    await new Promise(resolve => setTimeout(resolve, 0));
    harness.setPayload({
        filename: "filter-contract.pdf",
        text_length: 30,
        clauses: [
            { type: "Payment", title: "Payment terms", text: "Net 30 days.", reference: "Section 2" },
            { type: "Liability", title: "Liability cap", text: "Liability is limited.", confidence: 87 }
        ],
        compliance: [
            { clause: "Payment", status: "Compliant", risk: "Low", requirement: "Payment terms", text: "Net 30." },
            { clause: "Liability", status: "Missing", risk: "High", requirement: "Cap", text: "No cap found." }
        ],
        risk: { overall_risk: "Medium", risk_score: 4 },
        explanations: [
            { clause: "Payment", risk: "Low", reason: "Payment term found.", impact: "Defined.", recommendation: "Review." },
            { clause: "Liability", risk: "High", reason: "Cap absent.", impact: "Exposure.", recommendation: "Clarify." }
        ],
        negotiation: [{
            clause: "Liability",
            priority: "High",
            suggestion: "Confirm the scope of the limitation.",
            suggested_wording: "The parties will define an agreed cap."
        }]
    });
    startAnalysis(harness, "filter-contract.pdf");
    await new Promise(resolve => setTimeout(resolve, 10));

    assert.equal(harness.elements.get("clauses").children.length, 2);
    harness.elements.get("clauseCategoryFilter").value = "Payment";
    harness.elements.get("clauseCategoryFilter").listeners.change();
    assert.equal(harness.elements.get("clauses").children.length, 1);
    assert.equal(harness.elements.get("clauses").children[0].innerHTML.includes("Section 2"), true);

    assert.equal(harness.elements.get("complianceTable").children.length, 2);
    harness.elements.get("complianceStatusFilter").value = "Missing";
    harness.elements.get("complianceStatusFilter").listeners.change();
    assert.equal(harness.elements.get("complianceTable").children.length, 1);

    assert.equal(harness.elements.get("explanations").children.length, 2);
    harness.elements.get("riskSeverityFilter").value = "High";
    harness.elements.get("riskSeverityFilter").listeners.change();
    assert.equal(harness.elements.get("explanations").children.length, 1);
    assert.match(textInTree(harness.elements.get("explanations").children[0]), /Liability is limited/);
    assert.match(harness.elements.get("negotiations").children[0].innerHTML, /review draft/);
});

test("missing Law Analysis response shows a visible degraded/error state", async () => {
    const harness = createHarness();
    await new Promise(resolve => setTimeout(resolve, 0));
    harness.setPayload({
        filename: "legacy-response.pdf",
        text_length: 1,
        clauses: [],
        compliance: [],
        risk: {},
        compliance_prediction: {},
        explanations: [],
        negotiation: []
    });
    startAnalysis(harness, "legacy-response.pdf");
    await new Promise(resolve => setTimeout(resolve, 10));
    assert.equal(harness.elements.get("lawError").hidden, false);
    assert.match(harness.elements.get("lawError").textContent, /not included in the API response/i);
});

test("Law Analysis displays its loading state while the uploaded contract is analyzed", async () => {
    const harness = createHarness();
    await new Promise(resolve => setTimeout(resolve, 0));
    harness.pauseAnalysis();
    startAnalysis(harness, "pending-contract.pdf");
    await new Promise(resolve => setTimeout(resolve, 0));
    assert.equal(harness.elements.get("lawLoading").hidden, false);
    harness.resumeAnalysis();
    await new Promise(resolve => setTimeout(resolve, 10));
    assert.equal(harness.elements.get("lawLoading").hidden, true);
});

test("failed document analysis shows the error and clears Law Analysis loading state", async () => {
    const harness = createHarness();
    await new Promise(resolve => setTimeout(resolve, 0));
    harness.failAnalysis();
    startAnalysis(harness, "unreadable.pdf");
    await new Promise(resolve => setTimeout(resolve, 10));
    assert.equal(harness.elements.get("error").hidden, false);
    assert.match(harness.elements.get("error").textContent, /Document extraction failed/);
    assert.equal(harness.elements.get("lawLoading").hidden, true);
    assert.equal(harness.elements.get("lawEmpty").hidden, false);
});

test("Law Analysis displays a real empty state when the API has no supported evidence", async () => {
    const harness = createHarness();
    await new Promise(resolve => setTimeout(resolve, 0));
    harness.setPayload({
        filename: "short-contract.pdf",
        text_length: 20,
        clauses: [],
        compliance: [],
        risk: {},
        compliance_prediction: {},
        explanations: [],
        negotiation: [],
        legal_analysis: {
            status: "informational",
            analysis_status: "complete_with_review_required",
            overview: {
                parties: [],
                governing_law: { clause_found: false },
                dispute_resolution: {},
                potential_jurisdictions: [],
                missing_or_uncertain_information: []
            },
            company_analyses: [],
            findings: [],
            issues_to_resolve: [],
            legal_sources: [],
            source_verification: {}
        }
    });
    startAnalysis(harness, "short-contract.pdf");
    await new Promise(resolve => setTimeout(resolve, 10));
    assert.equal(harness.elements.get("lawEmpty").hidden, false);
    assert.equal(harness.elements.get("lawContent").hidden, true);
});
