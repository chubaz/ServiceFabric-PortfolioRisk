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

  const basicContextPacks = {
    morning_risk_context: { label: "Morning risk context", input: "OverallDefaultContext", detail: "Portfolio, mandate, deterministic metrics, eligible events and evidence state." },
    portfolio_event_review: { label: "Portfolio event review", input: "OverallDefaultContext", detail: "Eligible event, point-in-time mappings, portfolio exposure and prior eligible evidence." },
    portfolio_context: { label: "Portfolio context only", input: "PortfolioContext", detail: "Immutable holdings, cash, exposure and mandate state for the workflow date." },
    specialist_output_review: { label: "Specialist output review", input: "SpecialistOutputBundle", detail: "Typed specialist outputs and their evidence references for independent validation." },
  };

  const basicCapabilityPacks = {
    daily_risk_review: { label: "Daily risk review", ids: ["market_data", "risk_metrics", "portfolio_exposure", "scenario_stress", "event_retrieval", "evidence_critic"] },
    portfolio_event_triage: { label: "Portfolio event triage", ids: ["event_retrieval", "portfolio_exposure", "market_data", "evidence_critic"] },
    market_risk_summary: { label: "Market risk summary", ids: ["market_data", "risk_metrics", "portfolio_exposure", "evidence_critic"] },
    concentration_review: { label: "Concentration review", ids: ["portfolio_exposure", "risk_metrics", "evidence_critic"] },
    evidence_validation: { label: "Evidence validation", ids: ["event_retrieval", "evidence_critic"] },
  };

  const basicRecipeDefaults = {
    "risk-template-daily-portfolio-risk-reviewer": ["morning_risk_context", "daily_risk_review"],
    "risk-template-market-liquidity-risk-analyst": ["morning_risk_context", "market_risk_summary"],
    "risk-template-concentration-mandate-monitor": ["portfolio_context", "concentration_review"],
    "risk-template-scenario-stress-analyst": ["morning_risk_context", "daily_risk_review"],
    "risk-template-fundamental-event-deterioration-watcher": ["portfolio_event_review", "portfolio_event_triage"],
    "risk-template-evidence-point-in-time-critic": ["specialist_output_review", "evidence_validation"],
  };

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
    runtimeBoundary: null,
    activeWorkspace: "dataset",
    dataQueryResult: null,
    agentRuntime: null,
    riskAgentTemplates: null,
    agentBlueprint: null,
    agentCompile: null,
    agentRunDataMode: "synthetic_behavior_sample",
    agentRunExecutionMode: "deterministic",
    agentInputPreview: null,
    agentRuns: [],
    selectedAgentRunId: null,
    selectedAgentRunDetail: null,
    agentBuilderMode: "basic",
    agentBuilderStep: "outcome",
    agentBuilderMeta: {
      recipe_id: "risk-template-daily-portfolio-risk-reviewer",
      trigger: "workflow",
      scope: "selected_portfolio",
      as_of: "workflow_date",
      deduplication: "assignment_and_snapshot",
      context_pack: "morning_risk_context",
      capability_pack: "daily_risk_review",
      authority_profile: "A2",
      provenance: "recipe_defaults",
    },
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
    cycleSessionId: null,
    cycleSnapshot: null,
    cyclePollTimer: null,
    cycleDashboardPage: "overview",
    registryRecords: [],
    selectedRegistryReference: null,
    registryLoading: false,
    artifactRecords: [],
    artifactCandidates: [],
    selectedArtifactId: null,
    selectedArtifactDetail: null,
    artifactLoading: false,
    experimentRecords: [],
    experimentQueue: [],
    experimentSets: [],
    experimentOptions: null,
    selectedExperimentId: null,
    experimentLoading: false,
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

  function truthViewKey(name) {
    if (name === "dataset") return `dataset.${$("#dataset-mode")?.value === "synthetic" ? "synthetic" : "live"}`;
    if (name === "agent") return `agent.${labState.agentRunDataMode}`;
    return name;
  }

  function renderRuntimeTruth(name = labState.activeWorkspace) {
    const boundary = labState.runtimeBoundary;
    if (!boundary) {
      $("#truth-profile").textContent = "Local service unavailable";
      $("#truth-data").textContent = "Origin not verified";
      $("#truth-authority").textContent = "External effects prohibited";
      $("#truth-persistence").textContent = "Persistence not established";
      return;
    }
    const view = boundary.views?.[truthViewKey(name)] || {};
    $("#truth-profile").textContent = boundary.profile?.label || "Unknown profile";
    $("#truth-data").textContent = view.data || "Data origin unavailable";
    $("#truth-authority").textContent = view.authority || `External effects ${boundary.external_effects || "unknown"}`;
    $("#truth-persistence").textContent = view.persistence || "Persistence not declared";
  }

  function switchWorkspace(name, updateHistory = true) {
    labState.activeWorkspace = name;
    const full = name === "full";
    $("#lab-workspace").classList.toggle("hidden", full);
    $("#full-experiment-workspace").classList.toggle("hidden", !full);
    $$(".lab-page").forEach((page) => page.classList.toggle("active", page.id === `lab-${name}`));
    $$(".workspace-tab").forEach((button) => {
      const active = button.dataset.workspace === name;
      button.classList.toggle("active", active);
      if (active) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    renderRuntimeTruth(name);
    if (name === "dataset") populateDatasetPortfolios();
    if (name === "graph") refreshGraphAgents();
    if (name === "registry") loadRegistryCatalogue();
    if (name === "artifacts") loadArtifactCatalogue();
    if (name === "experiments") loadExperimentWorkspace();
    if (name === "cycle") populateCyclePortfolios();
    if (updateHistory) {
      const url = new URL(window.location.href);
      if (url.searchParams.get("workspace") !== name) {
        url.searchParams.set("workspace", name);
        window.history.pushState({ workspace: name }, "", url);
      }
    }
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

  function populateAgentRunPortfolios() {
    const select = $("#agent-real-portfolio");
    if (!select) return;
    const current = select.value;
    select.innerHTML = labState.livePortfolios.length
      ? labState.livePortfolios.map((portfolio) => `<option value="${escapeHtml(portfolio.id)}">${escapeHtml(portfolio.title)} · ${portfolio.holdings.length} positions</option>`).join("")
      : '<option value="">Real portfolio service unavailable</option>';
    if (labState.livePortfolios.some((portfolio) => portfolio.id === current)) select.value = current;
    select.disabled = !labState.livePortfolios.length;
  }

  function populateCyclePortfolios() {
    const select = $("#cycle-portfolio");
    if (!select) return;
    const current = select.value;
    select.innerHTML = labState.livePortfolios.length
      ? labState.livePortfolios.map((portfolio) => `<option value="${escapeHtml(portfolio.id)}">${escapeHtml(portfolio.title)} · ${portfolio.holdings.length} positions</option>`).join("")
      : '<option value="">Local portfolio service unavailable</option>';
    if (labState.livePortfolios.some((portfolio) => portfolio.id === current)) select.value = current;
    select.disabled = !labState.livePortfolios.length;
    $("#create-cycle-session").disabled = !labState.livePortfolios.length;
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
    const routedTables = payload.receipt?.catalog_routing?.selected_tables?.length || 0;
    const inputTokens = Number(payload.receipt?.input_tokens || 0);
    const modelNote = inputTokens
      ? ` · ${inputTokens.toLocaleString("en-US")} LLM input tokens · ${routedTables} routed ${routedTables === 1 ? "table" : "tables"}`
      : "";
    $("#data-query-result-meta").textContent = `${payload.row_count.toLocaleString("en-US")} rows · ${payload.column_count} columns · ${payload.elapsed_ms} ms${modelNote}${previewNote}${truncationNote}`;
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
      $("#data-query-agent").textContent = "Luna · low · routed schema";
      renderDataQuery(payload);
    } catch (error) {
      const serviceUnavailable = error instanceof TypeError && /fetch/i.test(error.message || "");
      $("#data-query-message").textContent = serviceUnavailable
        ? "The local data service is offline. Restart the Portfolio Replay Lab service, then run the question again."
        : error.message;
      $("#data-query-message").classList.add("error");
      $("#dataset-query-status").textContent = serviceUnavailable ? "Service offline" : "Query failed";
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
    if (!domains.length) throw new Error("Select at least one licensed dataset.");
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
    if (!response.ok) throw new Error(payload.detail || `Licensed-data query failed with HTTP ${response.status}.`);
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
    $("#dataset-result-title").textContent = `${payload.record_count} licensed historical records for ${portfolio.title}`;
    $("#dataset-result-meta").innerHTML = `<span>${eligible} eligible</span><span>${warnings} availability fallbacks</span><span>${missing} missing</span><span>${payload.elapsed_ms} ms</span>`;
    $("#dataset-query-status").textContent = missing ? "Licensed · gaps found" : warnings ? "Licensed · qualified" : "Licensed · complete";
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
      $("#dataset-results-body").innerHTML = `<tr><td colspan="6"><strong>Licensed-data query unavailable.</strong><br>${escapeHtml(error.message)}</td></tr>`;
      $("#dataset-trace").innerHTML = `<li>${escapeHtml(error.message)}</li><li>No synthetic fallback was used.</li>`;
    } finally {
      button.disabled = false;
      button.textContent = $("#dataset-mode").value === "live" ? "Query licensed Parquet data" : "Run synthetic fixture";
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
      ? (labState.liveConnected ? "Licensed local data · read-only" : "DuckDB service required")
      : "Synthetic behavior fixture";
    $("#run-dataset-query").textContent = live ? "Query licensed Parquet data" : "Run synthetic fixture";
    populateDatasetPortfolios();
    renderRuntimeTruth();
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
      labState.runtimeBoundary = health.runtime_boundary || null;
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
      populateAgentRunPortfolios();
      populateCyclePortfolios();
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
      renderRuntimeTruth();
    } catch (error) {
      labState.liveConnected = false;
      labState.runtimeBoundary = null;
      $("#duckdb-connection-status").textContent = "Not connected";
      $("#duckdb-connection-status").className = "quality-missing";
      $("#duckdb-connection-copy").textContent = "Open this application through the local DuckDB service URL; file:// pages cannot call the API.";
      $("#duckdb-catalog").innerHTML = "";
      $("#data-query-agent").textContent = "Luna unavailable";
      $("#data-query-message").textContent = "Open the live local service to query data.";
      $("#data-query-message").classList.add("error");
      $("#dataset-query-status").textContent = "Offline";
      $("#dataset-query-status").classList.add("warning");
      populateAgentRunPortfolios();
      configureDatasetMode();
      renderRuntimeTruth();
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
      builder_meta: structuredClone(labState.agentBuilderMeta),
      compiledArtifact: labState.agentCompile?.artifact_id || null,
    };
  }

  function agentBuilderLabel(value) {
    return String(value || "").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function setBasicValue(selector, value) {
    const element = $(selector);
    if (element && document.activeElement !== element) element.value = value;
  }

  function renderBasicRecipes() {
    const recipes = builtInRiskAgents();
    $("#basic-agent-recipes").innerHTML = recipes.map((agent) => `
      <button class="basic-recipe-card ${labState.agentBuilderMeta.recipe_id === agent.id ? "active" : ""}" type="button" data-basic-agent-recipe="${escapeHtml(agent.id)}">
        <span>${escapeHtml(agent.category || "Risk agent")}</span>
        <strong>${escapeHtml(agent.name)}</strong>
        <small>${escapeHtml(agent.blueprint?.purpose || agent.instructions)}</small>
      </button>`).join("");
  }

  function basicEffectiveCapabilities() {
    const blueprint = currentAgentBlueprint();
    return blueprint.capability_latches.map((latch) => latch.capability_id);
  }

  function renderBasicBuilder() {
    if (!$("#agent-basic-builder")) return;
    const blueprint = currentAgentBlueprint();
    const meta = labState.agentBuilderMeta;
    const context = basicContextPacks[meta.context_pack] || basicContextPacks.morning_risk_context;
    const capabilityIds = basicEffectiveCapabilities();
    const capabilityNames = capabilityIds.map((id) => capabilities.find((item) => item.id === id)?.name || id);
    const triggerLabels = {
      manual: "Manual run",
      workflow: "Workflow cycle",
      event: "Eligible event",
      scheduled: "Schedule",
    };
    const authorityA1 = meta.authority_profile === "A1";
    const recipe = builtInRiskAgents().find((item) => item.id === meta.recipe_id);
    const expectedIds = authorityA1
      ? ["evidence_critic"]
      : (basicCapabilityPacks[meta.capability_pack]?.ids || []);
    const customized = blueprint.input_contract !== context.input
      || blueprint.output_contract !== $("#basic-agent-output").value
      || capabilityIds.slice().sort().join("|") !== expectedIds.slice().sort().join("|");

    renderBasicRecipes();
    setBasicValue("#basic-agent-name", blueprint.name);
    setBasicValue("#basic-agent-outcome", blueprint.purpose);
    setBasicValue("#basic-agent-trigger", meta.trigger);
    setBasicValue("#basic-agent-scope", meta.scope);
    setBasicValue("#basic-agent-as-of", meta.as_of);
    setBasicValue("#basic-agent-dedup", meta.deduplication);
    setBasicValue("#basic-agent-context-pack", meta.context_pack);
    setBasicValue("#basic-agent-capability-pack", meta.capability_pack);
    setBasicValue("#basic-agent-output", blueprint.output_contract);
    setBasicValue("#basic-agent-authority", meta.authority_profile);

    $$("[data-basic-agent-step]").forEach((button, index) => {
      const active = button.dataset.basicAgentStep === labState.agentBuilderStep;
      button.classList.toggle("active", active);
      button.classList.toggle("complete", index < ["outcome", "scope", "context", "output", "test"].indexOf(labState.agentBuilderStep));
    });
    $$("[data-basic-agent-panel]").forEach((panel) => panel.classList.toggle("active", panel.dataset.basicAgentPanel === labState.agentBuilderStep));

    $("#basic-scope-summary").textContent = `${triggerLabels[meta.trigger]} · ${agentBuilderLabel(meta.scope)} · information eligible at ${agentBuilderLabel(meta.as_of).toLowerCase()} · duplicate key ${agentBuilderLabel(meta.deduplication).toLowerCase()}.`;
    $("#basic-capability-preview").innerHTML = capabilityNames.map((name, index) => `<span class="basic-capability-chip ${index === capabilityNames.length - 1 ? "required" : ""}">${escapeHtml(name)}</span>`).join("");
    $("#basic-authority-level").textContent = meta.authority_profile;
    $("#basic-authority-title").textContent = authorityA1 ? "Context-bound draft" : "Effect-free analysis and draft";
    $("#basic-authority-copy").textContent = authorityA1
      ? "Drafts from the supplied context and invokes only the evidence validator."
      : "May invoke the displayed analytical capabilities and prepare a review artifact.";
    $("#basic-output-preview").innerHTML = `
      <header><strong>${escapeHtml(agentBuilderLabel(blueprint.output_contract))}</strong><span>Human review required</span></header>
      <div><h3>${escapeHtml(blueprint.structured_output.fields[0]?.title || "Evidence-grounded result")}</h3><p>${escapeHtml(blueprint.structured_output.description)} The complete typed schema remains available in Advanced.</p></div>`;

    $("#basic-preview-version").textContent = customized ? "Draft · customized" : `Draft · ${recipe ? "recipe defaults" : "manual"}`;
    $("#basic-preview-name").textContent = blueprint.name;
    $("#basic-preview-outcome").textContent = blueprint.purpose;
    $("#basic-preview-trigger").innerHTML = `${escapeHtml(triggerLabels[meta.trigger])} · ${escapeHtml(agentBuilderLabel(meta.scope))}<span class="field-provenance user">User</span>`;
    $("#basic-preview-context").innerHTML = `${escapeHtml(context.label)} · ${escapeHtml(context.detail)}<span class="field-provenance recipe">Recipe</span>`;
    $("#basic-preview-capabilities").innerHTML = `${capabilityNames.length ? escapeHtml(capabilityNames.join(", ")) : "No analytical capability"}<span class="field-provenance ${customized ? "user" : "recipe"}">${customized ? "Customized" : "Recipe"}</span>`;
    $("#basic-preview-output").innerHTML = `${escapeHtml(agentBuilderLabel(blueprint.output_contract))}<span class="field-provenance derived">Contract</span>`;
    $("#basic-preview-authority").innerHTML = `${escapeHtml(meta.authority_profile)} · ${authorityA1 ? "context-bound draft" : "analytical tools and draft"} · human review<span class="field-provenance policy">Policy</span>`;
  }

  function syncBasicBuilderFromBlueprint() {
    const blueprint = currentAgentBlueprint();
    const matchingContext = Object.entries(basicContextPacks).find(([, pack]) => pack.input === blueprint.input_contract)?.[0];
    if (matchingContext) labState.agentBuilderMeta.context_pack = matchingContext;
    const enabled = blueprint.capability_latches.map((latch) => latch.capability_id).slice().sort().join("|");
    const matchingPack = Object.entries(basicCapabilityPacks).find(([, pack]) => pack.ids.slice().sort().join("|") === enabled)?.[0];
    if (matchingPack) labState.agentBuilderMeta.capability_pack = matchingPack;
    labState.agentBuilderMeta.authority_profile = enabled === "evidence_critic" ? "A1" : "A2";
    renderBasicBuilder();
  }

  function setAgentBuilderMode(mode) {
    labState.agentBuilderMode = mode;
    $("#lab-agent").dataset.builderMode = mode;
    $$("[data-agent-builder-mode]").forEach((button) => button.classList.toggle("active", button.dataset.agentBuilderMode === mode));
    if (mode === "basic") syncBasicBuilderFromBlueprint();
  }

  function setBasicAgentStep(step) {
    labState.agentBuilderStep = step;
    renderBasicBuilder();
  }

  function applyBasicCapabilityAndAuthority() {
    const meta = labState.agentBuilderMeta;
    const selected = new Set(meta.authority_profile === "A1"
      ? ["evidence_critic"]
      : (basicCapabilityPacks[meta.capability_pack]?.ids || ["evidence_critic"]));
    selected.add("evidence_critic");
    capabilities.forEach((capability) => {
      const latch = labState.agentCapabilityLatches[capability.id];
      latch.enabled = selected.has(capability.id);
      latch.required = capability.id === "evidence_critic" || selected.has(capability.id) && capability.id !== "market_data";
      if (latch.required) latch.failure_policy = "human_review";
    });
    $("#agent-evidence-required").checked = true;
    $("#agent-human-review").checked = true;
    $("#agent-pattern").value = "human_review";
    labState.agentBlueprint = null;
    renderCapabilities();
    renderAgentContract();
    renderBasicBuilder();
  }

  function selectBasicRecipe(id) {
    const agent = labState.savedAgents.find((item) => item.id === id && item.built_in);
    if (!agent?.blueprint) return;
    labState.agentBuilderMeta.recipe_id = id;
    labState.agentBuilderMeta.provenance = "recipe_defaults";
    const [contextPack, capabilityPack] = basicRecipeDefaults[id] || ["morning_risk_context", "daily_risk_review"];
    labState.agentBuilderMeta.context_pack = contextPack;
    labState.agentBuilderMeta.capability_pack = capabilityPack;
    labState.agentBuilderMeta.authority_profile = "A2";
    applyAgentBlueprint(structuredClone(agent.blueprint));
    $("#basic-agent-description").value = agent.blueprint.purpose;
    applyBasicCapabilityAndAuthority();
    $("#agent-builder-status").textContent = "Recipe loaded";
  }

  function applyBasicIdentity() {
    $("#agent-name").value = $("#basic-agent-name").value.trim() || "Untitled agent";
    const outcome = $("#basic-agent-outcome").value.trim();
    if (outcome) {
      $("#agent-purpose").value = outcome;
      $("#agent-objective").value = outcome;
    }
    labState.agentBlueprint = null;
    labState.agentBuilderMeta.provenance = "user_customized";
    renderAgentContract();
    renderBasicBuilder();
  }

  function applyBasicContext() {
    const meta = labState.agentBuilderMeta;
    const context = basicContextPacks[meta.context_pack];
    if (context) $("#agent-input").value = context.input;
    labState.agentBlueprint = null;
    renderAgentContract();
    renderBasicBuilder();
  }

  function applyBasicOutputContract() {
    const contract = $("#basic-agent-output").value;
    const presets = {
      RiskReviewDraft: {
        name: "risk_review_draft",
        description: "A review-bound portfolio risk artifact containing supported findings, uncertainty and effect-free next review actions.",
        fields: [
          ["material_findings", "Material findings", "array", "evidence", "Material portfolio-risk findings supported by supplied point-in-time evidence."],
          ["review_narrative", "Review narrative", "string", "narrative", "A concise interpretation that distinguishes observations, implications and uncertainty."],
          ["suggested_review_actions", "Suggested review actions", "array", "recommendations", "Effect-free questions and checks for the human reviewer to consider next."],
        ],
      },
      SpecialistInterpretation: {
        name: "specialist_interpretation",
        description: "A bounded specialist interpretation of supplied deterministic evidence with a clear conclusion and disclosed limitations.",
        fields: [
          ["specialist_findings", "Specialist findings", "array", "evidence", "Domain-specific findings linked to the supplied evidence and point-in-time context."],
          ["interpretation", "Interpretation", "string", "narrative", "The specialist conclusion, its portfolio relevance and material uncertainty."],
          ["limitations", "Limitations", "array", "metadata", "Missing information and methodological limits affecting the interpretation."],
        ],
      },
      EvidenceCritique: {
        name: "evidence_critique",
        description: "An independent evidence audit identifying unsupported claims, temporal defects, conflicts and required corrections.",
        fields: [
          ["evidence_findings", "Evidence findings", "array", "evidence", "Claim-level evidence and point-in-time validation findings."],
          ["audit_conclusion", "Audit conclusion", "string", "narrative", "A concise conclusion describing whether the reviewed output is supportable."],
          ["required_corrections", "Required corrections", "array", "recommendations", "Corrections required before the output can proceed to human review."],
        ],
      },
      CapabilityRequest: {
        name: "capability_request",
        description: "A governed request for unavailable information or analytical capability without invoking an unknown tool or weakening policy.",
        fields: [
          ["request_reason", "Request reason", "string", "narrative", "Why the current assignment cannot be completed with the granted context and capabilities."],
          ["required_capabilities", "Required capabilities", "array", "metadata", "Plain-language operations required to complete the bounded assignment."],
          ["missing_context", "Missing context", "array", "evidence", "Information that must become available before analysis can continue."],
        ],
      },
    };
    const preset = presets[contract];
    if (!preset) return;
    $("#agent-output").value = contract;
    $("#agent-structured-output-name").value = preset.name;
    $("#agent-structured-output-description").value = preset.description;
    labState.agentOutputFields = preset.fields.map(([name, title, valueType, semanticRole, description]) => ({
      name,
      title,
      value_type: valueType,
      semantic_role: semanticRole,
      description,
      nullable: false,
      format: valueType === "string" ? "markdown" : "json",
      enum_values: [],
      nested_schema_json: "",
      merge_strategy: "replace",
      citation_required: semanticRole === "evidence" || semanticRole === "narrative",
      validation_rule: "The field is complete, internally consistent and supported by the supplied eligible context.",
      produced_in_passes: ["produce_output"],
    }));
    labState.agentOutputPasses = [{
      pass_id: "produce_output",
      title: `Produce ${agentBuilderLabel(contract)}`,
      objective: "Populate the complete selected Output Contract from supplied context and accepted capability evidence.",
      target_fields: labState.agentOutputFields.map((field) => field.name),
      operation: "replace",
      context_policy: "full_context",
      depends_on: [],
      max_output_tokens: 3200,
      quality_gate: "Every required field is schema-valid, evidence-grounded, effect-free and ready for human review.",
      human_review_after: true,
    }];
    $("#agent-assembly-description").value = "Produce the selected typed artifact in one bounded pass, validate it and stop at human review.";
    $("#agent-assembly-token-budget").value = "4000";
    labState.agentBlueprint = null;
    labState.agentBuilderMeta.provenance = "user_customized";
    renderOutputFields();
    renderOutputPasses();
    renderAgentContract();
    renderBasicBuilder();
  }

  function openAdvancedAgentSection(sectionKey) {
    setAgentBuilderMode("advanced");
    const section = document.querySelector(`[data-agent-section="${sectionKey}"]`);
    if (!section) return;
    section.open = true;
    section.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function generateBasicAgent() {
    const description = $("#basic-agent-description").value.trim();
    if (description.length < 20) {
      $("#agent-builder-status").textContent = "Description too short";
      return;
    }
    const button = $("#basic-generate-agent");
    button.disabled = true;
    button.textContent = "Drafting…";
    $("#agent-description").value = description;
    const result = await generateAgentBlueprint();
    if (result) {
      labState.agentBuilderMeta.provenance = "ai_suggestion";
      syncBasicBuilderFromBlueprint();
    }
    button.disabled = false;
    button.textContent = "Draft with AI";
  }

  async function generateBasicStep(step, button) {
    const sectionByStep = {
      scope: "routing",
      context: "capabilities",
      output: "structured_output",
      test: "governance",
    };
    const section = sectionByStep[step];
    const input = document.querySelector(`[data-basic-step-intent="${step}"]`);
    const description = input?.value.trim() || "";
    if (!section || description.length < 10) {
      input?.focus();
      $("#agent-builder-status").textContent = "Describe this step first";
      return;
    }
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Preparing…";
    $("#agent-builder-status").textContent = `Preparing ${step}`;
    try {
      const result = await agentApi("/api/agents/blueprint/plan-section", {
        method: "POST",
        body: JSON.stringify({
          section,
          description,
          draft: currentAgentBlueprint(),
          model: $("#agent-model").value,
        }),
      });
      applyGeneratedSection(result.section, result.value);
      labState.agentBuilderMeta.provenance = "ai_suggestion";
      syncBasicBuilderFromBlueprint();
      const tokens = Number(result.receipt.input_tokens || 0) + Number(result.receipt.output_tokens || 0);
      $("#agent-builder-status").textContent = `${agentBuilderLabel(step)} prepared · ${tokens} tokens`;
    } catch (error) {
      $("#agent-builder-status").textContent = `${agentBuilderLabel(step)} unchanged`;
      $("#agent-validation-summary").className = "validation-summary";
      $("#agent-validation-summary").innerHTML = `<span>AI draft failed</span><small>${escapeHtml(error.message)}</small>`;
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
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
      return result;
    } catch (error) {
      $("#agent-builder-status").textContent = "Planning failed";
      $("#agent-blueprint-status").textContent = "Needs attention";
      $("#agent-validation-summary").className = "validation-summary";
      $("#agent-validation-summary").innerHTML = `<span>Error</span><small>${escapeHtml(error.message)}</small>`;
      return null;
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

  function currentAgentInputRequest() {
    return {
      data_mode: labState.agentRunDataMode,
      scenario: $("#agent-test-scenario").value,
      portfolio_id: $("#agent-real-portfolio").value || null,
      as_of: $("#agent-real-as-of").value || null,
      datasets: ["market", "fundamental", "identity", "links"],
    };
  }

  function setAgentRunDataMode(mode) {
    labState.agentRunDataMode = mode;
    labState.agentInputPreview = null;
    $$("[data-agent-data-mode]").forEach((button) => button.classList.toggle("active", button.dataset.agentDataMode === mode));
    $$("[data-agent-run-mode-panel]").forEach((panel) => panel.classList.toggle("hidden", panel.dataset.agentRunModePanel !== mode));
    const real = mode === "real_duckdb";
    $("#agent-run-mode-badge").textContent = real ? "New run · Licensed point-in-time data" : "New run · Synthetic behavior sample";
    $("#agent-run-mode-badge").className = `run-mode-identity ${real ? "real" : "synthetic"}`;
    $("#agent-input-preview-status").textContent = "Preview not loaded";
    $("#agent-input-json").textContent = "{}";
    $("#agent-input-provenance").innerHTML = `<p>${real ? "Select a reviewed portfolio and as-of date, then load the exact DuckDB input." : "Select a named fixture, then load its deliberately synthetic values."}</p>`;
    renderRuntimeTruth();
  }

  function setAgentRunExecutionMode(mode) {
    labState.agentRunExecutionMode = mode;
    const live = mode === "live_llm";
    $$('[data-agent-execution-mode]').forEach((button) => button.classList.toggle("active", button.dataset.agentExecutionMode === mode));
    $("#agent-live-run-model-field").classList.toggle("hidden", !live);
    $("#agent-run-status").textContent = live ? "Model call not run" : "Deterministic check not run";
    $("#test-agent").textContent = live ? "Run model and save" : "Run and save";
  }

  function renderAgentInputPreview(preview) {
    labState.agentInputPreview = preview;
    const provenance = preview.provenance || {};
    const real = provenance.data_mode === "real_duckdb";
    $("#agent-input-preview-status").textContent = provenance.label || (real ? "Licensed historical input" : "Synthetic behavior sample");
    $("#agent-input-json").textContent = JSON.stringify(preview.context, null, 2);
    const chips = [
      `<span class="run-provenance-chip ${real ? "real" : "warning"}">${escapeHtml(provenance.label || provenance.data_mode)}</span>`,
      `<span class="run-provenance-chip">${real ? "Licensed local rows used" : "No licensed rows used"}</span>`,
      provenance.as_of ? `<span class="run-provenance-chip">As of ${escapeHtml(provenance.as_of)}</span>` : "",
      provenance.record_count !== undefined ? `<span class="run-provenance-chip">${Number(provenance.record_count).toLocaleString()} source records</span>` : "",
      provenance.warning ? `<span class="run-provenance-chip warning">${escapeHtml(provenance.warning)}</span>` : "",
    ].filter(Boolean);
    $("#agent-input-provenance").innerHTML = chips.join("");
    $("#agent-input-preview-details").open = true;
  }

  async function previewAgentInput() {
    const button = $("#preview-agent-input");
    button.disabled = true;
    button.textContent = "Loading input…";
    $("#agent-input-preview-status").textContent = "Loading";
    try {
      const preview = await agentApi("/api/agents/input-preview", {
        method: "POST",
        body: JSON.stringify(currentAgentInputRequest()),
      });
      renderAgentInputPreview(preview);
      return preview;
    } catch (error) {
      $("#agent-input-preview-status").textContent = "Unavailable";
      $("#agent-input-provenance").innerHTML = `<p>${escapeHtml(error.message)}</p>`;
      throw error;
    } finally {
      button.disabled = false;
      button.textContent = "Preview exact input";
    }
  }

  function runPayloadMarkup(item) {
    const payload = item.payload;
    if (payload === undefined) return "";
    if (item.kind === "research_plan") {
      const steps = (payload.steps || []).map((step) => `<li>${escapeHtml(step)}</li>`).join("");
      return `<ol class="run-plan-steps">${steps}</ol>`;
    }
    if (item.kind === "capability_prepare") {
      const request = payload.request || {};
      const stages = (payload.stages || []).map((stage) => `<li><b>${escapeHtml(stage.name)}</b><span>${escapeHtml(stage.detail)}</span></li>`).join("");
      return `<div class="run-request-summary">
        <div><span>Contract</span><strong>${escapeHtml(request.contract || "Capability request")}</strong></div>
        <div><span>${request.observation_count !== undefined ? "Observations" : "Positions"}</span><strong>${escapeHtml(request.observation_count ?? request.position_count ?? "—")}</strong></div>
        <div><span>As of</span><strong>${escapeHtml(request.as_of || "—")}</strong></div>
        <div><span>Source</span><strong>${escapeHtml(request.source || "Frozen context")}</strong></div>
      </div><ul class="run-stage-list">${stages}</ul>`;
    }
    if (item.kind === "capability_call") {
      const largest = payload.largest_position || {};
      let entries;
      if (payload.annualized_volatility !== undefined) entries = [["Annualized volatility", runPercentage(payload.annualized_volatility, 2)], ["Observations", payload.observation_count ?? "—"]];
      else if (payload.maximum_drawdown !== undefined) entries = [["Maximum drawdown", runPercentage(-Math.abs(Number(payload.maximum_drawdown)), 2)], ["Peak", formatRunDate(payload.peak_at)], ["Trough", formatRunDate(payload.trough_at)]];
      else if (payload.value_at_risk !== undefined) entries = [["95% historical VaR", runPercentage(payload.value_at_risk, 2)], ["Tail observations", payload.tail_observation_count ?? "—"]];
      else if (payload.expected_shortfall !== undefined) entries = [["95% expected shortfall", runPercentage(payload.expected_shortfall, 2)], ["Tail observations", payload.tail_observation_count ?? "—"]];
      else if (payload.return_method !== undefined) {
        const returns = payload.observations || [];
        entries = [["Latest daily return", runPercentage(returns.at(-1)?.value, 2)], ["Return observations", payload.observation_count ?? returns.length]];
      } else entries = [
        ["Valued NAV", formatRunCurrency(payload.nav)],
        ["Gross exposure", runPercentage(payload.gross_exposure)],
        ["Largest position", largest.weight === undefined ? "—" : `${largest.display_name || largest.instrument_id || "Position"} · ${runPercentage(largest.weight)}`],
        ["Cash weight", runPercentage(payload.cash_weight)],
      ];
      const cards = entries.map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("");
      return `<div class="run-capability-summary">${cards}</div>`;
    }
    if (item.kind === "capability_receipt") {
      const evidence = (payload.evidence_ids || []).join(", ") || "No evidence identifier returned";
      const limitations = (payload.limitations || []).map((value) => `<li>${escapeHtml(value)}</li>`).join("");
      return `<div class="run-receipt-summary">
        <div><span>Capability time</span><strong>${escapeHtml(payload.capability_elapsed_ms ?? payload.elapsed_ms ?? "—")} ms</strong></div>
        <div><span>Evidence</span><strong>${escapeHtml(evidence)}</strong></div>
        <div><span>Effects</span><strong>${(payload.effects || []).length ? escapeHtml(payload.effects.join(", ")) : "None"}</strong></div>
      </div>${limitations ? `<ul class="run-receipt-notes">${limitations}</ul>` : ""}
      <details class="run-technical-receipt"><summary>Technical receipt</summary><pre>${escapeHtml(JSON.stringify(payload, null, 2))}</pre></details>`;
    }
    if (item.kind === "context_binding") {
      return `<div class="run-binding-list">${(payload.bindings || []).map((binding) => `<span>${escapeHtml(String(binding.name || "context").replaceAll("_", " "))} · ${escapeHtml(binding.status || "unknown")}</span>`).join("")}</div>`;
    }
    if (item.kind === "llm_call") {
      const rationale = (payload.rationale_summary || []).map((value) => `<li>${escapeHtml(value)}</li>`).join("");
      return `<div class="run-llm-summary">
        <div><span>Model</span><strong>${escapeHtml(payload.model || "Unknown")}</strong></div>
        <div><span>Response</span><strong>${escapeHtml(payload.response_id || "Unavailable")}</strong></div>
        <div><span>Confidence</span><strong>${payload.confidence === undefined || payload.confidence === null ? "Not supplied" : escapeHtml(`${Math.round(Number(payload.confidence) * 100)}%`)}</strong></div>
      </div>${rationale ? `<ol class="run-rationale-points">${rationale}</ol>` : ""}`;
    }
    if (item.kind === "llm_receipt") {
      return `<div class="run-llm-receipt">
        <div><span>Input tokens</span><strong>${Number(payload.input_tokens || 0).toLocaleString()}</strong></div>
        <div><span>Output tokens</span><strong>${Number(payload.output_tokens || 0).toLocaleString()}</strong></div>
        <div><span>Latency</span><strong>${escapeHtml(payload.elapsed_ms ?? "—")} ms</strong></div>
        <div><span>Provider storage</span><strong>${payload.store === false ? "Disabled" : "Unknown"}</strong></div>
      </div><details class="run-technical-receipt"><summary>Technical model receipt</summary><pre>${escapeHtml(JSON.stringify(payload, null, 2))}</pre></details>`;
    }
    return `<pre>${escapeHtml(JSON.stringify(payload, null, 2))}</pre>`;
  }

  function runMessageMarkup(item) {
    return `<article class="run-message ${escapeHtml(item.kind || "rationale")}">
      <header><strong>${escapeHtml(item.actor || "Agent")}</strong><span>${escapeHtml(item.title || "Work step")}</span></header>
      <p>${escapeHtml(item.detail || "")}</p>${runPayloadMarkup(item)}
    </article>`;
  }

  function runPercentage(value, decimals = 1) {
    if (value === null || value === undefined || value === "") return "Not calculated";
    const numeric = Number(value);
    return Number.isFinite(numeric) ? `${(numeric * 100).toFixed(decimals)}%` : "Unavailable";
  }

  function formatRunCurrency(value, currency = "USD") {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return "Not calculated";
    return new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 0 }).format(numeric);
  }

  function formatRunDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString();
  }

  function buildRunPresentation(input = {}, output = {}, meta = {}, provenance = {}) {
    const evidence = input.evidence_state || "unknown";
    const missingMetrics = [
      ["var_95", "95% historical VaR"],
      ["drawdown", "drawdown"],
      ["stress_loss", "scenario stress"],
    ].filter(([field]) => input[field] === null || input[field] === undefined).map(([, label]) => label);
    const limitations = [...(provenance.limitations || [])];
    if (missingMetrics.length) limitations.unshift(`The run did not calculate ${missingMetrics.join(", ")}.`);
    const eventContextMissing = input.event_context === "Not included" || input.news_context === "Not included";
    if (eventContextMissing && !limitations.some((item) => item.toLowerCase().includes("event") && item.toLowerCase().includes("news"))) limitations.push("Governed event and news context was not included in this test input.");
    const uniqueLimitations = [...new Set(limitations)];
    const largestWeight = input.largest_weight;
    const findings = [input.issue || "No portfolio exception was supplied."];
    if (largestWeight !== null && largestWeight !== undefined && Number(largestWeight) >= .25) findings.push(`The largest position represents ${runPercentage(largestWeight)} of available portfolio value and should be checked against the mandate.`);
    if (evidence !== "complete") findings.push(`Evidence coverage is ${evidence}; conclusions must remain qualified.`);
    const nextSteps = [];
    if (missingMetrics.length) nextSteps.push("Run the reviewed MetricPack before treating this as the complete daily risk review.");
    if (eventContextMissing) nextSteps.push("Attach eligible event and news context for the same point-in-time date.");
    if (largestWeight !== null && largestWeight !== undefined && Number(largestWeight) >= .25) nextSteps.push("Compare the largest position with the applicable mandate concentration limit.");
    nextSteps.push("A human reviewer should confirm, qualify, or reject the draft before any downstream decision.");
    const waiting = meta.status === "waiting_for_human_review";
    const real = meta.data_mode === "real_duckdb" || input.source_mode === "real_duckdb";
    const outcomeSought = (meta.assignment_summary || meta.purpose || "Review the supplied portfolio-risk context and create the declared artifact.").trim().replace(/[.\s]+$/, "");
    const review = output.review || {};
    const reviewReleased = Boolean(meta.auto_approved || review.approved);
    return {
      title: waiting ? "The draft is ready, but the human review checkpoint is still open." : uniqueLimitations.length ? "The portfolio review is usable, with important evidence limitations." : "The requested portfolio review is ready for human assessment.",
      status_label: waiting ? "Awaiting human review" : uniqueLimitations.length ? "Completed with limitations" : "Review ready",
      tone: waiting ? "review" : uniqueLimitations.length ? "limited" : "complete",
      outcome_sought: outcomeSought,
      premise: `Requested outcome: ${outcomeSought}. Data basis: ${real ? "point-in-time CRSP/Compustat records from local DuckDB" : `the code-generated ${meta.scenario || "test"} behavior sample`}.`,
      portfolio: input.portfolio_name || input.portfolio_id || "Supplied portfolio",
      as_of: input.as_of_date || meta.as_of || "Not specified",
      data_basis: real ? "Point-in-time CRSP/Compustat records from local DuckDB" : `Code-generated synthetic behavior sample: ${meta.scenario || "test"}`,
      execution_basis: meta.execution_mode === "live_llm" ? `OpenAI model-backed interpretation · ${meta.execution_model || "configured model"}` : "Deterministic LangGraph interpretation · no LLM call",
      executive_conclusion: output.narrative || "No final narrative was produced.",
      observations: [
        { label: "Daily return", value: runPercentage(input.daily_return, 2), note: "Available point-in-time portfolio signal" },
        { label: "Largest position", value: runPercentage(largestWeight), note: "Compare with the mandate limit" },
        { label: "Cash weight", value: runPercentage(input.cash_weight), note: "Share of available portfolio value" },
        { label: "Evidence", value: evidence.charAt(0).toUpperCase() + evidence.slice(1), note: output.critique || "Evidence review unavailable" },
      ],
      findings,
      limitations: uniqueLimitations,
      next_steps: nextSteps,
      review_boundary: reviewReleased ? "The isolated test released the graph's review interrupt. It did not authorize a trade, hedge, rebalance, or portfolio mutation." : "The graph remains review-bound and has not created any portfolio effect.",
      review,
      effects: [],
    };
  }

  function runPremiseMarkup(presentation, meta = {}) {
    return `<article class="run-premise-card">
      <header><div><span>Outcome sought</span><strong>${escapeHtml(presentation.outcome_sought)}</strong></div><b>${escapeHtml(meta.data_label || presentation.data_basis)}</b></header>
      <dl><div><dt>Portfolio</dt><dd>${escapeHtml(presentation.portfolio)}</dd></div><div><dt>As of</dt><dd>${escapeHtml(presentation.as_of)}</dd></div><div><dt>Output</dt><dd>${escapeHtml(meta.output_contract || "Review artifact")}</dd></div><div><dt>Execution</dt><dd>${escapeHtml(presentation.execution_basis || (meta.execution_mode === "live_llm" ? `Model call · ${meta.execution_model || "configured model"}` : "Deterministic · no LLM"))}</dd></div></dl>
      <p>The exact frozen input remains available above and in <strong>input.json</strong>; the conversation stays focused on the work and outcome.</p>
    </article>`;
  }

  function runOutcomeMarkup(presentation, output = {}) {
    const observations = (presentation.observations || []).map((item) => `<div><span>${escapeHtml(item.label)}</span><strong>${escapeHtml(item.value)}</strong><small>${escapeHtml(item.note)}</small></div>`).join("");
    const findings = (presentation.findings || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
    const limitations = (presentation.limitations || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>No additional limitation was recorded.</li>";
    const nextSteps = (presentation.next_steps || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
    const review = presentation.review || output.review || {};
    const reviewLabel = review.approved ? "Isolated checkpoint released" : "Human review required";
    const sections = presentation.report_sections || output.model_output?.report_sections || [];
    const sectionMarkup = sections.length ? `<div class="run-report-sections">${sections.map((section) => `<section class="${section.section_id === "executive_signal" ? "lead" : ""}"><span>${escapeHtml(section.title)}</span>${section.content ? `<p>${escapeHtml(section.content)}</p>` : ""}${section.items?.length ? `<ul>${section.items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}</section>`).join("")}</div>` : "";
    return `<article class="run-outcome-card ${escapeHtml(presentation.tone || "limited")}">
      <header class="run-outcome-masthead"><div><span>Agent result</span><h3>${escapeHtml(presentation.title)}</h3></div><b>${escapeHtml(presentation.status_label)}</b></header>
      <p class="run-outcome-premise">${escapeHtml(presentation.premise)}</p>
      ${sections.length ? sectionMarkup : `<section class="run-outcome-conclusion"><span>Executive conclusion</span><p>${escapeHtml(presentation.executive_conclusion)}</p></section>`}
      <div class="run-outcome-metrics">${observations}</div>
      ${sections.length ? `<details class="run-condensed-evidence"><summary>Additional execution and evidence limitations</summary><ul>${limitations}</ul></details>` : `<div class="run-outcome-columns">
        <section><span>Material findings</span><ul>${findings}</ul></section>
        <section><span>Important limitations</span><ul>${limitations}</ul></section>
      </div>
      <section class="run-outcome-next"><span>Recommended review steps</span><ol>${nextSteps}</ol></section>`}
      <footer><div><span>Decision boundary</span><p>${escapeHtml(presentation.review_boundary)}</p></div><b>${escapeHtml(reviewLabel)} · Effects: none</b></footer>
    </article>`;
  }

  async function renderLiveAgentRun(result) {
    const chat = $("#agent-run-chat");
    const state = result.final_state || {};
    const presentation = result.presentation || buildRunPresentation(result.input_context || {}, state, result, result.input_provenance || {});
    chat.innerHTML = runPremiseMarkup(presentation, result);
    for (const item of result.activity || []) {
      chat.insertAdjacentHTML("beforeend", runMessageMarkup(item));
      chat.scrollTop = chat.scrollHeight;
      await new Promise((resolve) => setTimeout(resolve, 70));
    }
    chat.insertAdjacentHTML("beforeend", runOutcomeMarkup(presentation, state));
    chat.scrollTop = chat.scrollHeight;
  }

  function renderSavedAgentRun(detail) {
    const manifest = detail.manifest;
    const contents = detail.contents || {};
    const input = contents["input.json"] || {};
    const provenance = contents["input-provenance.json"] || {};
    const blueprint = contents["blueprint.json"] || {};
    const output = contents["output.json"] || {};
    const activity = contents["activity.json"] || [];
    const real = manifest.data_mode === "real_duckdb" || provenance.data_mode === "real_duckdb";
    $("#agent-run-mode-badge").textContent = real ? "Saved run · Licensed historical data" : "Saved run · Synthetic behavior sample";
    $("#agent-run-mode-badge").className = `run-mode-identity ${real ? "real" : "synthetic"}`;
    const presentation = output.presentation || buildRunPresentation(input, output, { ...manifest, purpose: blueprint.purpose }, provenance);
    $("#agent-run-chat").innerHTML = `
      ${runPremiseMarkup(presentation, manifest)}
      ${activity.map(runMessageMarkup).join("")}
      ${runOutcomeMarkup(presentation, output)}`;
    $("#agent-run-chat").scrollTop = 0;
    renderRunFiles(detail);
  }

  function renderRunFiles(detail) {
    const manifest = detail.manifest;
    labState.selectedAgentRunDetail = detail;
    labState.selectedAgentRunId = manifest.run_id;
    $("#agent-run-folder").textContent = manifest.folder;
    $("#delete-agent-run").classList.remove("hidden");
    $("#agent-run-files").innerHTML = manifest.files.map((file) => `
      <button class="run-file-item" type="button" data-agent-run-file="${escapeHtml(file.name)}"><strong>${escapeHtml(file.name)}</strong><span>${Number(file.bytes || 0).toLocaleString()} bytes</span></button>`).join("");
    $("#agent-run-file-content").textContent = "Select a file to inspect it.";
    $$(".run-repository-item").forEach((item) => item.classList.toggle("active", item.dataset.agentRunId === manifest.run_id));
  }

  function renderAgentRunRepository() {
    $("#agent-run-repository").innerHTML = labState.agentRuns.length ? labState.agentRuns.map((run) => `
      <button class="run-repository-item ${labState.selectedAgentRunId === run.run_id ? "active" : ""}" type="button" data-agent-run-id="${escapeHtml(run.run_id)}">
        <b class="${run.data_mode === "real_duckdb" ? "real" : "synthetic"}">${run.data_mode === "real_duckdb" ? "Licensed historical" : run.data_mode === "synthetic_behavior_sample" ? "Synthetic behavior sample" : "Legacy unversioned synthetic"}</b>
        <strong>${escapeHtml(run.agent_name)}</strong>
        <span>${escapeHtml(run.created_at)} · ${escapeHtml(run.status)}${run.execution_mode === "live_llm" ? ` · model call` : " · deterministic"}</span>
      </button>`).join("") : '<div class="empty-state">No saved agent runs.</div>';
  }

  async function loadAgentRuns() {
    try {
      const result = await agentApi("/api/agents/runs");
      labState.agentRuns = result.runs || [];
      renderAgentRunRepository();
    } catch (error) {
      $("#agent-run-repository").innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
    }
  }

  async function openAgentRun(runId) {
    const detail = await agentApi(`/api/agents/runs/${encodeURIComponent(runId)}`);
    renderSavedAgentRun(detail);
    renderAgentRunRepository();
    $("#agent-live-state").textContent = "Saved run";
  }

  async function deleteSelectedAgentRun() {
    const runId = labState.selectedAgentRunId;
    if (!runId || !window.confirm(`Delete local test run ${runId} and every file in its folder?`)) return;
    await agentApi(`/api/agents/runs/${encodeURIComponent(runId)}`, { method: "DELETE" });
    labState.selectedAgentRunId = null;
    labState.selectedAgentRunDetail = null;
    $("#delete-agent-run").classList.add("hidden");
    $("#agent-run-folder").textContent = "No run folder selected.";
    $("#agent-run-files").innerHTML = "";
    $("#agent-run-file-content").textContent = "Select a file to inspect it.";
    $("#agent-run-chat").innerHTML = '<div class="run-chat-empty"><strong>Run deleted</strong><p>The local run folder and its files were removed.</p></div>';
    await loadAgentRuns();
  }

  async function runAgentTest() {
    $("#test-agent").disabled = true;
    $("#agent-run-status").textContent = "Preparing";
    $("#agent-live-state").textContent = "Freezing input";
    try {
      const preview = labState.agentInputPreview || await previewAgentInput();
      $("#agent-run-chat").innerHTML = `<article class="run-message assignment"><header><strong>System</strong><span>${escapeHtml(preview.provenance.label)}</span></header><p>Exact input frozen. Compiling the current blueprint and starting its governed graph.</p></article>`;
      $("#agent-live-state").textContent = "Compiling";
      const compiled = labState.agentCompile || await compileAgent();
      switchAgentOutputTab("run");
      $("#agent-live-state").textContent = "Agent working";
      $("#agent-run-status").textContent = "Running";
      const input = currentAgentInputRequest();
      const result = await agentApi("/api/agents/run", {
        method: "POST",
        body: JSON.stringify({
          blueprint: compiled.blueprint,
          ...input,
          execution_mode: labState.agentRunExecutionMode,
          execution_model: $("#agent-live-run-model").value,
          run_label: $("#agent-run-label").value.trim(),
          persist_run: true,
          auto_approve_review: $("#agent-auto-review").checked,
        }),
      });
      $("#agent-run-status").textContent = result.status === "completed" ? "Completed and saved" : "Paused and saved";
      $("#agent-run-status").classList.toggle("warning", result.status !== "completed");
      $("#agent-live-state").textContent = result.status === "completed" ? "Complete" : "Human review";
      await renderLiveAgentRun(result);
      $("#agent-builder-status").textContent = result.status === "completed" ? "Run saved" : "Review interrupt saved";
      await loadAgentRuns();
      if (result.run?.run_id) await openAgentRun(result.run.run_id);
      return result;
    } catch (error) {
      $("#agent-run-status").textContent = "Execution failed";
      $("#agent-run-status").classList.add("warning");
      $("#agent-live-state").textContent = "Failed";
      $("#agent-run-chat").insertAdjacentHTML("beforeend", `<article class="run-message critique"><header><strong>Runtime</strong><span>Execution failed</span></header><p>${escapeHtml(error.message)}</p></article>`);
      return null;
    } finally {
      $("#test-agent").disabled = false;
    }
  }

  function setBasicTestState(name, label, state) {
    const target = document.querySelector(`[data-basic-test-state="${name}"]`);
    if (!target) return;
    target.textContent = label;
    target.className = state;
  }

  async function runBasicTestSuite() {
    const button = $("#basic-test-agent");
    button.disabled = true;
    button.textContent = "Running tests…";
    $("#basic-test-result").className = "basic-test-result";
    $("#basic-test-result").innerHTML = "<span>Running</span><p>Compiling once, then checking representative, missing-evidence, and locked-policy behaviour.</p>";
    ["normal", "failure", "adversarial"].forEach((name) => setBasicTestState(name, "Running", "warning"));
    try {
      const compiled = labState.agentCompile || await compileAgent();
      if (!compiled) throw new Error("The blueprint did not compile.");
      const normal = await agentApi("/api/agents/run", {
        method: "POST",
        body: JSON.stringify({ blueprint: compiled.blueprint, scenario: "concentration", persist_run: false, auto_approve_review: true }),
      });
      const failure = await agentApi("/api/agents/run", {
        method: "POST",
        body: JSON.stringify({ blueprint: compiled.blueprint, scenario: "missing", persist_run: false, auto_approve_review: true }),
      });
      const policyPassed = compiled.blueprint.governance.effects_allowed === false
        && compiled.blueprint.governance.prohibited_actions.length > 0
        && compiled.blueprint.capability_latches.every((latch) => capabilities.some((capability) => capability.id === latch.capability_id));
      const normalPassed = normal.status === "completed" && normal.trace.length > 0;
      const failurePassed = failure.status === "completed" && (failure.interrupted || failure.trace.length > 0);
      setBasicTestState("normal", normalPassed ? "Passed" : "Attention", normalPassed ? "passed" : "warning");
      setBasicTestState("failure", failurePassed ? "Passed" : "Attention", failurePassed ? "passed" : "warning");
      setBasicTestState("adversarial", policyPassed ? "Passed" : "Attention", policyPassed ? "passed" : "warning");
      const allPassed = normalPassed && failurePassed && policyPassed;
      $("#basic-test-result").className = `basic-test-result ${allPassed ? "passed" : ""}`;
      $("#basic-test-result").innerHTML = `<span>${allPassed ? "Passed" : "Review"}</span><p>${allPassed ? "The blueprint compiled and all three quick gates passed. Save it as a review-bound draft." : "At least one quick gate needs attention before publication."}</p>`;
      $("#agent-run-status").textContent = allPassed ? "3 quick gates passed" : "Needs attention";
      $("#agent-builder-status").textContent = allPassed ? "Quick tests passed" : "Test attention";
      return allPassed;
    } catch (error) {
      ["normal", "failure", "adversarial"].forEach((name) => setBasicTestState(name, "Not passed", "warning"));
      $("#basic-test-result").innerHTML = `<span>Failed</span><p>${escapeHtml(error.message)}</p>`;
      return false;
    } finally {
      button.disabled = false;
      button.textContent = "Compile and run test";
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
      if (agent.builder_meta) labState.agentBuilderMeta = { ...labState.agentBuilderMeta, ...structuredClone(agent.builder_meta) };
      else if (agent.built_in) {
        labState.agentBuilderMeta.recipe_id = agent.id;
        const [contextPack, capabilityPack] = basicRecipeDefaults[agent.id] || ["morning_risk_context", "daily_risk_review"];
        labState.agentBuilderMeta.context_pack = contextPack;
        labState.agentBuilderMeta.capability_pack = capabilityPack;
      }
      applyAgentBlueprint(agent.blueprint);
      labState.agentCompile = null;
      $("#agent-builder-status").textContent = agent.compiledArtifact ? "Loaded compiled definition" : "Loaded draft";
      syncBasicBuilderFromBlueprint();
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

  function cycleMoney(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return "—";
    return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(numeric);
  }

  function cycleTimeLabel(value) {
    if (!value) return "—";
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime())
      ? value
      : parsed.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "medium", timeZone: "UTC" });
  }

  function cycleCandleChart(candles = []) {
    const values = candles.slice(-90);
    if (!values.length) return '<div class="cycle-chart-empty">No one-minute candle has been released.</div>';
    const width = 900;
    const height = 270;
    const pad = 34;
    const minimum = Math.min(...values.map((item) => Number(item.low)));
    const maximum = Math.max(...values.map((item) => Number(item.high)));
    const span = maximum - minimum || Math.abs(maximum) * .001 || 1;
    const xStep = (width - pad * 2) / Math.max(values.length, 1);
    const y = (value) => pad + (maximum - Number(value)) / span * (height - pad * 2);
    const candlesMarkup = values.map((item, index) => {
      const x = pad + index * xStep + xStep / 2;
      const open = y(item.open);
      const close = y(item.close);
      const high = y(item.high);
      const low = y(item.low);
      const positive = Number(item.close) >= Number(item.open);
      const bodyTop = Math.min(open, close);
      const bodyHeight = Math.max(Math.abs(close - open), 1.5);
      return `<g class="${positive ? "up" : "down"}"><line x1="${x}" y1="${high}" x2="${x}" y2="${low}"></line><rect x="${x - Math.max(1, xStep * .28)}" y="${bodyTop}" width="${Math.max(2, xStep * .56)}" height="${bodyHeight}"></rect></g>`;
    }).join("");
    return `<div class="cycle-chart"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Synthetic one-minute portfolio candles">
      <line class="grid" x1="${pad}" y1="${pad}" x2="${width - pad}" y2="${pad}"></line>
      <line class="grid" x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}"></line>
      ${candlesMarkup}
      <text x="${pad}" y="20">${escapeHtml(cycleMoney(maximum))}</text><text x="${pad}" y="${height - 8}">${escapeHtml(cycleMoney(minimum))}</text>
    </svg><footer><span>${escapeHtml(cycleTimeLabel(values[0].timestamp))}</span><b>Seeded synthetic candles · ${values.at(-1).updates || 0} updates in current minute</b><span>${escapeHtml(cycleTimeLabel(values.at(-1).timestamp))}</span></footer></div>`;
  }

  function cycleMetricCards(snapshot) {
    const market = snapshot.market || {};
    const largest = market.positions?.[0];
    const clock = snapshot.clock || {};
    return `<div class="cycle-metric-grid">
      <article><span>Portfolio NAV</span><strong>${escapeHtml(cycleMoney(market.nav))}</strong><small>Real close anchors · synthetic intraday path</small></article>
      <article><span>From session open</span><strong class="${Number(market.return_from_open) < 0 ? "negative" : "positive"}">${escapeHtml(runPercentage(market.return_from_open, 2))}</strong><small>Released observations only</small></article>
      <article><span>Largest exposure</span><strong>${escapeHtml(runPercentage(largest?.weight, 1))}</strong><small>${escapeHtml(largest?.display_name || "No valued position")}</small></article>
      <article><span>Released ticks</span><strong>${Number(clock.second_of_session || 0).toLocaleString()}</strong><small>Per active position · aggregated every minute</small></article>
    </div>`;
  }

  function cyclePositionTable(positions = []) {
    return `<div class="cycle-position-table"><div class="head"><span>Company</span><span>Price</span><span>From open</span><span>Weight</span></div>${positions.map((item) => `<div><strong>${escapeHtml(item.display_name || item.instrument_id)}<small>${escapeHtml(item.ticker || item.instrument_id)}</small></strong><span>${Number(item.price).toLocaleString(undefined, { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span><span class="${Number(item.return_from_open) < 0 ? "negative" : "positive"}">${runPercentage(item.return_from_open, 2)}</span><span>${runPercentage(item.weight, 1)}</span></div>`).join("")}</div>`;
  }

  function renderCycleDashboard(snapshot) {
    const dashboard = snapshot.dashboard || { pages: [] };
    const pages = dashboard.pages || [];
    if (!pages.some((item) => item.page_id === labState.cycleDashboardPage)) labState.cycleDashboardPage = pages[0]?.page_id || "overview";
    $("#cycle-dashboard-pages").innerHTML = pages.map((page) => `<button type="button" data-cycle-page="${escapeHtml(page.page_id)}" class="${page.page_id === labState.cycleDashboardPage ? "active" : ""}">${escapeHtml(page.title)}</button>`).join("");
    const page = pages.find((item) => item.page_id === labState.cycleDashboardPage) || pages[0];
    $("#cycle-dashboard-title").textContent = page?.title || "Living dashboard";
    $("#cycle-dashboard-version").textContent = `Version ${dashboard.version || 1} · ${page?.agent_id ? `interpreted by ${page.agent_id.replaceAll("-", " ")}` : "no specialist attached"}`;
    const market = snapshot.market || {};
    const candles = market.candles?.portfolio || [];
    if (labState.cycleDashboardPage === "market") {
      $("#cycle-dashboard-view").innerHTML = `<section class="cycle-page-intro"><span>Simulated market tape</span><p>Each completed candle contains sixty deterministic pseudo-random second updates. The current candle grows until the simulated minute closes.</p></section>${cycleCandleChart(candles)}${cyclePositionTable(market.positions || [])}`;
      return;
    }
    if (labState.cycleDashboardPage === "risk") {
      const findings = new Map((snapshot.findings || []).map((item) => [item.finding_id, item]));
      const proposals = snapshot.decision_proposals || [];
      const decisions = new Map((snapshot.decisions || []).map((item) => [item.proposal_id, item]));
      const receipts = new Map((snapshot.consequence_receipts || []).map((item) => [item.proposal_id, item]));
      const history = snapshot.daily_history || [];
      $("#cycle-dashboard-view").innerHTML = `${cycleMetricCards(snapshot)}<div class="cycle-risk-columns"><section><span>Decision proposals and resolutions</span>${proposals.length ? proposals.map((item) => { const finding = findings.get(item.finding_id); const decision = decisions.get(item.proposal_id); const receipt = receipts.get(item.proposal_id); return `<article class="cycle-decision-card"><b>${decision ? `resolved · ${escapeHtml(decision.outcome)}` : "awaiting human resolution"}</b><strong>${escapeHtml(finding?.summary || `Finding ${item.finding_id}`)}</strong><small>${decision ? `Resolver ${escapeHtml(decision.resolver?.resolver_id || "unknown")} · ${escapeHtml(receipt?.consequence || "No consequence receipt")}` : escapeHtml(cycleTimeLabel(item.as_of))}</small></article>`; }).join("") : '<div class="empty-state">No threshold finding has created a decision proposal.</div>'}</section><section><span>Completed dates</span>${history.length ? history.map((item) => `<article class="cycle-history-row"><strong>${escapeHtml(item.date)}</strong><b class="${Number(item.return) < 0 ? "negative" : "positive"}">${runPercentage(item.return, 2)}</b><small>${escapeHtml(cycleMoney(item.close_nav))}</small></article>`).join("") : '<div class="empty-state">No simulated day has closed.</div>'}</section></div>`;
      return;
    }
    if (labState.cycleDashboardPage === "agents") {
      const patches = dashboard.patches || [];
      $("#cycle-dashboard-view").innerHTML = `<section class="cycle-page-intro"><span>Dashboard composition record</span><p>Agents use bounded meta-capabilities to propose declarative changes. The platform records the reason and version; no application code or portfolio state is modified.</p></section><div class="cycle-patch-list">${patches.map((patch) => `<article><b>${escapeHtml(patch.capability_id)}</b><strong>${escapeHtml(patch.action.replaceAll("_", " "))} · ${escapeHtml(patch.page_id)}</strong><p>${escapeHtml(patch.rationale)}</p><small>Version ${patch.version} · effects limited to run artifact</small></article>`).join("")}</div>`;
      return;
    }
    $("#cycle-dashboard-view").innerHTML = `${cycleMetricCards(snapshot)}${cycleCandleChart(candles)}<section class="cycle-overview-note"><span>Current monitoring premise</span><p>${escapeHtml(snapshot.report?.sections?.find((item) => item.section_id === "risk_interpretation")?.content || "Waiting for the first risk interpretation.")}</p></section>`;
  }

  function renderCycleReport(report = {}) {
    $("#cycle-report-title").textContent = report.title || "Simulated portfolio risk review";
    $("#cycle-report-status").textContent = report.status || "Waiting";
    $("#cycle-report-sections").innerHTML = (report.sections || []).map((section) => `<article class="cycle-report-section ${section.section_id === "executive_signal" ? "lead" : ""}"><span>${escapeHtml(section.title)}</span>${section.content ? `<p>${escapeHtml(section.content)}</p>` : ""}${section.items?.length ? `<ul>${section.items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}</article>`).join("");
  }

  function renderCycleAgents(snapshot) {
    const pages = snapshot.dashboard?.pages || [];
    $("#cycle-agent-latches").innerHTML = pages.map((page) => `<article><span>${escapeHtml(page.title)}</span><strong>${escapeHtml(page.agent_id ? page.agent_id.replaceAll("-", " ") : "No specialist")}</strong><small>${escapeHtml(page.purpose)}</small></article>`).join("");
    const selected = $("#cycle-agent-page").value;
    $("#cycle-agent-page").innerHTML = pages.map((page) => `<option value="${escapeHtml(page.page_id)}">${escapeHtml(page.title)}</option>`).join("");
    if (pages.some((page) => page.page_id === selected)) $("#cycle-agent-page").value = selected;
    $("#cycle-meta-capabilities").innerHTML = (snapshot.meta_capabilities || []).map((item) => `<span>${escapeHtml(item)}</span>`).join("");
  }

  function renderCycleSnapshot(snapshot) {
    labState.cycleSnapshot = snapshot;
    const clock = snapshot.clock || {};
    $("#cycle-runtime-status").textContent = snapshot.status.replaceAll("_", " ");
    $("#cycle-runtime-status").classList.toggle("warning", snapshot.status === "paused_for_review");
    $("#cycle-clock-time").textContent = cycleTimeLabel(clock.timestamp);
    $("#cycle-clock-progress").textContent = `Day ${Number(clock.day_index || 0) + 1} of ${clock.day_count || 0} · ${Number(snapshot.speed || 1).toLocaleString()}× speed`;
    $("#cycle-day-label").textContent = `Day ${Number(clock.day_index || 0) + 1} / ${clock.day_count || 0}`;
    $("#cycle-day-progress-bar").style.width = `${Math.min(100, Number(clock.second_of_session || 0) / Number(clock.seconds_per_day || 1) * 100)}%`;
    $("#cycle-live-dot").classList.toggle("running", Boolean(snapshot.running));
    $("#cycle-live-label").textContent = snapshot.running ? "Generating" : snapshot.status === "complete" ? "Complete" : "Paused";
    const positions = snapshot.market?.positions?.length || 0;
    const released = Number(clock.second_of_session || 0) * positions;
    $("#cycle-update-count").textContent = `${released.toLocaleString()} released position updates`;
    $("#cycle-speed").value = String(snapshot.speed);
    $("#cycle-event-stream").innerHTML = (snapshot.events || []).length ? snapshot.events.map((item) => `<article class="${escapeHtml(item.kind)}"><span>${escapeHtml(cycleTimeLabel(item.timestamp))}</span><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.detail)}</p></article>`).join("") : '<div class="empty-state">No event has been released.</div>';
    renderCycleDashboard(snapshot);
    renderCycleReport(snapshot.report);
    renderCycleAgents(snapshot);
    const resolvedProposalIds = new Set((snapshot.decisions || []).map((item) => item.proposal_id));
    const proposal = (snapshot.decision_proposals || []).find((item) => !resolvedProposalIds.has(item.proposal_id));
    const finding = (snapshot.findings || []).find((item) => item.finding_id === proposal?.finding_id);
    $("#cycle-decision-panel").classList.toggle("hidden", !proposal);
    if (proposal) {
      $("#cycle-decision-panel").dataset.proposalId = proposal.proposal_id;
      $("#cycle-decision-finding").textContent = finding?.summary || `Finding ${proposal.finding_id}`;
      $("#cycle-decision-question").textContent = proposal.question;
      $("#cycle-decision-consequences").innerHTML = (proposal.options || []).map((option) => `<li><strong>${escapeHtml(option.label)}</strong> — ${escapeHtml(option.consequence)}</li>`).join("");
    }
  }

  async function loadCycleSnapshot() {
    if (!labState.cycleSessionId) return;
    try {
      const snapshot = await agentApi(`/api/workflow-cycle/sessions/${encodeURIComponent(labState.cycleSessionId)}`);
      renderCycleSnapshot(snapshot);
    } catch (error) {
      $("#cycle-runtime-status").textContent = "Connection lost";
      if (labState.cyclePollTimer) window.clearInterval(labState.cyclePollTimer);
      labState.cyclePollTimer = null;
    }
  }

  function startCyclePolling() {
    if (labState.cyclePollTimer) window.clearInterval(labState.cyclePollTimer);
    labState.cyclePollTimer = window.setInterval(loadCycleSnapshot, 500);
  }

  async function createCycleSession() {
    const button = $("#create-cycle-session");
    button.disabled = true;
    button.textContent = "Preparing real anchors…";
    try {
      if (labState.cycleSessionId) {
        await agentApi(`/api/workflow-cycle/sessions/${encodeURIComponent(labState.cycleSessionId)}`, { method: "DELETE" }).catch(() => {});
      }
      const snapshot = await agentApi("/api/workflow-cycle/sessions", {
        method: "POST",
        body: JSON.stringify({
          portfolio_id: $("#cycle-portfolio").value,
          start_date: $("#cycle-start-date").value,
          end_date: $("#cycle-end-date").value,
          seed: Number($("#cycle-seed").value),
          speed: Number($("#cycle-initial-speed").value),
          daily_loss_limit: Number($("#cycle-loss-limit").value),
        }),
      });
      labState.cycleSessionId = snapshot.session_id;
      labState.cycleDashboardPage = "overview";
      $("#cycle-console").classList.remove("hidden");
      $("#cycle-setup-panel").classList.add("compact");
      renderCycleSnapshot(snapshot);
      startCyclePolling();
    } catch (error) {
      $("#cycle-runtime-status").textContent = error.message;
      $("#cycle-runtime-status").classList.add("warning");
    } finally {
      button.disabled = false;
      button.textContent = "Create workflow-cycle session";
    }
  }

  async function controlCycle(action, speed = null) {
    if (!labState.cycleSessionId) return;
    const snapshot = await agentApi(`/api/workflow-cycle/sessions/${encodeURIComponent(labState.cycleSessionId)}/control`, {
      method: "POST",
      body: JSON.stringify({ action, speed }),
    });
    renderCycleSnapshot(snapshot);
  }

  async function resolveCycleDecision(outcome) {
    const proposalId = $("#cycle-decision-panel").dataset.proposalId;
    if (!labState.cycleSessionId || !proposalId) return;
    const resolverId = $("#cycle-decision-resolver").value.trim();
    if (resolverId.length < 3) {
      showToast("Enter a resolver ID before recording the decision.", "error");
      $("#cycle-decision-resolver").focus();
      return;
    }
    const snapshot = await agentApi(`/api/workflow-cycle/sessions/${encodeURIComponent(labState.cycleSessionId)}/decision-proposals/${encodeURIComponent(proposalId)}/resolve`, {
      method: "POST",
      body: JSON.stringify({ outcome, resolver_id: resolverId, resolver_type: "human" }),
    });
    $("#cycle-decision-resolver").value = "";
    renderCycleSnapshot(snapshot);
  }

  async function attachCycleAgent() {
    if (!labState.cycleSessionId) return;
    const snapshot = await agentApi(`/api/workflow-cycle/sessions/${encodeURIComponent(labState.cycleSessionId)}/agents`, {
      method: "POST",
      body: JSON.stringify({ page_id: $("#cycle-agent-page").value, agent_id: $("#cycle-agent-select").value }),
    });
    renderCycleSnapshot(snapshot);
  }

  function applyConciseReportStructure() {
    const field = (name, title, valueType, role, description, passId, validation) => ({
      name, title, value_type: valueType, semantic_role: role, description,
      nullable: false, format: valueType === "string" ? "markdown" : "none",
      enum_values: [], nested_schema_json: "", merge_strategy: "replace",
      citation_required: !["uncertainty", "review_actions"].includes(name),
      validation_rule: validation, produced_in_passes: [passId],
    });
    labState.agentOutputFields = [
      field("executive_signal", "Executive signal", "string", "introduction", "State only the decision-relevant portfolio conclusion in no more than 100 words.", "conclusion", "Contains one concise conclusion and does not repeat supporting sections."),
      field("what_changed", "What changed", "array", "results", "List no more than four material changes since the prior accepted workflow cycle.", "conclusion", "Contains only material deltas, with no methodology commentary."),
      field("risk_interpretation", "Risk interpretation", "string", "narrative", "Explain the non-trivial downside, drawdown, volatility and tail-risk implications.", "risk_analysis", "Explains why the calculated risk state matters without repeating the executive signal."),
      field("exposure_and_mandate", "Exposure and mandate", "string", "results", "Interpret concentration, cash, sector and applicable mandate relevance.", "risk_analysis", "Uses named firms and distinguishes priced-sleeve coverage from the full portfolio."),
      field("uncertainty", "Uncertainty", "array", "evidence", "List only limitations that could materially change the conclusion.", "review", "Contains no generic disclaimer or duplicated process description."),
      field("review_actions", "Review actions", "array", "recommendations", "List no more than five concrete questions or analyses for the human reviewer.", "review", "Every action is specific, effect-free and decision-relevant."),
    ];
    labState.agentOutputPasses = [
      { pass_id: "conclusion", title: "Material conclusion", objective: "Write the executive signal and material changes from the compact context projection.", target_fields: ["executive_signal", "what_changed"], operation: "replace", context_policy: "evidence_subset", depends_on: [], max_output_tokens: 800, quality_gate: "The conclusion is under 100 words and no fact is repeated.", human_review_after: false },
      { pass_id: "risk_analysis", title: "Risk and mandate interpretation", objective: "Explain downside, tail risk and exposure implications without repeating the conclusion.", target_fields: ["risk_interpretation", "exposure_and_mandate"], operation: "replace", context_policy: "evidence_subset", depends_on: ["conclusion"], max_output_tokens: 1000, quality_gate: "Each fact has one owning section and every numerical claim is supported.", human_review_after: false },
      { pass_id: "review", title: "Uncertainty and review actions", objective: "Surface only decision-changing uncertainty and concrete human review actions.", target_fields: ["uncertainty", "review_actions"], operation: "replace", context_policy: "selected_prior_fields", depends_on: ["risk_analysis"], max_output_tokens: 700, quality_gate: "No generic caveats, repeated findings or portfolio effects are present.", human_review_after: true },
    ];
    $("#agent-output-composition").value = "sectioned_report";
    $("#agent-output-density").value = "dense";
    $("#agent-assembly-token-budget").value = 4000;
    $("#agent-structured-output-description").value = "A concise six-section portfolio-risk review in which every fact has one owning section and only material uncertainty is shown.";
    renderOutputFields();
    renderOutputPasses();
    renderAgentContract();
    $("#agent-builder-status").textContent = "Concise report structure applied";
  }

  const registryStateLabels = {
    discovered: "Discovered only",
    candidate: "Candidate",
    validated: "Validated",
    published: "Published locally",
    deprecated: "Deprecated",
    retired: "Retired",
    archived: "Archived",
  };

  function registryIdentity(record) {
    return record.projection.identity;
  }

  function registryFilteredRecords() {
    const search = ($("#registry-search")?.value || "").trim().toLowerCase();
    const kind = $("#registry-kind-filter")?.value || "";
    const indexState = $("#registry-index-filter")?.value || "";
    const lifecycle = $("#registry-lifecycle-filter")?.value || "";
    return labState.registryRecords.filter((record) => {
      const projection = record.projection;
      const identity = registryIdentity(record);
      const haystack = [projection.display_name, identity.asset_id, identity.kind, projection.summary, projection.source.source_reference, ...(projection.tags || [])].join(" ").toLowerCase();
      if (search && !haystack.includes(search)) return false;
      if (kind && identity.kind !== kind) return false;
      if (indexState === "discovered" && record.indexed) return false;
      if (indexState === "indexed" && !record.indexed) return false;
      if (lifecycle && record.state !== lifecycle) return false;
      return true;
    });
  }

  function registryValue(value) {
    if (value == null || value === "") return "Not declared";
    if (Array.isArray(value)) return value.length ? value.join(", ") : "None";
    if (typeof value === "object") return JSON.stringify(value);
    if (typeof value === "boolean") return value ? "Yes" : "No";
    return String(value);
  }

  function renderRegistrySummary() {
    const records = labState.registryRecords;
    const discovered = records.filter((record) => !record.indexed).length;
    const indexed = records.filter((record) => record.indexed).length;
    const incompatible = records.filter((record) => ["incompatible", "unavailable"].includes(record.projection.compatibility.status)).length;
    $("#registry-summary").innerHTML = [
      [records.length, "source definitions"],
      [discovered, "discovered only"],
      [indexed, "indexed locally"],
      [incompatible, "compatibility warnings"],
    ].map(([value, label]) => `<div><strong>${value}</strong><span>${escapeHtml(label)}</span></div>`).join("");
  }

  function renderRegistryList() {
    const records = registryFilteredRecords();
    $("#registry-result-count").textContent = `${records.length} result${records.length === 1 ? "" : "s"}`;
    if (!records.length) {
      $("#registry-list").innerHTML = '<div class="empty-state">No definitions match these filters. The source preview remains unchanged.</div>';
      $("#registry-detail").innerHTML = '<div class="empty-state">Clear a filter to inspect a definition.</div>';
      return;
    }
    if (!records.some((record) => record.reference === labState.selectedRegistryReference)) {
      labState.selectedRegistryReference = records[0].reference;
    }
    $("#registry-list").innerHTML = records.map((record) => {
      const projection = record.projection;
      const identity = registryIdentity(record);
      const selected = record.reference === labState.selectedRegistryReference;
      const lifecycle = record.indexed ? `<span class="registry-badge lifecycle">${escapeHtml(registryStateLabels[record.state] || record.state)}</span>` : "";
      return `<button class="registry-result ${selected ? "selected" : ""}" type="button" data-registry-reference="${escapeHtml(record.reference)}" aria-pressed="${selected}">
        <span class="registry-result-top"><b>${escapeHtml(identity.kind)}</b><span class="registry-badge ${record.indexed ? "indexed" : "discovered"}">${record.indexed ? "Indexed" : "Discovered only"}</span>${lifecycle}</span>
        <strong>${escapeHtml(projection.display_name)}</strong>
        <code>${escapeHtml(identity.asset_id)} · ${escapeHtml(identity.version)}</code>
        <small>${escapeHtml(projection.summary)}</small>
      </button>`;
    }).join("");
    renderRegistryDetail();
  }

  function renderRegistryDetail() {
    const record = labState.registryRecords.find((item) => item.reference === labState.selectedRegistryReference);
    if (!record) return;
    const projection = record.projection;
    const identity = registryIdentity(record);
    const source = projection.source;
    const compatible = projection.compatibility.status;
    const versions = labState.registryRecords.filter((item) => {
      const other = registryIdentity(item);
      return item.indexed && other.kind === identity.kind && other.namespace === identity.namespace && other.asset_id === identity.asset_id && item.reference !== record.reference;
    });
    const next = (record.allowed_transitions || [])[0];
    const publishBlocked = next === "published" && (!source.canonical || compatible !== "compatible");
    const receipts = record.receipts || [];
    const relationships = (projection.relationships || []).map((relationship) => `<article><b>${escapeHtml(relationship.relationship.replaceAll("_", " "))}</b><span>${escapeHtml(relationship.target_native_id)} · ${escapeHtml(relationship.resolution)}</span>${relationship.target_reference ? `<code>${escapeHtml(relationship.target_reference)}</code>` : ""}</article>`).join("");
    $("#registry-detail").innerHTML = `
      <header class="registry-detail-header"><span class="panel-label">${escapeHtml(identity.kind)} · ${escapeHtml(identity.version)}</span><h2>${escapeHtml(projection.display_name)}</h2><code>${escapeHtml(identity.asset_id)}</code><p>${escapeHtml(projection.summary)}</p></header>
      <div class="registry-detail-badges"><span class="registry-badge ${record.indexed ? "indexed" : "discovered"}">${record.indexed ? "Indexed" : "Discovered only"}</span>${record.indexed ? `<span class="registry-badge lifecycle">${escapeHtml(registryStateLabels[record.state])}</span>` : ""}<span class="registry-badge">${escapeHtml(compatible)}</span></div>
      ${record.indexed ? '<p class="registry-helper">Local metadata projection. The canonical source remains authoritative.</p>' : '<p class="registry-helper">Found at its source. No persistent registry projection exists yet.</p>'}
      <details open><summary>Source and provenance</summary><dl class="registry-facts">
        <div><dt>Source</dt><dd>${escapeHtml(source.source_reference)}</dd></div>
        <div><dt>Source authority</dt><dd>${source.canonical ? "Reusable canonical source" : "Accepted or application-local candidate source"}</dd></div>
        <div><dt>Source SHA-256</dt><dd><code>${escapeHtml(source.source_digest)}</code></dd></div>
        <div><dt>Definition SHA-256</dt><dd><code>${escapeHtml(source.definition_digest)}</code></dd></div>
        <div><dt>Namespace</dt><dd>${escapeHtml(identity.namespace)}</dd></div>
        <div><dt>Source contract</dt><dd>${escapeHtml(projection.source_contract)}</dd></div>
        <div><dt>Repository commit</dt><dd><code>${escapeHtml(projection.provenance.repository_commit)}</code></dd></div>
        <div><dt>Adapter</dt><dd>${escapeHtml(source.adapter_id)}</dd></div>
        <div><dt>Adapter SHA-256</dt><dd><code>${escapeHtml(source.adapter_digest)}</code></dd></div>
        <div><dt>Observed</dt><dd>${escapeHtml(new Date(projection.provenance.discovered_at).toLocaleString())}</dd></div>
      </dl></details>
      <details open><summary>Compatibility and exact relationships</summary><dl class="registry-facts"><div><dt>Status</dt><dd>${escapeHtml(compatible)}</dd></div><div><dt>Evaluated source</dt><dd><code>${escapeHtml(registryValue(projection.compatibility.evaluated_source_digest))}</code></dd></div><div><dt>Evaluator revision</dt><dd><code>${escapeHtml(projection.compatibility.evaluator_revision)}</code></dd></div><div><dt>Exact lineage</dt><dd>${escapeHtml(registryValue(projection.lineage))}</dd></div></dl><div class="registry-receipts">${relationships || '<div class="empty-state">No cross-definition relationship is declared.</div>'}</div></details>
      <details ${record.indexed ? "open" : ""}><summary>Lifecycle receipts</summary><div class="registry-receipts">${receipts.length ? receipts.map((receipt) => `<article><b>${escapeHtml(registryStateLabels[receipt.to_state] || receipt.to_state)}</b><span>${escapeHtml(receipt.actor)} · ${escapeHtml(new Date(receipt.occurred_at).toLocaleString())}</span><p>${escapeHtml(receipt.rationale)}</p></article>`).join("") : '<div class="empty-state">Lifecycle begins only after explicit indexing.</div>'}</div></details>
      <div class="registry-actions">
        ${record.indexed ? "" : '<button class="button primary" id="registry-index-one" type="button">Index this definition</button>'}
        ${next ? `<label class="field wide"><span>Lifecycle rationale</span><input id="registry-transition-rationale" placeholder="Why is this transition justified?"></label><button class="button ${publishBlocked ? "ghost" : "primary"}" id="registry-transition" type="button" data-next-state="${next}" ${publishBlocked ? "disabled" : ""}>Move to ${escapeHtml(registryStateLabels[next])}</button>` : ""}
        ${publishBlocked ? '<p class="registry-blocked">Publication is blocked: this source lacks a reusable canonical contract or compatible runtime observation.</p>' : ""}
        ${versions.length ? `<label class="field wide"><span>Compare with version</span><select id="registry-compare-version">${versions.map((item) => `<option value="${escapeHtml(item.reference)}">${escapeHtml(registryIdentity(item).version)}</option>`).join("")}</select></label><button class="button ghost" id="registry-compare" type="button">Compare versions</button>` : '<small class="registry-no-version">No second indexed version is available for comparison.</small>'}
      </div>
      <div id="registry-comparison"></div>`;
  }

  async function loadRegistryCatalogue() {
    if (labState.registryLoading) return;
    labState.registryLoading = true;
    $("#registry-status").textContent = "Loading";
    try {
      const result = await agentApi("/api/registry/catalogue");
      labState.registryRecords = result.records || [];
      $("#registry-status").textContent = "Ready";
      $("#registry-index-all").disabled = !labState.registryRecords.some((record) => !record.indexed);
      renderRegistrySummary();
      renderRegistryList();
    } catch (error) {
      $("#registry-status").textContent = "Unavailable";
      $("#registry-list").innerHTML = `<div class="empty-state"><strong>Registry unavailable.</strong><br>${escapeHtml(error.message)}</div>`;
    } finally {
      labState.registryLoading = false;
    }
  }

  async function indexRegistry(record) {
    const identity = registryIdentity(record);
    if (!window.confirm(`Index ${record.projection.display_name} as a local candidate?\n\nThis stores metadata, digests, and one lifecycle receipt. It does not copy, run, deploy, or publish the definition.`)) return;
    $("#registry-status").textContent = "Indexing";
    await agentApi("/api/registry/index", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ identity, actor: "local.developer" }) });
    await loadRegistryCatalogue();
  }

  async function indexAllRegistryDefinitions() {
    const request = { actor: "local.developer" };
    $("#registry-status").textContent = "Preparing preview";
    const preview = await agentApi("/api/registry/bootstrap/preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request) });
    if ((preview.conflicts || []).length) {
      $("#registry-status").textContent = `Blocked · ${preview.conflicts.length} conflict${preview.conflicts.length === 1 ? "" : "s"}`;
      window.alert(`Nothing was indexed. Resolve these conflicts first:\n\n${preview.conflicts.join("\n")}`);
      return;
    }
    if (!preview.would_index) {
      $("#registry-status").textContent = "All definitions already indexed";
      return;
    }
    if (!window.confirm(`Index ${preview.would_index} discovered definition${preview.would_index === 1 ? "" : "s"}?\n\n${preview.consequence}\n\n${preview.already_indexed} existing projection${preview.already_indexed === 1 ? " is" : "s are"} unchanged.`)) return;
    $("#registry-status").textContent = "Indexing prevalidated batch";
    const result = await agentApi("/api/registry/bootstrap", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request) });
    if ((result.conflicts || []).length) throw new Error(`Bootstrap blocked: ${result.conflicts.join("; ")}`);
    await loadRegistryCatalogue();
  }

  async function transitionRegistry(record, nextState) {
    const rationale = ($("#registry-transition-rationale")?.value || "").trim();
    if (rationale.length < 3) {
      $("#registry-transition-rationale").focus();
      return;
    }
    const identity = registryIdentity(record);
    const replacement = nextState === "deprecated" ? window.prompt("Exact replacement reference (required for deprecation)", "") : null;
    if (nextState === "deprecated" && !replacement) return;
    if (!window.confirm(`Move ${record.projection.display_name} from ${registryStateLabels[record.state]} to ${registryStateLabels[nextState]}?\n\nThis appends one local, tamper-evident lifecycle receipt. It does not run, deploy, or externally publish the definition.`)) return;
    await agentApi("/api/registry/transition", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...identity, to_state: nextState, actor: "local.developer", rationale, replacement_reference: replacement, expected_revision: record.revision }) });
    await loadRegistryCatalogue();
  }

  async function compareRegistryVersions(record, other) {
    const result = await agentApi("/api/registry/compare", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ left: registryIdentity(record), right: registryIdentity(other) }) });
    $("#registry-comparison").innerHTML = `<section class="registry-comparison"><strong>${result.differences.length} changed projection field${result.differences.length === 1 ? "" : "s"}</strong>${result.differences.map((difference) => `<article><b>${escapeHtml(difference.field)}</b><div><span>Current</span><code>${escapeHtml(registryValue(difference.left))}</code></div><div><span>Compared</span><code>${escapeHtml(registryValue(difference.right))}</code></div></article>`).join("") || '<p>No projection differences.</p>'}</section>`;
  }

  function artifactBytes(value) {
    const size = Number(value || 0);
    if (size < 1024) return `${size.toLocaleString()} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  }

  function artifactLabel(value) {
    return String(value || "unavailable").replaceAll("_", " ");
  }

  function filteredArtifacts() {
    const search = ($("#artifact-search")?.value || "").trim().toLowerCase();
    const view = $("#artifact-view-filter")?.value || "active";
    const truth = $("#artifact-truth-filter")?.value || "";
    const retention = $("#artifact-retention-filter")?.value || "";
    return labState.artifactRecords.filter((record) => {
      const manifest = record.manifest;
      const matchesSearch = !search || [manifest.title, manifest.artifact_id, manifest.run_id, manifest.created_by].some((item) => String(item || "").toLowerCase().includes(search));
      const matchesView = view === "all"
        || (view === "recovery" && ["tombstoned", "deleted"].includes(record.state))
        || record.state === view;
      return matchesSearch && matchesView && (!truth || manifest.data_truth === truth) && (!retention || manifest.retention === retention);
    });
  }

  function renderArtifactSummary(summary = {}) {
    $("#artifact-summary").innerHTML = [
      [summary.retained_runs || 0, "retained runs"],
      [summary.artifacts || 0, "artifacts"],
      [summary.files || 0, "declared files"],
      [artifactBytes(summary.total_size_bytes || 0), `${summary.need_attention || 0} need attention`],
    ].map(([value, label]) => `<div><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`).join("");
  }

  function renderArtifactCandidates() {
    const candidates = labState.artifactCandidates;
    $("#artifact-admission").classList.toggle("hidden", !candidates.length);
    $("#artifact-candidate-count").textContent = `${candidates.length} candidate${candidates.length === 1 ? "" : "s"}`;
    $("#artifact-candidates").innerHTML = candidates.map((candidate) => `<article class="artifact-candidate">
      <div><strong>${escapeHtml(candidate.run_id)}</strong><span class="registry-badge ${candidate.eligible ? "indexed" : ""}">${candidate.eligible ? "Compatible" : "Blocked"}</span><p>${candidate.eligible ? `${artifactLabel(candidate.data_truth)} · ${candidate.file_count} files · ${artifactBytes(candidate.total_size_bytes)}` : artifactLabel(candidate.blockers?.[0])}</p>${(candidate.warnings || []).map((warning) => `<small>${escapeHtml(warning)}</small>`).join("")}</div>
      <button class="button ${candidate.eligible ? "primary" : "ghost"}" type="button" data-admit-run="${escapeHtml(candidate.run_id)}" ${candidate.eligible ? "" : "disabled"}>Review and retain</button>
    </article>`).join("");
  }

  function renderArtifactList() {
    const records = filteredArtifacts();
    $("#artifact-result-count").textContent = `${records.length} result${records.length === 1 ? "" : "s"}`;
    if (!records.length) {
      $("#artifact-list").innerHTML = '<div class="empty-state">No retained outputs match this view. Temporary runs are never imported automatically.</div>';
      $("#artifact-detail").innerHTML = '<div class="empty-state">Select or admit a retained output to inspect it.</div>';
      return;
    }
    if (!records.some((item) => item.manifest.artifact_id === labState.selectedArtifactId)) labState.selectedArtifactId = records[0].manifest.artifact_id;
    $("#artifact-list").innerHTML = records.map((record) => {
      const manifest = record.manifest;
      return `<button class="registry-result ${manifest.artifact_id === labState.selectedArtifactId ? "selected" : ""}" type="button" data-artifact-id="${escapeHtml(manifest.artifact_id)}">
        <span class="registry-result-top"><b>${escapeHtml(manifest.kind)}</b><span class="registry-badge lifecycle">${escapeHtml(artifactLabel(record.state))}</span></span>
        <strong>${escapeHtml(manifest.title)}</strong><code>${escapeHtml(manifest.run_id || manifest.artifact_id)}</code>
        <small>${escapeHtml(artifactLabel(manifest.data_truth))} · ${manifest.files.length} files · ${artifactBytes(manifest.total_size_bytes)}</small>
      </button>`;
    }).join("");
    selectArtifact(labState.selectedArtifactId, false);
  }

  async function selectArtifact(artifactId, reload = true) {
    labState.selectedArtifactId = artifactId;
    if (reload || !labState.selectedArtifactDetail || labState.selectedArtifactDetail.manifest.artifact_id !== artifactId) {
      $("#artifact-detail").innerHTML = '<div class="empty-state">Verifying the selected manifest and declared bytes.</div>';
      try {
        labState.selectedArtifactDetail = await agentApi(`/api/artifacts/${encodeURIComponent(artifactId)}`);
      } catch (error) {
        $("#artifact-detail").innerHTML = `<div class="empty-state"><strong>Artifact unavailable.</strong><br>${escapeHtml(error.message)}</div>`;
        return;
      }
    }
    $$("[data-artifact-id]").forEach((button) => button.classList.toggle("selected", button.dataset.artifactId === artifactId));
    renderArtifactDetail(labState.selectedArtifactDetail);
  }

  function renderArtifactDetail(record) {
    const manifest = record.manifest;
    const verification = record.verification || {};
    const preview = record.deletion_preview;
    const receipts = record.receipts || [];
    const files = manifest.files.map((file) => `<article class="artifact-file-row">
      <div><strong>${escapeHtml(file.path)}</strong><span>${escapeHtml(file.role)} · ${artifactBytes(file.size_bytes)}</span><code>${escapeHtml(file.file_id)}</code></div>
      <div>${file.preview_mode !== "none" ? `<button class="text-button" data-preview-file="${escapeHtml(file.file_id)}" type="button">Preview</button>` : '<span class="registry-badge">Preview blocked</span>'}${file.download_allowed ? `<button class="text-button" data-download-file="${escapeHtml(file.file_id)}" type="button">Download</button>` : ""}</div>
    </article>`).join("");
    const lifecycleAction = record.state === "active"
      ? '<button class="button ghost" id="artifact-archive" type="button">Archive</button>'
      : ["archived", "tombstoned"].includes(record.state)
        ? '<button class="button ghost" id="artifact-restore" type="button">Restore</button>'
        : "";
    const deletionAction = preview?.eligible
      ? `<button class="button danger" id="artifact-delete-action" type="button">${preview.operation === "finalize_delete" ? "Finalize deletion" : "Move to recovery"}</button>`
      : "";
    $("#artifact-detail").innerHTML = `<header class="registry-detail-header"><span class="panel-label">${escapeHtml(manifest.kind)} · ${escapeHtml(artifactLabel(record.state))}</span><h2>${escapeHtml(manifest.title)}</h2><code>${escapeHtml(manifest.artifact_id)}</code><p>${escapeHtml(manifest.run_id ? `Retained output of ${manifest.run_id}` : "Immutable generated artifact")}</p></header>
      <div class="registry-detail-badges"><span class="registry-badge ${verification.valid ? "indexed" : ""}">${verification.valid ? "Integrity verified" : "Integrity attention"}</span><span class="registry-badge">${escapeHtml(artifactLabel(manifest.data_truth))}</span><span class="registry-badge">${escapeHtml(artifactLabel(manifest.rights))}</span><span class="registry-badge">${escapeHtml(artifactLabel(manifest.retention))}</span></div>
      <details open><summary>Declared files</summary><div class="artifact-files">${files}</div><pre class="artifact-preview hidden" id="artifact-file-preview"></pre></details>
      <details><summary>Provenance and policy</summary><dl class="registry-facts"><div><dt>Created</dt><dd>${escapeHtml(new Date(manifest.created_at).toLocaleString())}</dd></div><div><dt>Producer</dt><dd>${escapeHtml(manifest.created_by)}</dd></div><div><dt>Creation method</dt><dd>${escapeHtml(manifest.creation_method)}</dd></div><div><dt>Rights policy</dt><dd>${escapeHtml(manifest.rights_policy_id)}</dd></div><div><dt>Publication</dt><dd>${escapeHtml(artifactLabel(manifest.publication))}</dd></div><div><dt>Manifest digest</dt><dd><code>${escapeHtml(manifest.artifact_digest)}</code></dd></div></dl></details>
      <details><summary>Lifecycle receipts</summary><div class="registry-receipts">${receipts.map((receipt) => `<article><b>${escapeHtml(artifactLabel(receipt.operation))}</b><span>${escapeHtml(receipt.actor)} · ${escapeHtml(new Date(receipt.occurred_at).toLocaleString())}</span><p>${escapeHtml(receipt.rationale)}</p></article>`).join("")}</div></details>
      <div class="registry-actions"><button class="button" id="artifact-verify" type="button">Verify files</button>${lifecycleAction}${deletionAction}${preview && !preview.eligible ? `<p class="registry-blocked">Deletion unavailable: ${escapeHtml(preview.blockers.join(" · "))}</p>` : ""}</div>`;
  }

  async function loadArtifactCatalogue() {
    if (labState.artifactLoading) return;
    labState.artifactLoading = true;
    $("#artifact-status").textContent = "Loading";
    try {
      const result = await agentApi("/api/artifacts/catalogue?include_deleted=true");
      labState.artifactRecords = result.records || [];
      labState.artifactCandidates = result.candidates || [];
      renderArtifactSummary(result.summary);
      renderArtifactCandidates();
      renderArtifactList();
      $("#artifact-status").textContent = "Ready";
    } catch (error) {
      $("#artifact-status").textContent = "Unavailable";
      $("#artifact-list").innerHTML = `<div class="empty-state"><strong>Repository unavailable.</strong><br>${escapeHtml(error.message)}</div>`;
    } finally {
      labState.artifactLoading = false;
    }
  }

  async function admitTemporaryRun(runId) {
    const preview = await agentApi(`/api/artifacts/admission/${encodeURIComponent(runId)}/preview`);
    if (!preview.eligible) throw new Error(preview.blockers.join(" · "));
    if (!window.confirm(`Retain ${runId}?\n\nThis copies exactly ${preview.file_count} validated files into immutable content-addressed storage. The temporary source folder remains unchanged.`)) return;
    await agentApi("/api/artifacts/admission", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ run_id: runId, confirmation_token: preview.confirmation_token, actor: "local.developer" }) });
    await loadArtifactCatalogue();
  }

  async function artifactTransition(action) {
    const record = labState.selectedArtifactDetail;
    if (!record) return;
    const rationale = window.prompt(`Why should this artifact be ${action === "archive" ? "archived" : "restored"}?`, "Reviewed local lifecycle change.");
    if (!rationale) return;
    await agentApi(`/api/artifacts/${encodeURIComponent(record.manifest.artifact_id)}/${action}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ actor: "local.developer", rationale, expected_revision: record.revision }) });
    labState.selectedArtifactDetail = null;
    await loadArtifactCatalogue();
  }

  async function artifactDeletion() {
    const record = labState.selectedArtifactDetail;
    const preview = record?.deletion_preview;
    if (!record || !preview?.eligible) return;
    if (!window.confirm(`${preview.consequence}\n\nContinue with this exact reviewed revision?`)) return;
    const rationale = window.prompt("Record the reason for this governed deletion step.", "Disposable local research output no longer required.");
    if (!rationale) return;
    const action = preview.operation === "finalize_delete" ? "finalize" : "tombstone";
    await agentApi(`/api/artifacts/${encodeURIComponent(record.manifest.artifact_id)}/${action}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ actor: "local.developer", rationale, expected_revision: preview.expected_revision, confirmation_token: preview.confirmation_token }) });
    labState.selectedArtifactDetail = null;
    await loadArtifactCatalogue();
  }

  const experimentLabels = {
    interactive_foreground: "Interactive foreground",
    background_headless: "Background / headless",
    evaluation_only: "Evaluation only",
    paused_for_decision: "Paused for decision",
    licensed_real: "Licensed real",
    public_real: "Public real",
    reviewed_synthetic: "Reviewed synthetic",
    simulated_intraday: "Simulated intraday",
  };

  function experimentLabel(value) {
    return experimentLabels[value] || String(value || "").replaceAll("_", " ");
  }

  function renderExperimentOptions() {
    const options = labState.experimentOptions || { system_assets: [], portfolios: [], defaults: {} };
    const mode = $("#experiment-mode").value;
    const kind = mode === "evaluation_only" ? "evaluation" : "workflow";
    const assets = options.system_assets.filter((item) => item.identity.kind === kind);
    $("#experiment-system-asset").innerHTML = assets.length
      ? assets.map((item) => `<option value="${escapeHtml(item.reference)}">${escapeHtml(item.display_name)} · ${escapeHtml(item.identity.version)}</option>`).join("")
      : `<option value="">No discovered ${escapeHtml(kind)} definition</option>`;
    const truth = $("#experiment-truth").value;
    const portfolios = (options.portfolios || []).filter((item) => item.data_truth === truth);
    $("#experiment-portfolio").innerHTML = portfolios.length
      ? portfolios.map((item) => `<option value="${escapeHtml(item.reference)}" data-revision="${escapeHtml(item.data_revision_reference)}">${escapeHtml(item.title || item.portfolio_id)}</option>`).join("")
      : '<option value="">No reviewed source is available for this truth class</option>';
    $("#experiment-data-revision").value = portfolios[0]?.data_revision_reference || "Unavailable until a reviewed source is configured";
    const defaults = options.defaults || {};
    if (defaults.snapshot_policy_reference) $("#experiment-snapshot-policy").value = defaults.snapshot_policy_reference;
    if (defaults.mandate_reference) $("#experiment-mandate").value = defaults.mandate_reference;
    $("#experiment-create-form button[type=submit]").disabled = !assets.length || !portfolios.length;
  }

  function renderExperimentWorkspace(result) {
    const summary = result.summary || {};
    $("#experiment-summary").innerHTML = [
      [summary.experiments || 0, "experiments"],
      [summary.ready_or_active || 0, "ready or active"],
      [summary.queued_jobs || 0, "active queue entries"],
      [summary.experiment_sets || 0, "comparison sets"],
    ].map(([value, label]) => `<div><strong>${value}</strong><span>${escapeHtml(label)}</span></div>`).join("");
    $("#experiment-result-count").textContent = `${labState.experimentRecords.length} records`;
    if (!labState.experimentRecords.some((item) => item.definition.experiment_id === labState.selectedExperimentId)) {
      labState.selectedExperimentId = labState.experimentRecords[0]?.definition.experiment_id || null;
    }
    $("#experiment-list").innerHTML = labState.experimentRecords.length ? labState.experimentRecords.map((record) => {
      const value = record.definition;
      const selected = value.experiment_id === labState.selectedExperimentId;
      return `<button class="registry-result ${selected ? "selected" : ""}" type="button" data-experiment-id="${escapeHtml(value.experiment_id)}" aria-pressed="${selected}">
        <span class="registry-result-top"><b>${escapeHtml(experimentLabel(value.presentation_mode))}</b><span class="registry-badge lifecycle">${escapeHtml(experimentLabel(record.state))}</span></span>
        <strong>${escapeHtml(value.name)}</strong><code>${escapeHtml(value.experiment_id)} · ${escapeHtml(value.version)}</code>
        <small>${escapeHtml(value.hypothesis)}</small></button>`;
    }).join("") : '<div class="empty-state">Create a draft to establish an isolated, persistent experiment boundary.</div>';
    renderExperimentDetail();
    $("#experiment-queue").innerHTML = labState.experimentQueue.length ? labState.experimentQueue.map((entry) => {
      const actions = entry.status === "queued" ? ["start", "cancel"] : entry.status === "running" ? ["pause", "complete", "fail", "cancel"] : entry.status === "paused" ? ["resume", "cancel"] : [];
      return `<article class="experiment-queue-entry"><div><b>${escapeHtml(experimentLabel(entry.status))}</b><strong>${escapeHtml(entry.experiment_id)}</strong><span>${escapeHtml(experimentLabel(entry.job_kind))}</span><small>${escapeHtml(entry.message)}</small></div><div>${actions.map((action) => `<button class="text-button" type="button" data-queue-id="${escapeHtml(entry.queue_id)}" data-queue-action="${action}">${escapeHtml(experimentLabel(action))}</button>`).join("")}</div></article>`;
    }).join("") : '<div class="empty-state">No queued work. Queue admission never starts a worker automatically.</div>';
    $("#experiment-sets").innerHTML = labState.experimentSets.length ? labState.experimentSets.map((item) => `<article class="experiment-set-card"><b>${escapeHtml(item.definition.name)}</b><span>${item.members.length} experiments · ${item.planned_runs} planned runs</span><small>${item.comparison_ready ? "All results are ready to compare" : "Waiting for completed and reviewed members"}</small></article>`).join("") : '<div class="empty-state">Group experiments only when they answer a shared research question.</div>';
    $("#experiment-create-set").disabled = !labState.experimentRecords.length;
  }

  function renderExperimentDetail() {
    const record = labState.experimentRecords.find((item) => item.definition.experiment_id === labState.selectedExperimentId);
    if (!record) {
      $("#experiment-detail").innerHTML = '<div class="empty-state">Select an experiment to inspect its exact definition.</div>';
      return;
    }
    const value = record.definition;
    const next = record.state === "draft" ? "validated" : record.state === "validated" ? "ready" : record.state === "completed" || record.state === "failed" || record.state === "cancelled" ? "reviewed" : record.state === "reviewed" ? "archived" : null;
    const canEnqueue = record.state === "ready";
    const sourceRows = value.source_bindings.map((item) => `<div><dt>${escapeHtml(experimentLabel(item.role))}</dt><dd><code>${escapeHtml(item.reference)}</code><small>${escapeHtml(item.revision)} · ${escapeHtml(item.digest)}</small></dd></div>`).join("");
    const assets = value.system_assets.map((item) => `<article><b>${escapeHtml(experimentLabel(item.kind))}</b><code>${escapeHtml(item.kind)}:${escapeHtml(item.namespace)}:${escapeHtml(item.asset_id)}@${escapeHtml(item.version)}</code></article>`).join("");
    $("#experiment-detail").innerHTML = `<header class="registry-detail-header"><span class="panel-label">${escapeHtml(experimentLabel(value.presentation_mode))} · ${escapeHtml(experimentLabel(record.state))}</span><h2>${escapeHtml(value.name)}</h2><code>${escapeHtml(value.experiment_id)}</code><p>${escapeHtml(value.purpose)}</p></header>
      <div class="registry-detail-badges"><span class="registry-badge indexed">${escapeHtml(experimentLabel(value.data_truth))}</span><span class="registry-badge">Effects ${escapeHtml(value.external_effects)}</span><span class="registry-badge">${value.budget.max_model_calls} model calls max</span><span class="registry-badge">$${Number(value.budget.max_cost_usd).toFixed(2)} max</span></div>
      <details open><summary>Question and temporal boundary</summary><p class="registry-helper"><strong>Hypothesis:</strong> ${escapeHtml(value.hypothesis)}</p><dl class="registry-facts"><div><dt>Period</dt><dd>${escapeHtml(value.temporal.start_date)} → ${escapeHtml(value.temporal.end_date)}</dd></div><div><dt>Eligibility</dt><dd>${escapeHtml(experimentLabel(value.temporal.as_of_policy))}</dd></div><div><dt>Replay</dt><dd>${escapeHtml(experimentLabel(value.temporal.replay_schedule))}</dd></div><div><dt>Definition digest</dt><dd><code>${escapeHtml(value.definition_digest)}</code></dd></div></dl></details>
      <details open><summary>Immutable source bindings</summary><dl class="registry-facts">${sourceRows}</dl></details>
      <details open><summary>Versioned system assets</summary><div class="registry-receipts">${assets}</div></details>
      <details><summary>Lifecycle receipts</summary><div class="registry-receipts">${record.receipts.map((receipt) => `<article><b>${escapeHtml(experimentLabel(receipt.to_state))}</b><span>${escapeHtml(receipt.actor)} · ${escapeHtml(new Date(receipt.occurred_at).toLocaleString())}</span><p>${escapeHtml(receipt.rationale)}</p></article>`).join("")}</div></details>
      <div class="registry-actions">${next ? `<button class="button primary" type="button" data-experiment-transition="${next}">Move to ${escapeHtml(experimentLabel(next))}</button>` : ""}${canEnqueue ? '<button class="button primary" type="button" data-experiment-enqueue>Admit to queue</button>' : ""}<p class="registry-helper">Queue admission is explicit and restart-safe. It does not imply that an agent, worker, or model call has started.</p></div>`;
  }

  async function loadExperimentWorkspace() {
    if (labState.experimentLoading) return;
    labState.experimentLoading = true;
    $("#experiment-status").textContent = "Loading";
    try {
      const [catalogue, options] = await Promise.all([
        agentApi("/api/experiments/catalogue"),
        labState.experimentOptions ? Promise.resolve(labState.experimentOptions) : agentApi("/api/experiments/options"),
      ]);
      labState.experimentOptions = options;
      labState.experimentRecords = catalogue.records || [];
      labState.experimentQueue = catalogue.queue || [];
      labState.experimentSets = catalogue.sets || [];
      renderExperimentOptions();
      renderExperimentWorkspace(catalogue);
      $("#experiment-status").textContent = "Ready";
    } catch (error) {
      $("#experiment-status").textContent = "Unavailable";
      $("#experiment-list").innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
    } finally {
      labState.experimentLoading = false;
    }
  }

  async function createExperimentDraft(event) {
    event.preventDefault();
    const reference = $("#experiment-system-asset").value;
    const asset = (labState.experimentOptions?.system_assets || []).find((item) => item.reference === reference);
    if (!asset) throw new Error("Select a discovered workflow or evaluation definition.");
    const slug = $("#experiment-name").value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 70) || "experiment";
    const id = `${slug}-${Date.now().toString(36)}`;
    await agentApi("/api/experiments/draft", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
      experiment_id: id,
      name: $("#experiment-name").value,
      purpose: $("#experiment-purpose").value,
      hypothesis: $("#experiment-hypothesis").value,
      start_date: $("#experiment-start").value,
      end_date: $("#experiment-end").value,
      presentation_mode: $("#experiment-mode").value,
      data_truth: $("#experiment-truth").value,
      portfolio_reference: $("#experiment-portfolio").value,
      snapshot_policy_reference: $("#experiment-snapshot-policy").value,
      mandate_reference: $("#experiment-mandate").value,
      data_revision_reference: $("#experiment-data-revision").value,
      system_asset: asset.identity,
      max_model_calls: Number($("#experiment-model-budget").value),
      max_cost_usd: $("#experiment-cost-budget").value,
      actor: "local.researcher",
    }) });
    labState.selectedExperimentId = id;
    await loadExperimentWorkspace();
  }

  async function transitionExperiment(toState) {
    const record = labState.experimentRecords.find((item) => item.definition.experiment_id === labState.selectedExperimentId);
    if (!record) return;
    await agentApi(`/api/experiments/${encodeURIComponent(record.definition.experiment_id)}/transition`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
      to_state: toState,
      actor: "local.researcher",
      rationale: toState === "validated" ? "Reviewed required bindings and canonical system asset resolution." : `Reviewed transition to ${toState}.`,
      idempotency_key: `${toState}-${record.definition.experiment_id}`,
      expected_revision: record.revision,
    }) });
    await loadExperimentWorkspace();
  }

  async function enqueueExperiment() {
    const record = labState.experimentRecords.find((item) => item.definition.experiment_id === labState.selectedExperimentId);
    if (!record) return;
    await agentApi(`/api/experiments/${encodeURIComponent(record.definition.experiment_id)}/enqueue`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ actor: "local.researcher", idempotency_key: `enqueue-${record.definition.experiment_id}`, expected_revision: record.revision }) });
    await loadExperimentWorkspace();
  }

  async function controlExperimentQueue(queueId, action) {
    const entry = labState.experimentQueue.find((item) => item.queue_id === queueId);
    if (!entry) return;
    await agentApi(`/api/experiment-queue/${encodeURIComponent(queueId)}/control`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, resume_token: entry.resume_token }) });
    await loadExperimentWorkspace();
  }

  async function createExperimentSet() {
    if (!labState.experimentRecords.length) return;
    const now = new Date().toISOString();
    const id = `experiment-set-${Date.now().toString(36)}`;
    await agentApi("/api/experiment-sets", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ definition: {
      experiment_set_id: id,
      name: "Workspace comparison",
      research_question: "How do the current governed experiment configurations compare on their reviewed outputs?",
      owner: "local.researcher",
      experiment_ids: labState.experimentRecords.map((item) => item.definition.experiment_id).sort(),
      controlled_factors: [], variable_factors: [], seeds: [1], repeat_count: 1,
      max_concurrency: 2, max_total_cost_usd: "25.00", aggregation_rule: "per_experiment_then_set_summary",
      created_at: now,
    } }) });
    await loadExperimentWorkspace();
  }

  function bind() {
    $$(".workspace-tab").forEach((button) => button.addEventListener("click", () => switchWorkspace(button.dataset.workspace)));
    window.addEventListener("popstate", () => {
      const workspace = new URLSearchParams(window.location.search).get("workspace") || "dataset";
      if (["dataset", "portfolio", "agent", "graph", "registry", "artifacts", "experiments", "cycle", "full"].includes(workspace)) switchWorkspace(workspace, false);
    });
    $("#registry-refresh").addEventListener("click", loadRegistryCatalogue);
    $("#registry-index-all").addEventListener("click", () => indexAllRegistryDefinitions().catch((error) => { $("#registry-status").textContent = error.message; }));
    ["#registry-search", "#registry-kind-filter", "#registry-index-filter", "#registry-lifecycle-filter"].forEach((selector) => {
      $(selector).addEventListener(selector === "#registry-search" ? "input" : "change", () => {
        const discoveredOnly = $("#registry-index-filter").value === "discovered";
        $("#registry-lifecycle-filter").disabled = discoveredOnly;
        if (discoveredOnly) $("#registry-lifecycle-filter").value = "";
        renderRegistryList();
      });
    });
    $("#registry-clear-filters").addEventListener("click", () => {
      $("#registry-search").value = "";
      $("#registry-kind-filter").value = "";
      $("#registry-index-filter").value = "";
      $("#registry-lifecycle-filter").value = "";
      $("#registry-lifecycle-filter").disabled = false;
      renderRegistryList();
      $("#registry-search").focus();
    });
    $("#registry-list").addEventListener("click", (event) => {
      const button = event.target.closest("[data-registry-reference]");
      if (!button) return;
      labState.selectedRegistryReference = button.dataset.registryReference;
      renderRegistryList();
    });
    $("#registry-detail").addEventListener("click", (event) => {
      const record = labState.registryRecords.find((item) => item.reference === labState.selectedRegistryReference);
      if (!record) return;
      if (event.target.closest("#registry-index-one")) indexRegistry(record).catch((error) => { $("#registry-status").textContent = error.message; });
      const transition = event.target.closest("#registry-transition");
      if (transition) transitionRegistry(record, transition.dataset.nextState).catch((error) => { $("#registry-status").textContent = error.message; });
      if (event.target.closest("#registry-compare")) {
        const other = labState.registryRecords.find((item) => item.reference === $("#registry-compare-version").value);
        if (other) compareRegistryVersions(record, other).catch((error) => { $("#registry-status").textContent = error.message; });
      }
    });
    $("#artifact-refresh").addEventListener("click", loadArtifactCatalogue);
    ["#artifact-search", "#artifact-view-filter", "#artifact-truth-filter", "#artifact-retention-filter"].forEach((selector) => {
      $(selector).addEventListener(selector === "#artifact-search" ? "input" : "change", renderArtifactList);
    });
    $("#artifact-clear-filters").addEventListener("click", () => {
      $("#artifact-search").value = "";
      $("#artifact-view-filter").value = "active";
      $("#artifact-truth-filter").value = "";
      $("#artifact-retention-filter").value = "";
      renderArtifactList();
      $("#artifact-search").focus();
    });
    $("#artifact-candidates").addEventListener("click", (event) => {
      const button = event.target.closest("[data-admit-run]");
      if (button) admitTemporaryRun(button.dataset.admitRun).catch((error) => { $("#artifact-status").textContent = error.message; });
    });
    $("#artifact-list").addEventListener("click", (event) => {
      const button = event.target.closest("[data-artifact-id]");
      if (button) selectArtifact(button.dataset.artifactId);
    });
    $("#artifact-detail").addEventListener("click", (event) => {
      const record = labState.selectedArtifactDetail;
      if (!record) return;
      if (event.target.closest("#artifact-verify")) selectArtifact(record.manifest.artifact_id).catch((error) => { $("#artifact-status").textContent = error.message; });
      if (event.target.closest("#artifact-archive")) artifactTransition("archive").catch((error) => { $("#artifact-status").textContent = error.message; });
      if (event.target.closest("#artifact-restore")) artifactTransition("restore").catch((error) => { $("#artifact-status").textContent = error.message; });
      if (event.target.closest("#artifact-delete-action")) artifactDeletion().catch((error) => { $("#artifact-status").textContent = error.message; });
      const previewButton = event.target.closest("[data-preview-file]");
      if (previewButton) agentApi(`/api/artifacts/${encodeURIComponent(record.manifest.artifact_id)}/files/${encodeURIComponent(previewButton.dataset.previewFile)}/preview`).then((result) => {
        $("#artifact-file-preview").textContent = result.text;
        $("#artifact-file-preview").classList.remove("hidden");
      }).catch((error) => { $("#artifact-status").textContent = error.message; });
      const downloadButton = event.target.closest("[data-download-file]");
      if (downloadButton) window.location.assign(`/api/artifacts/${encodeURIComponent(record.manifest.artifact_id)}/files/${encodeURIComponent(downloadButton.dataset.downloadFile)}/download`);
    });
    $("#experiment-refresh").addEventListener("click", loadExperimentWorkspace);
    $("#experiment-mode").addEventListener("change", renderExperimentOptions);
    $("#experiment-truth").addEventListener("change", renderExperimentOptions);
    $("#experiment-portfolio").addEventListener("change", () => {
      $("#experiment-data-revision").value = $("#experiment-portfolio").selectedOptions[0]?.dataset.revision || "";
    });
    $("#experiment-create-form").addEventListener("submit", (event) => createExperimentDraft(event).catch((error) => { $("#experiment-status").textContent = error.message; }));
    $("#experiment-list").addEventListener("click", (event) => {
      const button = event.target.closest("[data-experiment-id]");
      if (!button) return;
      labState.selectedExperimentId = button.dataset.experimentId;
      renderExperimentWorkspace({ summary: {
        experiments: labState.experimentRecords.length,
        ready_or_active: labState.experimentRecords.filter((item) => ["ready", "queued", "running", "paused_for_decision"].includes(item.state)).length,
        queued_jobs: labState.experimentQueue.filter((item) => ["queued", "running", "paused"].includes(item.status)).length,
        experiment_sets: labState.experimentSets.length,
      } });
    });
    $("#experiment-detail").addEventListener("click", (event) => {
      const transition = event.target.closest("[data-experiment-transition]");
      if (transition) transitionExperiment(transition.dataset.experimentTransition).catch((error) => { $("#experiment-status").textContent = error.message; });
      if (event.target.closest("[data-experiment-enqueue]")) enqueueExperiment().catch((error) => { $("#experiment-status").textContent = error.message; });
    });
    $("#experiment-queue").addEventListener("click", (event) => {
      const action = event.target.closest("[data-queue-action]");
      if (action) controlExperimentQueue(action.dataset.queueId, action.dataset.queueAction).catch((error) => { $("#experiment-status").textContent = error.message; });
    });
    $("#experiment-create-set").addEventListener("click", () => createExperimentSet().catch((error) => { $("#experiment-status").textContent = error.message; }));
    $("#create-cycle-session").addEventListener("click", createCycleSession);
    $("#cycle-start").addEventListener("click", () => controlCycle("start").catch((error) => { $("#cycle-runtime-status").textContent = error.message; }));
    $("#cycle-pause").addEventListener("click", () => controlCycle("pause").catch((error) => { $("#cycle-runtime-status").textContent = error.message; }));
    $("#cycle-speed").addEventListener("change", () => controlCycle("set_speed", Number($("#cycle-speed").value)).catch((error) => { $("#cycle-runtime-status").textContent = error.message; }));
    $("#cycle-new-session").addEventListener("click", async () => {
      if (labState.cycleSessionId) await agentApi(`/api/workflow-cycle/sessions/${encodeURIComponent(labState.cycleSessionId)}`, { method: "DELETE" }).catch(() => {});
      labState.cycleSessionId = null;
      labState.cycleSnapshot = null;
      if (labState.cyclePollTimer) window.clearInterval(labState.cyclePollTimer);
      labState.cyclePollTimer = null;
      $("#cycle-console").classList.add("hidden");
      $("#cycle-setup-panel").classList.remove("compact");
      $("#cycle-runtime-status").textContent = "Not configured";
    });
    $("#cycle-dashboard-pages").addEventListener("click", (event) => {
      const button = event.target.closest("[data-cycle-page]");
      if (!button || !labState.cycleSnapshot) return;
      labState.cycleDashboardPage = button.dataset.cyclePage;
      renderCycleDashboard(labState.cycleSnapshot);
    });
    $("#cycle-decision-panel").addEventListener("click", (event) => {
      const button = event.target.closest("[data-cycle-decision]");
      if (button) resolveCycleDecision(button.dataset.cycleDecision).catch((error) => { $("#cycle-runtime-status").textContent = error.message; });
    });
    $("#cycle-attach-agent").addEventListener("click", () => attachCycleAgent().catch((error) => { $("#cycle-runtime-status").textContent = error.message; }));
    $("#open-cycle-from-agent").addEventListener("click", () => {
      const selectedPortfolio = $("#agent-real-portfolio").value;
      switchWorkspace("cycle");
      if (selectedPortfolio && [...$("#cycle-portfolio").options].some((item) => item.value === selectedPortfolio)) $("#cycle-portfolio").value = selectedPortfolio;
    });
    $("#apply-concise-report").addEventListener("click", applyConciseReportStructure);
    $$("[data-agent-builder-mode]").forEach((button) => button.addEventListener("click", () => setAgentBuilderMode(button.dataset.agentBuilderMode)));
    $$("[data-basic-agent-step]").forEach((button) => button.addEventListener("click", () => setBasicAgentStep(button.dataset.basicAgentStep)));
    $("#basic-agent-recipes").addEventListener("click", (event) => {
      const button = event.target.closest("[data-basic-agent-recipe]");
      if (button) selectBasicRecipe(button.dataset.basicAgentRecipe);
    });
    $("#basic-agent-name").addEventListener("input", applyBasicIdentity);
    $("#basic-agent-outcome").addEventListener("input", applyBasicIdentity);
    [
      ["#basic-agent-trigger", "trigger"],
      ["#basic-agent-scope", "scope"],
      ["#basic-agent-as-of", "as_of"],
      ["#basic-agent-dedup", "deduplication"],
    ].forEach(([selector, key]) => $(selector).addEventListener("change", () => {
      labState.agentBuilderMeta[key] = $(selector).value;
      labState.agentBuilderMeta.provenance = "user_customized";
      renderBasicBuilder();
    }));
    $("#basic-agent-context-pack").addEventListener("change", () => {
      labState.agentBuilderMeta.context_pack = $("#basic-agent-context-pack").value;
      labState.agentBuilderMeta.provenance = "user_customized";
      applyBasicContext();
    });
    $("#basic-agent-capability-pack").addEventListener("change", () => {
      labState.agentBuilderMeta.capability_pack = $("#basic-agent-capability-pack").value;
      labState.agentBuilderMeta.provenance = "user_customized";
      applyBasicCapabilityAndAuthority();
    });
    $("#basic-agent-output").addEventListener("change", () => {
      applyBasicOutputContract();
    });
    $("#basic-agent-authority").addEventListener("change", () => {
      labState.agentBuilderMeta.authority_profile = $("#basic-agent-authority").value;
      labState.agentBuilderMeta.provenance = "user_customized";
      applyBasicCapabilityAndAuthority();
    });
    $("#basic-generate-agent").addEventListener("click", generateBasicAgent);
    $$('[data-generate-basic-step]').forEach((button) => button.addEventListener("click", () => generateBasicStep(button.dataset.generateBasicStep, button)));
    $("#basic-inspect-manifest").addEventListener("click", () => setAgentBuilderMode("advanced"));
    $$(".basic-open-advanced").forEach((button) => button.addEventListener("click", () => openAdvancedAgentSection(button.dataset.openAgentSection)));
    $("#basic-validate-agent").addEventListener("click", async () => {
      try {
        await validateAgentBlueprint();
        $("#basic-test-result").className = "basic-test-result passed";
        $("#basic-test-result").innerHTML = "<span>Valid</span><p>The simplified choices compile into the existing strict blueprint contract.</p>";
      } catch {}
    });
    $("#basic-test-agent").addEventListener("click", runBasicTestSuite);
    $("#basic-save-agent").addEventListener("click", saveAgent);
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
    $$("[data-agent-output-tab]").forEach((button) => button.addEventListener("click", () => {
      switchAgentOutputTab(button.dataset.agentOutputTab);
      if (button.dataset.agentOutputTab === "run") loadAgentRuns();
    }));
    $$("[data-agent-data-mode]").forEach((button) => button.addEventListener("click", () => setAgentRunDataMode(button.dataset.agentDataMode)));
    $$("[data-agent-execution-mode]").forEach((button) => button.addEventListener("click", () => setAgentRunExecutionMode(button.dataset.agentExecutionMode)));
    ["#agent-test-scenario", "#agent-real-portfolio", "#agent-real-as-of"].forEach((selector) => $(selector).addEventListener("change", () => {
      labState.agentInputPreview = null;
      $("#agent-input-preview-status").textContent = "Preview changed · reload required";
    }));
    $("#preview-agent-input").addEventListener("click", () => previewAgentInput().catch(() => {}));
    $("#refresh-agent-runs").addEventListener("click", loadAgentRuns);
    $("#agent-run-repository").addEventListener("click", (event) => {
      const button = event.target.closest("[data-agent-run-id]");
      if (button) openAgentRun(button.dataset.agentRunId).catch((error) => {
        $("#agent-live-state").textContent = "Load failed";
        $("#agent-run-chat").innerHTML = `<article class="run-message critique"><p>${escapeHtml(error.message)}</p></article>`;
      });
    });
    $("#agent-run-files").addEventListener("click", (event) => {
      const button = event.target.closest("[data-agent-run-file]");
      if (!button || !labState.selectedAgentRunDetail) return;
      const name = button.dataset.agentRunFile;
      const content = labState.selectedAgentRunDetail.contents?.[name];
      $("#agent-run-file-content").textContent = typeof content === "string" ? content : JSON.stringify(content ?? "File preview unavailable.", null, 2);
      $$(".run-file-item").forEach((item) => item.classList.toggle("active", item === button));
    });
    $("#delete-agent-run").addEventListener("click", () => deleteSelectedAgentRun().catch((error) => {
      $("#agent-live-state").textContent = "Delete failed";
      $("#agent-run-file-content").textContent = error.message;
    }));
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
    selectBasicRecipe(labState.agentBuilderMeta.recipe_id);
    renderSavedAgents();
    renderBasicBuilder();
    setAgentBuilderMode("basic");
    setAgentRunDataMode("synthetic_behavior_sample");
    setAgentRunExecutionMode("deterministic");
    populateAgentRunPortfolios();
    populateCyclePortfolios();
    loadAgentRuns();
    refreshGraphAgents();
    bind();
    configureDatasetMode();
    initializeLiveConnection();
    initializeAgentRuntime();
    const requestedWorkspace = new URLSearchParams(window.location.search).get("workspace");
    if (["dataset", "portfolio", "agent", "graph", "registry", "artifacts", "experiments", "cycle", "full"].includes(requestedWorkspace)) switchWorkspace(requestedWorkspace, false);
  }

  initialize();
})();
