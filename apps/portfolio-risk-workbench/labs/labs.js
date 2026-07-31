(() => {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[character]);
  const money = (value) => Number(value || 0).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
  const percent = (value, digits = 1) => `${(Number(value || 0) * 100).toFixed(digits)}%`;
  const isoDate = (value) => new Date(`${value}T12:00:00Z`).toISOString().slice(0, 10);
  const seedFor = (value) => [...String(value)].reduce(
    (total, character) => (total * 31 + character.charCodeAt(0)) % 10007,
    23,
  );

  const storage = {
    get(key, fallback) {
      try {
        const value = localStorage.getItem(key);
        return value ? JSON.parse(value) : fallback;
      } catch {
        return fallback;
      }
    },
    set(key, value) {
      try {
        localStorage.setItem(key, JSON.stringify(value));
        return true;
      } catch {
        return false;
      }
    },
  };

  const instruments = [
    { id: "real-diversified-01", label: "Research Equity 01", asset: "Listed equity", region: "United States", sector: "Technology", industry: "Software", price: 12.40 },
    { id: "real-diversified-02", label: "Research Equity 02", asset: "Listed equity", region: "United States", sector: "Industrials", industry: "Machinery", price: 64.20 },
    { id: "real-diversified-03", label: "Research Equity 03", asset: "Listed equity", region: "United States", sector: "Consumer", industry: "Retail", price: 42.80 },
    { id: "real-diversified-04", label: "Research Equity 04", asset: "Listed equity", region: "United States", sector: "Health care", industry: "Medical devices", price: 51.10 },
    { id: "real-diversified-05", label: "Research Equity 05", asset: "Listed equity", region: "United States", sector: "Financials", industry: "Insurance", price: 77.40 },
    { id: "real-diversified-06", label: "Research Equity 06", asset: "Listed equity", region: "United States", sector: "Technology", industry: "Semiconductors", price: 118.20 },
    { id: "real-diversified-07", label: "Research Equity 07", asset: "Listed equity", region: "United States", sector: "Utilities", industry: "Electric utilities", price: 32.60 },
    { id: "real-diversified-08", label: "Research Equity 08", asset: "Listed equity", region: "United States", sector: "Consumer", industry: "Food products", price: 91.70 },
    { id: "real-technology-concentrated-01", label: "Technology Equity 01", asset: "Listed equity", region: "United States", sector: "Technology", industry: "Software", price: 141.20 },
    { id: "real-technology-concentrated-02", label: "Technology Equity 02", asset: "Listed equity", region: "United States", sector: "Technology", industry: "Semiconductors", price: 37.80 },
    { id: "real-defensive-multi-asset-01", label: "Defensive Equity 01", asset: "Listed equity", region: "United States", sector: "Health care", industry: "Pharmaceuticals", price: 93.60 },
    { id: "real-defensive-multi-asset-02", label: "Defensive Equity 02", asset: "Listed equity", region: "United States", sector: "Utilities", industry: "Electric utilities", price: 31.20 },
  ];

  const capabilities = [
    { id: "market_data", name: "Point-in-time market data", purpose: "Retrieve eligible prices and market observations.", status: "runnable" },
    { id: "risk_metrics", name: "Risk metric lookup", purpose: "Read deterministic MetricPack observations.", status: "runnable" },
    { id: "portfolio_exposure", name: "Portfolio exposure", purpose: "Calculate position weights and concentration.", status: "runnable" },
    { id: "scenario_stress", name: "Scenario stress", purpose: "Apply bounded deterministic shocks without mutation.", status: "runnable" },
    { id: "fundamental_change", name: "Fundamental change", purpose: "Compare point-in-time company fundamentals.", status: "synthetic adapter" },
    { id: "event_retrieval", name: "Event retrieval", purpose: "Retrieve governed events available by the as-of time.", status: "synthetic adapter" },
    { id: "evidence_critic", name: "Evidence critic", purpose: "Reject unsupported claims and invalid references.", status: "runnable" },
  ];

  const promptVariableCandidates = [
    { id: "as_of_date", label: "Workflow date", source: "Workflow cycle" },
    { id: "portfolio_name", label: "Portfolio name", source: "PortfolioContext" },
    { id: "issue", label: "Material issue", source: "RiskContext" },
    { id: "daily_return", label: "Daily return", source: "MetricPack" },
    { id: "var_95", label: "Historical VaR 95%", source: "MetricPack" },
    { id: "largest_weight", label: "Largest position weight", source: "PortfolioContext" },
    { id: "cash_weight", label: "Cash weight", source: "PortfolioContext" },
    { id: "mandate_status", label: "Mandate status", source: "Mandate / IPS" },
    { id: "evidence_state", label: "Evidence state", source: "OverallDefaultContext" },
    { id: "event_context", label: "Event context", source: "OverallDefaultContext" },
    { id: "news_context", label: "News context", source: "OverallDefaultContext" },
    { id: "workflow_cycle_id", label: "Workflow cycle ID", source: "Workflow runtime" },
  ];

  const agentSectionDefinitions = {
    identity: { api: "identity", label: "Describe identity and contracts", text: "Define who this agent is, its financial responsibility, the canonical context it receives and the exact contract it should produce." },
    instructions: { api: "instructions", label: "Describe the operating instructions", text: "Explain the outcome, what good completion means, the rules it must respect, when it should stop and how it should write." },
    prompts: { api: "prompts", label: "Describe the prompt strategy", text: "Describe the roles, evidence boundaries, variables and request template that should guide every run." },
    state: { api: "state", label: "Describe state management", text: "Explain what information must persist through the graph, who produces it and whether updates replace, append or merge." },
    routing: { api: "routing", label: "Describe routing behaviour", text: "Explain the normal route, revision triggers, evidence failure route, escalation conditions and stopping boundary." },
    memory: { api: "memory", label: "Describe memory behaviour", text: "Explain what should be remembered, for how long, at which scope and how long histories should be compacted." },
    capabilities: { api: "capabilities", label: "Describe required capabilities", text: "Explain which evidence or calculations the agent needs, when each may run and what should happen when one fails." },
    governance: { api: "governance", label: "Describe governance", text: "Explain evidence requirements, abstention, prohibited actions and where human approval is mandatory." },
    "structured-output": { api: "structured_output", label: "Describe the complete output", text: "Describe what the finished result should contain and how it should look. The model can replace the detailed presentation rules and propose the minimum necessary fields." },
    assembly: { api: "assembly", label: "Describe how the output is assembled", text: "Explain whether one run is enough or which repeated passes should build and review the artifact section by section." },
    reliability: { api: "reliability", label: "Describe reliability expectations", text: "Explain acceptable retry and timeout behaviour for this agent." },
  };

  const agentSectionHelp = {
    whole: {
      title: "Whole-agent description",
      works: "Creates a complete first draft across every section. It is the fastest way to move from an intended financial result to a coherent Agent Blueprint.",
      describe: "State the agent's responsibility, input context, evidence needs, desired result, safety boundaries and human-review requirement.",
      compile: "The planner returns schema-validated configuration only. Review the generated sections, validate the complete blueprint, then compile it into an executable LangGraph graph.",
    },
    identity: {
      title: "Identity and contracts",
      works: "Defines who the agent is and the canonical object it receives and produces.",
      describe: "Explain the financial responsibility and the exact result expected; use the selectors only to refine the canonical input, output and model.",
      compile: "Becomes the graph's typed entry boundary, model binding and final output-contract check.",
    },
    instructions: {
      title: "Instructions",
      works: "Defines the agent's objective, completion standard, constraints, stopping rules and writing behaviour.",
      describe: "Describe what success looks like, what must never happen, when the work is complete and how the result should read.",
      compile: "Becomes the principal instruction contract supplied to the agent nodes on every run.",
    },
    prompts: {
      title: "Prompt messages and template",
      works: "Controls the ordered system, developer and user messages plus the variables inserted for each workflow date.",
      describe: "Explain the role, evidence boundary, recurring request and which values must be supplied at runtime.",
      compile: "Messages are ordered, template variables are checked, and the rendered prompt is passed to the model node.",
    },
    state: {
      title: "State management",
      works: "Defines the information carried between LangGraph nodes and how each update replaces, appends or merges data.",
      describe: "List what must persist, who produces it, whether it is required and how repeated updates should combine.",
      compile: "Becomes the typed graph state shared by capability, drafting, critique and human-review nodes.",
    },
    routing: {
      title: "Routing conditions",
      works: "Defines the branches between evidence gathering, drafting, revision, abstention, escalation and completion.",
      describe: "Describe the normal path, revision trigger, missing-evidence response, human escalation and stopping boundary.",
      compile: "Becomes bounded conditional edges with a maximum iteration count and an explicit terminal route.",
    },
    memory: {
      title: "Memory rules",
      works: "Controls what graph state is checkpointed, for how long and at which workflow scope.",
      describe: "Explain which fields must survive a pause or revision and when they must be discarded or compacted.",
      compile: "Configures the LangGraph checkpointer and limits memory to the selected workflow-cycle, experiment or session scope.",
    },
    capabilities: {
      title: "Capabilities",
      works: "Latches approved data and calculation tools to the agent without giving it unrestricted access.",
      describe: "Explain which evidence is needed, when each capability may run, where its result belongs and how failure should be handled.",
      compile: "Creates allow-listed tool nodes and routes their typed results into the declared state bindings.",
    },
    governance: {
      title: "Governance and abstention",
      works: "Defines evidence standards, prohibited behaviour, abstention rules and mandatory human decisions.",
      describe: "State what requires evidence, when the agent must stop or abstain and where human approval is compulsory.",
      compile: "Adds validation gates and human interrupts; portfolio-changing effects remain prohibited.",
    },
    "structured-output": {
      title: "Structured Output",
      works: "Defines the exact fields and the visual form of the persistent artifact produced by the agent.",
      describe: "Describe what the finished result should contain and how a reader should experience it. Add fields only for genuinely separate components.",
      compile: "Becomes a strict output schema plus rendering instructions; undeclared properties are rejected.",
    },
    assembly: {
      title: "Multi-pass assembly",
      works: "Lets repeated bounded runs build a larger artifact without asking one response to produce everything at once.",
      describe: "Explain whether one pass is sufficient or how sections should be produced, reviewed and carried forward across passes.",
      compile: "Creates an ordered pass plan with dependencies, field targets, token ceilings, quality gates and optional human pauses.",
    },
    reliability: {
      title: "Reliability and runtime",
      works: "Bounds execution time and the number of automatic retries.",
      describe: "State how quickly the agent should fail and whether a transient failure justifies another attempt.",
      compile: "Applies retry and timeout policies around graph execution without changing the agent's financial authority.",
    },
  };

  const labState = {
    savedPortfolios: storage.get("portfolio-replay-lab.portfolios", []),
    savedAgents: storage.get("portfolio-replay-lab.agents", []),
    builderHoldings: [],
    graphAgentIds: [],
    livePortfolios: [],
    liveCatalog: [],
    liveConnected: false,
    dataQueryResult: null,
    agentRuntime: null,
    riskAgentTemplates: null,
    agentBlueprint: null,
    agentCompile: null,
    agentStateFields: [
      { name: "context", value_type: "object", description: "Immutable Overall Default Context supplied for the workflow date.", source: "input", required: true, reducer: "replace" },
      { name: "capability_results", value_type: "array", description: "Effect-free evidence returned by latched capabilities.", source: "capability", required: true, reducer: "append" },
      { name: "narrative", value_type: "string", description: "Current evidence-grounded portfolio risk narrative.", source: "agent", required: true, reducer: "replace" },
      { name: "critique", value_type: "string", description: "Latest evidence-critic finding and revision guidance.", source: "governance", required: true, reducer: "replace" },
      { name: "review", value_type: "object", description: "Human approval response recorded at the interrupt.", source: "runtime", required: false, reducer: "replace" },
    ],
    agentPromptMessages: [
      { role: "system", name: "Financial role", content: "You are a portfolio risk reviewer operating inside a historical point-in-time replay.", enabled: true },
      { role: "developer", name: "Evidence boundary", content: "Use only supplied context and latched capability results. Distinguish facts, interpretation, and unavailable evidence.", enabled: true },
      { role: "user", name: "Workflow request", content: "Prepare the daily portfolio risk review for the current workflow date.", enabled: true },
    ],
    agentPromptVariables: ["as_of_date", "issue", "daily_return", "var_95", "largest_weight", "evidence_state"],
    agentCapabilityLatches: {},
    advisorMessages: [],
    advisorProposal: null,
    agentOutputFields: [
      { name: "main_output", title: "Main output", value_type: "string", semantic_role: "narrative", description: "The primary evidence-grounded result produced by the agent.", nullable: false, format: "markdown", enum_values: [], nested_schema_json: "", merge_strategy: "replace", citation_required: true, validation_rule: "The output is complete, clear, grounded in supplied evidence and consistent with governance.", produced_in_passes: ["main_output"] },
    ],
    agentOutputPasses: [
      { pass_id: "main_output", title: "Produce main output", objective: "Populate the primary output field from the supplied context and accepted evidence.", target_fields: ["main_output"], operation: "replace", context_policy: "full_context", depends_on: [], max_output_tokens: 3000, quality_gate: "The primary output is schema-valid, evidence-grounded and ready for review.", human_review_after: true },
    ],
    outputAssemblyArtifact: {},
    outputAssemblyCompleted: [],
    outputAssemblyLog: [],
    outputAssemblyReviewPending: null,
  };

  function canonicalCurrentPortfolio() {
    return window.PortfolioReplayLab?.getCurrentPortfolio?.() || {
      id: "opening",
      title: "Opening research portfolio",
      cash: 4000000,
      holdings: instruments.slice(0, 8).map((instrument, index) => ({
        id: instrument.id,
        quantity: 100000 + index * 10000,
        price: instrument.price,
      })),
    };
  }

  function portfolioOptions() {
    const current = canonicalCurrentPortfolio();
    return [
      { ...current, source: "Current experiment" },
      ...labState.savedPortfolios.map((portfolio) => ({ ...portfolio, source: "Saved locally" })),
    ];
  }

  function switchWorkspace(name) {
    const full = name === "full";
    $("#lab-workspace").classList.toggle("hidden", full);
    $("#full-experiment-workspace").classList.toggle("hidden", !full);
    $$(".lab-page").forEach((page) => page.classList.toggle("active", page.id === `lab-${name}`));
    $$(".workspace-tab").forEach((button) => button.classList.toggle("active", button.dataset.workspace === name));
    $(".mode-badge").textContent = name === "dataset" && labState.liveConnected
      ? "Local data · read-only"
      : "Synthetic sandbox";
    if (name === "dataset") populateDatasetPortfolios();
    if (name === "graph") refreshGraphAgents();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function populateDatasetPortfolios() {
    const live = $("#dataset-mode").value === "live";
    const options = live && labState.livePortfolios.length
      ? labState.livePortfolios
      : portfolioOptions();
    const selected = $("#dataset-portfolio").value;
    $("#dataset-portfolio").innerHTML = options.map((portfolio, index) =>
      `<option value="${escapeHtml(portfolio.id || `saved-${index}`)}">${escapeHtml(portfolio.title)} · ${portfolio.holdings.length} positions</option>`).join("");
    if (options.some((portfolio) => String(portfolio.id) === selected)) $("#dataset-portfolio").value = selected;
  }

  function selectedDatasetPortfolio() {
    const options = $("#dataset-mode").value === "live" && labState.livePortfolios.length
      ? labState.livePortfolios
      : portfolioOptions();
    return options.find((portfolio) => String(portfolio.id) === $("#dataset-portfolio").value) || options[0];
  }

  function eligibleRecord(holding, domain, scenario, asOf, index) {
    const instrument = instruments.find((item) => item.id === holding.id);
    const identity = instrument?.label || holding.id;
    const seed = seedFor(`${holding.id}-${asOf}-${domain}`);
    const date = isoDate(asOf);
    if (domain === "market") {
      if (scenario === "missing" && index === 0) {
        return { identity, domain: "Market", observed: "—", available: "—", value: "No eligible observation", quality: "missing" };
      }
      const shock = scenario === "shock" ? .92 : 1;
      const price = (Number(holding.price || instrument?.price || 50) * (1 + ((seed % 13) - 6) / 1000) * shock).toFixed(2);
      return { identity, domain: "Market", observed: `${date} 16:00`, available: `${date} 16:05`, value: `$${price} close`, quality: "good" };
    }
    if (domain === "fundamental") {
      const stale = scenario === "stale";
      const observed = stale ? "2023-09-30" : "2024-03-31";
      const available = stale ? "2023-11-08" : "2024-04-10";
      return {
        identity,
        domain: "Fundamental",
        observed,
        available,
        value: `Revenue growth ${((seed % 170) / 10 - 5).toFixed(1)}% · leverage ${(1 + (seed % 35) / 10).toFixed(1)}×`,
        quality: stale ? "warning" : "good",
      };
    }
    if (scenario === "missing") {
      return { identity, domain: "Events", observed: "—", available: "—", value: "Event source unavailable", quality: "missing" };
    }
    if ((seed + index) % 3 !== 0) {
      return { identity, domain: "Events", observed: date, available: `${date} 09:00`, value: "No eligible material event record", quality: "good" };
    }
    return {
      identity,
      domain: "Events",
      observed: `${date} 07:30`,
      available: `${date} 08:15`,
      value: scenario === "shock" ? "Negative market-movement event · high relevance" : "Corporate update · moderate relevance",
      quality: "good",
    };
  }

  function renderDatasetRows(rows) {
    $("#dataset-results-body").innerHTML = rows.length ? rows.map((row) => `
      <tr>
        <td><strong>${escapeHtml(row.identity)}</strong></td>
        <td>${escapeHtml(row.domain)}</td>
        <td>${escapeHtml(row.observed || "—")}</td>
        <td>${escapeHtml(row.available || "—")}</td>
        <td>${escapeHtml(row.value)}</td>
        <td><span class="quality-${row.quality}">${escapeHtml(row.qualityLabel || row.quality)}</span></td>
      </tr>`).join("") : `<tr><td colspan="6">The query returned no records.</td></tr>`;
  }

  function dataCell(value) {
    if (value == null) return "—";
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  }

  function renderDataQuery(payload) {
    const previewRows = payload.rows.slice(0, 500);
    const table = $("#data-query-table");
    table.querySelector("thead").innerHTML = `<tr>${payload.columns.map((column) =>
      `<th scope="col">${escapeHtml(column)}</th>`).join("")}</tr>`;
    table.querySelector("tbody").innerHTML = previewRows.length
      ? previewRows.map((row) => `<tr>${row.map((value) => {
        const rendered = dataCell(value);
        return `<td title="${escapeHtml(rendered)}">${escapeHtml(rendered)}</td>`;
      }).join("")}</tr>`).join("")
      : `<tr><td colspan="${Math.max(payload.column_count, 1)}">No rows returned.</td></tr>`;
    $("#data-query-title").textContent = payload.question;
    const previewNote = payload.row_count > previewRows.length
      ? ` · showing first ${previewRows.length.toLocaleString("en-US")}`
      : "";
    const truncationNote = payload.truncated ? " · capped" : "";
    $("#data-query-result-meta").textContent = `${payload.row_count.toLocaleString("en-US")} rows · ${payload.column_count} columns · ${payload.elapsed_ms} ms${previewNote}${truncationNote}`;
    $("#data-query-sql").textContent = payload.sql;
    $("#data-query-result").classList.remove("hidden");
    $("#data-query-message").textContent = "";
    $("#data-query-message").classList.remove("error");
    $("#dataset-query-status").textContent = "Ready";
    $("#dataset-query-status").classList.remove("warning");
  }

  async function askDatabase(event) {
    event.preventDefault();
    const question = $("#data-query-question").value.trim();
    if (!question) return;
    const button = $("#data-query-run");
    button.disabled = true;
    button.textContent = "Running…";
    $("#data-query-message").textContent = "Luna is writing SQL…";
    $("#data-query-message").classList.remove("error");
    $("#dataset-query-status").textContent = "Running";
    try {
      const response = await fetch("/api/query/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || `Query failed with HTTP ${response.status}.`);
      labState.dataQueryResult = payload;
      $("#data-query-agent").textContent = "Luna · low";
      renderDataQuery(payload);
    } catch (error) {
      $("#data-query-message").textContent = error.message;
      $("#data-query-message").classList.add("error");
      $("#dataset-query-status").textContent = "Query failed";
      $("#dataset-query-status").classList.add("warning");
    } finally {
      button.disabled = false;
      button.textContent = "Run";
    }
  }

  function csvCell(value) {
    let rendered = value == null ? "" : typeof value === "object" ? JSON.stringify(value) : String(value);
    if (/^[=+@]/.test(rendered) || /^-[^0-9.]/.test(rendered)) rendered = `'${rendered}`;
    return `"${rendered.replaceAll('"', '""')}"`;
  }

  function exportDataQueryCsv() {
    const payload = labState.dataQueryResult;
    if (!payload) return;
    const csv = [payload.columns, ...payload.rows]
      .map((row) => row.map(csvCell).join(","))
      .join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `duckdb-query-${new Date().toISOString().slice(0, 19).replaceAll(":", "-")}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function liveValueSummary(record) {
    const values = record.values || {};
    if (record.dataset.startsWith("crsp_ds") || record.dataset.startsWith("crsp_ms")) {
      const price = values.price == null ? "price unavailable" : `$${Number(values.price).toFixed(2)}`;
      const returned = values.return == null ? "return unavailable" : `${(Number(values.return) * 100).toFixed(2)}% return`;
      const volume = values.volume == null ? "volume unavailable" : `${Number(values.volume).toLocaleString("en-US")} volume`;
      return `${price} · ${returned} · ${volume}`;
    }
    if (record.dataset === "compustat_fundq") {
      const formatted = (value) => value == null ? "—" : Number(value).toLocaleString("en-US", { maximumFractionDigits: 1 });
      return `Assets ${formatted(values.assets)} · revenue ${formatted(values.revenue ?? values.sales)} · net income ${formatted(values.net_income)} · debt ${formatted((Number(values.long_term_debt) || 0) + (Number(values.current_debt) || 0))}`;
    }
    if (record.dataset === "crsp_stocknames") {
      return `${values.ticker || "No ticker"} · ${values.company_name || "No active company name"} · exchange ${values.exchange_code ?? "—"} · SIC ${values.sic_code ?? "—"}`;
    }
    if (record.dataset === "ccmxpf_linktable") {
      return `Link type ${values.link_type || "—"} · primary ${values.link_primary || "—"} · end ${values.link_end_date || "open"}`;
    }
    return JSON.stringify(values);
  }

  async function runLiveDatasetQuery() {
    if (!labState.liveConnected) {
      throw new Error("The DuckDB API is not connected. Open the prototype through the local service URL.");
    }
    const portfolio = selectedDatasetPortfolio();
    const asOf = $("#dataset-as-of").value;
    const domains = $$("[data-dataset-domain]:checked")
      .map((input) => input.value)
      .filter((value) => ["market", "fundamental", "identity", "links"].includes(value));
    if (!domains.length) throw new Error("Select at least one live dataset.");
    const request = {
      portfolio_id: portfolio.id,
      as_of: asOf,
      datasets: domains,
      market_source: "dsf",
      include_native_ids: false,
    };
    $("#dataset-request-json").textContent = JSON.stringify(request, null, 2);
    const response = await fetch("/api/query/portfolio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || `Live query failed with HTTP ${response.status}.`);
    const rows = payload.records.map((record) => ({
      identity: record.instrument_alias,
      domain: record.dataset,
      observed: record.observed_at,
      available: record.available_at,
      value: liveValueSummary(record),
      quality: record.quality === "eligible" ? "good" : record.quality === "fallback_date" ? "warning" : "missing",
      qualityLabel: record.quality,
    }));
    renderDatasetRows(rows);
    const eligible = payload.quality_counts.eligible || 0;
    const warnings = payload.quality_counts.fallback_date || 0;
    const missing = payload.quality_counts.missing || 0;
    $("#dataset-result-title").textContent = `${payload.record_count} live records for ${portfolio.title}`;
    $("#dataset-result-meta").innerHTML = `<span>${eligible} eligible</span><span>${warnings} availability fallbacks</span><span>${missing} missing</span><span>${payload.elapsed_ms} ms</span>`;
    $("#dataset-query-status").textContent = missing ? "Live · gaps found" : warnings ? "Live · qualified" : "Live · complete";
    $("#dataset-query-status").classList.toggle("warning", warnings + missing > 0);
    $("#dataset-trace").innerHTML = [
      `Resolved ${payload.position_count} approved aliases through the private CRSP mapping.`,
      `DuckDB pushed position and as-of filters into ${domains.join(", ")} Parquet queries.`,
      `Applied the point-in-time rule: ${payload.point_in_time_rule}.`,
      `Returned ${payload.record_count} records in ${payload.elapsed_ms} ms; native CRSP and Compustat identifiers remained server-side.`,
    ].map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  }

  function runSyntheticDatasetQuery() {
    const portfolio = selectedDatasetPortfolio();
    const asOf = $("#dataset-as-of").value;
    const scenario = $("#dataset-scenario").value;
    const domains = $$("[data-dataset-domain]:checked").map((input) => input.value);
    const rows = portfolio.holdings.flatMap((holding, index) =>
      domains.map((domain) => eligibleRecord(holding, domain, scenario, asOf, index)));
    const eligible = rows.filter((row) => row.quality !== "missing").length;
    const warnings = rows.filter((row) => row.quality === "warning").length;
    const missing = rows.filter((row) => row.quality === "missing").length;
    renderDatasetRows(rows);
    $("#dataset-result-title").textContent = `${rows.length} records evaluated for ${portfolio.title}`;
    $("#dataset-result-meta").innerHTML = `<span>${eligible} eligible</span><span>${warnings} stale</span><span>${missing} unavailable</span>`;
    $("#dataset-query-status").textContent = missing ? "Completed with gaps" : warnings ? "Completed with warnings" : "Complete";
    $("#dataset-query-status").classList.toggle("warning", warnings + missing > 0);
    $("#dataset-trace").innerHTML = [
      `Resolved ${portfolio.holdings.length} positions from the selected PortfolioDefinition.`,
      `Applied available_at ≤ ${asOf} to ${domains.length} requested dataset domains.`,
      `Returned ${eligible} eligible records; preserved ${warnings + missing} quality exceptions.`,
      "Produced a model-safe capability result without interpretation or portfolio effects.",
    ].map((item) => `<li>${escapeHtml(item)}</li>`).join("");
    $("#dataset-request-json").textContent = JSON.stringify({
      capability: "portfolio_data_query",
      portfolio_id: portfolio.id,
      instrument_aliases: portfolio.holdings.map((holding) => holding.id),
      as_of: `${asOf}T16:30:00Z`,
      datasets: domains,
      point_in_time_rule: "available_at <= as_of",
      synthetic_scenario: scenario,
    }, null, 2);
  }

  async function runDatasetQuery() {
    const button = $("#run-dataset-query");
    button.disabled = true;
    button.textContent = $("#dataset-mode").value === "live" ? "Querying DuckDB…" : "Running fixture…";
    try {
      if ($("#dataset-mode").value === "live") await runLiveDatasetQuery();
      else runSyntheticDatasetQuery();
    } catch (error) {
      $("#dataset-query-status").textContent = "Connection required";
      $("#dataset-query-status").classList.add("warning");
      $("#dataset-results-body").innerHTML = `<tr><td colspan="6"><strong>Live query unavailable.</strong><br>${escapeHtml(error.message)}</td></tr>`;
      $("#dataset-trace").innerHTML = `<li>${escapeHtml(error.message)}</li><li>No synthetic fallback was used.</li>`;
    } finally {
      button.disabled = false;
      button.textContent = $("#dataset-mode").value === "live" ? "Query live Parquet data" : "Run synthetic fixture";
    }
  }

  function configureDatasetMode() {
    const live = $("#dataset-mode").value === "live";
    $("#dataset-scenario-field").classList.toggle("hidden", live);
    $("#synthetic-event-domain").classList.toggle("hidden", live);
    $("#live-identity-domain").classList.toggle("hidden", !live);
    $("#live-links-domain").classList.toggle("hidden", !live);
    const eventInput = $("#synthetic-event-domain input");
    const identityInput = $("#live-identity-domain input");
    if (eventInput) eventInput.checked = !live;
    if (identityInput) identityInput.checked = live;
    $("#dataset-adapter-truth").textContent = live
      ? (labState.liveConnected ? "Live DuckDB · read-only" : "DuckDB service required")
      : "Explicit synthetic fixture";
    $("#run-dataset-query").textContent = live ? "Query live Parquet data" : "Run synthetic fixture";
    populateDatasetPortfolios();
  }

  async function initializeLiveConnection() {
    try {
      const [healthResponse, catalogResponse, portfoliosResponse] = await Promise.all([
        fetch("/api/health"),
        fetch("/api/catalog"),
        fetch("/api/portfolios"),
      ]);
      if (!healthResponse.ok || !catalogResponse.ok || !portfoliosResponse.ok) {
        throw new Error("The local data service returned an error.");
      }
      const health = await healthResponse.json();
      const catalog = await catalogResponse.json();
      const portfolios = await portfoliosResponse.json();
      labState.liveConnected = health.status === "ok";
      if ($("#lab-dataset").classList.contains("active")) {
        $(".mode-badge").textContent = "Local data · read-only";
      }
      labState.liveCatalog = catalog.datasets;
      labState.livePortfolios = portfolios.portfolios.map((portfolio) => ({
        id: portfolio.portfolio_id,
        title: portfolio.title,
        cash: (portfolio.cash || []).reduce((sum, item) => sum + Number(item.amount || 0), 0),
        holdings: portfolio.positions.map((position) => ({
          id: position.instrument_alias,
          quantity: Number(position.quantity),
          price: instruments.find((item) => item.id === position.instrument_alias)?.price || 0,
        })),
      }));
      $("#duckdb-connection-status").textContent = "Connected";
      $("#duckdb-connection-status").className = "quality-good";
      $("#duckdb-connection-copy").textContent = `${health.reviewed_portfolios} reviewed portfolios · ${health.datasets} Parquet datasets · read-only localhost service.`;
      $("#data-query-agent").textContent = health.sql_agent?.available ? "Luna · low" : "Luna unavailable";
      $("#dataset-query-status").textContent = health.sql_agent?.available ? "Connected" : "Key required";
      $("#dataset-query-status").classList.toggle("warning", !health.sql_agent?.available);
      const named = ["dsf", "fundq", "stocknames", "ccmxpf_linktable"];
      $("#duckdb-catalog").innerHTML = labState.liveCatalog.filter((item) => named.includes(item.dataset)).map((item) =>
        `<div><strong>${escapeHtml(item.dataset)}</strong><span>${Number(item.row_count).toLocaleString("en-US")} rows</span><small>${escapeHtml(item.minimum_date)} → ${escapeHtml(item.maximum_date)}</small></div>`).join("");
      configureDatasetMode();
    } catch (error) {
      labState.liveConnected = false;
      $("#duckdb-connection-status").textContent = "Not connected";
      $("#duckdb-connection-status").className = "quality-missing";
      $("#duckdb-connection-copy").textContent = "Open this application through the local DuckDB service URL; file:// pages cannot call the API.";
      $("#duckdb-catalog").innerHTML = "";
      $("#data-query-agent").textContent = "Luna unavailable";
      $("#data-query-message").textContent = "Open the live local service to query data.";
      $("#data-query-message").classList.add("error");
      $("#dataset-query-status").textContent = "Offline";
      $("#dataset-query-status").classList.add("warning");
      configureDatasetMode();
    }
  }

  function filteredInstruments() {
    const filters = {
      asset: $("#builder-asset").value,
      region: $("#builder-region").value,
      sector: $("#builder-sector").value,
      industry: $("#builder-industry").value,
    };
    return instruments.filter((instrument) =>
      Object.entries(filters).every(([field, value]) => !value || instrument[field] === value));
  }

  function fillSelect(id, values, prior) {
    const select = $(id);
    select.innerHTML = [...new Set(values)].sort().map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("");
    if ([...select.options].some((option) => option.value === prior)) select.value = prior;
  }

  function updateInstrumentHierarchy(changedLevel = 0) {
    const prior = {
      asset: $("#builder-asset").value,
      region: $("#builder-region").value,
      sector: $("#builder-sector").value,
      industry: $("#builder-industry").value,
      instrument: $("#builder-instrument").value,
    };
    if (changedLevel <= 0) fillSelect("#builder-asset", instruments.map((item) => item.asset), prior.asset);
    const assetSet = instruments.filter((item) => item.asset === $("#builder-asset").value);
    if (changedLevel <= 1) fillSelect("#builder-region", assetSet.map((item) => item.region), prior.region);
    const regionSet = assetSet.filter((item) => item.region === $("#builder-region").value);
    if (changedLevel <= 2) fillSelect("#builder-sector", regionSet.map((item) => item.sector), prior.sector);
    const sectorSet = regionSet.filter((item) => item.sector === $("#builder-sector").value);
    if (changedLevel <= 3) fillSelect("#builder-industry", sectorSet.map((item) => item.industry), prior.industry);
    const matches = filteredInstruments();
    $("#builder-instrument").innerHTML = matches.map((instrument) =>
      `<option value="${instrument.id}">${escapeHtml(instrument.label)} · ${escapeHtml(instrument.id)}</option>`).join("");
    if (matches.some((instrument) => instrument.id === prior.instrument)) $("#builder-instrument").value = prior.instrument;
    renderInstrumentDetail();
  }

  function renderInstrumentDetail() {
    const instrument = instruments.find((item) => item.id === $("#builder-instrument").value);
    $("#builder-instrument-detail").innerHTML = instrument
      ? `<strong>${escapeHtml(instrument.label)}</strong><br>${escapeHtml(instrument.sector)} · ${escapeHtml(instrument.industry)}<br>Reference opening price ${money(instrument.price)}<br><small>Private-neutral research alias; no licensed identifier is exposed.</small>`
      : "No instrument matches this hierarchy.";
  }

  function builderCandidate() {
    return {
      id: `local-${Date.now()}`,
      title: $("#builder-name").value.trim() || "Untitled research portfolio",
      cash: Math.max(0, Number($("#builder-cash").value) || 0),
      holdings: labState.builderHoldings.map((holding) => ({ ...holding })),
      maxPosition: Math.max(0, Number($("#builder-max-position").value) || 0) / 100,
      minimumCash: Math.max(0, Number($("#builder-min-cash").value) || 0) / 100,
    };
  }

  function checkBuilderMandate(candidate = builderCandidate()) {
    const invested = candidate.holdings.map((holding) => Number(holding.quantity) * Number(holding.price));
    const total = candidate.cash + invested.reduce((sum, value) => sum + value, 0);
    const topWeight = total ? Math.max(...invested, 0) / total : 0;
    const cashWeight = total ? candidate.cash / total : 0;
    const warnings = [];
    if (candidate.holdings.length < 5) warnings.push(`At least 5 positions are required; ${candidate.holdings.length} selected.`);
    if (candidate.holdings.length > 8) warnings.push(`At most 8 positions are permitted; ${candidate.holdings.length} selected.`);
    if (topWeight > candidate.maxPosition) warnings.push(`Largest position ${percent(topWeight)} exceeds ${percent(candidate.maxPosition)}.`);
    if (cashWeight < candidate.minimumCash) warnings.push(`Cash ${percent(cashWeight)} is below ${percent(candidate.minimumCash)}.`);
    return { total, topWeight, cashWeight, warnings };
  }

  function renderBuilder() {
    const candidate = builderCandidate();
    const check = checkBuilderMandate(candidate);
    const values = candidate.holdings.map((holding) => holding.quantity * holding.price);
    $("#builder-total-value").textContent = money(check.total);
    $("#builder-holdings-body").innerHTML = candidate.holdings.length ? candidate.holdings.map((holding, index) => `
      <tr>
        <td><strong>${escapeHtml(instruments.find((item) => item.id === holding.id)?.label || holding.id)}</strong><br><small>${escapeHtml(holding.id)}</small></td>
        <td><input type="number" min="1" step="1" value="${holding.quantity}" data-builder-quantity="${index}" aria-label="Quantity for ${escapeHtml(holding.id)}"></td>
        <td>${money(holding.price)}</td>
        <td>${percent(check.total ? values[index] / check.total : 0)}</td>
        <td><button class="remove-button" type="button" data-builder-remove="${index}" aria-label="Remove ${escapeHtml(holding.id)}">×</button></td>
      </tr>`).join("") : `<tr><td colspan="5">No positions selected.</td></tr>`;
    $("#builder-mandate-result").innerHTML = check.warnings.length
      ? `<div class="mandate-check exception"><strong>${check.warnings.length} review item${check.warnings.length === 1 ? "" : "s"}</strong><ul>${check.warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")}</ul></div>`
      : `<div class="mandate-check compliant"><strong>Candidate passes the selected controls</strong><span>Largest position ${percent(check.topWeight)} · cash ${percent(check.cashWeight)}</span></div>`;
    $("#portfolio-builder-status").textContent = check.warnings.length ? "Review required" : "Ready to save";
    $("#portfolio-builder-status").classList.toggle("warning", check.warnings.length > 0);
  }

  function addBuilderPosition() {
    const instrument = instruments.find((item) => item.id === $("#builder-instrument").value);
    if (!instrument) return;
    const existing = labState.builderHoldings.find((holding) => holding.id === instrument.id);
    if (existing) existing.quantity += Math.max(1, Number($("#builder-quantity").value) || 1);
    else labState.builderHoldings.push({
      id: instrument.id,
      quantity: Math.max(1, Number($("#builder-quantity").value) || 1),
      price: instrument.price,
    });
    renderBuilder();
  }

  function savePortfolio() {
    const candidate = builderCandidate();
    const check = checkBuilderMandate(candidate);
    if (candidate.holdings.length < 5 || candidate.holdings.length > 8) {
      $("#portfolio-builder-status").textContent = "Position count invalid";
      $("#portfolio-builder-status").classList.add("warning");
      return;
    }
    candidate.reviewed = true;
    candidate.reviewedAt = new Date().toISOString();
    candidate.warnings = check.warnings;
    labState.savedPortfolios = [candidate, ...labState.savedPortfolios.filter((portfolio) => portfolio.title !== candidate.title)].slice(0, 12);
    const persisted = storage.set("portfolio-replay-lab.portfolios", labState.savedPortfolios);
    $("#portfolio-builder-status").textContent = persisted ? (check.warnings.length ? "Saved with warnings" : "Saved locally") : "Saved for this session";
    renderSavedPortfolios();
    populateDatasetPortfolios();
  }

  function renderSavedPortfolios() {
    $("#saved-portfolios").innerHTML = labState.savedPortfolios.length ? labState.savedPortfolios.map((portfolio) => `
      <div class="saved-item"><strong>${escapeHtml(portfolio.title)}</strong><small>${portfolio.holdings.length} positions · ${money(portfolio.cash)} cash${portfolio.warnings?.length ? ` · ${portfolio.warnings.length} warnings` : ""}</small><button type="button" data-load-portfolio="${escapeHtml(portfolio.id)}">Load</button></div>`).join("")
      : `<div class="empty-state">No locally saved portfolio.</div>`;
  }

  function renderCapabilities() {
    capabilities.forEach((capability, index) => {
      if (!labState.agentCapabilityLatches[capability.id]) {
        labState.agentCapabilityLatches[capability.id] = {
          capability_id: capability.id,
          purpose: capability.purpose,
          invocation_condition: capability.id === "evidence_critic"
            ? "After every narrative draft and before any human review."
            : "When the required source field is present and this evidence is relevant to the requested review.",
          output_binding: capability.id === "evidence_critic" ? "critique" : `${capability.id}_result`,
          required: index < 3 || capability.id === "evidence_critic",
          failure_policy: capability.id === "evidence_critic" ? "human_review" : "continue_with_warning",
          enabled: index < 4 || capability.id === "evidence_critic",
        };
      }
    });
    $("#agent-capabilities").innerHTML = capabilities.map((capability) => {
      const latch = labState.agentCapabilityLatches[capability.id];
      return `
        <div class="capability-latch-card ${latch.enabled ? "enabled" : ""}" data-capability-card="${escapeHtml(capability.id)}">
          <div class="card-heading">
            <label class="capability-latch-toggle">
              <input type="checkbox" value="${escapeHtml(capability.id)}" data-agent-capability ${latch.enabled ? "checked" : ""}>
              <span><strong>${escapeHtml(capability.name)}</strong><small>${escapeHtml(capability.purpose)} · ${escapeHtml(capability.status)}</small></span>
            </label>
            <small>${latch.enabled ? "Latched" : "Unavailable to agent"}</small>
          </div>
          <div class="capability-latch-fields ${latch.enabled ? "" : "hidden"}">
            <label class="field purpose"><span>Purpose in this agent</span><textarea rows="2" data-capability-purpose="${escapeHtml(capability.id)}">${escapeHtml(latch.purpose)}</textarea></label>
            <label class="field condition"><span>Invocation condition</span><textarea rows="2" data-capability-condition="${escapeHtml(capability.id)}">${escapeHtml(latch.invocation_condition)}</textarea></label>
            <label class="field"><span>Output state binding</span><input value="${escapeHtml(latch.output_binding)}" data-capability-binding="${escapeHtml(capability.id)}"></label>
            <label class="field"><span>Failure policy</span><select data-capability-failure="${escapeHtml(capability.id)}">
              ${["abstain", "continue_with_warning", "retry", "human_review"].map((value) => `<option value="${value}" ${latch.failure_policy === value ? "selected" : ""}>${value.replaceAll("_", " ")}</option>`).join("")}
            </select></label>
            <label class="review-test-toggle"><input type="checkbox" data-capability-required="${escapeHtml(capability.id)}" ${latch.required ? "checked" : ""}><span>Required for completion</span></label>
          </div>
        </div>`;
    }).join("");
    $("#agent-capability-count").textContent = `${Object.values(labState.agentCapabilityLatches).filter((item) => item.enabled).length} latched`;
  }

  function listFrom(selector) {
    return $(selector).value.split(/\n+/).map((value) => value.trim()).filter(Boolean);
  }

  function commaListFrom(selector) {
    return $(selector).value.split(",").map((value) => value.trim()).filter(Boolean);
  }

  function compiledInstructions(blueprint) {
    return [
      blueprint.instructions.objective,
      `Success criteria:\n- ${blueprint.instructions.success_criteria.join("\n- ")}`,
      `Constraints:\n- ${blueprint.instructions.constraints.join("\n- ")}`,
      `Stopping conditions:\n- ${blueprint.instructions.stopping_conditions.join("\n- ")}`,
      `Narrative style:\n${blueprint.instructions.narrative_style}`,
    ].join("\n\n");
  }

  function renderPromptMessages() {
    $("#agent-prompt-messages").innerHTML = labState.agentPromptMessages.map((message, index) => `
      <div class="prompt-message-card" data-prompt-message-index="${index}">
        <div class="card-heading"><strong>Prompt Message ${index + 1}</strong><button type="button" data-remove-prompt-message="${index}">Remove</button></div>
        <div class="prompt-message-fields">
          <label class="field"><span>Role</span><select data-prompt-role="${index}">${["system", "developer", "user"].map((role) => `<option value="${role}" ${message.role === role ? "selected" : ""}>${role}</option>`).join("")}</select></label>
          <label class="field"><span>Message name</span><input value="${escapeHtml(message.name)}" data-prompt-name="${index}"></label>
          <label class="review-test-toggle"><input type="checkbox" data-prompt-enabled="${index}" ${message.enabled ? "checked" : ""}><span>Enabled</span></label>
          <label class="field wide"><span>Message content</span><textarea rows="3" data-prompt-content="${index}">${escapeHtml(message.content)}</textarea></label>
        </div>
      </div>`).join("");
    $("#agent-prompt-count").textContent = `${labState.agentPromptMessages.length} messages`;
  }

  function availablePromptVariables() {
    const candidates = promptVariableCandidates.map((item) => ({ ...item }));
    const known = new Set(candidates.map((item) => item.id));
    labState.agentStateFields.forEach((field) => {
      if (known.has(field.name)) return;
      known.add(field.name);
      candidates.push({ id: field.name, label: field.name.replaceAll("_", " "), source: "Agent state" });
    });
    labState.agentPromptVariables.forEach((variable) => {
      if (known.has(variable)) return;
      known.add(variable);
      candidates.push({ id: variable, label: variable.replaceAll("_", " "), source: "Generated blueprint" });
    });
    return candidates;
  }

  function renderPromptVariables() {
    const picker = $("#agent-prompt-variable-picker");
    if (!picker) return;
    const selected = new Set(labState.agentPromptVariables);
    picker.innerHTML = availablePromptVariables().map((candidate) => `
      <label class="prompt-variable-option ${selected.has(candidate.id) ? "selected" : ""}">
        <input type="checkbox" value="${escapeHtml(candidate.id)}" data-prompt-variable="${escapeHtml(candidate.id)}" ${selected.has(candidate.id) ? "checked" : ""}>
        <span><strong>${escapeHtml(candidate.label)}</strong><small>{${escapeHtml(candidate.id)}} · ${escapeHtml(candidate.source)}</small></span>
      </label>`).join("");
  }

  function renderStateFields() {
    $("#agent-state-fields").innerHTML = labState.agentStateFields.map((field, index) => `
      <div class="state-field-card" data-state-field-index="${index}">
        <div class="card-heading"><strong>State field ${index + 1}</strong><button type="button" data-remove-state-field="${index}">Remove</button></div>
        <div class="state-field-fields">
          <label class="field"><span>Name</span><input value="${escapeHtml(field.name)}" data-state-name="${index}"></label>
          <label class="field"><span>Type</span><select data-state-type="${index}">${["string", "number", "boolean", "object", "array"].map((value) => `<option value="${value}" ${field.value_type === value ? "selected" : ""}>${value}</option>`).join("")}</select></label>
          <label class="field"><span>Source</span><select data-state-source="${index}">${["input", "capability", "agent", "governance", "runtime"].map((value) => `<option value="${value}" ${field.source === value ? "selected" : ""}>${value}</option>`).join("")}</select></label>
          <label class="field"><span>Reducer</span><select data-state-reducer="${index}">${["replace", "append", "merge"].map((value) => `<option value="${value}" ${field.reducer === value ? "selected" : ""}>${value}</option>`).join("")}</select></label>
          <label class="review-test-toggle"><input type="checkbox" data-state-required="${index}" ${field.required ? "checked" : ""}><span>Required</span></label>
          <label class="field description"><span>Description</span><textarea rows="2" data-state-description="${index}">${escapeHtml(field.description)}</textarea></label>
        </div>
      </div>`).join("");
    $("#agent-state-count").textContent = `${labState.agentStateFields.length} fields`;
    renderPromptVariables();
  }

  function renderOutputFields() {
    const types = ["string", "number", "integer", "boolean", "object", "array"];
    const roles = ["introduction", "narrative", "table", "chart_spec", "html_fragment", "d3_spec", "dashboard", "methodology", "results", "recommendations", "evidence", "metadata", "other"];
    const formats = ["none", "date", "date-time", "duration", "email", "uuid", "markdown", "html", "json"];
    $("#agent-output-fields").innerHTML = labState.agentOutputFields.map((field, index) => `
      <div class="output-field-card" data-output-field-index="${index}">
        <div class="card-heading"><strong>Output field ${index + 1} · ${escapeHtml(field.title)}</strong><button type="button" data-remove-output-field="${index}">Remove</button></div>
        <div class="output-field-grid">
          <label class="field"><span>Field name</span><input value="${escapeHtml(field.name)}" data-output-field-name="${index}"></label>
          <label class="field"><span>Human title</span><input value="${escapeHtml(field.title)}" data-output-field-title="${index}"></label>
          <label class="field important-attribute"><span>JSON type</span><select data-output-field-type="${index}">${types.map((value) => `<option value="${value}" ${field.value_type === value ? "selected" : ""}>${value}</option>`).join("")}</select></label>
          <label class="field important-attribute"><span>Semantic role</span><select data-output-field-role="${index}">${roles.map((value) => `<option value="${value}" ${field.semantic_role === value ? "selected" : ""}>${value.replaceAll("_", " ")}</option>`).join("")}</select></label>
          <label class="field"><span>Content format</span><select data-output-field-format="${index}">${formats.map((value) => `<option value="${value}" ${field.format === value ? "selected" : ""}>${value}</option>`).join("")}</select></label>
          <label class="field"><span>Merge behavior</span><select data-output-field-merge="${index}">${["replace", "append", "merge"].map((value) => `<option value="${value}" ${field.merge_strategy === value ? "selected" : ""}>${value}</option>`).join("")}</select></label>
          <label class="review-test-toggle"><input type="checkbox" data-output-field-nullable="${index}" ${field.nullable ? "checked" : ""}><span>Nullable when evidence is unavailable</span></label>
          <label class="review-test-toggle"><input type="checkbox" data-output-field-citations="${index}" ${field.citation_required ? "checked" : ""}><span>Evidence references required</span></label>
          <label class="field wide intent-field"><span>Description</span><textarea rows="3" data-output-field-description="${index}">${escapeHtml(field.description)}</textarea></label>
          <label class="field"><span>Enum values · comma separated</span><input value="${escapeHtml(field.enum_values.join(", "))}" data-output-field-enum="${index}"></label>
          <label class="field"><span>Producing pass IDs · comma separated</span><input value="${escapeHtml(field.produced_in_passes.join(", "))}" data-output-field-passes="${index}"></label>
          <label class="field wide"><span>Validation rule</span><textarea rows="2" data-output-field-validation="${index}">${escapeHtml(field.validation_rule)}</textarea></label>
          <label class="field wide"><span>Nested object or array-item JSON Schema · optional</span><textarea rows="4" class="mono-field" data-output-field-schema="${index}">${escapeHtml(field.nested_schema_json)}</textarea><small>Use a strict object schema for structured table/chart items. Leave blank for scalar arrays.</small></label>
        </div>
      </div>`).join("");
    $("#agent-output-field-count").textContent = `${labState.agentOutputFields.length} ${labState.agentOutputFields.length === 1 ? "field" : "fields"}`;
  }

  function renderOutputPasses() {
    $("#agent-output-passes").innerHTML = labState.agentOutputPasses.map((outputPass, index) => `
      <div class="output-pass-card" data-output-pass-index="${index}">
        <div class="card-heading"><strong>Pass ${index + 1} · ${escapeHtml(outputPass.title)}</strong><button type="button" data-remove-output-pass="${index}">Remove</button></div>
        <div class="output-pass-grid">
          <label class="field"><span>Pass ID</span><input value="${escapeHtml(outputPass.pass_id)}" data-output-pass-id="${index}"></label>
          <label class="field"><span>Pass title</span><input value="${escapeHtml(outputPass.title)}" data-output-pass-title="${index}"></label>
          <label class="field wide intent-field"><span>Objective</span><textarea rows="3" data-output-pass-objective="${index}">${escapeHtml(outputPass.objective)}</textarea></label>
          <label class="field"><span>Target field names</span><input value="${escapeHtml(outputPass.target_fields.join(", "))}" data-output-pass-targets="${index}"></label>
          <label class="field"><span>Depends on pass IDs</span><input value="${escapeHtml(outputPass.depends_on.join(", "))}" data-output-pass-dependencies="${index}"></label>
          <label class="field"><span>Operation</span><select data-output-pass-operation="${index}">${["replace", "append", "merge"].map((value) => `<option value="${value}" ${outputPass.operation === value ? "selected" : ""}>${value}</option>`).join("")}</select></label>
          <label class="field"><span>Context policy</span><select data-output-pass-context="${index}">${["full_context", "evidence_subset", "prior_output_summary", "selected_prior_fields"].map((value) => `<option value="${value}" ${outputPass.context_policy === value ? "selected" : ""}>${value.replaceAll("_", " ")}</option>`).join("")}</select></label>
          <label class="field"><span>Maximum output tokens</span><input type="number" min="256" max="16000" step="256" value="${outputPass.max_output_tokens}" data-output-pass-tokens="${index}"></label>
          <label class="review-test-toggle"><input type="checkbox" data-output-pass-review="${index}" ${outputPass.human_review_after ? "checked" : ""}><span>Human review after this pass</span></label>
          <label class="field wide"><span>Pass quality gate</span><textarea rows="2" data-output-pass-quality="${index}">${escapeHtml(outputPass.quality_gate)}</textarea></label>
        </div>
      </div>`).join("");
    $("#agent-output-pass-count").textContent = `${labState.agentOutputPasses.length} ${labState.agentOutputPasses.length === 1 ? "pass" : "passes"}`;
    renderAssemblyRuntime();
  }

  function renderAssemblyRuntime() {
    const completed = new Set(labState.outputAssemblyCompleted);
    const nextIndex = labState.agentOutputPasses.findIndex((item) => !completed.has(item.pass_id));
    $("#agent-assembly-progress").innerHTML = labState.agentOutputPasses.map((outputPass, index) => {
      const state = completed.has(outputPass.pass_id) ? "complete" : index === nextIndex ? "current" : "pending";
      return `<div class="assembly-progress-item ${state}"><i>${completed.has(outputPass.pass_id) ? "✓" : index + 1}</i><span><strong>${escapeHtml(outputPass.title)}</strong><small>${escapeHtml(outputPass.target_fields.join(", "))} · ${outputPass.max_output_tokens.toLocaleString()} token ceiling</small></span></div>`;
    }).join("");
    $("#agent-assembly-artifact").textContent = JSON.stringify(labState.outputAssemblyArtifact, null, 2);
    const html = labState.outputAssemblyArtifact.dashboard_html;
    const introduction = labState.outputAssemblyArtifact.introduction;
    const results = labState.outputAssemblyArtifact.results;
    $("#agent-assembly-preview").innerHTML = html
      ? `<iframe sandbox title="Sandboxed assembled dashboard" srcdoc="${escapeHtml(html)}"></iframe>`
      : `<article>${introduction ? `<h3>Introduction</h3><p>${escapeHtml(introduction)}</p>` : ""}${results ? `<h3>Results</h3><p>${escapeHtml(results)}</p>` : ""}${!introduction && !results ? "<p>Run passes to populate the artifact preview.</p>" : ""}</article>`;
    $("#agent-assembly-log").innerHTML = labState.outputAssemblyLog.length
      ? labState.outputAssemblyLog.map((item) => `<div class="assembly-log-item"><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.summary)}</span><small>${escapeHtml(item.receipt)}</small></div>`).join("")
      : `<div class="empty-state">No output pass has run.</div>`;
    const finished = nextIndex === -1 && labState.agentOutputPasses.length > 0;
    $("#agent-assembly-status").textContent = labState.outputAssemblyReviewPending
      ? `Review · ${labState.outputAssemblyReviewPending}`
      : finished ? "Complete" : completed.size ? `${completed.size}/${labState.agentOutputPasses.length} passes` : "Not started";
    $("#run-agent-output-pass").textContent = labState.outputAssemblyReviewPending ? "Approve pass and continue" : "Run next pass";
    $("#run-agent-output-pass").disabled = finished && !labState.outputAssemblyReviewPending;
  }

  function renderSectionIntentControls() {
    Object.entries(agentSectionDefinitions).forEach(([sectionKey, definition]) => {
      const body = document.querySelector(`[data-agent-section="${sectionKey}"] .agent-section-body`);
      if (!body || body.querySelector(".section-intent-author")) return;
      body.insertAdjacentHTML("afterbegin", `
        <div class="section-intent-author">
          <div class="section-intent-copy"><span>Describe instead of configuring</span><strong>${escapeHtml(definition.label)}</strong><small>Your description can populate this section. The detailed controls remain available for precise changes.</small></div>
          <textarea rows="3" data-section-intent="${escapeHtml(sectionKey)}" placeholder="${escapeHtml(definition.text)}"></textarea>
          <button class="button section-generate-button" type="button" data-generate-agent-section="${escapeHtml(sectionKey)}">Generate this section</button>
        </div>`);
    });
  }

  function agentHelpPanelMarkup(sectionKey, help) {
    const paragraph = `${help.works} ${help.describe} ${help.compile} To finish: generate or edit the section, validate the complete blueprint, then compile the executable agent.`;
    return `
      <div class="agent-help-panel" id="agent-help-${escapeHtml(sectionKey)}" data-agent-help-panel="${escapeHtml(sectionKey)}" role="tooltip" aria-live="polite" hidden><p>${escapeHtml(paragraph)}</p></div>`;
  }

  function renderAgentHelpControls() {
    const launcher = document.querySelector(".agent-description-launcher");
    if (launcher && !launcher.querySelector('[data-agent-help="whole"]')) {
      launcher.insertAdjacentHTML("afterbegin", `<button class="agent-help-button launcher-help-button" type="button" data-agent-help="whole" aria-expanded="false" aria-controls="agent-help-whole" aria-label="Explain how the whole-agent description works">?</button>`);
      launcher.insertAdjacentHTML("beforeend", agentHelpPanelMarkup("whole", agentSectionHelp.whole));
    }
    Object.entries(agentSectionHelp).forEach(([sectionKey, help]) => {
      if (sectionKey === "whole") return;
      const section = document.querySelector(`[data-agent-section="${sectionKey}"]`);
      const summary = section?.querySelector(":scope > summary");
      if (!section || !summary || summary.querySelector("[data-agent-help]")) return;
      summary.insertAdjacentHTML("beforeend", `<button class="agent-help-button" type="button" data-agent-help="${escapeHtml(sectionKey)}" aria-expanded="false" aria-controls="agent-help-${escapeHtml(sectionKey)}" aria-label="Explain ${escapeHtml(help.title)}">?</button>`);
      summary.insertAdjacentHTML("afterend", agentHelpPanelMarkup(sectionKey, help));
    });
  }

  let agentHelpTimer = null;

  function closeAgentHelp() {
    if (agentHelpTimer) window.clearTimeout(agentHelpTimer);
    agentHelpTimer = null;
    document.querySelectorAll("[data-agent-help-panel]").forEach((item) => { item.hidden = true; });
    document.querySelectorAll("[data-agent-help]").forEach((item) => item.setAttribute("aria-expanded", "false"));
  }

  function toggleAgentHelp(button) {
    const sectionKey = button.dataset.agentHelp;
    const panel = document.querySelector(`[data-agent-help-panel="${sectionKey}"]`);
    if (!panel) return;
    const willOpen = panel.hidden;
    closeAgentHelp();
    if (willOpen) {
      panel.hidden = false;
      button.setAttribute("aria-expanded", "true");
      button.closest("details")?.setAttribute("open", "");
      agentHelpTimer = window.setTimeout(closeAgentHelp, 14000);
    }
  }

  function cohereGeneratedAssembly(blueprint) {
    const fieldNames = new Set(blueprint.structured_output.fields.map((field) => field.name));
    const passes = blueprint.output_assembly.passes;
    passes.forEach((outputPass) => {
      outputPass.target_fields = outputPass.target_fields.filter((name) => fieldNames.has(name));
      if (!outputPass.target_fields.length && blueprint.structured_output.fields[0]) outputPass.target_fields = [blueprint.structured_output.fields[0].name];
    });
    const passIds = new Set(passes.map((outputPass) => outputPass.pass_id));
    passes.forEach((outputPass) => {
      outputPass.depends_on = outputPass.depends_on.filter((passId) => passIds.has(passId) && passId !== outputPass.pass_id);
    });
    blueprint.structured_output.fields.forEach((field) => {
      const producers = passes.filter((outputPass) => outputPass.target_fields.includes(field.name)).map((outputPass) => outputPass.pass_id);
      if (!producers.length && passes[0]) {
        passes[0].target_fields.push(field.name);
        producers.push(passes[0].pass_id);
      }
      field.produced_in_passes = producers;
    });
    const requested = passes.reduce((sum, outputPass) => sum + Number(outputPass.max_output_tokens || 0), 0);
    blueprint.output_assembly.max_total_output_tokens = Math.max(1000, requested, blueprint.output_assembly.max_total_output_tokens || 0);
  }

  function applyGeneratedSection(section, value) {
    const blueprint = currentAgentBlueprint();
    if (section === "identity") Object.assign(blueprint, value);
    else if (section === "instructions") blueprint.instructions = value;
    else if (section === "prompts") Object.assign(blueprint, value);
    else if (section === "state") Object.assign(blueprint, value);
    else if (section === "routing") blueprint.routing = value;
    else if (section === "memory") blueprint.memory_rules = value;
    else if (section === "capabilities") blueprint.capability_latches = value.capability_latches;
    else if (section === "governance") blueprint.governance = value;
    else if (section === "structured_output") {
      blueprint.structured_output = value;
      const passId = "build_output";
      blueprint.structured_output.fields.forEach((field) => { field.produced_in_passes = [passId]; });
      blueprint.output_assembly.passes = [{
        pass_id: passId,
        title: "Build structured output",
        objective: "Populate every currently declared output field from the supplied context and accepted evidence.",
        target_fields: blueprint.structured_output.fields.map((field) => field.name),
        operation: "replace",
        context_policy: "full_context",
        depends_on: [],
        max_output_tokens: Math.min(12000, Math.max(3000, blueprint.structured_output.fields.length * 1200)),
        quality_gate: "Every declared field is schema-valid, evidence-grounded and consistent with the presentation contract.",
        human_review_after: true,
      }];
      blueprint.output_assembly.max_total_output_tokens = blueprint.output_assembly.passes[0].max_output_tokens;
    } else if (section === "assembly") {
      blueprint.output_assembly = value;
      cohereGeneratedAssembly(blueprint);
    } else if (section === "reliability") Object.assign(blueprint, value);

    if (blueprint.governance.human_approval) blueprint.routing.strategy = "human_review";
    if (!blueprint.governance.human_approval && blueprint.routing.strategy === "human_review") blueprint.routing.strategy = "reflection";
    if (blueprint.governance.evidence_required && !blueprint.capability_latches.some((latch) => latch.capability_id === "evidence_critic")) {
      blueprint.capability_latches.push({ capability_id: "evidence_critic", purpose: "Check every material claim against supplied evidence.", invocation_condition: "After drafting and before any human review.", output_binding: "critique", required: true, failure_policy: "human_review" });
    }
    applyAgentBlueprint(blueprint);
  }

  async function generateAgentSection(sectionKey, button) {
    const definition = agentSectionDefinitions[sectionKey];
    const input = document.querySelector(`[data-section-intent="${sectionKey}"]`);
    const description = input?.value.trim() || "";
    if (!definition || description.length < 10) {
      input?.focus();
      $("#agent-builder-status").textContent = "Write a description first";
      $("#agent-validation-summary").className = "validation-summary";
      $("#agent-validation-summary").innerHTML = "<span>Description required</span><small>The grey instructional text is an example only and is never sent to the planner.</small>";
      return;
    }
    button.disabled = true;
    button.textContent = "Generating…";
    $("#agent-builder-status").textContent = `${definition.label}…`;
    try {
      const result = await agentApi("/api/agents/blueprint/plan-section", {
        method: "POST",
        body: JSON.stringify({
          section: definition.api,
          description,
          draft: currentAgentBlueprint(),
          model: $("#agent-model").value,
        }),
      });
      applyGeneratedSection(result.section, result.value);
      const tokens = Number(result.receipt.input_tokens || 0) + Number(result.receipt.output_tokens || 0);
      $("#agent-builder-status").textContent = `${definition.label} generated`;
      $("#agent-validation-summary").className = "validation-summary valid";
      $("#agent-validation-summary").innerHTML = `<span>Section populated</span><small>${escapeHtml(result.receipt.model)} · ${tokens} tokens · stored=false · validate the complete blueprint when ready.</small>`;
    } catch (error) {
      $("#agent-builder-status").textContent = "Section generation failed";
      $("#agent-validation-summary").className = "validation-summary";
      $("#agent-validation-summary").innerHTML = `<span>Section unchanged</span><small>${escapeHtml(error.message)}</small>`;
    } finally {
      button.disabled = false;
      button.textContent = "Generate this section";
    }
  }

  function currentAgentBlueprint() {
    const enabledLatches = capabilities.map((capability) => labState.agentCapabilityLatches[capability.id]).filter((latch) => latch?.enabled);
    return {
      name: $("#agent-name").value.trim() || "Untitled agent",
      purpose: $("#agent-purpose").value.trim(),
      model: $("#agent-config-model").value,
      input_contract: $("#agent-input").value,
      output_contract: $("#agent-output").value,
      instructions: {
        objective: $("#agent-objective").value.trim(),
        success_criteria: listFrom("#agent-success-criteria"),
        constraints: listFrom("#agent-constraints"),
        stopping_conditions: listFrom("#agent-stopping-conditions"),
        narrative_style: $("#agent-narrative-style").value.trim(),
      },
      prompt_messages: labState.agentPromptMessages.map(({ role, name, content, enabled }) => ({ role, name, content, enabled })),
      prompt_template: {
        template: $("#agent-prompt-template").value,
        variables: [...labState.agentPromptVariables],
        missing_variable_policy: $("#agent-prompt-missing-policy").value,
        output_format_instruction: $("#agent-output-format-instruction").value.trim(),
      },
      state_management_description: $("#agent-state-description").value.trim(),
      state_schema: labState.agentStateFields.map(({ name, value_type, description, source, required, reducer }) => ({ name, value_type, description, source, required, reducer })),
      routing: {
        description: $("#agent-routing-description").value.trim(),
        strategy: $("#agent-pattern").value,
        entry_condition: $("#agent-entry-condition").value.trim(),
        revision_condition: $("#agent-revision-condition").value.trim(),
        escalation_condition: $("#agent-escalation-condition").value.trim(),
        stop_condition: $("#agent-stop-condition").value.trim(),
        missing_evidence_route: $("#agent-missing-evidence-route").value,
        max_iterations: Number($("#agent-max-iterations").value),
      },
      memory_rules: {
        description: $("#agent-memory-description").value.trim(),
        scope: $("#agent-memory-scope").value,
        checkpoint: $("#agent-memory").value,
        remember_fields: commaListFrom("#agent-remember-fields"),
        retention_rule: $("#agent-retention-rule").value.trim(),
        compaction_rule: $("#agent-compaction-rule").value.trim(),
      },
      governance: {
        description: $("#agent-governance-description").value.trim(),
        evidence_required: $("#agent-evidence-required").checked,
        human_approval: $("#agent-human-review").checked,
        abstention_rule: $("#agent-abstention-rule").value.trim(),
        prohibited_actions: listFrom("#agent-prohibited-actions"),
        effects_allowed: false,
      },
      capability_latches: enabledLatches.map(({ capability_id, purpose, invocation_condition, output_binding, required, failure_policy }) => ({
        capability_id, purpose, invocation_condition, output_binding, required, failure_policy,
      })),
      structured_output: {
        name: $("#agent-structured-output-name").value.trim(),
        description: $("#agent-structured-output-description").value.trim(),
        rendering_target: $("#agent-output-rendering-target").value,
        strict: true,
        additional_properties: false,
        presentation: {
          description: $("#agent-presentation-description").value.trim(),
          composition: $("#agent-output-composition").value,
          visual_hierarchy: $("#agent-output-visual-hierarchy").value.trim(),
          tone: $("#agent-output-tone").value.trim(),
          information_density: $("#agent-output-density").value,
          typography_direction: $("#agent-output-typography").value.trim(),
          color_direction: $("#agent-output-color").value.trim(),
          chart_policy: $("#agent-output-chart-policy").value.trim(),
          table_policy: $("#agent-output-table-policy").value.trim(),
          html_policy: $("#agent-output-html-policy").value.trim(),
          responsive_behavior: $("#agent-output-responsive").value.trim(),
          accessibility_requirements: listFrom("#agent-output-accessibility"),
          rendering_instructions: $("#agent-output-rendering-instructions").value.trim(),
        },
        fields: labState.agentOutputFields.map((field) => ({ ...field })),
        completion_rule: $("#agent-output-completion-rule").value.trim(),
        quality_gate: $("#agent-output-quality-gate").value.trim(),
        versioning_strategy: $("#agent-output-versioning").value,
      },
      output_assembly: {
        description: $("#agent-assembly-description").value.trim(),
        strategy: $("#agent-assembly-strategy").value,
        passes: labState.agentOutputPasses.map((outputPass) => ({ ...outputPass })),
        carry_forward_rule: $("#agent-assembly-carry-rule").value.trim(),
        finalization_rule: $("#agent-assembly-final-rule").value.trim(),
        max_total_output_tokens: Number($("#agent-assembly-token-budget").value),
        stop_on_failure: $("#agent-assembly-stop-failure").checked,
        human_review_between_passes: $("#agent-assembly-human-between").checked,
      },
      retry_attempts: Number($("#agent-retries").value),
      timeout_seconds: Number($("#agent-timeout").value),
    };
  }

  function currentAgentDefinition() {
    const blueprint = labState.agentBlueprint || currentAgentBlueprint();
    return {
      id: `agent-${String(blueprint.name).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}`,
      name: blueprint.name,
      framework: "langgraph",
      role: blueprint.routing.strategy === "human_review" ? "reviewer" : "interpreter",
      input: blueprint.input_contract,
      output: blueprint.output_contract,
      engine: "langgraph",
      instructions: compiledInstructions(blueprint),
      capabilities: blueprint.capability_latches.map((latch) => latch.capability_id),
      blueprint,
      compiledArtifact: labState.agentCompile?.artifact_id || null,
    };
  }

  function frameworkLabel(value) {
    return {
      custom: "Custom typed Python",
      langgraph: "Compiled LangGraph",
      agents_sdk: "OpenAI Agents SDK agent",
    }[value] || value;
  }

  async function agentApi(path, options = {}) {
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof body.detail === "string"
        ? body.detail
        : Array.isArray(body.detail)
          ? body.detail.map((item) => `${item.loc?.at(-1) || "field"}: ${item.msg}`).join(" · ")
          : "The local agent service returned an error.";
      throw new Error(detail);
    }
    return body;
  }

  async function initializeAgentRuntime() {
    try {
      const runtime = await agentApi("/api/agents/runtime");
      labState.agentRuntime = runtime;
      $("#agent-langgraph-dot").className = `runtime-dot ${runtime.langgraph.available ? "" : "error"}`;
      $("#agent-langgraph-status").textContent = runtime.langgraph.available
        ? `Installed ${runtime.langgraph.version} · executable`
        : "Dependency unavailable";
      const openaiReady = runtime.openai.available && runtime.openai.key_configured;
      $("#agent-openai-dot").className = `runtime-dot ${openaiReady ? "" : "error"}`;
      $("#agent-openai-status").textContent = openaiReady
        ? `SDK ${runtime.openai.sdk_version} · Keychain connected`
        : "SDK or server credential unavailable";
      $("#agent-framework-truth").textContent = runtime.langgraph.available
        ? "Real LangGraph runtime"
        : "Runtime blocked";
      if (runtime.models?.length) {
        const selected = $("#agent-model").value;
        $("#agent-model").innerHTML = runtime.models.map((model) =>
          `<option value="${escapeHtml(model.id)}">${escapeHtml(model.label)}</option>`).join("");
        if (runtime.models.some((model) => model.id === selected)) $("#agent-model").value = selected;
      }
    } catch (error) {
      $("#agent-langgraph-dot").className = "runtime-dot error";
      $("#agent-openai-dot").className = "runtime-dot error";
      $("#agent-langgraph-status").textContent = "Local API unavailable";
      $("#agent-openai-status").textContent = "Local API unavailable";
      $("#agent-framework-truth").textContent = "Open through localhost";
    }
  }

  function renderPromptPreview() {
    const blueprint = currentAgentBlueprint();
    const synthetic = {
      as_of_date: "2008-09-15",
      issue: "Largest position exceeds the reviewed concentration threshold.",
      daily_return: "-3.10%",
      var_95: "2.60%",
      largest_weight: "31.0%",
      evidence_state: "complete",
    };
    let value = blueprint.prompt_template.template;
    blueprint.prompt_template.variables.forEach((variable) => {
      const placeholder = `{${variable}}`;
      if (Object.hasOwn(synthetic, variable)) value = value.replaceAll(placeholder, synthetic[variable]);
    });
    $("#agent-prompt-preview").textContent = value;
    $("#agent-instructions-preview").textContent = compiledInstructions(blueprint);
  }

  function renderSectionReadiness(blueprint) {
    const sections = [
      ["Identity", blueprint.name.length >= 3 && blueprint.purpose.length >= 20, `${blueprint.input_contract} → ${blueprint.output_contract}`],
      ["Instructions", blueprint.instructions.success_criteria.length > 0 && blueprint.instructions.constraints.length > 0, `${blueprint.instructions.success_criteria.length} success criteria`],
      ["Prompt stack", blueprint.prompt_messages.length > 0 && blueprint.prompt_template.variables.length > 0, `${blueprint.prompt_messages.length} messages · ${blueprint.prompt_template.variables.length} variables`],
      ["State", blueprint.state_schema.length > 0, `${blueprint.state_schema.length} typed fields`],
      ["Routing", blueprint.routing.description.length >= 20, blueprint.routing.strategy.replaceAll("_", " ")],
      ["Memory", blueprint.memory_rules.description.length >= 20, blueprint.memory_rules.scope.replaceAll("_", " ")],
      ["Capabilities", blueprint.capability_latches.length > 0, `${blueprint.capability_latches.length} latched`],
      ["Governance", blueprint.governance.prohibited_actions.length > 0, blueprint.governance.human_approval ? "human approval" : "effect-free output"],
      ["Structured output", blueprint.structured_output.fields.length > 0, `${blueprint.structured_output.fields.length} typed fields`],
      ["Output assembly", blueprint.output_assembly.passes.length > 0, `${blueprint.output_assembly.passes.length} bounded passes`],
    ];
    $("#agent-section-readiness").innerHTML = sections.map(([name, ready, detail]) => `
      <div><i class="${ready ? "" : "incomplete"}"></i><strong>${escapeHtml(name)}</strong><small>${escapeHtml(detail)}</small></div>`).join("");
  }

  function renderAgentContract(invalidate = true) {
    const blueprint = currentAgentBlueprint();
    $("#agent-blueprint-json").textContent = JSON.stringify(blueprint, null, 2);
    $("#agent-contract-flow").innerHTML = `<span>${escapeHtml(blueprint.input_contract)}</span><i>→</i><span>${escapeHtml(blueprint.name)}</span><i>→</i><span>${escapeHtml(blueprint.output_contract)}</span>`;
    renderPromptPreview();
    renderSectionReadiness(blueprint);
    if (invalidate && labState.agentCompile) {
      labState.agentCompile = null;
    }
    $("#agent-blueprint-status").textContent = "Draft";
    $("#agent-validation-summary").className = "validation-summary";
    $("#agent-validation-summary").innerHTML = "<span>Not validated</span><small>Validate before compiling or executing.</small>";
  }

  function applyAgentBlueprint(blueprint) {
    labState.agentBlueprint = blueprint;
    $("#agent-name").value = blueprint.name;
    $("#agent-purpose").value = blueprint.purpose;
    $("#agent-model").value = blueprint.model;
    $("#agent-config-model").value = blueprint.model;
    $("#agent-input").value = blueprint.input_contract;
    $("#agent-output").value = blueprint.output_contract;
    $("#agent-objective").value = blueprint.instructions.objective;
    $("#agent-success-criteria").value = blueprint.instructions.success_criteria.join("\n");
    $("#agent-constraints").value = blueprint.instructions.constraints.join("\n");
    $("#agent-stopping-conditions").value = blueprint.instructions.stopping_conditions.join("\n");
    $("#agent-narrative-style").value = blueprint.instructions.narrative_style;
    labState.agentPromptMessages = blueprint.prompt_messages.map((message) => ({ ...message }));
    $("#agent-prompt-template").value = blueprint.prompt_template.template;
    labState.agentPromptVariables = [...blueprint.prompt_template.variables];
    $("#agent-prompt-missing-policy").value = blueprint.prompt_template.missing_variable_policy;
    $("#agent-output-format-instruction").value = blueprint.prompt_template.output_format_instruction;
    $("#agent-state-description").value = blueprint.state_management_description || "";
    labState.agentStateFields = blueprint.state_schema.map((field) => ({ ...field }));
    $("#agent-routing-description").value = blueprint.routing.description;
    $("#agent-pattern").value = blueprint.routing.strategy;
    $("#agent-entry-condition").value = blueprint.routing.entry_condition;
    $("#agent-revision-condition").value = blueprint.routing.revision_condition;
    $("#agent-escalation-condition").value = blueprint.routing.escalation_condition;
    $("#agent-stop-condition").value = blueprint.routing.stop_condition;
    $("#agent-missing-evidence-route").value = blueprint.routing.missing_evidence_route;
    $("#agent-max-iterations").value = String(blueprint.routing.max_iterations);
    $("#agent-memory-description").value = blueprint.memory_rules.description;
    $("#agent-memory-scope").value = blueprint.memory_rules.scope;
    $("#agent-memory").value = blueprint.memory_rules.checkpoint;
    $("#agent-remember-fields").value = blueprint.memory_rules.remember_fields.join(", ");
    $("#agent-retention-rule").value = blueprint.memory_rules.retention_rule;
    $("#agent-compaction-rule").value = blueprint.memory_rules.compaction_rule;
    $("#agent-governance-description").value = blueprint.governance.description;
    $("#agent-human-review").checked = blueprint.governance.human_approval;
    $("#agent-evidence-required").checked = blueprint.governance.evidence_required;
    $("#agent-abstention-rule").value = blueprint.governance.abstention_rule;
    $("#agent-prohibited-actions").value = blueprint.governance.prohibited_actions.join("\n");
    $("#agent-structured-output-name").value = blueprint.structured_output.name;
    $("#agent-structured-output-description").value = blueprint.structured_output.description;
    $("#agent-output-rendering-target").value = blueprint.structured_output.rendering_target;
    $("#agent-output-versioning").value = blueprint.structured_output.versioning_strategy;
    $("#agent-presentation-description").value = blueprint.structured_output.presentation.description;
    $("#agent-output-composition").value = blueprint.structured_output.presentation.composition;
    $("#agent-output-visual-hierarchy").value = blueprint.structured_output.presentation.visual_hierarchy;
    $("#agent-output-tone").value = blueprint.structured_output.presentation.tone;
    $("#agent-output-density").value = blueprint.structured_output.presentation.information_density;
    $("#agent-output-typography").value = blueprint.structured_output.presentation.typography_direction;
    $("#agent-output-color").value = blueprint.structured_output.presentation.color_direction;
    $("#agent-output-chart-policy").value = blueprint.structured_output.presentation.chart_policy;
    $("#agent-output-table-policy").value = blueprint.structured_output.presentation.table_policy;
    $("#agent-output-html-policy").value = blueprint.structured_output.presentation.html_policy;
    $("#agent-output-responsive").value = blueprint.structured_output.presentation.responsive_behavior;
    $("#agent-output-accessibility").value = blueprint.structured_output.presentation.accessibility_requirements.join("\n");
    $("#agent-output-rendering-instructions").value = blueprint.structured_output.presentation.rendering_instructions;
    $("#agent-output-completion-rule").value = blueprint.structured_output.completion_rule;
    $("#agent-output-quality-gate").value = blueprint.structured_output.quality_gate;
    labState.agentOutputFields = blueprint.structured_output.fields.map((field) => ({ ...field }));
    $("#agent-assembly-description").value = blueprint.output_assembly.description;
    $("#agent-assembly-strategy").value = blueprint.output_assembly.strategy;
    $("#agent-assembly-carry-rule").value = blueprint.output_assembly.carry_forward_rule;
    $("#agent-assembly-final-rule").value = blueprint.output_assembly.finalization_rule;
    $("#agent-assembly-token-budget").value = String(blueprint.output_assembly.max_total_output_tokens);
    $("#agent-assembly-stop-failure").checked = blueprint.output_assembly.stop_on_failure;
    $("#agent-assembly-human-between").checked = blueprint.output_assembly.human_review_between_passes;
    labState.agentOutputPasses = blueprint.output_assembly.passes.map((outputPass) => ({ ...outputPass }));
    labState.outputAssemblyArtifact = {};
    labState.outputAssemblyCompleted = [];
    labState.outputAssemblyLog = [];
    labState.outputAssemblyReviewPending = null;
    $("#agent-retries").value = String(blueprint.retry_attempts);
    $("#agent-timeout").value = String(blueprint.timeout_seconds);
    capabilities.forEach((capability) => {
      const proposed = blueprint.capability_latches.find((latch) => latch.capability_id === capability.id);
      const prior = labState.agentCapabilityLatches[capability.id] || {};
      labState.agentCapabilityLatches[capability.id] = proposed
        ? { ...proposed, enabled: true }
        : { ...prior, capability_id: capability.id, enabled: false };
    });
    renderPromptMessages();
    renderStateFields();
    renderPromptVariables();
    renderCapabilities();
    renderOutputFields();
    renderOutputPasses();
    renderAgentContract(false);
  }

  function switchAgentOutputTab(tab) {
    $$("[data-agent-output-tab]").forEach((button) => button.classList.toggle("active", button.dataset.agentOutputTab === tab));
    $$(".agent-output-view").forEach((view) => view.classList.toggle("active", view.id === `agent-output-${tab}`));
  }

  async function generateAgentBlueprint() {
    const button = $("#generate-agent-blueprint");
    const description = $("#agent-description").value.trim();
    if (description.length < 20) {
      $("#agent-builder-status").textContent = "Description too short";
      return;
    }
    button.disabled = true;
    button.textContent = "OpenAI is planning…";
    $("#agent-builder-status").textContent = "Planning";
    try {
      const result = await agentApi("/api/agents/blueprint/plan", {
        method: "POST",
        body: JSON.stringify({
          description,
          model: $("#agent-model").value,
          draft: currentAgentBlueprint(),
        }),
      });
      applyAgentBlueprint(result.blueprint);
      $("#agent-builder-status").textContent = "Blueprint generated";
      $("#agent-blueprint-status").textContent = "OpenAI + schema";
      $("#agent-validation-summary").className = "validation-summary valid";
      $("#agent-validation-summary").innerHTML = `<span>Validated</span><small>${escapeHtml(result.receipt.model)} · ${result.receipt.input_tokens + result.receipt.output_tokens} tokens · ${result.receipt.elapsed_ms} ms · stored=false</small>`;
      $("#agent-compile-checks").innerHTML = `<div class="agent-receipt">Structured blueprint receipt · response ${escapeHtml(result.receipt.response_id || "not returned")} · no tools · no browser credential exposure</div>`;
    } catch (error) {
      $("#agent-builder-status").textContent = "Planning failed";
      $("#agent-blueprint-status").textContent = "Needs attention";
      $("#agent-validation-summary").className = "validation-summary";
      $("#agent-validation-summary").innerHTML = `<span>Error</span><small>${escapeHtml(error.message)}</small>`;
    } finally {
      button.disabled = false;
      button.textContent = "Transform description into complete blueprint";
    }
  }

  async function validateAgentBlueprint() {
    $("#agent-builder-status").textContent = "Validating";
    try {
      const result = await agentApi("/api/agents/blueprint/validate", {
        method: "POST",
        body: JSON.stringify(currentAgentBlueprint()),
      });
      labState.agentBlueprint = result.blueprint;
      applyAgentBlueprint(result.blueprint);
      $("#agent-builder-status").textContent = "Blueprint valid";
      $("#agent-blueprint-status").textContent = "Validated";
      $("#agent-validation-summary").className = "validation-summary valid";
      $("#agent-validation-summary").innerHTML = `<span>Valid</span><small>${result.checks.length} compiler checks passed. Ready to compile.</small>`;
      return result.blueprint;
    } catch (error) {
      labState.agentBlueprint = null;
      $("#agent-builder-status").textContent = "Blueprint invalid";
      $("#agent-blueprint-status").textContent = "Invalid";
      $("#agent-validation-summary").className = "validation-summary";
      $("#agent-validation-summary").innerHTML = `<span>Fix fields</span><small>${escapeHtml(error.message)}</small>`;
      throw error;
    }
  }

  function renderCompileResult(result) {
    labState.agentCompile = result;
    labState.agentBlueprint = result.blueprint;
    $("#agent-generated-code").textContent = result.source;
    $("#agent-compile-checks").innerHTML = `<div class="compile-checks">${result.checks.map((check) => `
      <div class="compile-check ${check.status === "passed" ? "" : "warning"}">
        <strong>${check.status === "passed" ? "Pass" : "Info"} · ${escapeHtml(check.name)}</strong>
        <span>${escapeHtml(check.detail)}</span>
      </div>`).join("")}</div>
      <div class="agent-receipt">Artifact ${escapeHtml(result.artifact_id)} · compiler ${escapeHtml(result.compiler_version)} · source saved locally</div>`;
    $("#agent-blueprint-status").textContent = "Compiled";
    $("#agent-builder-status").textContent = "LangGraph compiled";
  }

  async function compileAgent() {
    $("#compile-agent").disabled = true;
    $("#agent-builder-status").textContent = "Compiling";
    try {
      const blueprint = await validateAgentBlueprint();
      const result = await agentApi("/api/agents/compile", {
        method: "POST",
        body: JSON.stringify({ blueprint, persist: true }),
      });
      renderCompileResult(result);
      switchAgentOutputTab("code");
      return result;
    } catch (error) {
      $("#agent-builder-status").textContent = "Compilation failed";
      throw error;
    } finally {
      $("#compile-agent").disabled = false;
    }
  }

  async function runAgentTest() {
    $("#test-agent").disabled = true;
    $("#agent-run-status").textContent = "Running";
    try {
      const compiled = labState.agentCompile || await compileAgent();
      const result = await agentApi("/api/agents/run", {
        method: "POST",
        body: JSON.stringify({
          blueprint: compiled.blueprint,
          scenario: $("#agent-test-scenario").value,
          auto_approve_review: $("#agent-auto-review").checked,
        }),
      });
      $("#agent-run-status").textContent = result.status === "completed" ? "Completed" : "Paused for review";
      $("#agent-run-status").classList.toggle("warning", result.status !== "completed");
      $("#agent-trace").innerHTML = result.trace.map((event) =>
        `<li><strong>${escapeHtml(event.node.replaceAll("_", " "))}</strong><br>${escapeHtml(event.detail)}</li>`).join("");
      if (result.interrupted && !result.auto_approved) {
        $("#agent-trace").innerHTML += "<li><strong>human interrupt</strong><br>Execution is checkpointed and waiting for a reviewer.</li>";
      }
      const state = result.final_state;
      $("#agent-test-output").innerHTML = `
        <h3>${result.status === "completed" ? "Compiled agent completed" : "Agent is waiting for human review"}</h3>
        <p>${escapeHtml(state.narrative || "The graph paused before final state completion.")}</p>
        <ul>
          <li>Evidence critic: ${escapeHtml(state.critique || "not part of this pattern")}</li>
          <li>Human interrupt reached: ${result.interrupted ? "yes" : "no"}${result.auto_approved ? " · automatically resumed for this test" : ""}</li>
          <li>Checkpoints: ${result.checkpoint_count} · elapsed: ${result.elapsed_ms} ms</li>
          <li>Portfolio effects: none</li>
        </ul>
        <details class="run-prompt-details">
          <summary>Inspect rendered Prompt Messages + PromptTemplate</summary>
          <pre>${escapeHtml(state.rendered_prompt || "The selected route did not render a prompt.")}</pre>
        </details>
        <div class="agent-receipt">Thread ${escapeHtml(result.thread_id)} · generated artifact ${escapeHtml(result.artifact_id)}</div>`;
      $("#agent-builder-status").textContent = result.status === "completed" ? "Execution complete" : "Review interrupt";
      switchAgentOutputTab("run");
    } catch (error) {
      $("#agent-run-status").textContent = "Execution failed";
      $("#agent-run-status").classList.add("warning");
      $("#agent-test-output").innerHTML = `<h3>Execution could not complete</h3><p>${escapeHtml(error.message)}</p>`;
    } finally {
      $("#test-agent").disabled = false;
    }
  }

  function resetOutputAssembly() {
    labState.outputAssemblyArtifact = {};
    labState.outputAssemblyCompleted = [];
    labState.outputAssemblyLog = [];
    labState.outputAssemblyReviewPending = null;
    $("#agent-assembly-status").classList.remove("warning");
    renderAssemblyRuntime();
  }

  async function runNextOutputPass() {
    if (labState.outputAssemblyReviewPending) {
      const approved = labState.outputAssemblyReviewPending;
      labState.outputAssemblyReviewPending = null;
      labState.outputAssemblyLog.push({
        title: "Human review recorded",
        summary: `${approved} was accepted for continued assembly.`,
        receipt: "Local review boundary · no portfolio effect",
      });
      renderAssemblyRuntime();
      return;
    }
    const completed = new Set(labState.outputAssemblyCompleted);
    const outputPass = labState.agentOutputPasses.find((item) => !completed.has(item.pass_id));
    if (!outputPass) return;
    const button = $("#run-agent-output-pass");
    button.disabled = true;
    button.textContent = "Running one pass…";
    $("#agent-assembly-status").textContent = outputPass.title;
    $("#agent-assembly-status").classList.remove("warning");
    try {
      const result = await agentApi("/api/agents/output-pass", {
        method: "POST",
        body: JSON.stringify({
          blueprint: currentAgentBlueprint(),
          pass_id: outputPass.pass_id,
          scenario: $("#agent-assembly-scenario").value,
          mode: $("#agent-assembly-mode").value,
          current_artifact: labState.outputAssemblyArtifact,
          model: $("#agent-assembly-model").value,
        }),
      });
      labState.outputAssemblyArtifact = result.artifact;
      labState.outputAssemblyCompleted.push(outputPass.pass_id);
      labState.outputAssemblyReviewPending = result.human_review_required ? outputPass.pass_id : null;
      const tokens = Number(result.receipt.input_tokens || 0) + Number(result.receipt.output_tokens || 0);
      labState.outputAssemblyLog.push({
        title: result.pass_title,
        summary: `${result.pass_summary} ${result.updated_fields.length} fields updated.${result.quality_notes.length ? ` Quality: ${result.quality_notes.join(" ")}` : ""}`,
        receipt: `${result.receipt.provider} · ${tokens} tokens · ${result.receipt.elapsed_ms} ms · stored=false`,
      });
      renderAssemblyRuntime();
    } catch (error) {
      $("#agent-assembly-status").textContent = "Pass failed";
      $("#agent-assembly-status").classList.add("warning");
      labState.outputAssemblyLog.push({
        title: `${outputPass.title} failed`,
        summary: error.message,
        receipt: "Artifact was not changed",
      });
      renderAssemblyRuntime();
    } finally {
      button.disabled = false;
      renderAssemblyRuntime();
    }
  }

  function setAdvisorOpen(open) {
    $("#agent-advisor").classList.toggle("collapsed", !open);
    $("#toggle-agent-advisor").textContent = open ? "Close design advisor" : "Open design advisor";
    $("#toggle-agent-advisor").setAttribute("aria-expanded", String(open));
    $("#collapse-agent-advisor").textContent = open ? "−" : "+";
    $("#collapse-agent-advisor").setAttribute("aria-label", open ? "Collapse design advisor" : "Open design advisor");
  }

  function renderAdvisorMessages() {
    const welcome = `<div class="advisor-message assistant"><strong>Design Advisor</strong><p>I can review the current blueprint, explain weaknesses, suggest agent techniques, and prepare a complete proposal. Nothing is applied until you approve it.</p></div>`;
    $("#agent-advisor-messages").innerHTML = welcome + labState.advisorMessages.map((message) => `
      <div class="advisor-message ${escapeHtml(message.role)}"><strong>${message.role === "user" ? "You" : "Design Advisor"}</strong><p>${escapeHtml(message.content)}</p></div>`).join("");
    $("#agent-advisor-messages").scrollTop = $("#agent-advisor-messages").scrollHeight;
  }

  function renderAdvisorProposal(advice, receipt) {
    labState.advisorProposal = advice.improved_design_brief;
    $("#agent-advisor-proposal").classList.remove("hidden");
    $("#agent-advisor-proposal").innerHTML = `
      <div class="advisor-score"><b>${advice.overall_score}</b><span><strong>Blueprint score</strong><small>${escapeHtml(receipt.model)} · ${receipt.input_tokens + receipt.output_tokens} tokens · ${receipt.elapsed_ms} ms</small></span></div>
      <div class="advisor-recommendations">${advice.recommendations.slice(0, 5).map((item) => `
        <div><strong>${escapeHtml(item.priority)} · ${escapeHtml(item.section)} · ${escapeHtml(item.title)}</strong><small>${escapeHtml(item.proposed_change)}</small></div>`).join("")}</div>
      <button class="button primary" id="apply-agent-advisor-proposal" type="button">Use improved design brief</button>`;
  }

  async function sendAdvisorMessage() {
    const input = $("#agent-advisor-input");
    const message = input.value.trim();
    if (message.length < 3) return;
    const blueprint = currentAgentBlueprint();
    labState.advisorMessages.push({ role: "user", content: message });
    renderAdvisorMessages();
    input.value = "";
    $("#send-agent-advisor").disabled = true;
    $("#send-agent-advisor").textContent = "Reviewing…";
    try {
      const result = await agentApi("/api/agents/advisor", {
        method: "POST",
        body: JSON.stringify({
          blueprint,
          message,
          history: labState.advisorMessages.slice(0, -1).slice(-8),
          focus: $("#agent-advisor-focus").value,
          model: $("#agent-advisor-model").value,
        }),
      });
      labState.advisorMessages.push({ role: "assistant", content: result.advice.response });
      renderAdvisorMessages();
      renderAdvisorProposal(result.advice, result.receipt);
    } catch (error) {
      labState.advisorMessages.push({ role: "assistant", content: `I could not complete this review: ${error.message}` });
      renderAdvisorMessages();
    } finally {
      $("#send-agent-advisor").disabled = false;
      $("#send-agent-advisor").textContent = "Review blueprint";
    }
  }

  function saveAgent() {
    const agent = currentAgentDefinition();
    if (!agent.capabilities.length) {
      $("#agent-builder-status").textContent = "Select a capability";
      $("#agent-builder-status").classList.add("warning");
      return;
    }
    agent.savedAt = new Date().toISOString();
    labState.savedAgents = [agent, ...labState.savedAgents.filter((item) => item.name !== agent.name)].slice(0, 16);
    const persisted = storage.set("portfolio-replay-lab.agents", labState.savedAgents);
    $("#agent-builder-status").textContent = persisted ? "Saved locally" : "Saved for this session";
    $("#agent-builder-status").classList.remove("warning");
    renderSavedAgents();
    refreshGraphAgents();
  }

  function createRiskAgentTemplate(spec) {
    const blueprint = structuredClone(currentAgentBlueprint());
    const humanReview = spec.strategy === "human_review";
    const capabilityIds = [...new Set([...spec.capabilities, "evidence_critic"])];
    blueprint.name = spec.name;
    blueprint.purpose = spec.purpose;
    blueprint.model = spec.model || "gpt-5.6-terra";
    blueprint.input_contract = spec.input;
    blueprint.output_contract = spec.output;
    blueprint.instructions.objective = spec.objective;
    blueprint.instructions.narrative_style = spec.style;
    blueprint.prompt_messages = [
      { role: "system", name: "Specialist risk role", content: spec.system, enabled: true },
      { role: "developer", name: "Point-in-time evidence boundary", content: "Use only supplied canonical context and latched capability results. Separate observation, interpretation, uncertainty and unavailable evidence.", enabled: true },
      { role: "user", name: "Workflow request", content: spec.request, enabled: true },
    ];
    blueprint.prompt_template = {
      template: `Workflow date: {as_of_date}\nPortfolio: {portfolio_name}\nMandate status: {mandate_status}\nEvidence state: {evidence_state}\n\nSpecialist task: ${spec.task}`,
      variables: ["as_of_date", "portfolio_name", "mandate_status", "evidence_state"],
      missing_variable_policy: "fail",
      output_format_instruction: "Return the declared strict Structured Output with evidence-grounded findings, an executive assessment and bounded review guidance.",
    };
    blueprint.routing = {
      ...blueprint.routing,
      description: spec.routing,
      strategy: spec.strategy,
      missing_evidence_route: humanReview ? "human_review" : spec.strategy === "direct" ? "abstain" : "revise",
      max_iterations: spec.strategy === "direct" ? 1 : 2,
    };
    blueprint.governance = {
      ...blueprint.governance,
      description: `Require point-in-time evidence for ${spec.category.toLowerCase()} findings, prohibit portfolio effects and apply the configured review boundary.`,
      human_approval: humanReview,
      evidence_required: true,
      effects_allowed: false,
    };
    blueprint.capability_latches = capabilityIds.map((capabilityId) => {
      const capability = capabilities.find((item) => item.id === capabilityId);
      const required = spec.required.includes(capabilityId) || capabilityId === "evidence_critic";
      return {
        capability_id: capabilityId,
        purpose: capability?.purpose || "Provide governed evidence for the specialist risk assessment.",
        invocation_condition: capabilityId === "evidence_critic" ? "After drafting and before completion." : "When the validated context contains the required identifiers and this evidence is relevant to the specialist task.",
        output_binding: capabilityId === "evidence_critic" ? "critique" : `${capabilityId}_result`,
        required,
        failure_policy: required ? (humanReview ? "human_review" : "abstain") : "continue_with_warning",
      };
    });
    blueprint.structured_output.name = `${spec.slug.replaceAll("-", "_")}_artifact`;
    blueprint.structured_output.description = spec.outputDescription;
    blueprint.structured_output.rendering_target = spec.renderingTarget;
    blueprint.structured_output.presentation.composition = spec.composition;
    blueprint.structured_output.presentation.description = `Create a compact ${spec.category.toLowerCase()} report with the conclusion first, restrained evidence displays and an explicit review boundary.`;
    blueprint.structured_output.fields = [
      {
        name: "risk_findings", title: "Risk findings", value_type: "array", semantic_role: "evidence",
        description: "Material specialist findings with evidence references, mandate relevance and uncertainty.", nullable: false, format: "json", enum_values: [], nested_schema_json: "", merge_strategy: "replace", citation_required: true,
        validation_rule: "Every finding identifies supplied evidence or explicitly records unavailable evidence.", produced_in_passes: ["analyze_risk"],
      },
      {
        name: "executive_assessment", title: "Executive assessment", value_type: "string", semantic_role: "narrative",
        description: "Concise evidence-grounded conclusion explaining the current specialist risk state.", nullable: false, format: "markdown", enum_values: [], nested_schema_json: "", merge_strategy: "replace", citation_required: true,
        validation_rule: "The conclusion is consistent with findings and separates observation from interpretation.", produced_in_passes: ["write_review"],
      },
      {
        name: "review_recommendation", title: "Review recommendation", value_type: "string", semantic_role: "recommendations",
        description: "Effect-free guidance describing what a human reviewer or downstream workflow should examine next.", nullable: false, format: "markdown", enum_values: [], nested_schema_json: "", merge_strategy: "replace", citation_required: true,
        validation_rule: "The recommendation never claims that a portfolio action has been executed.", produced_in_passes: ["write_review"],
      },
    ];
    blueprint.structured_output.completion_rule = "All three fields pass their producing pass and the final evidence consistency check.";
    blueprint.structured_output.quality_gate = "All material claims are point-in-time, evidence-grounded, internally consistent and effect-free.";
    blueprint.output_assembly = {
      ...blueprint.output_assembly,
      description: "Build the specialist artifact in one evidence-analysis pass followed by one bounded synthesis pass.",
      strategy: spec.assembly,
      passes: [
        {
          pass_id: "analyze_risk", title: "Analyse specialist risk", objective: "Evaluate supplied context and capability evidence to produce the material specialist findings.",
          target_fields: ["risk_findings"], operation: "replace", context_policy: "full_context", depends_on: [], max_output_tokens: 2200,
          quality_gate: "Every finding is material, point-in-time and linked to supplied evidence.", human_review_after: false,
        },
        {
          pass_id: "write_review", title: "Write specialist review", objective: "Synthesize accepted findings into an executive assessment and effect-free review guidance.",
          target_fields: ["executive_assessment", "review_recommendation"], operation: "replace", context_policy: "selected_prior_fields", depends_on: ["analyze_risk"], max_output_tokens: 2200,
          quality_gate: "The narrative and recommendation agree with accepted findings and disclose uncertainty.", human_review_after: humanReview,
        },
      ],
      max_total_output_tokens: 4800,
      human_review_between_passes: false,
      stop_on_failure: true,
    };
    return {
      id: `risk-template-${spec.slug}`,
      name: spec.name,
      framework: "langgraph",
      engine: "langgraph",
      role: spec.role,
      input: spec.input,
      output: spec.output,
      instructions: spec.objective,
      capabilities: capabilityIds,
      blueprint,
      built_in: true,
      category: spec.category,
    };
  }

  function builtInRiskAgents() {
    if (labState.riskAgentTemplates) return labState.riskAgentTemplates;
    labState.riskAgentTemplates = [
      {
        slug: "daily-portfolio-risk-reviewer", name: "Daily Portfolio Risk Reviewer", category: "Holistic review", role: "reviewer", input: "OverallDefaultContext", output: "RiskReviewDraft", strategy: "human_review", assembly: "sequential_section_build", renderingTarget: "mixed_artifact", composition: "report_and_dashboard",
        purpose: "Interpret the complete deterministic portfolio context and prepare the daily evidence-grounded risk review for human approval.", objective: "Produce a holistic daily review of market, exposure, scenario, event and mandate-relevant portfolio risk.", style: "Lead with the portfolio risk conclusion, explain material changes and evidence, disclose uncertainty and end at a human decision boundary.", system: "You are the senior daily portfolio risk reviewer in a historical point-in-time workflow.", request: "Prepare the complete daily portfolio risk review for the current workflow date.", task: "Synthesize the full deterministic context into the daily risk review.", routing: "Gather required evidence, draft the review, critique material claims, revise once and interrupt for human approval.", capabilities: ["market_data", "risk_metrics", "portfolio_exposure", "scenario_stress", "event_retrieval"], required: ["risk_metrics", "portfolio_exposure"], outputDescription: "A complete daily portfolio risk review combining material findings, narrative interpretation and an explicit human-review recommendation.",
      },
      {
        slug: "market-liquidity-risk-analyst", name: "Market and Liquidity Risk Analyst", category: "Market risk", role: "interpreter", input: "OverallDefaultContext", output: "SpecialistInterpretation", strategy: "reflection", assembly: "iterative_refinement", renderingTarget: "mixed_artifact", composition: "dashboard",
        purpose: "Interpret market moves, volatility, drawdown, liquidity proxies and exposure interactions using point-in-time evidence.", objective: "Explain the portfolio's material market and liquidity risk state without recalculating unprovided metrics.", style: "Separate price observations, metric changes, exposure implications and uncertainty in a compact market-risk note.", system: "You are a market and liquidity risk specialist operating inside a historical portfolio replay.", request: "Assess market and liquidity risk for the current portfolio workflow date.", task: "Interpret market observations, risk metrics and exposure interactions.", routing: "Gather market and metric evidence, draft the specialist interpretation, critique its claims and revise when required.", capabilities: ["market_data", "risk_metrics", "portfolio_exposure"], required: ["market_data", "risk_metrics"], outputDescription: "A specialist market and liquidity interpretation with supported findings, a concise assessment and bounded review guidance.",
      },
      {
        slug: "concentration-mandate-monitor", name: "Concentration and Mandate Monitor", category: "Mandate risk", role: "reviewer", input: "PortfolioContext", output: "RiskReviewDraft", strategy: "human_review", assembly: "sequential_section_build", renderingTarget: "markdown_document", composition: "sectioned_report",
        purpose: "Evaluate portfolio concentration, cash and mandate-relevant exposure conditions and stop at a human review boundary for breaches.", objective: "Identify material concentration and mandate exceptions from deterministic holdings and MetricPack evidence.", style: "State the exception first, quantify the exposure, cite the mandate context and avoid proposing an executed trade.", system: "You are a concentration and mandate-control reviewer with no authority to change the portfolio.", request: "Review concentration and mandate conditions for the current portfolio context.", task: "Evaluate concentration, cash and mandate-relevant exposure conditions.", routing: "Calculate exposure evidence, interpret threshold relevance, critique the finding and interrupt for material exceptions.", capabilities: ["portfolio_exposure", "risk_metrics"], required: ["portfolio_exposure"], outputDescription: "A mandate-focused exception review with exposure findings, evidence-grounded interpretation and a human-review recommendation.",
      },
      {
        slug: "scenario-stress-analyst", name: "Scenario Stress Analyst", category: "Scenario risk", role: "interpreter", input: "OverallDefaultContext", output: "SpecialistInterpretation", strategy: "reflection", assembly: "map_reduce_sections", renderingTarget: "mixed_artifact", composition: "report_and_dashboard",
        purpose: "Interpret bounded deterministic stress results and explain exposures, assumptions and uncertainties driving scenario sensitivity.", objective: "Produce an evidence-grounded specialist interpretation of deterministic portfolio stress scenarios.", style: "Explain the scenario, dominant exposures, concentrated sensitivities and limitations in compact analytical prose.", system: "You are a deterministic scenario-stress specialist and may not create unapproved shocks or mutate holdings.", request: "Interpret the configured stress scenario for the current workflow date.", task: "Explain deterministic scenario results and their exposure drivers.", routing: "Run the approved stress capability, collect exposure evidence, draft the interpretation and revise unsupported claims.", capabilities: ["scenario_stress", "portfolio_exposure", "risk_metrics"], required: ["scenario_stress", "portfolio_exposure"], outputDescription: "A deterministic scenario-risk interpretation containing material sensitivities, assumptions, evidence and effect-free review guidance.",
      },
      {
        slug: "fundamental-event-deterioration-watcher", name: "Fundamental and Event Deterioration Watcher", category: "Fundamental risk", role: "interpreter", input: "OverallDefaultContext", output: "SpecialistInterpretation", strategy: "reflection", assembly: "sequential_section_build", renderingTarget: "markdown_document", composition: "sectioned_report",
        purpose: "Detect mandate-relevant fundamental deterioration and governed events without using information unavailable at the workflow date.", objective: "Explain material point-in-time fundamental changes and events that may alter the portfolio risk interpretation.", style: "Use a chronological evidence-led narrative that distinguishes reported fundamentals, governed events and interpretation.", system: "You are a point-in-time fundamental and event-risk specialist using Compustat and governed event evidence.", request: "Assess fundamental and event deterioration for current holdings and the workflow date.", task: "Interpret eligible fundamental changes and governed events for current holdings.", routing: "Retrieve eligible fundamentals and events, draft the interpretation, critique point-in-time eligibility and revise once.", capabilities: ["fundamental_change", "event_retrieval", "market_data"], required: ["fundamental_change", "event_retrieval"], outputDescription: "A point-in-time fundamental and event-risk interpretation with eligible findings, uncertainties and bounded follow-up guidance.",
      },
      {
        slug: "evidence-point-in-time-critic", name: "Evidence and Point-in-Time Critic", category: "Governance", role: "critic", input: "SpecialistOutputBundle", output: "EvidenceCritique", strategy: "direct", assembly: "iterative_refinement", renderingTarget: "json", composition: "data_product", model: "gpt-5.6-sol",
        purpose: "Audit specialist outputs for unsupported claims, invalid references, look-ahead leakage and missing uncertainty disclosures.", objective: "Produce a strict evidence and point-in-time critique of the supplied specialist output bundle.", style: "Identify each claim, evidence defect, consequence and required correction in concise audit language.", system: "You are the independent evidence and point-in-time critic for portfolio risk agent outputs.", request: "Audit the supplied specialist outputs before synthesis or human review.", task: "Test every material specialist claim for evidence support and point-in-time eligibility.", routing: "Inspect the bundle, retrieve governed event eligibility when needed, issue the critique and abstain when audit context is incomplete.", capabilities: ["event_retrieval"], required: ["evidence_critic"], outputDescription: "A strict evidence critique listing unsupported claims, point-in-time defects, uncertainty omissions and required corrections.",
      },
    ].map(createRiskAgentTemplate);
    return labState.riskAgentTemplates;
  }

  function seedAgents() {
    const templates = builtInRiskAgents();
    const templateIds = new Set(templates.map((agent) => agent.id));
    const legacyIds = new Set(["agent-market-interpreter", "agent-evidence-critic", "agent-review-synthesizer"]);
    const userAgents = labState.savedAgents.filter((agent) => !agent.built_in && !templateIds.has(agent.id) && !legacyIds.has(agent.id));
    labState.savedAgents = [...templates, ...userAgents];
  }

  function renderSavedAgents() {
    const templates = labState.savedAgents.filter((agent) => agent.built_in);
    const userAgents = labState.savedAgents.filter((agent) => !agent.built_in);
    const cards = (agents, action) => agents.map((agent) => `
      <div class="saved-item agent-library-item"><strong>${escapeHtml(agent.name)}</strong><small>${escapeHtml(agent.category || frameworkLabel(agent.framework))} · ${escapeHtml(agent.blueprint?.routing?.strategy?.replaceAll("_", " ") || agent.role)} · ${agent.capabilities.length} capabilities</small><button type="button" data-load-agent="${escapeHtml(agent.id)}">${action}</button></div>`).join("");
    $("#saved-agents").innerHTML = `
      <div class="agent-library-group"><span>Risk templates</span>${cards(templates, "Load template")}</div>
      ${userAgents.length ? `<div class="agent-library-group"><span>My saved agents</span>${cards(userAgents, "Load")}</div>` : ""}`;
  }

  function loadAgent(id) {
    const agent = labState.savedAgents.find((item) => item.id === id);
    if (!agent) return;
    if (agent.blueprint?.instructions && agent.blueprint?.routing && agent.blueprint?.structured_output?.presentation && agent.blueprint?.output_assembly) {
      applyAgentBlueprint(agent.blueprint);
      labState.agentCompile = null;
      $("#agent-builder-status").textContent = agent.compiledArtifact ? "Loaded compiled definition" : "Loaded draft";
      return;
    }
    $("#agent-name").value = agent.name;
    $("#agent-input").value = agent.input;
    $("#agent-output").value = agent.output;
    $("#agent-objective").value = agent.instructions || $("#agent-objective").value;
    capabilities.forEach((capability) => {
      labState.agentCapabilityLatches[capability.id].enabled = agent.capabilities.includes(capability.id);
    });
    renderCapabilities();
    renderAgentContract();
  }

  function refreshGraphAgents() {
    seedAgents();
    const current = $("#graph-agent-select").value;
    $("#graph-agent-select").innerHTML = labState.savedAgents.map((agent) =>
      `<option value="${escapeHtml(agent.id)}">${escapeHtml(agent.name)} · ${escapeHtml(frameworkLabel(agent.framework))}</option>`).join("");
    if (labState.savedAgents.some((agent) => agent.id === current)) $("#graph-agent-select").value = current;
    if (!labState.graphAgentIds.length) labState.graphAgentIds = labState.savedAgents.slice(0, 2).map((agent) => agent.id);
    renderGraph();
  }

  function graphAgents() {
    return labState.graphAgentIds.map((id) => labState.savedAgents.find((agent) => agent.id === id)).filter(Boolean);
  }

  function renderGraph() {
    const agents = graphAgents();
    const pattern = $("#graph-pattern").value;
    const nodes = [
      `<div class="graph-node context-node"><span>Entry</span><strong>Overall Default Context</strong><small>Frozen portfolio, mandate, metrics and eligible evidence.</small></div>`,
      ...agents.map((agent) => `<div class="graph-node"><span>${escapeHtml(frameworkLabel(agent.framework))}</span><strong>${escapeHtml(agent.name)}</strong><small>${escapeHtml(agent.input)} → ${escapeHtml(agent.output)}<br>${agent.capabilities.length} capability grants</small><button type="button" data-remove-graph-agent="${escapeHtml(agent.id)}">Remove node</button></div>`),
      `<div class="graph-node terminal-node"><span>Human boundary</span><strong>Review decision</strong><small>Accept, reject or request changes. No automatic portfolio effect.</small></div>`,
    ];
    if (pattern === "parallel" && agents.length > 1) {
      $("#agent-graph-canvas").innerHTML = `${nodes[0]}<span class="graph-edge">→</span><div class="graph-parallel">${nodes.slice(1, -1).join("")}</div><span class="graph-edge">→</span>${nodes.at(-1)}`;
    } else {
      $("#agent-graph-canvas").innerHTML = nodes.map((node, index) => `${index ? '<span class="graph-edge">→</span>' : ""}${node}`).join("");
    }
    $("#graph-status").textContent = "Not compiled";
    $("#graph-status").classList.remove("warning");
  }

  function compileGraph() {
    const agents = graphAgents();
    const pattern = $("#graph-pattern").value;
    const checks = [];
    checks.push({ ok: agents.length > 0, name: "Agent nodes", detail: agents.length ? `${agents.length} saved agent definitions included.` : "At least one saved agent is required." });
    checks.push({ ok: agents.every((agent) => agent.capabilities.length > 0), name: "Capability grants", detail: agents.every((agent) => agent.capabilities.length > 0) ? "Every agent has at least one bounded capability." : "An agent has no capability grant." });
    const unavailable = agents.filter((agent) =>
      agent.framework === "agents_sdk"
      || (agent.framework === "langgraph" && !labState.agentRuntime?.langgraph?.available));
    checks.push({ ok: unavailable.length === 0, name: "Runtime availability", detail: unavailable.length ? `${unavailable.map((agent) => agent.name).join(", ")} use framework adapters that are not installed.` : "Every selected LangGraph agent can use the installed local runtime." });
    checks.push({ ok: true, name: "Human interrupt", detail: "The terminal review boundary is present and portfolio effects remain prohibited." });
    const structurallyValid = checks.slice(0, 2).every((check) => check.ok);
    $("#graph-validation").innerHTML = `<div class="compile-checks">${checks.map((check) => `
      <div class="compile-check ${check.ok ? "" : "warning"}"><strong>${check.ok ? "Pass" : "Attention"} · ${escapeHtml(check.name)}</strong><span>${escapeHtml(check.detail)}</span></div>`).join("")}</div>`;
    $("#graph-compile-plan").textContent = JSON.stringify({
      graph_pattern: pattern,
      orchestration_state: "transport only; canonical domain objects remain unchanged",
      entry: "OverallDefaultContext",
      nodes: agents.map((agent, index) => ({
        order: index + 1,
        agent_id: agent.id,
        framework_adapter: agent.framework,
        input_contract: agent.input,
        output_contract: agent.output,
        capabilities: agent.capabilities,
      })),
      terminal: "human_review_interrupt",
      checkpoint_required: true,
      compile_state: structurallyValid ? (unavailable.length ? "contract_valid_runtime_blocked" : "runnable_local") : "invalid",
    }, null, 2);
    $("#graph-status").textContent = structurallyValid ? (unavailable.length ? "Valid · runtime blocked" : "Compiled locally") : "Invalid graph";
    $("#graph-status").classList.toggle("warning", !structurallyValid || unavailable.length > 0);
  }

  function bind() {
    $$(".workspace-tab").forEach((button) => button.addEventListener("click", () => switchWorkspace(button.dataset.workspace)));
    $("#data-query-form").addEventListener("submit", askDatabase);
    $("#data-query-export").addEventListener("click", exportDataQueryCsv);
    $("#run-dataset-query").addEventListener("click", runDatasetQuery);
    $("#dataset-mode").addEventListener("change", () => {
      configureDatasetMode();
      runDatasetQuery();
    });
    ["#builder-asset", "#builder-region", "#builder-sector", "#builder-industry"].forEach((selector, index) =>
      $(selector).addEventListener("change", () => updateInstrumentHierarchy(index + 1)));
    $("#builder-instrument").addEventListener("change", renderInstrumentDetail);
    $("#builder-add-position").addEventListener("click", addBuilderPosition);
    $("#builder-cash").addEventListener("input", renderBuilder);
    $("#builder-max-position").addEventListener("input", renderBuilder);
    $("#builder-min-cash").addEventListener("input", renderBuilder);
    $("#builder-holdings-body").addEventListener("input", (event) => {
      const index = Number(event.target.dataset.builderQuantity);
      if (!Number.isInteger(index)) return;
      labState.builderHoldings[index].quantity = Math.max(1, Number(event.target.value) || 1);
      renderBuilder();
    });
    $("#builder-holdings-body").addEventListener("click", (event) => {
      const button = event.target.closest("[data-builder-remove]");
      if (!button) return;
      labState.builderHoldings.splice(Number(button.dataset.builderRemove), 1);
      renderBuilder();
    });
    $("#save-portfolio").addEventListener("click", savePortfolio);
    $("#use-portfolio-experiment").addEventListener("click", () => {
      const candidate = builderCandidate();
      if (!candidate.holdings.length) return;
      window.PortfolioReplayLab?.loadPortfolioCandidate?.(candidate);
      switchWorkspace("full");
    });
    $("#saved-portfolios").addEventListener("click", (event) => {
      const button = event.target.closest("[data-load-portfolio]");
      if (!button) return;
      const portfolio = labState.savedPortfolios.find((item) => item.id === button.dataset.loadPortfolio);
      if (!portfolio) return;
      $("#builder-name").value = portfolio.title;
      $("#builder-cash").value = portfolio.cash;
      $("#builder-max-position").value = portfolio.maxPosition * 100;
      $("#builder-min-cash").value = portfolio.minimumCash * 100;
      labState.builderHoldings = portfolio.holdings.map((holding) => ({ ...holding }));
      renderBuilder();
    });
    $$("[data-agent-output-tab]").forEach((button) => button.addEventListener("click", () => switchAgentOutputTab(button.dataset.agentOutputTab)));
    $("#lab-agent").addEventListener("click", (event) => {
      const helpButton = event.target.closest("[data-agent-help]");
      if (!helpButton) {
        if (!event.target.closest("[data-agent-help-panel]")) closeAgentHelp();
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      toggleAgentHelp(helpButton);
    });
    $("#lab-agent").addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeAgentHelp();
    });
    $(".agent-recursive-form").addEventListener("click", (event) => {
      const button = event.target.closest("[data-generate-agent-section]");
      if (button) generateAgentSection(button.dataset.generateAgentSection, button);
    });
    [
      "#agent-name", "#agent-purpose", "#agent-config-model", "#agent-input", "#agent-output",
      "#agent-objective", "#agent-success-criteria", "#agent-constraints",
      "#agent-stopping-conditions", "#agent-narrative-style", "#agent-prompt-template",
      "#agent-prompt-missing-policy", "#agent-output-format-instruction",
      "#agent-state-description", "#agent-routing-description", "#agent-entry-condition",
      "#agent-revision-condition", "#agent-escalation-condition", "#agent-stop-condition",
      "#agent-missing-evidence-route", "#agent-memory-description", "#agent-memory-scope",
      "#agent-memory", "#agent-remember-fields", "#agent-retention-rule",
      "#agent-compaction-rule", "#agent-max-iterations", "#agent-retries", "#agent-timeout",
      "#agent-governance-description", "#agent-evidence-required", "#agent-human-review",
      "#agent-abstention-rule", "#agent-prohibited-actions",
      "#agent-structured-output-name", "#agent-structured-output-description",
      "#agent-output-rendering-target", "#agent-output-versioning",
      "#agent-output-completion-rule", "#agent-output-quality-gate",
      "#agent-presentation-description", "#agent-output-composition",
      "#agent-output-visual-hierarchy", "#agent-output-tone", "#agent-output-density",
      "#agent-output-typography", "#agent-output-color", "#agent-output-chart-policy",
      "#agent-output-table-policy", "#agent-output-html-policy", "#agent-output-responsive",
      "#agent-output-accessibility", "#agent-output-rendering-instructions",
      "#agent-assembly-description", "#agent-assembly-strategy",
      "#agent-assembly-token-budget", "#agent-assembly-stop-failure",
      "#agent-assembly-human-between", "#agent-assembly-carry-rule",
      "#agent-assembly-final-rule",
    ].forEach((selector) => {
      $(selector).addEventListener("input", () => {
        labState.agentBlueprint = null;
        renderAgentContract();
      });
    });
    $("#agent-pattern").addEventListener("change", () => {
      $("#agent-human-review").checked = $("#agent-pattern").value === "human_review";
      labState.agentBlueprint = null;
      renderAgentContract();
    });
    $("#agent-human-review").addEventListener("change", () => {
      if ($("#agent-human-review").checked) $("#agent-pattern").value = "human_review";
      if (!$("#agent-human-review").checked && $("#agent-pattern").value === "human_review") $("#agent-pattern").value = "reflection";
      renderAgentContract();
    });
    $("#add-agent-prompt-message").addEventListener("click", () => {
      labState.agentPromptMessages.push({ role: "developer", name: "New message", content: "Describe the instruction supplied by this message.", enabled: true });
      renderPromptMessages();
      renderAgentContract();
    });
    $("#agent-prompt-variable-picker").addEventListener("change", (event) => {
      const variable = event.target.dataset.promptVariable;
      if (!variable) return;
      const selected = new Set(labState.agentPromptVariables);
      if (event.target.checked) selected.add(variable);
      else selected.delete(variable);
      labState.agentPromptVariables = [...selected];
      renderPromptVariables();
      renderAgentContract();
    });
    $("#agent-prompt-messages").addEventListener("input", (event) => {
      const mappings = [
        ["promptRole", "role"], ["promptName", "name"], ["promptContent", "content"], ["promptEnabled", "enabled"],
      ];
      mappings.forEach(([datasetKey, field]) => {
        if (event.target.dataset[datasetKey] === undefined) return;
        const index = Number(event.target.dataset[datasetKey]);
        labState.agentPromptMessages[index][field] = event.target.type === "checkbox" ? event.target.checked : event.target.value;
      });
      renderAgentContract();
    });
    $("#agent-prompt-messages").addEventListener("click", (event) => {
      const button = event.target.closest("[data-remove-prompt-message]");
      if (!button || labState.agentPromptMessages.length === 1) return;
      labState.agentPromptMessages.splice(Number(button.dataset.removePromptMessage), 1);
      renderPromptMessages();
      renderAgentContract();
    });
    $("#add-agent-state-field").addEventListener("click", () => {
      labState.agentStateFields.push({ name: `state_field_${labState.agentStateFields.length + 1}`, value_type: "string", description: "Describe the information stored in this state field.", source: "agent", required: false, reducer: "replace" });
      renderStateFields();
      renderAgentContract();
    });
    $("#agent-state-fields").addEventListener("input", (event) => {
      const mappings = [
        ["stateName", "name"], ["stateType", "value_type"], ["stateSource", "source"],
        ["stateReducer", "reducer"], ["stateRequired", "required"], ["stateDescription", "description"],
      ];
      mappings.forEach(([datasetKey, field]) => {
        if (event.target.dataset[datasetKey] === undefined) return;
        const index = Number(event.target.dataset[datasetKey]);
        labState.agentStateFields[index][field] = event.target.type === "checkbox" ? event.target.checked : event.target.value;
      });
      renderPromptVariables();
      renderAgentContract();
    });
    $("#agent-state-fields").addEventListener("click", (event) => {
      const button = event.target.closest("[data-remove-state-field]");
      if (!button || labState.agentStateFields.length === 1) return;
      labState.agentStateFields.splice(Number(button.dataset.removeStateField), 1);
      renderStateFields();
      renderAgentContract();
    });
    $("#add-agent-output-field").addEventListener("click", () => {
      const fallbackPass = labState.agentOutputPasses[0]?.pass_id || "draft_output";
      labState.agentOutputFields.push({
        name: `output_field_${labState.agentOutputFields.length + 1}`,
        title: "New output field",
        value_type: "string",
        semantic_role: "other",
        description: "Describe the information this structured output field must contain.",
        nullable: false,
        format: "none",
        enum_values: [],
        nested_schema_json: "",
        merge_strategy: "replace",
        citation_required: false,
        validation_rule: "The field is complete, internally consistent and supported by supplied context.",
        produced_in_passes: [fallbackPass],
      });
      if (labState.agentOutputPasses[0]) labState.agentOutputPasses[0].target_fields.push(labState.agentOutputFields.at(-1).name);
      renderOutputFields();
      renderOutputPasses();
      renderAgentContract();
    });
    $("#agent-output-fields").addEventListener("input", (event) => {
      const mappings = [
        ["outputFieldName", "name"], ["outputFieldTitle", "title"], ["outputFieldType", "value_type"],
        ["outputFieldRole", "semantic_role"], ["outputFieldFormat", "format"], ["outputFieldMerge", "merge_strategy"],
        ["outputFieldNullable", "nullable"], ["outputFieldCitations", "citation_required"],
        ["outputFieldDescription", "description"], ["outputFieldSchema", "nested_schema_json"],
        ["outputFieldValidation", "validation_rule"],
      ];
      for (const [datasetKey, fieldName] of mappings) {
        if (event.target.dataset[datasetKey] === undefined) continue;
        const index = Number(event.target.dataset[datasetKey]);
        const field = labState.agentOutputFields[index];
        const oldName = field.name;
        field[fieldName] = event.target.type === "checkbox" ? event.target.checked : event.target.value;
        if (fieldName === "name" && oldName !== field.name) {
          labState.agentOutputPasses.forEach((outputPass) => {
            outputPass.target_fields = outputPass.target_fields.map((value) => value === oldName ? field.name : value);
          });
        }
      }
      if (event.target.dataset.outputFieldEnum !== undefined) {
        labState.agentOutputFields[Number(event.target.dataset.outputFieldEnum)].enum_values = event.target.value.split(",").map((value) => value.trim()).filter(Boolean);
      }
      if (event.target.dataset.outputFieldPasses !== undefined) {
        labState.agentOutputFields[Number(event.target.dataset.outputFieldPasses)].produced_in_passes = event.target.value.split(",").map((value) => value.trim()).filter(Boolean);
      }
      renderAgentContract();
    });
    $("#agent-output-fields").addEventListener("click", (event) => {
      const button = event.target.closest("[data-remove-output-field]");
      if (!button || labState.agentOutputFields.length === 1) return;
      const [removed] = labState.agentOutputFields.splice(Number(button.dataset.removeOutputField), 1);
      labState.agentOutputPasses.forEach((outputPass) => {
        outputPass.target_fields = outputPass.target_fields.filter((value) => value !== removed.name);
      });
      renderOutputFields();
      renderOutputPasses();
      renderAgentContract();
    });
    $("#add-agent-output-pass").addEventListener("click", () => {
      const target = labState.agentOutputFields[0]?.name || "output";
      labState.agentOutputPasses.push({
        pass_id: `output_pass_${labState.agentOutputPasses.length + 1}`,
        title: "New output pass",
        objective: "Populate the selected structured output fields using the supplied context and accepted prior artifact.",
        target_fields: [target],
        operation: "replace",
        context_policy: "selected_prior_fields",
        depends_on: labState.agentOutputPasses.length ? [labState.agentOutputPasses.at(-1).pass_id] : [],
        max_output_tokens: 2400,
        quality_gate: "Target fields are complete, schema-valid and consistent with accepted prior sections.",
        human_review_after: false,
      });
      const targetField = labState.agentOutputFields.find((field) => field.name === target);
      if (targetField && !targetField.produced_in_passes.includes(labState.agentOutputPasses.at(-1).pass_id)) targetField.produced_in_passes.push(labState.agentOutputPasses.at(-1).pass_id);
      renderOutputPasses();
      renderOutputFields();
      renderAgentContract();
    });
    $("#agent-output-passes").addEventListener("input", (event) => {
      const mappings = [
        ["outputPassId", "pass_id"], ["outputPassTitle", "title"], ["outputPassObjective", "objective"],
        ["outputPassOperation", "operation"], ["outputPassContext", "context_policy"],
        ["outputPassQuality", "quality_gate"], ["outputPassReview", "human_review_after"],
      ];
      for (const [datasetKey, fieldName] of mappings) {
        if (event.target.dataset[datasetKey] === undefined) continue;
        const index = Number(event.target.dataset[datasetKey]);
        const outputPass = labState.agentOutputPasses[index];
        const oldId = outputPass.pass_id;
        outputPass[fieldName] = event.target.type === "checkbox" ? event.target.checked : event.target.value;
        if (fieldName === "pass_id" && oldId !== outputPass.pass_id) {
          labState.agentOutputPasses.forEach((item) => {
            item.depends_on = item.depends_on.map((value) => value === oldId ? outputPass.pass_id : value);
          });
          labState.agentOutputFields.forEach((field) => {
            field.produced_in_passes = field.produced_in_passes.map((value) => value === oldId ? outputPass.pass_id : value);
          });
        }
      }
      if (event.target.dataset.outputPassTargets !== undefined) {
        labState.agentOutputPasses[Number(event.target.dataset.outputPassTargets)].target_fields = event.target.value.split(",").map((value) => value.trim()).filter(Boolean);
      }
      if (event.target.dataset.outputPassDependencies !== undefined) {
        labState.agentOutputPasses[Number(event.target.dataset.outputPassDependencies)].depends_on = event.target.value.split(",").map((value) => value.trim()).filter(Boolean);
      }
      if (event.target.dataset.outputPassTokens !== undefined) {
        labState.agentOutputPasses[Number(event.target.dataset.outputPassTokens)].max_output_tokens = Number(event.target.value);
      }
      renderAgentContract();
      renderAssemblyRuntime();
    });
    $("#agent-output-passes").addEventListener("click", (event) => {
      const button = event.target.closest("[data-remove-output-pass]");
      if (!button || labState.agentOutputPasses.length === 1) return;
      const [removed] = labState.agentOutputPasses.splice(Number(button.dataset.removeOutputPass), 1);
      labState.agentOutputPasses.forEach((item) => {
        item.depends_on = item.depends_on.filter((value) => value !== removed.pass_id);
      });
      labState.agentOutputFields.forEach((field) => {
        field.produced_in_passes = field.produced_in_passes.filter((value) => value !== removed.pass_id);
      });
      renderOutputPasses();
      renderOutputFields();
      renderAgentContract();
    });
    $("#agent-capabilities").addEventListener("input", (event) => {
      const id = event.target.matches("[data-agent-capability]")
        ? event.target.value
        : event.target.dataset.capabilityPurpose
          || event.target.dataset.capabilityCondition
          || event.target.dataset.capabilityBinding
          || event.target.dataset.capabilityFailure
          || event.target.dataset.capabilityRequired;
      if (!id || !labState.agentCapabilityLatches[id]) return;
      const latch = labState.agentCapabilityLatches[id];
      if (event.target.matches("[data-agent-capability]")) {
        latch.enabled = event.target.checked;
        renderCapabilities();
      } else if (event.target.dataset.capabilityPurpose) latch.purpose = event.target.value;
      else if (event.target.dataset.capabilityCondition) latch.invocation_condition = event.target.value;
      else if (event.target.dataset.capabilityBinding) latch.output_binding = event.target.value;
      else if (event.target.dataset.capabilityFailure) latch.failure_policy = event.target.value;
      else if (event.target.dataset.capabilityRequired) latch.required = event.target.checked;
      renderAgentContract();
    });
    $("#agent-evidence-required").addEventListener("change", () => {
      if ($("#agent-evidence-required").checked) {
        labState.agentCapabilityLatches.evidence_critic.enabled = true;
        renderCapabilities();
      }
    });
    $("#toggle-agent-advisor").addEventListener("click", () => setAdvisorOpen($("#agent-advisor").classList.contains("collapsed")));
    $("#collapse-agent-advisor").addEventListener("click", () => setAdvisorOpen($("#agent-advisor").classList.contains("collapsed")));
    $("#agent-advisor .agent-advisor-header").addEventListener("click", (event) => {
      if (event.target.closest("button") || !$("#agent-advisor").classList.contains("collapsed")) return;
      setAdvisorOpen(true);
    });
    $("#send-agent-advisor").addEventListener("click", sendAdvisorMessage);
    $("#agent-advisor-input").addEventListener("keydown", (event) => {
      if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) sendAdvisorMessage();
    });
    $("#agent-advisor-proposal").addEventListener("click", (event) => {
      if (!event.target.closest("#apply-agent-advisor-proposal") || !labState.advisorProposal) return;
      $("#agent-description").value = labState.advisorProposal;
      $("#agent-builder-status").textContent = "Improved brief ready";
      $("#agent-advisor-proposal").classList.add("hidden");
      labState.advisorMessages.push({ role: "assistant", content: "The improved brief is now in the design field. Review it, then explicitly transform it into a complete blueprint when ready." });
      renderAdvisorMessages();
    });
    $("#generate-agent-blueprint").addEventListener("click", generateAgentBlueprint);
    $("#validate-agent-blueprint").addEventListener("click", () => validateAgentBlueprint().catch(() => {}));
    $("#compile-agent").addEventListener("click", () => compileAgent().catch(() => {}));
    $("#test-agent").addEventListener("click", runAgentTest);
    $("#run-agent-output-pass").addEventListener("click", runNextOutputPass);
    $("#reset-agent-assembly").addEventListener("click", resetOutputAssembly);
    $("#save-agent").addEventListener("click", saveAgent);
    $("#copy-agent-code").addEventListener("click", async () => {
      const source = $("#agent-generated-code").textContent;
      try {
        await navigator.clipboard.writeText(source);
        $("#copy-agent-code").textContent = "Copied";
        setTimeout(() => { $("#copy-agent-code").textContent = "Copy code"; }, 1200);
      } catch {
        $("#copy-agent-code").textContent = "Select and copy";
      }
    });
    $("#saved-agents").addEventListener("click", (event) => {
      const button = event.target.closest("[data-load-agent]");
      if (button) loadAgent(button.dataset.loadAgent);
    });
    $("#graph-pattern").addEventListener("change", renderGraph);
    $("#graph-add-agent").addEventListener("click", () => {
      const id = $("#graph-agent-select").value;
      if (id && !labState.graphAgentIds.includes(id)) labState.graphAgentIds.push(id);
      renderGraph();
    });
    $("#agent-graph-canvas").addEventListener("click", (event) => {
      const button = event.target.closest("[data-remove-graph-agent]");
      if (!button) return;
      labState.graphAgentIds = labState.graphAgentIds.filter((id) => id !== button.dataset.removeGraphAgent);
      renderGraph();
    });
    $("#compile-graph").addEventListener("click", compileGraph);
  }

  function initialize() {
    populateDatasetPortfolios();
    const current = canonicalCurrentPortfolio();
    labState.builderHoldings = current.holdings.slice(0, 5).map((holding) => ({ ...holding }));
    updateInstrumentHierarchy();
    renderBuilder();
    renderSavedPortfolios();
    renderCapabilities();
    renderPromptMessages();
    renderStateFields();
    renderOutputFields();
    renderOutputPasses();
    renderSectionIntentControls();
    renderAgentHelpControls();
    renderAdvisorMessages();
    setAdvisorOpen(false);
    seedAgents();
    renderSavedAgents();
    renderAgentContract();
    refreshGraphAgents();
    bind();
    configureDatasetMode();
    initializeLiveConnection();
    initializeAgentRuntime();
    const requestedWorkspace = new URLSearchParams(window.location.search).get("workspace");
    if (["dataset", "portfolio", "agent", "graph", "full"].includes(requestedWorkspace)) switchWorkspace(requestedWorkspace);
  }

  initialize();
})();
