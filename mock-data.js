/**
 * Bundled demo data — shaped exactly like the response the backend's
 * pipeline produces once POST /api/analyze is wired up:
 *
 *   clause_extractor.extract_clauses()        -> clauses
 *   compliance_engine.analyze_compliance()     -> compliance
 *   risk_engine.calculate_risk()               -> risk
 *   risk_engine.generate_explanations()        -> explanations
 *   negotiation_engine.generate_negotiation_suggestions() -> negotiation
 *
 * Used whenever "Use demo data" is on, or as the response for the
 * "Load a sample analysis" shortcut on the intake screen.
 */

window.DEMO_ANALYSIS = {
  filename: "sample_contract.pdf",
  clauses: [
    { type: "Payment", title: "3. Fees and Payment", text: "Client shall pay Vendor the fees set out in Schedule A. Invoices are issued monthly in arrears." },
    { type: "Confidentiality", title: "5. Confidentiality", text: "Each party shall keep the other's confidential information secret and use it only for purposes of this Agreement." },
    { type: "Termination", title: "8. Term and Termination", text: "This Agreement may be terminated by either party for convenience upon 60 days' written notice." },
    { type: "Intellectual Property", title: "9. Intellectual Property", text: "All deliverables created under this Agreement shall be owned exclusively by Vendor unless otherwise agreed in writing." },
    { type: "Other", title: "11. Notices", text: "All notices under this Agreement shall be delivered in writing to the addresses set out in Schedule B." },
    { type: "Other", title: "12. Force Majeure", text: "Neither party shall be liable for delays caused by events beyond its reasonable control." }
  ],

  compliance: [
    { clause: "Payment", status: "Compliant", risk: "Low", explanation: "Payment clause is present in the contract.", requirement: "Payment terms should clearly define fees, invoice timing, and payment deadlines.", text: "Client shall pay Vendor the fees set out in Schedule A. Invoices are issued monthly in arrears." },
    { clause: "Confidentiality", status: "Compliant", risk: "Low", explanation: "Confidentiality clause is present in the contract.", requirement: "A confidentiality clause should protect non-public information.", text: "Each party shall keep the other's confidential information secret and use it only for purposes of this Agreement." },
    { clause: "Termination", status: "Compliant", risk: "Low", explanation: "Termination clause is present in the contract.", requirement: "Termination conditions and notice periods should be clearly defined.", text: "This Agreement may be terminated by either party for convenience upon 60 days' written notice." },
    { clause: "Intellectual Property", status: "Compliant", risk: "Low", explanation: "Intellectual Property clause is present in the contract.", requirement: "Ownership of intellectual property and deliverables should be clearly defined.", text: "All deliverables created under this Agreement shall be owned exclusively by Vendor unless otherwise agreed in writing." },
    { clause: "Data Protection", status: "Missing", risk: "High", explanation: "Data Protection clause is missing from the contract.", requirement: "The contract should define responsibilities for protecting personal and confidential data.", text: "" },
    { clause: "Liability", status: "Missing", risk: "High", explanation: "Liability clause is missing from the contract.", requirement: "Liability limits and exclusions should be clearly defined.", text: "" },
    { clause: "Dispute Resolution", status: "Missing", risk: "High", explanation: "Dispute Resolution clause is missing from the contract.", requirement: "The contract should specify how disputes will be resolved.", text: "" },
    { clause: "Governing Law", status: "Missing", risk: "High", explanation: "Governing Law clause is missing from the contract.", requirement: "The governing law should be explicitly stated.", text: "" }
  ],

  risk: { overall_risk: "Medium", risk_score: 16 },

  explanations: [
    { clause: "Payment", risk: "Low", reason: "Payment clause is present in the contract.", impact: "The required contractual provision has been identified.", recommendation: "Review the Payment clause to ensure it meets organizational requirements." },
    { clause: "Confidentiality", risk: "Low", reason: "Confidentiality clause is present in the contract.", impact: "The required contractual provision has been identified.", recommendation: "Review the Confidentiality clause to ensure it meets organizational requirements." },
    { clause: "Termination", risk: "Low", reason: "Termination clause is present in the contract.", impact: "The required contractual provision has been identified.", recommendation: "Review the Termination clause to ensure it meets organizational requirements." },
    { clause: "Intellectual Property", risk: "Low", reason: "Intellectual Property clause is present in the contract.", impact: "The required contractual provision has been identified.", recommendation: "Review the Intellectual Property clause to ensure it meets organizational requirements." },
    { clause: "Data Protection", risk: "High", reason: "Data Protection clause is missing from the contract.", impact: "Missing Data Protection terms may create contractual ambiguity or increase business risk.", recommendation: "Add a clearly defined Data Protection clause." },
    { clause: "Liability", risk: "High", reason: "Liability clause is missing from the contract.", impact: "Missing Liability terms may create contractual ambiguity or increase business risk.", recommendation: "Add a clearly defined Liability clause." },
    { clause: "Dispute Resolution", risk: "High", reason: "Dispute Resolution clause is missing from the contract.", impact: "Missing Dispute Resolution terms may create contractual ambiguity or increase business risk.", recommendation: "Add a clearly defined Dispute Resolution clause." },
    { clause: "Governing Law", risk: "High", reason: "Governing Law clause is missing from the contract.", impact: "Missing Governing Law terms may create contractual ambiguity or increase business risk.", recommendation: "Add a clearly defined Governing Law clause." }
  ],

  negotiation: [
    { clause: "Data Protection", priority: "High", suggestion: "Request explicit responsibilities for data security and breach notification.", suggested_wording: "The Service Provider shall implement reasonable security measures and notify the Client of confirmed data breaches without undue delay." },
    { clause: "Liability", priority: "High", suggestion: "Negotiate specific exceptions to the general liability cap for serious contractual violations.", suggested_wording: "The general liability limitation shall not apply to confidentiality breaches, data-protection violations, or infringement of intellectual property rights." },
    { clause: "Dispute Resolution", priority: "High", suggestion: "Request a clear dispute-resolution process with negotiation followed by arbitration or court proceedings.", suggested_wording: "The parties shall first attempt good-faith negotiation. Unresolved disputes shall be referred to arbitration." },
    { clause: "Governing Law", priority: "High", suggestion: "Ensure the governing law and jurisdiction are explicitly stated and commercially acceptable.", suggested_wording: "This Agreement shall be governed by the laws of India and subject to the agreed jurisdiction." },
    { clause: "Payment", priority: "Low", suggestion: "Request a clear payment deadline and protection against excessive payment delays.", suggested_wording: "Invoices shall be payable within 30 days of receipt. Late payments may be subject to reasonable interest." },
    { clause: "Termination", priority: "Low", suggestion: "Request a clearly defined termination notice period and cure period for breaches.", suggested_wording: "Either party may terminate this Agreement by providing 30 days' written notice. Material breaches shall have a 15-day cure period." }
  ]
};
