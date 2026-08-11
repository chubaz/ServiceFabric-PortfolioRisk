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

  function showToast(message, tone = "info") {
    let region = $("#application-toast-region");
    if (!region) {
      region = document.createElement("div");
      region.id = "application-toast-region";
      region.className = "application-toast-region";
      region.setAttribute("role", "status");
      region.setAttribute("aria-live", "polite");
      document.body.append(region);
    }
    const item = document.createElement("div");
    item.className = `application-toast ${tone}`;
    item.textContent = String(message);
    region.replaceChildren(item);
    window.setTimeout(() => {
      if (item.isConnected) item.remove();
    }, 4200);
  }

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
    { id: "registry_agent_search", name: "Agent registry search", purpose: "Find reusable agent definitions and versions before proposing new work.", status: "system" },
    { id: "agent_blueprint_examples", name: "Agent blueprint examples", purpose: "Retrieve bounded examples and class-specific design guidance.", status: "system" },
    { id: "agent_blueprint_validate", name: "Agent blueprint validator", purpose: "Validate class, contract, authority and lifecycle invariants.", status: "system" },
    { id: "studio_codex_brief_prepare", name: "Studio-Codex brief preparation", purpose: "Prepare a non-executing candidate build brief after human approval.", status: "system" },
  ];

  const basicContextPacks = {
    morning_risk_context: { label: "Morning risk context", input: "OverallDefaultContext", detail: "Portfolio, mandate, deterministic metrics, eligible events and evidence state." },
    portfolio_event_review: { label: "Portfolio event review", input: "OverallDefaultContext", detail: "Eligible event, point-in-time mappings, portfolio exposure and prior eligible evidence." },
    portfolio_context: { label: "Portfolio context only", input: "PortfolioContext", detail: "Immutable holdings, cash, exposure and mandate state for the workflow date." },
    specialist_output_review: { label: "Specialist output review", input: "SpecialistOutputBundle", detail: "Typed specialist outputs and their evidence references for independent validation." },
    agent_blueprint_context: { label: "Agent blueprint context", input: "AgentBlueprintContext", detail: "Design intent, Registry matches, policies, examples, codebase scope and unresolved questions." },
  };

  const basicCapabilityPacks = {
    daily_risk_review: { label: "Daily risk review", ids: ["market_data", "risk_metrics", "portfolio_exposure", "scenario_stress", "event_retrieval", "evidence_critic"] },
    portfolio_event_triage: { label: "Portfolio event triage", ids: ["event_retrieval", "portfolio_exposure", "market_data", "evidence_critic"] },
    market_risk_summary: { label: "Market risk summary", ids: ["market_data", "risk_metrics", "portfolio_exposure", "evidence_critic"] },
    concentration_review: { label: "Concentration review", ids: ["portfolio_exposure", "risk_metrics", "evidence_critic"] },
    evidence_validation: { label: "Evidence validation", ids: ["event_retrieval", "evidence_critic"] },
    agent_design_support: { label: "Agent design support", ids: ["registry_agent_search", "agent_blueprint_examples", "agent_blueprint_validate", "studio_codex_brief_prepare"] },
  };

  const basicRecipeDefaults = {
    "risk-template-daily-portfolio-risk-reviewer": ["morning_risk_context", "daily_risk_review"],
    "risk-template-market-liquidity-risk-analyst": ["morning_risk_context", "market_risk_summary"],
    "risk-template-concentration-mandate-monitor": ["portfolio_context", "concentration_review"],
    "risk-template-scenario-stress-analyst": ["morning_risk_context", "daily_risk_review"],
    "risk-template-fundamental-event-deterioration-watcher": ["portfolio_event_review", "portfolio_event_triage"],
    "risk-template-evidence-point-in-time-critic": ["specialist_output_review", "evidence_validation"],
    "system-agent-agent-studio-architect": ["agent_blueprint_context", "agent_design_support"],
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
    activeZone: "system",
    activeWorkspace: "system",
    platformArchitecture: null,
    selectedStudioId: "capability",
    studioBuildBrief: null,
    mandateCatalogue: null,
    selectedMandateId: null,
    mandateDesignPreview: null,
    mandateApplicationCatalogue: null,
    mandateApplicationRun: null,
    applicationStudioSelection: null,
    agentStudioSystemAgents: [],
    agentStudioMessages: [],
    agentStudioCandidate: null,
    agentStudioCandidateBase: null,
    agentStudioReceipt: null,
    agentStudioCandidateValidated: false,
    agentStudioCandidateApplied: false,
    agentStudioReview: null,
    agentStudioRequirementMemory: [],
    agentStudioPendingRequirements: [],
    agentStudioReviewBusy: false,
    agentDevelopmentHistory: null,
    agentStudioBusy: false,
    agentCodexStatus: null,
    agentCodexProposal: null,
    agentCodexSession: null,
    agentCodexSessions: [],
    agentCodexPollTimer: null,
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
    agentClass: "experimental_specialist",
    agentVersion: "0.1.0",
    agentExperimentalRole: "final_decision_agent",
    staticSystemScope: null,
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
    experimentRunAudit: null,
    experimentRunComparison: null,
    selectedExperimentId: null,
    experimentLoading: false,
    decisionRecords: [],
    selectedDecisionId: null,
    decisionLoading: false,
    dueDiligenceData: null,
    dueDiligenceLoading: false,
    capabilityCatalogue: null,
    capabilityAssessment: null,
    capabilityDesignMessages: [],
    capabilityDesignSessionId: null,
    capabilityDesignParentSessionId: null,
    capabilityDesignSessions: [],
    capabilityDraftBlueprint: null,
    capabilityDraftDecision: null,
    capabilityProposals: [],
    capabilityRuns: [],
    selectedCapabilityId: null,
    selectedCapabilityProposalId: null,
    selectedCapabilityRun: null,
    selectedCapabilityPackageId: null,
    selectedCapabilityHostId: null,
    capabilityLibraryTab: "capabilities",
    capabilityInspectorView: "tests",
    capabilityDescriptionView: "contract",
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

  const zoneDefaults = {
    system: "system",
    research: "experiments",
  };

  const workbenchWorkspaces = new Set([
    "application", "dictionary", "registry", "portfolio", "agent", "graph",
    "dataset", "decisions", "decision-diligence", "cycle",
  ]);

  function normalizedZone(zone) {
    return zone === "application" ? "system" : zone;
  }

  function workspaceSupportsZone(name, zone) {
    if (zone === "system" && workbenchWorkspaces.has(name)) return true;
    return Boolean($(`.workspace-tab[data-workspace="${name}"][data-zone="${zone}"]`));
  }

  function switchZone(zone, preferredWorkspace = null, updateHistory = true) {
    zone = normalizedZone(zone);
    if (!zoneDefaults[zone]) return;
    labState.activeZone = zone;
    document.body.dataset.operatingZone = zone;
    $$(".operating-zone-tab").forEach((button) => {
      const active = button.dataset.zone === zone;
      button.classList.toggle("active", active);
      if (active) button.setAttribute("aria-current", "true");
      else button.removeAttribute("aria-current");
    });
    $$(".workspace-tab").forEach((button) => button.classList.toggle("hidden", button.dataset.zone !== zone));
    const target = preferredWorkspace && workspaceSupportsZone(preferredWorkspace, zone)
      ? preferredWorkspace
      : zoneDefaults[zone];
    switchWorkspace(target, updateHistory, zone);
  }

  function renderRuntimeTruth(name = labState.activeWorkspace) {
    // Runtime boundaries remain on the relevant object and API response. The
    // former four-field global banner duplicated them and is intentionally gone.
  }

  function switchWorkspace(name, updateHistory = true, zoneOverride = null) {
    const supportedZones = $$(`.workspace-tab[data-workspace="${name}"]`).map((button) => button.dataset.zone);
    const requestedZone = normalizedZone(zoneOverride);
    const zone = requestedZone || (supportedZones.includes(labState.activeZone) ? labState.activeZone : supportedZones[0]);
    if (zone && zone !== labState.activeZone) {
      labState.activeZone = zone;
      document.body.dataset.operatingZone = zone;
      $$(".operating-zone-tab").forEach((button) => button.classList.toggle("active", button.dataset.zone === zone));
      $$(".workspace-tab").forEach((button) => button.classList.toggle("hidden", button.dataset.zone !== zone));
    }
    labState.activeWorkspace = name;
    const full = name === "full";
    const inWorkbench = labState.activeZone === "system" && workbenchWorkspaces.has(name);
    $("#lab-workspace").classList.toggle("hidden", full);
    $("#lab-workspace").classList.toggle("workbench-mode", inWorkbench);
    $("#full-experiment-workspace").classList.toggle("hidden", !full);
    $("#workbench-sidebar").classList.toggle("hidden", !inWorkbench);
    document.body.classList.toggle("workbench-open", inWorkbench);
    $$(".lab-page").forEach((page) => page.classList.toggle("active", page.id === `lab-${name}`));
    $$(".workspace-tab").forEach((button) => {
      const active = button.dataset.zone === labState.activeZone && (
        button.dataset.workspace === name || (button.hasAttribute("data-workbench-root") && inWorkbench)
      );
      button.classList.toggle("active", active);
      if (active) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    $$("[data-workbench-workspace]").forEach((button) => {
      const active = button.dataset.workbenchWorkspace === name;
      button.classList.toggle("active", active);
      if (active) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    renderRuntimeTruth(name);
    const activeZoneTitle = $(`.operating-zone-tab[data-zone="${labState.activeZone}"]`)?.textContent || "Development";
    $("#active-zone-badge").textContent = activeZoneTitle;
    if (["system", "studio", "application", "dictionary"].includes(name)) loadPlatformWorkspaces();
    if (name === "dataset") populateDatasetPortfolios();
    if (name === "graph") refreshGraphAgents();
    if (name === "registry") loadRegistryCatalogue();
    if (name === "artifacts") loadArtifactCatalogue();
    if (name === "experiments") loadExperimentWorkspace();
    if (name === "decisions") loadDecisionWorkspace();
    if (name === "decision-diligence") loadDueDiligenceWorkspace();
    if (name === "cycle") populateCyclePortfolios();
    if (updateHistory) {
      const url = new URL(window.location.href);
      const hadHash = Boolean(url.hash);
      url.hash = "";
      if (name === "decision-diligence" && labState.selectedDecisionId) url.searchParams.set("proposal", labState.selectedDecisionId);
      if (url.searchParams.get("workspace") !== name) {
        url.searchParams.set("workspace", name);
        url.searchParams.set("zone", labState.activeZone);
        window.history.pushState({ workspace: name }, "", url);
      } else if (url.searchParams.get("zone") !== labState.activeZone) {
        url.searchParams.set("zone", labState.activeZone);
        window.history.pushState({ workspace: name, zone: labState.activeZone }, "", url);
      } else if (hadHash) {
        window.history.replaceState({ workspace: name, zone: labState.activeZone }, "", url);
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
      agent_class: labState.agentClass,
      version: labState.agentVersion,
      static_system_scope: labState.agentClass === "static_system" ? structuredClone(labState.staticSystemScope) : null,
      experimental_role: labState.agentClass === "experimental_specialist" ? labState.agentExperimentalRole : null,
      experimental_wrapper: labState.agentClass === "experimental_specialist" ? {
        execution_mode: "headless",
        evaluation_contract: "AgentStructuredOutput/v1",
        presentation_artifact_policy: "label_and_exclude",
        captures_runtime_behavior: true,
        maps_to_architecture_output: labState.agentExperimentalRole === "final_decision_agent",
      } : null,
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
      agent_class: blueprint.agent_class,
      version: blueprint.version,
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
    const recipes = builtInRiskAgents().filter((agent) => (agent.agent_class || agent.blueprint?.agent_class || "experimental_specialist") === labState.agentClass);
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
    const context = basicContextPacks[meta.context_pack] || (labState.agentClass === "static_system" ? basicContextPacks.agent_blueprint_context : basicContextPacks.morning_risk_context);
    const capabilityIds = basicEffectiveCapabilities();
    const capabilityNames = capabilityIds.map((id) => capabilities.find((item) => item.id === id)?.name || id);
    const triggerLabels = {
      manual: "Manual run",
      workflow: "Workflow cycle",
      event: "Eligible event",
      scheduled: "Schedule",
    };
    const authorityA1 = meta.authority_profile === "A1";
    const staticSystem = labState.agentClass === "static_system";
    const recipe = builtInRiskAgents().find((item) => item.id === meta.recipe_id);
    const expectedIds = authorityA1
      ? ["evidence_critic"]
      : (basicCapabilityPacks[meta.capability_pack]?.ids || []);
    const customized = blueprint.input_contract !== context.input
      || blueprint.output_contract !== $("#basic-agent-output").value
      || capabilityIds.slice().sort().join("|") !== expectedIds.slice().sort().join("|");

    renderBasicRecipes();
    $$('[data-agent-class]').forEach((button) => button.classList.toggle('active', button.dataset.agentClass === labState.agentClass));
    $("#basic-static-scope").classList.toggle("hidden", !staticSystem);
    if (staticSystem && labState.staticSystemScope) {
      $("#basic-static-scope").innerHTML = `<span>Static System boundary</span><strong>${escapeHtml(agentBuilderLabel(labState.staticSystemScope.owning_studio))} Studio · v${escapeHtml(labState.agentVersion)}</strong><p>Proposal only · ${labState.staticSystemScope.skill_ids.map(escapeHtml).join(", ")} · ${labState.staticSystemScope.codebase_scope.length} bounded paths</p>`;
    }
    setBasicValue("#basic-agent-name", blueprint.name);
    setBasicValue("#basic-agent-outcome", blueprint.purpose);
    setBasicValue("#basic-agent-trigger", meta.trigger);
    setBasicValue("#basic-agent-scope", meta.scope);
    setBasicValue("#basic-agent-as-of", meta.as_of);
    setBasicValue("#basic-agent-dedup", meta.deduplication);
    setBasicValue("#basic-agent-context-pack", meta.context_pack);
    setBasicValue("#basic-agent-capability-pack", meta.capability_pack);
    setBasicValue("#basic-agent-output", blueprint.output_contract);
    setBasicValue("#basic-agent-experimental-role", labState.agentExperimentalRole);
    setBasicValue("#basic-agent-authority", meta.authority_profile);
    $("#basic-agent-experimental-role").disabled = staticSystem;
    $("#agent-experimental-role").disabled = staticSystem;

    $$("[data-basic-agent-step]").forEach((button, index) => {
      const active = button.dataset.basicAgentStep === labState.agentBuilderStep;
      button.classList.toggle("active", active);
      button.classList.toggle("complete", index < ["outcome", "scope", "context", "output", "test"].indexOf(labState.agentBuilderStep));
    });
    $$("[data-basic-agent-panel]").forEach((panel) => panel.classList.toggle("active", panel.dataset.basicAgentPanel === labState.agentBuilderStep));

    $("#basic-scope-summary").textContent = `${triggerLabels[meta.trigger]} · ${agentBuilderLabel(meta.scope)} · information eligible at ${agentBuilderLabel(meta.as_of).toLowerCase()} · duplicate key ${agentBuilderLabel(meta.deduplication).toLowerCase()}.`;
    $("#basic-capability-preview").innerHTML = capabilityNames.map((name, index) => `<span class="basic-capability-chip ${index === capabilityNames.length - 1 ? "required" : ""}">${escapeHtml(name)}</span>`).join("");
    $("#basic-authority-level").textContent = meta.authority_profile;
    $("#basic-authority-title").textContent = staticSystem ? "Proposal-only design" : authorityA1 ? "Context-bound draft" : "Effect-free analysis and draft";
    $("#basic-authority-copy").textContent = staticSystem
      ? "May inspect bounded design context and prepare a candidate brief; it cannot code, register, activate or publish."
      : authorityA1
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
    $("#basic-preview-output").innerHTML = `${escapeHtml(agentBuilderLabel(blueprint.output_contract))} · ${escapeHtml(staticSystem ? "system proposal" : agentBuilderLabel(labState.agentExperimentalRole))}<span class="field-provenance derived">Headless contract</span>`;
    $("#basic-preview-authority").innerHTML = `${escapeHtml(staticSystem ? "S0" : meta.authority_profile)} · ${staticSystem ? "proposal only" : authorityA1 ? "context-bound draft" : "analytical tools and draft"} · human review<span class="field-provenance policy">Policy</span>`;
  }

  function syncBasicBuilderFromBlueprint() {
    const blueprint = currentAgentBlueprint();
    const matchingContext = Object.entries(basicContextPacks).find(([, pack]) => pack.input === blueprint.input_contract)?.[0];
    if (matchingContext) labState.agentBuilderMeta.context_pack = matchingContext;
    const enabled = blueprint.capability_latches.map((latch) => latch.capability_id).slice().sort().join("|");
    const matchingPack = Object.entries(basicCapabilityPacks).find(([, pack]) => pack.ids.slice().sort().join("|") === enabled)?.[0];
    if (matchingPack) labState.agentBuilderMeta.capability_pack = matchingPack;
    labState.agentBuilderMeta.authority_profile = blueprint.agent_class === "static_system"
      ? "S0"
      : enabled === "evidence_critic" ? "A1" : "A2";
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

  function setAgentClass(agentClass) {
    if (!["static_system", "experimental_specialist"].includes(agentClass)) return;
    labState.agentClass = agentClass;
    const firstRecipe = builtInRiskAgents().find((agent) =>
      (agent.agent_class || agent.blueprint?.agent_class || "experimental_specialist") === agentClass
    );
    if (firstRecipe) selectBasicRecipe(firstRecipe.id);
    else {
      renderBasicRecipes();
      showToast("The local API is still loading this agent class.", "error");
    }
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
    labState.agentClass = agent.agent_class || agent.blueprint.agent_class || "experimental_specialist";
    labState.agentVersion = agent.version || agent.blueprint.version || "0.1.0";
    labState.staticSystemScope = structuredClone(agent.blueprint.static_system_scope || null);
    labState.agentBuilderMeta.provenance = "recipe_defaults";
    const [contextPack, capabilityPack] = basicRecipeDefaults[id] || ["morning_risk_context", "daily_risk_review"];
    labState.agentBuilderMeta.context_pack = contextPack;
    labState.agentBuilderMeta.capability_pack = capabilityPack;
    labState.agentBuilderMeta.authority_profile = labState.agentClass === "static_system" ? "S0" : "A2";
    applyAgentBlueprint(structuredClone(agent.blueprint));
    $("#basic-agent-description").value = agent.blueprint.purpose;
    if (labState.agentClass === "static_system") {
      renderCapabilities();
      renderAgentContract();
      renderBasicBuilder();
    } else applyBasicCapabilityAndAuthority();
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
    labState.agentExperimentalRole = contract === "RiskReviewDraft"
      ? "final_decision_agent"
      : "specialist_node";
    setBasicValue("#basic-agent-experimental-role", labState.agentExperimentalRole);
    setBasicValue("#agent-experimental-role", labState.agentExperimentalRole);
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
      const [runtime, templatesPayload] = await Promise.all([
        agentApi("/api/agents/runtime"),
        agentApi("/api/agents/templates"),
      ]);
      labState.agentRuntime = runtime;
      if (templatesPayload.agents?.length) {
        labState.riskAgentTemplates = templatesPayload.agents;
        seedAgents();
        renderSavedAgents();
        renderBasicRecipes();
      }
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
      ["Experiment wrapper", blueprint.agent_class === "static_system" || blueprint.experimental_wrapper?.execution_mode === "headless", blueprint.agent_class === "static_system" ? "not applicable" : `${agentBuilderLabel(blueprint.experimental_role)} · headless`],
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
    labState.agentClass = blueprint.agent_class || "experimental_specialist";
    labState.agentVersion = blueprint.version || "0.1.0";
    labState.agentExperimentalRole = blueprint.experimental_role || (
      blueprint.output_contract === "RiskReviewDraft" ? "final_decision_agent" : "specialist_node"
    );
    labState.staticSystemScope = structuredClone(blueprint.static_system_scope || null);
    $("#agent-name").value = blueprint.name;
    $("#agent-purpose").value = blueprint.purpose;
    $("#agent-model").value = blueprint.model;
    $("#agent-config-model").value = blueprint.model;
    $("#agent-input").value = blueprint.input_contract;
    $("#agent-output").value = blueprint.output_contract;
    $("#agent-experimental-role").value = labState.agentExperimentalRole;
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
    $$("[data-agent-run-mode-panel]").forEach((panel) => panel.classList.toggle("hidden", !panel.dataset.agentRunModePanel.split(" ").includes(mode)));
    const real = mode === "real_duckdb";
    const calibrated = mode === "historically_calibrated_synthetic";
    $("#agent-run-mode-badge").textContent = real ? "Licensed point-in-time data" : calibrated ? "Historically calibrated synthetic" : "Controlled synthetic fixture";
    $("#agent-run-mode-badge").className = `run-mode-identity ${real ? "real" : "synthetic"}`;
    $("#agent-input-preview-status").textContent = "Preview not loaded";
    $("#agent-input-json").textContent = "{}";
    $("#agent-input-provenance").innerHTML = `<p>${real ? "Select a reviewed portfolio and as-of date." : calibrated ? "Select the local portfolio history used for in-sample calibration; licensed rows will not be retained." : "Select a fixed controlled fixture."}</p>`;
    renderRuntimeTruth();
  }

  function setAgentRunExecutionMode(mode) {
    labState.agentRunExecutionMode = mode;
    const live = mode === "live_llm";
    const compare = mode === "compare";
    $$('[data-agent-execution-mode]').forEach((button) => button.classList.toggle("active", button.dataset.agentExecutionMode === mode));
    $("#agent-live-run-model-field").classList.toggle("hidden", !(live || compare));
    $("#agent-run-status").textContent = compare ? "Comparison not run" : live ? "Model call not run" : "Verification not run";
    $("#test-agent").textContent = compare ? "Run comparison" : live ? "Run model" : "Run verification";
  }

  function renderAgentInputPreview(preview) {
    labState.agentInputPreview = preview;
    const provenance = preview.provenance || {};
    const real = provenance.data_mode === "real_duckdb";
    const calibrated = provenance.data_mode === "historically_calibrated_synthetic";
    $("#agent-input-preview-status").textContent = provenance.label || (real ? "Licensed historical input" : calibrated ? "Historically calibrated synthetic" : "Controlled synthetic fixture");
    $("#agent-input-json").textContent = JSON.stringify(preview.context, null, 2);
    const chips = [
      `<span class="run-provenance-chip ${real ? "real" : "warning"}">${escapeHtml(provenance.label || provenance.data_mode)}</span>`,
      `<span class="run-provenance-chip">${real ? "Licensed rows in run context" : calibrated ? "Licensed calibration · no rows retained" : "No licensed rows used"}</span>`,
      provenance.as_of ? `<span class="run-provenance-chip">As of ${escapeHtml(provenance.as_of)}</span>` : "",
      provenance.record_count !== undefined ? `<span class="run-provenance-chip">${Number(provenance.record_count).toLocaleString()} source records</span>` : "",
      provenance.reserved_oos_window ? `<span class="run-provenance-chip">${Number(provenance.reserved_oos_window.observations || 0).toLocaleString()} OOS observations reserved</span>` : "",
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
    if (item.kind === "semantic_verification") {
      const conflicts = (payload.conflicts || []).map((item) => `<li><strong>${escapeHtml(item.fact_id)}</strong><span>${escapeHtml(item.claim)}</span></li>`).join("");
      return `<div class="run-semantic-summary"><div><span>Fields checked</span><strong>${Number(payload.checked_field_count || 0)}</strong></div><div><span>Available</span><strong>${Number(payload.available_field_count || 0)}</strong></div><div><span>Material coverage</span><strong>${Math.round(Number(payload.material_field_coverage || 0) * 100)}%</strong></div><div><span>Contradictions</span><strong>${(payload.conflicts || []).length}</strong></div></div>${conflicts ? `<ul class="run-stage-list">${conflicts}</ul>` : ""}<details class="run-technical-receipt"><summary>Field-by-field checks</summary><pre>${escapeHtml(JSON.stringify(payload.checks || [], null, 2))}</pre></details>`;
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
    const report = presentation.report || output.report || null;
    const reportValidation = presentation.report_validation || output.report_validation || null;
    const semanticValidation = presentation.semantic_verification || output.semantic_verification || null;
    const trustedReport = report?.renderer_version === "portfolio-risk.safe-markdown/v1" && typeof report?.rendered_html === "string";
    const reportNavigation = trustedReport ? `<nav class="report-section-nav" aria-label="Report sections">${(report.sections || []).map((section, index) => `<a href="#report-${escapeHtml(section.section_id)}"><span>${index + 1}</span>${escapeHtml(section.title)}</a>`).join("")}</nav>` : "";
    const reportChecks = reportValidation ? `<div class="report-validation ${reportValidation.valid ? "valid" : "attention"}">
      <strong>${reportValidation.valid ? "Report checks passed" : "Review checks need attention"}</strong>
      <span>${Math.round(Number(reportValidation.evidence_coverage || 0) * 100)}% evidence coverage</span>
      <span>${(reportValidation.repetition_pairs || []).length} repeated section pair${(reportValidation.repetition_pairs || []).length === 1 ? "" : "s"}</span>
      <span>${(reportValidation.length_violations || []).length} length warning${(reportValidation.length_violations || []).length === 1 ? "" : "s"}</span>
    </div>` : "";
    const semanticChecks = semanticValidation ? `<div class="report-validation ${semanticValidation.status === "passed" ? "valid" : "attention"}"><strong>${semanticValidation.status === "passed" ? "Semantic checks passed" : "Semantic conflicts require review"}</strong><span>${Number(semanticValidation.checked_field_count || 0)} fields checked</span><span>${Math.round(Number(semanticValidation.material_field_coverage || 0) * 100)}% material-field coverage</span><span>${(semanticValidation.conflicts || []).length} contradiction${(semanticValidation.conflicts || []).length === 1 ? "" : "s"}</span></div>` : "";
    const sections = presentation.report_sections || output.model_output?.report_sections || [];
    const sectionMarkup = sections.length ? `<div class="run-report-sections">${sections.map((section) => `<section class="${section.section_id === "executive_signal" ? "lead" : ""}"><span>${escapeHtml(section.title)}</span>${section.content ? `<p>${escapeHtml(section.content)}</p>` : ""}${section.items?.length ? `<ul>${section.items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}</section>`).join("")}</div>` : "";
    return `<article class="run-outcome-card ${escapeHtml(presentation.tone || "limited")}">
      <header class="run-outcome-masthead"><div><span>Agent result</span><h3>${escapeHtml(presentation.title)}</h3></div><b>${escapeHtml(presentation.status_label)}</b></header>
      <p class="run-outcome-premise">${escapeHtml(presentation.premise)}</p>
      ${semanticChecks}${trustedReport ? `${reportChecks}${reportNavigation}<div class="run-report-document">${report.rendered_html}</div>` : sections.length ? sectionMarkup : `<section class="run-outcome-conclusion"><span>Executive conclusion</span><p>${escapeHtml(presentation.executive_conclusion)}</p></section>`}
      <div class="run-outcome-metrics">${observations}</div>
      ${trustedReport || sections.length ? `<details class="run-condensed-evidence"><summary>Additional execution and evidence limitations</summary><ul>${limitations}</ul></details>` : `<div class="run-outcome-columns">
        <section><span>Material findings</span><ul>${findings}</ul></section>
        <section><span>Important limitations</span><ul>${limitations}</ul></section>
      </div>
      <section class="run-outcome-next"><span>Recommended review steps</span><ol>${nextSteps}</ol></section>`}
      <footer><div><span>Decision boundary</span><p>${escapeHtml(presentation.review_boundary)}</p></div><b>${escapeHtml(reviewLabel)} · Effects: none</b></footer>
    </article>`;
  }

  function comparisonRunSummary(label, run) {
    const state = run.final_state || {};
    const semantic = state.semantic_verification || {};
    const receipt = (state.model_receipts || [])[0] || {};
    return `<article class="agent-comparison-result">
      <header><strong>${escapeHtml(label)}</strong><b class="${semantic.status === "passed" ? "passed" : "warning"}">${semantic.status === "passed" ? "Semantically consistent" : `${(semantic.conflicts || []).length} conflict(s)`}</b></header>
      <p>${escapeHtml(state.narrative || "No conclusion produced.")}</p>
      <dl><div><dt>Runtime</dt><dd>${Number(run.elapsed_ms || 0).toLocaleString()} ms</dd></div><div><dt>Fields checked</dt><dd>${Number(semantic.checked_field_count || 0)}</dd></div><div><dt>Model tokens</dt><dd>${Number(receipt.total_tokens || 0).toLocaleString()}</dd></div></dl>
    </article>`;
  }

  function renderAgentComparison(comparison) {
    const deterministic = comparison.deterministic || {};
    const live = comparison.live_llm || {};
    const modelFindings = live.final_state?.model_output?.material_findings || [];
    $("#agent-run-chat").innerHTML = `<article class="run-premise-card comparison-premise"><header><div><span>Controlled comparison</span><strong>One blueprint · one frozen input · two interpretation methods</strong></div><b>${escapeHtml(comparison.comparison_id)}</b></header><p>Both runs used input digest <code>${escapeHtml(comparison.input_digest)}</code>. Capabilities and evidence were held constant.</p></article>
      <div class="agent-comparison-grid">${comparisonRunSummary("Deterministic baseline", deterministic)}${comparisonRunSummary("Luna interpretation", live)}</div>
      <article class="run-message rationale"><header><strong>What the model added</strong><span>${modelFindings.length} material finding${modelFindings.length === 1 ? "" : "s"}</span></header><ul>${modelFindings.map((item) => `<li>${escapeHtml(item.claim)}</li>`).join("") || "<li>No additional structured finding was produced.</li>"}</ul></article>`;
    $("#agent-run-chat").scrollTop = 0;
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
    const calibrated = manifest.data_mode === "historically_calibrated_synthetic" || provenance.data_mode === "historically_calibrated_synthetic";
    $("#agent-run-mode-badge").textContent = real ? "Saved · Licensed historical" : calibrated ? "Saved · Calibrated synthetic" : "Saved · Controlled fixture";
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
    $("#retain-agent-run").classList.remove("hidden");
    $("#agent-run-files").innerHTML = manifest.files.map((file) => `
      <button class="run-file-item" type="button" data-agent-run-file="${escapeHtml(file.name)}"><strong>${escapeHtml(file.name)}</strong><span>${Number(file.bytes || 0).toLocaleString()} bytes</span></button>`).join("");
    $("#agent-run-file-content").textContent = "Select a file to inspect it.";
    $$(".run-repository-item").forEach((item) => item.classList.toggle("active", item.dataset.agentRunId === manifest.run_id));
  }

  function renderAgentRunRepository() {
    $("#agent-run-repository").innerHTML = labState.agentRuns.length ? labState.agentRuns.map((run) => `
      <button class="run-repository-item ${labState.selectedAgentRunId === run.run_id ? "active" : ""}" type="button" data-agent-run-id="${escapeHtml(run.run_id)}">
        <b class="${run.data_mode === "real_duckdb" ? "real" : "synthetic"}">${run.data_mode === "real_duckdb" ? "Licensed historical" : run.data_mode === "historically_calibrated_synthetic" ? "Calibrated synthetic" : run.data_mode === "synthetic_behavior_sample" ? "Controlled fixture" : "Legacy unversioned synthetic"}</b>
        <strong>${escapeHtml(run.agent_name)}</strong>
        <span>${escapeHtml(run.created_at)} · ${escapeHtml(run.status)}${run.execution_mode === "live_llm" ? ` · model call` : " · deterministic"}</span>
      </button>`).join("") : '<div class="empty-state">No saved agent runs.</div>';
  }

  async function loadAgentRuns() {
    try {
      const result = await agentApi("/api/agents/runs");
      labState.agentRuns = result.runs || [];
      renderAgentRunRepository();
      $("#refresh-agent-runs").title = result.hidden_retained_run_count ? `${result.hidden_retained_run_count} retained run(s) are in the Artifact Repository.` : "Refresh temporary runs";
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

  async function retainSelectedAgentRun() {
    const runId = labState.selectedAgentRunId;
    if (!runId) return;
    await admitTemporaryRun(runId);
    $("#retain-agent-run").classList.add("hidden");
    $("#agent-live-state").textContent = "Retained";
    $("#agent-run-chat").insertAdjacentHTML("afterbegin", '<article class="run-message review"><header><strong>Repository</strong><span>Retained for comparison</span></header><p>An immutable copy is now available in the Artifact Repository. This run no longer appears in the temporary queue.</p></article>');
    await loadAgentRuns();
  }

  async function runAgentTest() {
    $("#test-agent").disabled = true;
    $("#agent-run-status").textContent = "Preparing";
    $("#agent-live-state").textContent = "Freezing input";
    try {
      const runLabel = $("#agent-run-label").value.trim();
      if (runLabel.length > 120) {
        throw new Error("Assignment must be 120 characters or fewer. Keep detailed instructions in the agent blueprint.");
      }
      const preview = labState.agentInputPreview || await previewAgentInput();
      $("#agent-run-chat").innerHTML = `<article class="run-message assignment"><header><strong>System</strong><span>${escapeHtml(preview.provenance.label)}</span></header><p>Exact input frozen. Compiling the current blueprint and starting its governed graph.</p></article>`;
      $("#agent-live-state").textContent = "Compiling";
      const compiled = labState.agentCompile || await compileAgent();
      switchAgentOutputTab("run");
      $("#agent-live-state").textContent = "Agent working";
      $("#agent-run-status").textContent = "Running";
      const input = currentAgentInputRequest();
      const compare = labState.agentRunExecutionMode === "compare";
      const result = await agentApi(compare ? "/api/agents/compare" : "/api/agents/run", {
        method: "POST",
        body: JSON.stringify({
          blueprint: compiled.blueprint,
          ...input,
          execution_mode: compare ? "deterministic" : labState.agentRunExecutionMode,
          execution_model: $("#agent-live-run-model").value,
          run_label: runLabel,
          persist_run: true,
          auto_approve_review: $("#agent-auto-review").checked,
        }),
      });
      if (compare) {
        $("#agent-run-status").textContent = "Comparison saved";
        $("#agent-run-status").classList.remove("warning");
        $("#agent-live-state").textContent = "Comparison complete";
        renderAgentComparison(result);
        $("#agent-builder-status").textContent = "Comparison saved";
        await loadAgentRuns();
        return result;
      }
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
    const welcome = `<div class="advisor-message assistant"><strong>Agent Studio Architect · v0.1.0</strong><p>I can find reuse, explain design choices, critique this blueprint, and prepare a candidate brief. I cannot write, register, activate or publish an agent.</p></div>`;
    $("#agent-advisor-messages").innerHTML = welcome + labState.advisorMessages.map((message) => `
      <div class="advisor-message ${escapeHtml(message.role)}"><strong>${message.role === "user" ? "You" : "Agent Studio Architect"}</strong><p>${escapeHtml(message.content)}</p></div>`).join("");
    $("#agent-advisor-messages").scrollTop = $("#agent-advisor-messages").scrollHeight;
  }

  function renderAdvisorProposal(advice, receipt) {
    labState.advisorProposal = advice.improved_design_brief;
    $("#agent-advisor-proposal").classList.remove("hidden");
    $("#agent-advisor-proposal").innerHTML = `
      <div class="advisor-score"><b>${advice.overall_score}</b><span><strong>Blueprint score</strong><small>${escapeHtml(receipt.system_agent_id || "system agent")} · v${escapeHtml(receipt.system_agent_version || "0.1.0")} · ${receipt.input_tokens + receipt.output_tokens} tokens</small></span></div>
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
    blueprint.model = "gpt-5.6-luna";
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
        slug: "evidence-point-in-time-critic", name: "Evidence and Point-in-Time Critic", category: "Governance", role: "critic", input: "SpecialistOutputBundle", output: "EvidenceCritique", strategy: "direct", assembly: "iterative_refinement", renderingTarget: "json", composition: "data_product", model: "gpt-5.6-luna",
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
      loadAgentDevelopmentHistory(agent.blueprint).catch((error) => {
        $("#agent-history-count").textContent = "History unavailable";
        $("#agent-history-summary").innerHTML = `<div class="agent-review-empty">${escapeHtml(error.message)}</div>`;
      });
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
      const decisions = new Map([...(snapshot.decisions || [])].reverse().map((item) => [item.proposal_id, item]));
      const receipts = new Map([...(snapshot.consequence_receipts || [])].reverse().map((item) => [item.proposal_id, item]));
      const history = snapshot.daily_history || [];
      $("#cycle-dashboard-view").innerHTML = `${cycleMetricCards(snapshot)}<div class="cycle-risk-columns"><section><span>Decision proposals and resolutions</span>${proposals.length ? proposals.map((item) => { const finding = findings.get(item.finding_id); const decision = decisions.get(item.proposal_id); const receipt = receipts.get(item.proposal_id); const state = String(item.status || "awaiting_review").replaceAll("_", " "); return `<article class="cycle-decision-card"><b>${escapeHtml(state)}${decision ? ` · ${escapeHtml(decision.outcome)}` : ""}</b><strong>${escapeHtml(finding?.summary || `Finding ${item.finding_id}`)}</strong><small>${decision ? `Resolver ${escapeHtml(decision.resolver?.resolver_id || "unknown")} · ${escapeHtml(receipt?.consequence || "No consequence receipt")}` : escapeHtml(cycleTimeLabel(item.as_of))}</small></article>`; }).join("") : '<div class="empty-state">No threshold finding has created a decision proposal.</div>'}</section><section><span>Completed dates</span>${history.length ? history.map((item) => `<article class="cycle-history-row"><strong>${escapeHtml(item.date)}</strong><b class="${Number(item.return) < 0 ? "negative" : "positive"}">${runPercentage(item.return, 2)}</b><small>${escapeHtml(cycleMoney(item.close_nav))}</small></article>`).join("") : '<div class="empty-state">No simulated day has closed.</div>'}</section></div>`;
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
    const proposal = (snapshot.decision_proposals || []).find((item) => !["resolved", "rejected", "expired", "superseded"].includes(item.status));
    const finding = (snapshot.findings || []).find((item) => item.finding_id === proposal?.finding_id);
    $("#cycle-decision-panel").classList.toggle("hidden", !proposal);
    if (proposal) {
      $("#cycle-decision-panel").dataset.proposalId = proposal.proposal_id;
      $("#cycle-decision-finding").textContent = finding?.summary || `Finding ${proposal.finding_id}`;
      $("#cycle-decision-question").textContent = proposal.question;
      $("#cycle-decision-consequences").innerHTML = (proposal.options || []).map((option) => `<li><strong>${escapeHtml(option.label)}</strong> — ${escapeHtml(option.consequence)}</li>`).join("");
      $("#cycle-decision-panel").dataset.recordRevision = proposal.record_revision || "";
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
    const rationale = $("#cycle-decision-rationale").value.trim();
    if (resolverId.length < 3) {
      showToast("Enter a resolver ID before recording the decision.", "error");
      $("#cycle-decision-resolver").focus();
      return;
    }
    if (rationale.length < 3) {
      showToast("Explain briefly why you chose this outcome.", "error");
      $("#cycle-decision-rationale").focus();
      return;
    }
    const snapshot = await agentApi(`/api/workflow-cycle/sessions/${encodeURIComponent(labState.cycleSessionId)}/decision-proposals/${encodeURIComponent(proposalId)}/resolve`, {
      method: "POST",
      body: JSON.stringify({
        outcome, resolver_id: resolverId, resolver_type: "human", rationale,
        idempotency_key: `cycle-review-${Date.now()}`,
        expected_revision: $("#cycle-decision-panel").dataset.recordRevision,
      }),
    });
    $("#cycle-decision-rationale").value = "";
    renderCycleSnapshot(snapshot);
    if (labState.activeWorkspace === "decisions") loadDecisionWorkspace();
  }

  function decisionOutcomeLabel(value) {
    return ({ investigate: "Investigate", accept_and_monitor: "Accept & monitor", defer: "Defer", reject: "Reject", escalate: "Escalate" })[value] || String(value || "").replaceAll("_", " ");
  }

  function selectedDecisionRecord() {
    return labState.decisionRecords.find((item) => item.proposal?.proposal_id === labState.selectedDecisionId) || null;
  }

  function renderDecisionWorkspace() {
    const records = labState.decisionRecords || [];
    $("#decision-catalogue-status").textContent = `${records.length} proposal${records.length === 1 ? "" : "s"}`;
    $("#decision-card-list").innerHTML = records.length ? records.map((record) => {
      const proposal = record.proposal || {};
      const selected = proposal.proposal_id === labState.selectedDecisionId;
      return `<button class="decision-list-card ${selected ? "active" : ""}" type="button" data-decision-id="${escapeHtml(proposal.proposal_id)}"><span>${escapeHtml(String(record.state || "unknown").replaceAll("_", " "))}</span><strong>${escapeHtml(proposal.question || "Decision proposal")}</strong><small>${escapeHtml(proposal.why_now || "No timing premise supplied.")}</small></button>`;
    }).join("") : '<div class="empty-state">No proposals have been created. Run a simulated cycle until a threshold pauses it.</div>';
    const record = selectedDecisionRecord();
    if (!record) {
      $("#decision-detail-panel").innerHTML = '<div class="empty-state">Select a Decision Card to inspect its evidence and consequences.</div>';
      return;
    }
    const proposal = record.proposal || {};
    const finalState = ["resolved", "rejected", "expired", "superseded"].includes(record.state);
    const recommendation = decisionOutcomeLabel(proposal.recommendation);
    const latestDecision = (record.decisions || []).at(-1);
    const latestRevision = (record.context_revisions || []).at(-1);
    $("#decision-detail-panel").innerHTML = `
      <article class="decision-hero"><div><span>${escapeHtml(String(record.state).replaceAll("_", " "))} · D1 · human only</span><h2>${escapeHtml(proposal.question)}</h2><p>${escapeHtml(proposal.why_now)}</p></div><b>Recommended: ${escapeHtml(recommendation)}</b></article>
      <div class="decision-context-grid">
        <article><span>Portfolio relevance</span><p>${escapeHtml(proposal.portfolio_relevance)}</p></article>
        <article><span>Mandate relevance</span><p>${escapeHtml(proposal.mandate_relevance)}</p></article>
        <article><span>Risk-environment relevance</span><p>${escapeHtml(proposal.risk_environment_relevance)}</p></article>
      </div>
      <section class="decision-option-grid">${(proposal.options || []).map((option) => `<article><strong>${escapeHtml(option.label)}</strong><p>${escapeHtml(option.consequence)}</p><small>${escapeHtml(option.workflow_effect.replaceAll("_", " "))} · effects none</small></article>`).join("")}</section>
      <section class="decision-diligence-launch"><div><span>Need more evidence?</span><strong>Open a dedicated due-diligence workspace</strong><p>Inspect receipts, policy, artifacts and alternatives, then retain an additive candidate revision.</p></div><button class="button primary" type="button" data-open-due-diligence>Open due diligence</button></section>
      <details class="decision-evidence"><summary>Evidence, uncertainty and lifecycle</summary><div class="decision-context-grid"><article><span>Evidence</span><p>${escapeHtml((proposal.evidence_ids || []).join(", ") || "No direct evidence references")}</p></article><article><span>Uncertainty</span><p>${escapeHtml((proposal.uncertainties || []).join(" ") || "None declared")}</p></article><article><span>Missing information</span><p>${escapeHtml((proposal.missing_information || []).join(" ") || "None declared")}</p></article></div><ol>${(record.lifecycle || []).map((item) => `<li><strong>${escapeHtml(item.to_state.replaceAll("_", " "))}</strong> — ${escapeHtml(item.rationale)}</li>`).join("")}</ol></details>
      ${latestRevision ? `<section class="decision-context-revision"><span>Supplemental context revision</span><strong>${escapeHtml(latestRevision.generated_by_workflow)}</strong><ul>${latestRevision.supplemental_findings.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul><small>The immutable proposal was not rewritten.</small></section>` : ""}
      ${latestDecision ? `<section class="decision-last-resolution"><span>Latest human choice</span><strong>${escapeHtml(decisionOutcomeLabel(latestDecision.outcome))}</strong><p>${escapeHtml(latestDecision.rationale)}</p></section>` : ""}
      ${finalState ? '<div class="decision-final-note">This proposal is final. Its finding, evidence, decision and consequence remain separately inspectable.</div>' : `<form id="decision-resolution-form" class="decision-resolution-form"><label><span>Reviewer ID</span><input id="decision-reviewer-id" placeholder="Enter your reviewer ID" minlength="3" required></label><label><span>Reason for the choice</span><textarea id="decision-review-rationale" rows="3" required placeholder="What evidence or uncertainty determines your choice?"></textarea></label><div>${(proposal.options || []).map((option) => `<button class="button ${option.outcome === "accept_and_monitor" ? "primary" : ""}" type="submit" data-decision-outcome="${escapeHtml(option.outcome)}">${escapeHtml(option.label)}</button>`).join("")}</div></form>`}`;
  }

  async function loadDecisionWorkspace(preferredId = null) {
    if (labState.decisionLoading) return;
    labState.decisionLoading = true;
    try {
      const payload = await agentApi("/api/decisions");
      labState.decisionRecords = payload.records || [];
      if (preferredId) labState.selectedDecisionId = preferredId;
      if (!selectedDecisionRecord()) labState.selectedDecisionId = labState.decisionRecords[0]?.proposal?.proposal_id || null;
      renderDecisionWorkspace();
    } catch (error) {
      $("#decision-catalogue-status").textContent = "Unavailable";
      $("#decision-detail-panel").innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
    } finally {
      labState.decisionLoading = false;
    }
  }

  async function resolveDecisionWorkspace(outcome) {
    const record = selectedDecisionRecord();
    if (!record) return;
    const resolverId = $("#decision-reviewer-id").value.trim();
    const rationale = $("#decision-review-rationale").value.trim();
    if (resolverId.length < 3 || rationale.length < 3) {
      showToast("Enter a reviewer ID and a short reason.", "error");
      return;
    }
    await agentApi(`/api/decisions/${encodeURIComponent(record.proposal.proposal_id)}/resolve`, {
      method: "POST",
      body: JSON.stringify({ outcome, resolver_id: resolverId, resolver_type: "human", rationale, idempotency_key: `decision-review-${Date.now()}`, expected_revision: record.revision }),
    });
    await loadDecisionWorkspace(record.proposal.proposal_id);
  }

  function diligenceGroupMarkup(group = {}) {
    const items = group.items || [];
    return `<details class="diligence-reference-group" open><summary><span>${escapeHtml(group.title || "References")}</span><b>${items.length}</b></summary><p>${escapeHtml(group.explanation || "")}</p><div>${items.length ? items.map((item) => `<article><header><strong>${escapeHtml(item.label || item.reference_id)}</strong><span>${escapeHtml(String(item.data_truth || "reference_only").replaceAll("_", " "))}</span></header><p>${escapeHtml(item.note || "")}</p>${item.workflow_effect ? `<small>${escapeHtml(item.workflow_effect.replaceAll("_", " "))} · effects none</small>` : `<small>${escapeHtml(item.status || "declared reference")}</small>`}</article>`).join("") : '<div class="diligence-empty-reference">Nothing is attached in this category. It remains unavailable rather than being inferred.</div>'}</div></details>`;
  }

  function diligenceRunMarkup(run = {}, evidenceById = new Map()) {
    return `<details class="diligence-run-card" open><summary><div><span>Temporary workflow · ${escapeHtml(run.created_by || "human")}</span><strong>${escapeHtml(run.name || run.run_id)}</strong></div><b>${(run.steps || []).length} steps</b></summary><p>${escapeHtml(run.investigation_question || "")}</p><ol>${(run.steps || []).map((step) => { const evidence = evidenceById.get(step.output_evidence_ids?.[0]); return `<li><span>${escapeHtml(String(step.capability_id || "inspection").replace("decision.", "").replaceAll(".", " "))}</span><strong>${escapeHtml(evidence?.title || step.objective)}</strong><p>${escapeHtml(step.result_summary)}</p><small>${(step.input_reference_ids || []).length} input references · ${(step.output_evidence_ids || []).length} retained evidence · effects none</small></li>`; }).join("")}</ol><footer>Completed ${escapeHtml(formatRunDate(run.completed_at))} · temporary · not publishable · not a decision</footer></details>`;
  }

  function renderDueDiligenceWorkspace() {
    const payload = labState.dueDiligenceData;
    const root = $("#diligence-workspace");
    if (!payload) {
      root.innerHTML = '<div class="empty-state">Open due diligence from a Decision Card.</div>';
      $("#diligence-status").textContent = "Select a proposal";
      return;
    }
    const workspace = payload.workspace || {};
    const proposal = payload.proposal || {};
    const runs = payload.investigation_runs || [];
    const supplemental = payload.supplemental_evidence || [];
    const revisions = payload.proposal_revisions || [];
    const latestRevision = revisions.at(-1);
    const evidenceById = new Map(supplemental.map((item) => [item.evidence_id, item]));
    $("#diligence-status").textContent = `${String(workspace.state || "unknown").replaceAll("_", " ")} · ${runs.length} run${runs.length === 1 ? "" : "s"}`;
    root.innerHTML = `
      <article class="diligence-proposal-hero"><div><span>Immutable proposal · version ${Number(proposal.version || 1)}</span><h2>${escapeHtml(proposal.question)}</h2><p>${escapeHtml(proposal.why_now)}</p></div><div><small>Current recommendation</small><strong>${escapeHtml(decisionOutcomeLabel(proposal.recommendation))}</strong>${latestRevision ? `<small>Latest candidate revision</small><strong>${escapeHtml(decisionOutcomeLabel(latestRevision.recommendation))}</strong>` : ""}</div></article>
      <div class="diligence-main-grid">
        <aside class="diligence-reference-ledger"><header><span>Decision basis</span><strong>What the proposal can actually use</strong></header>${(payload.reference_groups || []).map(diligenceGroupMarkup).join("")}</aside>
        <main class="diligence-investigation-studio">
          <header><span>Temporary investigation workflow</span><h2>Choose the checks this question needs</h2><p>Modules run in the order shown. Each inspects already eligible references and retains one explicit evidence item.</p></header>
          <form id="diligence-run-form">
            <div class="diligence-form-row"><label><span>Workflow name</span><input id="diligence-run-name" value="Decision evidence review" minlength="3" maxlength="160" required></label><label><span>Candidate recommendation</span><select id="diligence-candidate-recommendation">${(proposal.options || []).map((item) => `<option value="${escapeHtml(item.outcome)}" ${item.outcome === (latestRevision?.recommendation || proposal.recommendation) ? "selected" : ""}>${escapeHtml(item.label)}</option>`).join("")}</select></label></div>
            <label class="diligence-question"><span>Question to test</span><textarea id="diligence-question" rows="3" minlength="5" maxlength="1200" required>Does the declared evidence and policy support the proposed recommendation, and what remains unresolved?</textarea></label>
            <fieldset class="diligence-module-picker"><legend>Effect-free modules</legend>${(payload.modules || []).map((module, index) => `<label><input type="checkbox" name="diligence-module" value="${escapeHtml(module.capability_id)}" ${index < 4 ? "checked" : ""}><span><strong>${escapeHtml(module.label)}</strong><small>${escapeHtml(module.purpose)}</small></span><b>${index + 1}</b></label>`).join("")}</fieldset>
            <div class="diligence-form-row"><label><span>Human reviewer ID</span><input id="diligence-actor-id" placeholder="reviewer.name" minlength="3" maxlength="120" required></label><div class="diligence-run-boundary"><strong>No decision is taken</strong><span>The output is a candidate proposal revision for review.</span></div></div>
            <button class="button primary" type="submit" ${workspace.executable ? "" : "disabled"}>${workspace.executable ? "Run temporary investigation" : "Final proposal · inspection only"}</button>
          </form>
        </main>
        <aside class="diligence-lineage"><header><span>Retained work</span><strong>Revisions and run lineage</strong></header>${latestRevision ? `<article class="diligence-revision-card"><span>Candidate revision ${latestRevision.revision_number}</span><strong>${escapeHtml(decisionOutcomeLabel(latestRevision.recommendation))}</strong><p>${escapeHtml(latestRevision.rationale)}</p><small>${(latestRevision.supplemental_evidence_ids || []).length} supplemental evidence items · base proposal unchanged</small></article>` : '<div class="diligence-empty-reference">No candidate revision yet. Run a temporary investigation to create one.</div>'}<details class="diligence-digest"><summary>Immutable lineage</summary><dl><dt>Base proposal</dt><dd>${escapeHtml(proposal.proposal_digest || "Unavailable")}</dd><dt>Current record</dt><dd>${escapeHtml(workspace.record_revision || "Unavailable")}</dd></dl></details></aside>
      </div>
      <section class="diligence-results"><header><div><span>Investigation history</span><h2>Evidence added without rewriting the proposal</h2></div><b>${supplemental.length} supplemental evidence item${supplemental.length === 1 ? "" : "s"}</b></header>${runs.length ? runs.slice().reverse().map((run) => diligenceRunMarkup(run, evidenceById)).join("") : '<div class="empty-state">No due-diligence workflow has run for this proposal.</div>'}</section>`;
  }

  async function loadDueDiligenceWorkspace(preferredId = null) {
    if (labState.dueDiligenceLoading) return;
    const urlProposal = new URLSearchParams(window.location.search).get("proposal");
    const proposalId = preferredId || labState.selectedDecisionId || urlProposal;
    if (!proposalId) {
      labState.dueDiligenceData = null;
      renderDueDiligenceWorkspace();
      return;
    }
    labState.selectedDecisionId = proposalId;
    labState.dueDiligenceLoading = true;
    try {
      labState.dueDiligenceData = await agentApi(`/api/decisions/${encodeURIComponent(proposalId)}/due-diligence`);
      renderDueDiligenceWorkspace();
    } catch (error) {
      $("#diligence-status").textContent = "Unavailable";
      $("#diligence-workspace").innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
    } finally {
      labState.dueDiligenceLoading = false;
    }
  }

  function openDecisionDueDiligence() {
    if (!labState.selectedDecisionId) return;
    const url = new URL(window.location.href);
    url.searchParams.set("proposal", labState.selectedDecisionId);
    window.history.replaceState({ workspace: "decision-diligence" }, "", url);
    switchWorkspace("decision-diligence");
  }

  async function runDecisionDueDiligence(event) {
    event.preventDefault();
    const payload = labState.dueDiligenceData;
    if (!payload?.workspace?.executable) return;
    const actorId = $("#diligence-actor-id").value.trim();
    const capabilityIds = $$('input[name="diligence-module"]:checked').map((item) => item.value);
    if (actorId.length < 3) throw new Error("Enter the human reviewer ID.");
    if (!capabilityIds.length) throw new Error("Select at least one effect-free investigation module.");
    labState.dueDiligenceData = await agentApi(`/api/decisions/${encodeURIComponent(payload.workspace.proposal_id)}/due-diligence/runs`, {
      method: "POST",
      body: JSON.stringify({
        name: $("#diligence-run-name").value.trim(),
        investigation_question: $("#diligence-question").value.trim(),
        capability_ids: capabilityIds,
        candidate_recommendation: $("#diligence-candidate-recommendation").value,
        actor_id: actorId,
        actor_type: "human",
        idempotency_key: `due-diligence-${Date.now()}`,
        expected_revision: payload.workspace.record_revision,
      }),
    });
    renderDueDiligenceWorkspace();
    showToast("Temporary investigation retained. The base proposal remains unchanged.", "success");
  }

  async function attachCycleAgent() {
    if (!labState.cycleSessionId) return;
    const snapshot = await agentApi(`/api/workflow-cycle/sessions/${encodeURIComponent(labState.cycleSessionId)}/agents`, {
      method: "POST",
      body: JSON.stringify({ page_id: $("#cycle-agent-page").value, agent_id: $("#cycle-agent-select").value }),
    });
    renderCycleSnapshot(snapshot);
  }

  function definitionOptions(kind) {
    return (labState.platformArchitecture?.saved_definitions || []).filter((item) => item.identity.kind === kind);
  }

  function populateDefinitionSelect(selector, kind, emptyLabel) {
    const select = $(selector);
    if (!select) return;
    const records = definitionOptions(kind);
    select.innerHTML = records.length
      ? records.map((item) => `<option value="${escapeHtml(item.reference)}">${escapeHtml(item.display_name)} · ${escapeHtml(item.lifecycle_state)} · ${escapeHtml(item.identity.version)}</option>`).join("")
      : `<option value="">${escapeHtml(emptyLabel)}</option>`;
    select.disabled = !records.length;
  }

  function studioProfiles() {
    return labState.platformArchitecture?.studio_profiles || [];
  }

  function selectedStudioProfile() {
    return studioProfiles().find((item) => item.studio_id === labState.selectedStudioId) || studioProfiles()[0] || null;
  }

  function selectedRiskAnalysisPackage() {
    return labState.platformArchitecture?.risk_analysis_packages?.[0] || null;
  }

  function selectedMandateRecord() {
    const records = labState.mandateCatalogue?.records || [];
    return records.find((item) => item.mandate.object_id === labState.selectedMandateId) || records[0] || null;
  }

  function mandateCriterion(rule) {
    if (["in", "not_in"].includes(rule.operator)) return `${rule.operator.replaceAll("_", " ")} · ${(rule.allowed_values || []).join(", ")}`;
    const value = typeof rule.threshold === "number" ? rule.threshold.toLocaleString(undefined, { maximumFractionDigits: 4 }) : rule.threshold;
    return `${rule.operator} ${value}${rule.denominator ? ` · ${rule.denominator.replaceAll("_", " ")}` : ""}`;
  }

  function renderMandateLibrary() {
    const records = labState.mandateCatalogue?.records || [];
    if (!records.length) {
      $("#mandate-library-list").innerHTML = '<div class="mandate-empty"><strong>No mandates</strong><p>No reviewed mandate definitions are available.</p></div>';
      $("#mandate-library-count").textContent = "0";
      return;
    }
    if (!records.some((item) => item.mandate.object_id === labState.selectedMandateId)) labState.selectedMandateId = records[0].mandate.object_id;
    $("#mandate-library-count").textContent = String(records.length);
    $("#mandate-library-list").innerHTML = records.map((item) => `<button class="mandate-library-item ${item.mandate.object_id === labState.selectedMandateId ? "active" : ""}" type="button" data-mandate-id="${escapeHtml(item.mandate.object_id)}">
      <strong>${escapeHtml(item.mandate.name)}</strong>
      <span>${escapeHtml(item.mandate.objective)}</span>
      <small>${item.registry.registered ? `Registry · ${escapeHtml(item.registry.mandate_state)}` : "Reviewed source · not registered"}</small>
    </button>`).join("");
  }

  function renderMandateReview() {
    const record = selectedMandateRecord();
    if (!record) return;
    const mandate = record.mandate;
    const policy = record.risk_policy;
    const validation = record.validation;
    const bindings = Object.fromEntries((validation.bindings || []).map((item) => [item.rule_id, item]));
    const constraints = Object.fromEntries((mandate.constraints || []).map((item) => [item.constraint_id, item]));
    $("#mandate-review").innerHTML = `<header>
      <div><span>MandateVersion · ${escapeHtml(mandate.version)}</span><h2>${escapeHtml(mandate.name)}</h2><p>${escapeHtml(mandate.objective)}</p></div>
      <div class="mandate-review-actions"><small>${escapeHtml(record.registry.mandate_state)} mandate · ${escapeHtml(record.registry.policy_state)} policy</small><div><button class="button ghost" type="button" data-mandate-action="validate">Validate</button>${record.registry.registered ? '<button class="button primary" type="button" data-mandate-action="registry">Open Registry</button>' : '<button class="button primary" type="button" data-mandate-action="register">Register versions</button>'}</div></div>
    </header>
    <div class="mandate-facts"><div><span>Horizon</span><strong>${Math.round(Number(mandate.horizon_seconds) / 31557600)} years</strong></div><div><span>Clauses</span><strong>${mandate.constraints.length}</strong></div><div><span>Metrics ready</span><strong>${validation.constructible_metric_count} / ${validation.rule_count}</strong></div><div><span>Capability gaps</span><strong>${validation.capability_gap_count}</strong></div><div><span>Private data roles</span><strong>${(mandate.data_requirements || []).filter((item) => ["confidential", "restricted"].includes(item.confidentiality)).length}</strong></div></div>
    <div class="mandate-validation ${validation.executable ? "" : "warning"}"><strong>${validation.executable ? "Executable design passed" : validation.valid ? "Structure valid · metric work required" : "Design requires attention"}</strong><div>${(validation.checks || []).map((item) => `<i>${item.passed ? "✓" : "!"} ${escapeHtml(item.label)}</i>`).join("")}</div></div>
    <section class="mandate-rule-list">${policy.rules.map((rule) => {
      const clause = constraints[rule.mandate_constraint_id] || {};
      const binding = bindings[rule.rule_id] || {};
      return `<article class="mandate-rule">
        <div><label>Mandate clause</label><strong>${escapeHtml(clause.statement || rule.mandate_constraint_id)}</strong><small>${escapeHtml((clause.clause_type || "").replaceAll("_", " "))} · ${escapeHtml(clause.source_clause_reference || "")}</small></div>
        <div class="mandate-treatment"><label>System treatment</label><strong>${escapeHtml(rule.system_treatment.replaceAll("_", " "))}</strong><small>${escapeHtml(mandateCriterion(rule))} · ${escapeHtml(rule.evaluation_basis.replaceAll("_", " "))}</small></div>
        <div><label>Evaluation binding</label><strong>${escapeHtml(binding.capability_id || rule.capability_reference)}</strong><p>${escapeHtml(rule.metric_reference)}</p><small>${escapeHtml(binding.metric_status || binding.capability_status || "unavailable")} · ${escapeHtml((binding.required_data_roles || []).join(" · ") || "portfolio context")}</small>${binding.metric_status === "capability_gap" ? `<button class="button text" type="button" data-mandate-capability-gap="${escapeHtml(rule.rule_id)}">Design capability</button>` : ""}</div>
        <div><label>Governance</label><strong>${escapeHtml(rule.governance_route.outcome.replaceAll("_", " "))}</strong><p>${escapeHtml(rule.governance_route.governance_level.replaceAll("_", " "))}</p><small>${escapeHtml(rule.severity)} · no effects</small></div>
      </article>`;
    }).join("")}</section>
    <details class="mandate-sources"><summary>Sources, universe and exact identities</summary><div>
      ${mandate.sources.map((source) => `<article><strong>${escapeHtml(source.title)}</strong><p>${escapeHtml(source.note)}</p><small>${escapeHtml(source.authority_effect)} · ${escapeHtml(source.reference)}</small></article>`).join("")}
      <article><strong>Eligible universe</strong><p>${escapeHtml(mandate.eligible_universe_reference)}</p><small>Binding is evaluated at the assignment as-of time.</small></article>
      ${(mandate.data_requirements || []).map((item) => `<article><strong>${escapeHtml(item.data_role.replaceAll("_", " "))}</strong><p>${escapeHtml(item.description)}</p><small>${escapeHtml(item.confidentiality)} · ${escapeHtml(item.temporal_basis)} · bound by exact experiment assignment · missing remains unable to assess</small></article>`).join("")}
      <article><strong>Registry identities</strong><p>${escapeHtml(record.registry.mandate_reference)}</p><p>${escapeHtml(record.registry.policy_reference)}</p><small>Exact immutable versions are admitted together.</small></article>
    </div></details>`;
  }

  function populateMandateDesigner() {
    const records = labState.mandateCatalogue?.records || [];
    const select = $("#mandate-design-base");
    select.innerHTML = records.map((item) => `<option value="${escapeHtml(item.mandate.object_id)}">${escapeHtml(item.mandate.name)}</option>`).join("");
    const record = selectedMandateRecord();
    if (!record) return;
    select.value = record.mandate.object_id;
    if (!$("#mandate-design-name").value) $("#mandate-design-name").value = `${record.mandate.name} — new version`;
    if (!$("#mandate-design-objective").value) $("#mandate-design-objective").value = record.mandate.objective;
  }

  async function initializeMandateStudio(force = false) {
    if (!force && labState.mandateCatalogue) {
      renderMandateLibrary();
      renderMandateReview();
      populateMandateDesigner();
      return;
    }
    labState.mandateCatalogue = await agentApi("/api/studios/mandates/catalogue");
    labState.selectedMandateId = labState.selectedMandateId || labState.mandateCatalogue.records?.[0]?.mandate?.object_id || null;
    renderMandateLibrary();
    renderMandateReview();
    populateMandateDesigner();
  }

  async function validateSelectedMandate() {
    const record = selectedMandateRecord();
    if (!record) return;
    const validation = await agentApi("/api/studios/mandates/validate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mandate_id: record.mandate.object_id }) });
    record.validation = validation;
    renderMandateReview();
    showToast(validation.valid ? "Mandate and policy bindings passed validation." : "Mandate requires design review.", validation.valid ? "success" : "error");
  }

  async function registerSelectedMandate() {
    const record = selectedMandateRecord();
    if (!record || record.registry.registered) return;
    if (!window.confirm(`Register ${record.mandate.name} and its exact RiskPolicySet as development candidates?\n\nThis saves two immutable Registry definitions. It does not publish them, run an experiment, interpret law, or create portfolio effects.`)) return;
    await agentApi("/api/studios/mandates/register", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mandate_id: record.mandate.object_id, actor: "local.developer" }) });
    await Promise.all([loadPlatformWorkspaces(true), initializeMandateStudio(true), loadRegistryCatalogue()]);
    showToast("MandateVersion and RiskPolicySet registered as candidates.", "success");
  }

  function openSelectedMandateInRegistry() {
    switchWorkspace("registry", true, "system");
    $("#registry-kind-filter").value = "mandate";
    $("#registry-search").value = selectedMandateRecord()?.mandate.object_id || "";
    renderRegistryList();
  }

  async function prepareMandateDesignPreview(event) {
    event.preventDefault();
    const result = await agentApi("/api/studios/mandates/design-preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
      base_mandate_id: $("#mandate-design-base").value,
      name: $("#mandate-design-name").value.trim(),
      objective: $("#mandate-design-objective").value.trim(),
      change_request: $("#mandate-design-change").value.trim(),
    }) });
    labState.mandateDesignPreview = result;
    $("#mandate-design-preview").innerHTML = `<div class="mandate-design-brief"><header><span>Design brief · diff only</span><strong>${escapeHtml(result.name)}</strong></header><p>${escapeHtml(result.objective)}</p><p><b>Requested change:</b> ${escapeHtml(result.requested_diff)}</p><ul>${result.required_review.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul><pre>${escapeHtml(result.studio_codex_brief)}</pre><footer><button class="button primary" type="button" data-mandate-design-action="copy">Copy Studio–Codex brief</button></footer></div>`;
  }

  function renderRiskAnalysisPackage() {
    const panel = $("#studio-risk-package-preview");
    if (!panel) return;
    const profile = selectedStudioProfile();
    const record = selectedRiskAnalysisPackage();
    if (profile?.studio_id !== "risk_analysis" || !record) {
      panel.classList.add("hidden");
      panel.innerHTML = "";
      return;
    }
    const definition = record.definition;
    const rows = (items, render) => items.map(render).join("");
    const deterministic = definition.capability_roles.filter((item) => item.implementation_kind === "deterministic");
    const agentBacked = definition.capability_roles.filter((item) => item.implementation_kind === "agent_backed");
    panel.classList.remove("hidden");
    panel.innerHTML = `<header class="risk-package-header">
      <div><span>Reference package · ${escapeHtml(definition.version)}</span><h2>${escapeHtml(definition.display_name)}</h2><p>${escapeHtml(definition.risk_question)}</p></div>
      <div><b>${escapeHtml(record.registry_state)}</b>${record.indexed ? "" : '<button class="button primary" id="studio-risk-package-index" type="button">Save candidate</button>'}</div>
    </header>
    <div class="risk-package-summary">
      <span><b>${definition.data_roles.length}</b> semantic data roles</span>
      <span><b>${definition.capability_roles.length}</b> analytical roles</span>
      <span><b>${definition.output_fields.length}</b> ArchitectureOutput fields</span>
      <span><b>2</b> value-admission paths</span>
    </div>
    <div class="risk-package-grid">
      <article><header><span>Data</span><b>Semantic roles</b></header>${rows(definition.data_roles, (item) => `<div class="risk-package-row"><strong>${escapeHtml(item.role_id.replaceAll("_", " "))}</strong><p>${escapeHtml(item.description)}</p><small>${escapeHtml(item.default_binding)} · ${escapeHtml(item.as_of_rule.replaceAll("_", " "))}</small></div>`)}</article>
      <article><header><span>Analysis</span><b>Hybrid resolution</b></header><div class="risk-package-group"><em>Deterministic</em>${rows(deterministic, (item) => `<div class="risk-package-row"><strong>${escapeHtml(item.role_id.replaceAll("_", " "))}</strong><p>${escapeHtml(item.objective)}</p><small>${escapeHtml(item.default_implementation)}${item.substitutable ? " · substitutable" : ""}</small></div>`)}</div><div class="risk-package-group"><em>Agent-backed</em>${rows(agentBacked, (item) => `<div class="risk-package-row"><strong>${escapeHtml(item.role_id.replaceAll("_", " "))}</strong><p>${escapeHtml(item.objective)}</p><small>${escapeHtml(item.default_implementation)} · bounded child run</small></div>`)}</div></article>
      <article><header><span>Output</span><b>Retain only valuable findings</b></header>${rows(definition.output_fields, (item) => `<div class="risk-package-row"><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.question)}</p><small>Structured field · empty allowed · evidence-bound</small></div>`)}</article>
      <article><header><span>Controls</span><b>Replayable core</b></header>
        <div class="risk-package-row"><strong>Temporal envelope</strong><p>All inputs and supplemental queries inherit the package as-of boundary.</p><small>${escapeHtml(definition.temporal_envelope.eligibility_field)} · pinned revisions · point-in-time mappings</small></div>
        <div class="risk-package-row"><strong>Value gate</strong><p>Decision value or research value may admit a finding. Repetition and unsupported inference are penalised.</p><small>Silence is a valid output</small></div>
        <div class="risk-package-row"><strong>Output gate</strong><p>Deterministic schema and evidence validation plus one representative human review.</p><small>${definition.output_validation.fixture_cases.map((item) => escapeHtml(item.replaceAll("_", " "))).join(" · ")}</small></div>
        <div class="risk-package-row"><strong>Supplemental expansion</strong><p>An agent may add analysis without mutating the stable package core.</p><small>Successful additions become revision proposals</small></div>
      </article>
    </div>
    <section class="risk-package-runner" aria-label="Apply package to an isolated fixture">
      <header><div><span>Apply</span><b>Isolated package run</b></div><small>Effect-free · human review required</small></header>
      <div class="risk-package-run-controls">
        <label><span>Data</span><select id="risk-package-fixture"><option value="reviewed_synthetic">Reviewed synthetic fixture</option><option disabled>Licensed real · bindings not validated</option><option disabled>Generated simulation · future slice</option></select></label>
        <label><span>Narrative</span><select id="risk-package-narrative-mode"><option value="deterministic_preview">Deterministic preview · no LLM</option><option value="live_llm">Live LLM · explicit call</option></select></label>
        <label><span>Model</span><select id="risk-package-model"><option value="gpt-5.6-luna">GPT-5.6 Luna · lowest cost</option></select></label>
        <button class="button primary" id="risk-package-run" type="button">Run isolated fixture</button>
      </div>
      <div class="risk-package-run-history">
        <select id="risk-package-recent-runs" aria-label="Recent Risk Analysis Package runs"><option value="">No saved runs</option></select>
        <button class="button" id="risk-package-open-run" type="button" disabled>Open run</button>
        <button class="button" id="risk-package-delete-run" type="button" disabled>Delete run</button>
        <span id="risk-package-run-status">Ready</span>
      </div>
      <div class="risk-package-run-review hidden" id="risk-package-run-review" aria-live="polite"></div>
    </section>`;
    $("#studio-risk-package-index")?.addEventListener("click", () => indexRiskAnalysisPackage().catch((error) => showToast(error.message, "error")));
    $("#risk-package-run")?.addEventListener("click", () => runRiskAnalysisPackage().catch((error) => {
      $("#risk-package-run-status").textContent = error.message;
      showToast(error.message, "error");
    }));
    $("#risk-package-open-run")?.addEventListener("click", () => openRiskAnalysisPackageRun().catch((error) => showToast(error.message, "error")));
    $("#risk-package-delete-run")?.addEventListener("click", () => deleteRiskAnalysisPackageRun().catch((error) => showToast(error.message, "error")));
    loadRiskAnalysisPackageRuns().catch((error) => {
      $("#risk-package-run-status").textContent = `Run repository unavailable · ${error.message}`;
    });
  }

  function riskPackageRunLabel(run) {
    const created = run.created_at ? new Date(run.created_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" }) : run.run_id;
    return `${created} · ${run.narrative_mode === "live_llm" ? "live LLM" : "deterministic"} · ${run.finding_count || 0} findings`;
  }

  async function loadRiskAnalysisPackageRuns(selectedRunId = "") {
    const select = $("#risk-package-recent-runs");
    if (!select) return;
    const response = await agentApi("/api/studios/risk-analysis/runs");
    const runs = response.runs || [];
    select.innerHTML = runs.length
      ? runs.map((run) => `<option value="${escapeHtml(run.run_id)}">${escapeHtml(riskPackageRunLabel(run))}</option>`).join("")
      : '<option value="">No saved runs</option>';
    if (selectedRunId && runs.some((run) => run.run_id === selectedRunId)) select.value = selectedRunId;
    $("#risk-package-open-run").disabled = !runs.length;
    $("#risk-package-delete-run").disabled = !runs.length;
  }

  async function runRiskAnalysisPackage() {
    const button = $("#risk-package-run");
    const status = $("#risk-package-run-status");
    button.disabled = true;
    status.textContent = $("#risk-package-narrative-mode").value === "live_llm"
      ? "Running capabilities and one explicit LLM narrative pass…"
      : "Running capabilities…";
    try {
      const result = await agentApi("/api/studios/risk-analysis/runs", {
        method: "POST",
        body: JSON.stringify({
          fixture_id: $("#risk-package-fixture").value,
          narrative_mode: $("#risk-package-narrative-mode").value,
          model: $("#risk-package-model").value,
        }),
      });
      renderRiskAnalysisPackageRun(result);
      await loadRiskAnalysisPackageRuns(result.manifest.run_id);
      status.textContent = `Completed · ${result.manifest.capability_call_count} capability calls · ${result.manifest.finding_count} findings`;
      showToast("Risk Analysis Package run completed and saved.", "success");
    } finally {
      button.disabled = false;
    }
  }

  async function openRiskAnalysisPackageRun() {
    const runId = $("#risk-package-recent-runs")?.value;
    if (!runId) return;
    $("#risk-package-run-status").textContent = "Loading saved run…";
    const result = await agentApi(`/api/studios/risk-analysis/runs/${encodeURIComponent(runId)}`);
    renderRiskAnalysisPackageRun(result);
    $("#risk-package-run-status").textContent = `Loaded ${runId}`;
  }

  async function deleteRiskAnalysisPackageRun() {
    const runId = $("#risk-package-recent-runs")?.value;
    if (!runId || !window.confirm(`Delete isolated run ${runId}?\n\nIts dedicated local folder and saved output files will be permanently removed.`)) return;
    await agentApi(`/api/studios/risk-analysis/runs/${encodeURIComponent(runId)}`, { method: "DELETE" });
    $("#risk-package-run-review")?.classList.add("hidden");
    $("#risk-package-run-status").textContent = `Deleted ${runId} · not recoverable`;
    await loadRiskAnalysisPackageRuns();
    showToast("Isolated run folder deleted.", "success");
  }

  function renderRiskAnalysisPackageRun(result) {
    const review = $("#risk-package-run-review");
    if (!review) return;
    const manifest = result.manifest || {};
    const contents = result.contents || {};
    const input = contents["input.json"] || {};
    const fixture = input.fixture || {};
    const snapshot = fixture.snapshot || {};
    const packet = fixture.evidence_packet || {};
    const receipts = contents["capability-receipts.json"] || [];
    const modelReceipt = contents["model-receipt.json"] || {};
    const validation = contents["output-validation.json"] || {};
    const output = contents["architecture-output.json"] || {};
    const positions = snapshot.positions || [];
    const warnings = packet.warnings || [];
    const providerLabel = modelReceipt.provider === "none"
      ? "No LLM · deterministic narrative"
      : `${modelReceipt.model || "OpenAI model"} · ${Number(modelReceipt.input_tokens || 0).toLocaleString()} in / ${Number(modelReceipt.output_tokens || 0).toLocaleString()} out`;
    review.classList.remove("hidden");
    review.innerHTML = `<div class="risk-run-heading">
      <div><span>Reviewed synthetic</span><b>ArchitectureOutput</b><small>${escapeHtml(manifest.run_id || "")}</small></div>
      <div><strong>${manifest.status === "completed" ? "Validated" : "Review validation"}</strong><small>${escapeHtml(providerLabel)}</small></div>
    </div>
    <div class="risk-run-facts">
      <span><b>${Number(manifest.capability_call_count || 0)}</b> actual capability calls</span>
      <span><b>${Number(manifest.finding_count || 0)}</b> admitted findings</span>
      <span><b>${positions.length}</b> named holdings</span>
      <span><b>${Number(packet.observation_count || 0).toLocaleString()}</b> return observations</span>
    </div>
    <div class="risk-run-layout">
      <article class="risk-run-dossier"><header><span>Outcome</span><b>Evidence-backed structured output</b></header><p class="risk-run-premise">${escapeHtml(input.package?.risk_question || "")}</p><div class="risk-run-report">${(output.findings || []).length ? output.findings.map((finding) => `<section><h3>${escapeHtml(finding.title)}</h3><p>${escapeHtml(finding.markdown)}</p><small>${escapeHtml((finding.evidence_ids || []).join(" · "))}</small></section>`).join("") : "<p>No material finding was admitted.</p>"}</div></article>
      <aside class="risk-run-evidence">
        <section><header><span>Input</span><b>Frozen context</b></header><dl><div><dt>As of</dt><dd>${escapeHtml(packet.as_of || snapshot.as_of || "—")}</dd></div><div><dt>Fixture</dt><dd>Reviewed deterministic synthetic data</dd></div>${positions.map((position) => `<div><dt>${escapeHtml(position.instrument_id)}</dt><dd>${money(position.market_value)}</dd></div>`).join("")}</dl></section>
        <section><header><span>Execution</span><b>Capability receipts</b></header><div class="risk-run-receipts">${receipts.map((receipt) => `<div><i>${receipt.sequence}</i><span><strong>${escapeHtml(receipt.role_id.replaceAll("_", " "))}</strong><small>${escapeHtml(receipt.resolved_implementation)} · ${Number(receipt.elapsed_ms || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })} ms · ${escapeHtml(receipt.status)}</small></span></div>`).join("")}</div></section>
        <section><header><span>Validation</span><b>${validation.valid ? "Passed" : "Needs review"}</b></header><p>${validation.valid ? "Schema and evidence references reconcile." : escapeHtml((validation.errors || []).join(" · ") || "Inspect validation receipt.")}</p>${warnings.length ? `<small>${warnings.map(escapeHtml).join(" · ")}</small>` : ""}</section>
        <section><header><span>Files</span><b>${(manifest.files || []).length} saved</b></header><div class="risk-run-files">${(manifest.files || []).map((file) => `<span><b>${escapeHtml(file.name)}</b><small>${Number(file.bytes || 0).toLocaleString()} B</small></span>`).join("")}</div><p class="risk-run-folder">${escapeHtml(manifest.folder || "")}</p></section>
      </aside>
    </div>`;
    review.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function indexRiskAnalysisPackage() {
    const record = selectedRiskAnalysisPackage();
    if (!record || record.indexed) return;
    if (!window.confirm(`Save ${record.definition.display_name} as a Registry candidate?\n\nThis indexes the reviewed definition and its exact capability relationships. It does not run or publish the package.`)) return;
    await agentApi("/api/registry/index", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ identity: record.registry_identity, actor: "local.developer" }) });
    await refreshDefinitionConsumers();
    renderStudioProfile(false);
    showToast("Risk Analysis Package saved as a candidate.", "success");
  }

  function capabilityRecord(capabilityId = labState.selectedCapabilityId) {
    return (labState.capabilityCatalogue?.capabilities || []).find((item) => item.capability_id === capabilityId) || null;
  }

  function capabilityValue(value, format) {
    if (value === null || value === undefined) return "—";
    if (format === "percent") return percent(value, 2);
    if (format === "money") return money(value);
    if (format === "integer") return Number(value).toLocaleString();
    if (typeof value === "number") return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
    return String(value);
  }

  function renderCapabilityBlueprint(proposal = null) {
    const assessment = labState.capabilityAssessment;
    if (!proposal && !labState.capabilityDraftBlueprint && assessment?.discussion_status === "concluded" && assessment.design_target !== "capability") {
      $("#capability-blueprint").innerHTML = `<header><div><span>Studio design proposal</span><strong>${escapeHtml(assessment.blueprint.display_name)}</strong></div><i>${escapeHtml(assessment.design_target)}</i></header>
        <p>${escapeHtml(assessment.consensus_summary)}</p>
        <dl><div><dt>Outcome</dt><dd>${escapeHtml(assessment.requirement)}</dd></div><div><dt>Capabilities</dt><dd>${(assessment.proposed_capability_ids || []).map(escapeHtml).join(" · ") || "No registered capability proposed yet"}</dd></div><div><dt>Authority</dt><dd>Proposal only · the owning Studio must validate and approve the object</dd></div></dl>
        <div class="capability-blueprint-actions"><button class="button primary" type="button" data-capability-studio-handoff>Save to ${escapeHtml(assessment.design_target)} Studio</button><button class="button ghost" type="button" data-capability-draft-action="revise">Revise in chat</button></div>`;
      return;
    }
    const blueprint = proposal?.blueprint || labState.capabilityDraftBlueprint;
    if (!blueprint) {
      const message = assessment?.discussion_status === "concluded"
        ? "Consensus recorded. Choose reuse, compose, improve, new or blocked to compile a draft blueprint."
        : "Continue the design conversation and resolve its open questions before compiling a blueprint.";
      $("#capability-blueprint").innerHTML = `<div class="capability-empty">${escapeHtml(message)}</div>`;
      return;
    }
    const status = proposal?.status || `draft · ${labState.capabilityDraftDecision || "decision pending"}`;
    const codex = proposal?.studio_codex || {};
    const host = blueprint.host_binding || null;
    const dependencies = proposal?.dependency_map || assessment?.dependency_map || [];
    $("#capability-blueprint").innerHTML = `<header><div><span>Blueprint</span><strong>${escapeHtml(blueprint.display_name)}</strong></div><i>${escapeHtml(status.replaceAll("_", " "))}</i></header>
      <p>${escapeHtml(blueprint.outcome)}</p>
      <dl>
        <div><dt>Input</dt><dd>${(blueprint.inputs || []).map((item) => escapeHtml(item.semantic_role)).join(" · ")}</dd></div>
        <div><dt>Output</dt><dd>${escapeHtml(blueprint.output_contract)} · ${escapeHtml(blueprint.renderer)}</dd></div>
        <div><dt>Execution</dt><dd>${escapeHtml(blueprint.implementation_class.replaceAll("_", " "))}</dd></div>
        ${host ? `<div><dt>Host</dt><dd>${escapeHtml(host.host_id)} · ${escapeHtml(host.surface_kind.replaceAll("_", " "))}</dd></div><div><dt>Framework</dt><dd>${escapeHtml(host.framework)} · ${escapeHtml(host.connection_contract)}</dd></div>` : ""}
        <div><dt>Dependencies</dt><dd>${dependencies.length ? dependencies.map((item) => `${escapeHtml(item.display_name)} · ${escapeHtml(item.status)}`).join("<br>") : "None"}</dd></div>
        <div><dt>Effect</dt><dd>${escapeHtml(blueprint.effect_profile.replaceAll("_", " "))}</dd></div>
      </dl>
      ${proposal ? `<div class="capability-blueprint-actions">
        ${status === "identified" ? '<button class="button primary" type="button" data-capability-transition="approve">Approve</button>' : ""}
        ${status === "human_approved" ? '<button class="button primary" type="button" data-capability-transition="prepare_codex">Prepare Studio–Codex</button>' : ""}
        ${["identified", "human_approved", "ready_for_studio_codex"].includes(status) ? '<button class="button ghost" type="button" data-capability-transition="return_to_design">Revise</button>' : ""}
        <button class="button ghost danger" type="button" data-capability-delete-proposal>Delete</button>
      </div>` : '<div class="capability-blueprint-actions"><button class="button primary" type="button" data-capability-draft-action="approve">Approve blueprint</button><button class="button ghost" type="button" data-capability-draft-action="revise">Revise in chat</button></div>'}
      ${codex.build_brief ? `<details class="capability-codex-brief" open><summary>Studio–Codex brief</summary><pre>${escapeHtml(codex.build_brief)}</pre><button class="button ghost" type="button" id="capability-copy-codex">Copy brief</button><button class="button primary" type="button" disabled>Start session · PLATFORM-P12</button></details>` : ""}`;
  }

  function capabilityDependencyMarkup(dependencies = []) {
    if (!dependencies.length) return "";
    return `<details class="capability-dependencies" open><summary>Dependency map · ${dependencies.length}</summary><div>${dependencies.map((item) => {
      const canDiscuss = item.dependency_type === "proposed_capability";
      const gate = item.blocks_design ? "design blocked" : item.blocks_build ? "build dependency" : "non-blocking";
      return `<article><header><b>${escapeHtml(item.display_name)}</b><i>${escapeHtml(item.status)} · ${escapeHtml(gate)}</i></header><p>${escapeHtml(item.purpose)}</p><small>Provides ${escapeHtml(item.provides)}</small>${canDiscuss ? `<button type="button" data-capability-dependency="${escapeHtml(item.dependency_id)}">Discuss dependency</button>` : ""}</article>`;
    }).join("")}</div></details>`;
  }

  function renderCapabilityConversation(error = null) {
    const values = labState.capabilityDesignMessages || [];
    const assessment = labState.capabilityAssessment;
    const latestIndex = values.length - 1;
    $("#capability-chat").innerHTML = values.length ? values.map((item, index) => {
      const turn = item.assessment || null;
      const latestAssistant = item.role === "assistant" && index === latestIndex;
      const quiz = latestAssistant ? turn?.quiz : null;
      const plan = latestAssistant ? turn?.plan_steps || [] : [];
      const candidates = latestAssistant ? turn?.candidates || [] : [];
      const dependencies = latestAssistant ? turn?.dependency_map || [] : [];
      return `<article class="${item.role === "assistant" ? "assistant" : "user"}"><span>${item.role === "assistant" ? escapeHtml((turn?.intent || "design partner").replaceAll("_", " ")) : "You"}</span><p>${escapeHtml(item.content)}</p>
        ${latestAssistant && turn?.rationale ? `<small>${escapeHtml(turn.rationale)}</small>` : ""}
        ${plan.length ? `<details class="capability-turn-plan"><summary>Working plan</summary>${plan.map((step) => `<p>${escapeHtml(step)}</p>`).join("")}</details>` : ""}
        ${candidates.length ? `<div class="capability-candidates">${candidates.slice(0, 4).map((candidate) => `<button type="button" data-select-capability="${escapeHtml(candidate.capability_id)}"><b>${escapeHtml(candidate.name)}</b><small>${Math.round(Number(candidate.score || 0) * 100)}% match</small></button>`).join("")}</div>` : ""}
        ${capabilityDependencyMarkup(dependencies)}
        ${quiz ? `<div class="capability-quiz"><strong>${escapeHtml(quiz.question)}</strong><div>${quiz.options.map((option, optionIndex) => `<button type="button" data-capability-quiz-option="${optionIndex}"><b>${escapeHtml(option.label)}</b><span>${escapeHtml(option.answer)}</span><small>${escapeHtml(option.explanation)}</small></button>`).join("")}<button class="other" type="button" data-capability-quiz-other><b>Other answer</b><span>Write a different answer in your own words.</span></button></div></div>` : ""}
      </article>`;
    }).join("") : "<p>Describe the intended outcome. The design partner will examine feasibility and ask focused questions before compiling anything.</p>";
    if (error) $("#capability-chat").insertAdjacentHTML("beforeend", `<p class="capability-chat-error">${escapeHtml(error)}</p>`);
    if (!assessment) return;
    $("#capability-token-note").textContent = assessment.model_receipt?.status === "failed"
      ? "Luna unavailable · deterministic result"
      : assessment.model_receipt?.provider === "none"
        ? `${Number(assessment.estimated_prompt_characters || 0).toLocaleString()} chars · no LLM`
        : `${Number(assessment.model_receipt.input_tokens || 0).toLocaleString()} input · ${Number(assessment.model_receipt.output_tokens || 0).toLocaleString()} output · ${(assessment.model_receipt.calls || []).length || 1} call${(assessment.model_receipt.calls || []).length === 1 ? "" : "s"}`;
    const consensusText = assessment.discussion_status === "concluded"
      ? "Consensus recorded. Choose the implementation path to compile a draft."
      : assessment.discussion_status === "consensus_ready"
        ? "No material open questions remain. Record consensus when the shared design is correct."
        : `${Number((assessment.open_questions || []).length).toLocaleString()} open design question${(assessment.open_questions || []).length === 1 ? "" : "s"} · continue the discussion.`;
    $("#capability-consensus").querySelector("span").textContent = consensusText;
    $("#capability-conclude-design").classList.toggle("hidden", assessment.discussion_status !== "consensus_ready");
    $("#capability-decisions").classList.toggle("hidden", assessment.discussion_status !== "concluded" || assessment.design_target !== "capability");
    $$('[data-capability-decision]').forEach((button) => button.classList.toggle("recommended", button.dataset.capabilityDecision === assessment.recommendation));
    $("#capability-chat").scrollTop = $("#capability-chat").scrollHeight;
  }

  async function assessCapabilityRequirement(event) {
    event.preventDefault();
    const requirement = $("#capability-requirement").value.trim();
    if (requirement.length < 8) return;
    const submit = $("#capability-prompt button[type='submit']");
    submit.disabled = true;
    submit.textContent = "Thinking";
    const conversation = labState.capabilityDesignMessages.map((item) => ({ role: item.role, content: item.content }));
    labState.capabilityDesignMessages.push({ role: "user", content: requirement });
    renderCapabilityConversation();
    try {
      const assessment = await agentApi("/api/studios/capabilities/assess", {
        method: "POST",
        body: JSON.stringify({ requirement, conversation, conclude: false, use_llm: $("#capability-use-ai").checked, session_id: labState.capabilityDesignSessionId, parent_session_id: labState.capabilityDesignParentSessionId }),
      });
      labState.capabilityAssessment = assessment;
      labState.capabilityDesignSessionId = assessment.session_id;
      const assistantContent = assessment.next_question && !assessment.response.includes(assessment.next_question)
        ? `${assessment.response}\n\n${assessment.next_question}`
        : assessment.response;
      labState.capabilityDesignMessages.push({ role: "assistant", content: assistantContent, assessment });
      $("#capability-requirement").value = "";
      labState.capabilityDraftBlueprint = null;
      labState.capabilityDraftDecision = null;
      renderCapabilityConversation();
      renderCapabilityBlueprint();
      await loadCapabilityDesignSessions();
    } catch (error) {
      renderCapabilityConversation(error.message);
    } finally {
      submit.disabled = false;
      submit.textContent = "Discuss";
    }
  }

  async function decideCapability(decision) {
    if (!labState.capabilityAssessment || labState.capabilityAssessment.discussion_status !== "concluded") return;
    const compiled = await agentApi("/api/studios/capabilities/blueprints", {
      method: "POST",
      body: JSON.stringify({ assessment: labState.capabilityAssessment, decision }),
    });
    labState.capabilityDraftDecision = decision;
    labState.capabilityDraftBlueprint = compiled.blueprint;
    labState.selectedCapabilityProposalId = null;
    renderCapabilityProposals();
    renderCapabilityBlueprint();
    showToast(`${decision[0].toUpperCase()}${decision.slice(1)} blueprint compiled locally. Nothing has been added to the backlog.`, "success");
  }

  function capabilityConversationPayload() {
    const values = labState.capabilityDesignMessages || [];
    let userIndex = -1;
    for (let index = values.length - 1; index >= 0; index -= 1) {
      if (values[index].role === "user") { userIndex = index; break; }
    }
    if (userIndex < 0) return null;
    return {
      requirement: values[userIndex].content,
      conversation: values.filter((_, index) => index !== userIndex).map((item) => ({ role: item.role, content: item.content })),
    };
  }

  async function concludeCapabilityDesign() {
    const payload = capabilityConversationPayload();
    if (!payload) return;
    const button = $("#capability-conclude-design");
    button.disabled = true;
    try {
      const assessment = await agentApi("/api/studios/capabilities/assess", {
        method: "POST",
        body: JSON.stringify({ ...payload, conclude: true, use_llm: $("#capability-use-ai").checked, session_id: labState.capabilityDesignSessionId, parent_session_id: labState.capabilityDesignParentSessionId }),
      });
      labState.capabilityAssessment = assessment;
      labState.capabilityDesignSessionId = assessment.session_id;
      labState.capabilityDesignMessages.push({ role: "assistant", content: assessment.discussion_status === "concluded" ? assessment.consensus_summary : assessment.response, assessment });
      renderCapabilityConversation();
      renderCapabilityBlueprint();
      await loadCapabilityDesignSessions();
    } finally {
      button.disabled = false;
    }
  }

  function resetCapabilityDesign() {
    labState.capabilityAssessment = null;
    labState.capabilityDesignMessages = [];
    labState.capabilityDesignSessionId = null;
    labState.capabilityDesignParentSessionId = null;
    labState.capabilityDraftBlueprint = null;
    labState.capabilityDraftDecision = null;
    labState.selectedCapabilityProposalId = null;
    $("#capability-requirement").value = "";
    $("#capability-token-note").textContent = "";
    $("#capability-decisions").classList.add("hidden");
    $("#capability-conclude-design").classList.add("hidden");
    $("#capability-consensus").querySelector("span").textContent = "Refine the design before choosing an implementation path.";
    renderCapabilityConversation();
    renderCapabilityBlueprint();
    renderCapabilityProposals();
  }

  async function approveCapabilityDraft() {
    if (!labState.capabilityAssessment || !labState.capabilityDraftDecision) return;
    const proposal = await agentApi("/api/studios/capabilities/proposals/approve", {
      method: "POST",
      body: JSON.stringify({ assessment: labState.capabilityAssessment, decision: labState.capabilityDraftDecision }),
    });
    labState.selectedCapabilityProposalId = proposal.proposal_id;
    labState.capabilityDraftBlueprint = null;
    labState.capabilityDraftDecision = null;
    await loadCapabilityProposals();
    renderCapabilityBlueprint(proposal);
    showToast("Approved blueprint added to the proposal backlog.", "success");
  }

  function reviseCapabilityDraft() {
    labState.capabilityDraftBlueprint = null;
    labState.capabilityDraftDecision = null;
    $("#capability-requirement").value = "I would like to revise the compiled blueprint by changing: ";
    $("#capability-requirement").focus();
    renderCapabilityBlueprint();
    showToast("Draft discarded. Describe the change in the design conversation.", "success");
  }

  async function deleteCapabilityProposal() {
    const proposalId = labState.selectedCapabilityProposalId;
    if (!proposalId) return;
    const proposal = labState.capabilityProposals.find((item) => item.proposal_id === proposalId);
    if (!window.confirm(`Delete ${proposal?.blueprint?.display_name || proposalId} from the local proposal backlog?\n\nCapabilities, Registry definitions, fixtures and source data are unaffected.`)) return;
    await agentApi(`/api/studios/capabilities/proposals/${encodeURIComponent(proposalId)}`, { method: "DELETE" });
    labState.selectedCapabilityProposalId = null;
    await loadCapabilityProposals();
    renderCapabilityBlueprint();
    showToast("Proposal deleted from the local backlog.", "success");
  }

  async function sendCapabilityDesignToStudio() {
    const assessment = labState.capabilityAssessment;
    if (!assessment || assessment.discussion_status !== "concluded" || assessment.design_target === "capability") return;
    const proposal = await agentApi("/api/studios/design-proposals", {
      method: "POST",
      body: JSON.stringify({ assessment, actor: "local.human" }),
    });
    const targetMap = { agent: "agent", workflow: "workflow", dashboard: "dashboard", report: "report", package: "risk_analysis" };
    const studioId = targetMap[assessment.design_target];
    if (studioId) {
      openStudio(studioId);
      $("#studio-object-name").value = proposal.title || "Design proposal";
      $("#studio-object-brief").value = `${proposal.outcome}\n\nConsensus\n${proposal.consensus_summary}`;
      $("#studio-capability-brief").value = `Proposed registered capabilities\n${(proposal.proposed_capability_ids || []).join("\n") || "No capability selected"}\n\nProposal only. Validate the target object's own contract before approval.`;
    }
    showToast(`Design proposal saved to the ${assessment.design_target} Studio. It has not been finalized.`, "success");
  }

  async function transitionCapabilityProposal(action) {
    const proposalId = labState.selectedCapabilityProposalId;
    if (!proposalId) return;
    const proposal = await agentApi(`/api/studios/capabilities/proposals/${encodeURIComponent(proposalId)}/transition`, {
      method: "POST",
      body: JSON.stringify({ action, actor: "local.human" }),
    });
    await loadCapabilityProposals();
    renderCapabilityBlueprint(proposal);
    if (action === "return_to_design") {
      const requirement = $("#capability-requirement");
      requirement.value = proposal.requirement || "";
      requirement.focus();
      showToast("Proposal returned to design. Update the requirement and assess it again.", "success");
    }
  }

  function renderCapabilityProposals() {
    const values = labState.capabilityProposals || [];
    $("#capability-proposal-count").textContent = String(values.length);
    $("#capability-proposal-list").innerHTML = values.length ? `<table class="capability-proposal-table"><thead><tr><th>Proposal</th><th>Status</th></tr></thead><tbody>${values.map((item) => `<tr tabindex="0" class="${item.proposal_id === labState.selectedCapabilityProposalId ? "active" : ""}" data-capability-proposal="${escapeHtml(item.proposal_id)}"><td><b>${escapeHtml(item.blueprint?.display_name || item.proposal_id)}</b><small>${escapeHtml(item.decision)} · ${escapeHtml(item.updated_at.slice(0, 10))}</small></td><td>${escapeHtml(item.status.replaceAll("_", " "))}</td></tr>`).join("")}</tbody></table>` : '<div class="capability-empty">No proposals yet.</div>';
  }

  async function loadCapabilityProposals() {
    const payload = await agentApi("/api/studios/capabilities/proposals");
    labState.capabilityProposals = payload.proposals || [];
    renderCapabilityProposals();
  }

  function renderCapabilityDesignSessions() {
    const select = $("#capability-session-select");
    if (!select) return;
    const sessions = labState.capabilityDesignSessions || [];
    select.innerHTML = '<option value="">Saved discussions</option>' + sessions.map((item) => {
      const relation = item.parent_session_id ? " · dependency" : "";
      return `<option value="${escapeHtml(item.session_id)}">${escapeHtml(item.title)} · r${Number(item.revision)}${relation}</option>`;
    }).join("");
    if (labState.capabilityDesignSessionId && sessions.some((item) => item.session_id === labState.capabilityDesignSessionId)) select.value = labState.capabilityDesignSessionId;
    $("#capability-load-session").disabled = !select.value;
    $("#capability-delete-session").disabled = !select.value;
  }

  async function loadCapabilityDesignSessions() {
    const payload = await agentApi("/api/studios/capabilities/design-sessions");
    labState.capabilityDesignSessions = payload.sessions || [];
    renderCapabilityDesignSessions();
  }

  async function resumeCapabilityDesignSession() {
    const sessionId = $("#capability-session-select").value;
    if (!sessionId) return;
    const session = await agentApi(`/api/studios/capabilities/design-sessions/${encodeURIComponent(sessionId)}`);
    const messages = (session.messages || []).map((item) => ({ role: item.role, content: item.content }));
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      if (messages[index].role === "assistant") { messages[index].assessment = session.assessment; break; }
    }
    labState.capabilityDesignMessages = messages;
    labState.capabilityAssessment = session.assessment || null;
    labState.capabilityDesignSessionId = session.session_id;
    labState.capabilityDesignParentSessionId = session.parent_session_id || null;
    labState.capabilityDraftBlueprint = null;
    labState.capabilityDraftDecision = null;
    labState.selectedCapabilityProposalId = null;
    $("#capability-requirement").value = "";
    renderCapabilityConversation();
    renderCapabilityBlueprint();
    renderCapabilityDesignSessions();
    showToast("Design discussion resumed with its dependency context.", "success");
  }

  async function deleteCapabilityDesignSession() {
    const sessionId = $("#capability-session-select").value;
    if (!sessionId) return;
    const summary = labState.capabilityDesignSessions.find((item) => item.session_id === sessionId);
    if (!window.confirm(`Delete the saved discussion “${summary?.title || sessionId}”?\n\nCapability proposals and Registry objects are unaffected.`)) return;
    await agentApi(`/api/studios/capabilities/design-sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
    if (labState.capabilityDesignSessionId === sessionId) resetCapabilityDesign();
    await loadCapabilityDesignSessions();
    showToast("Saved design discussion deleted.", "success");
  }

  function discussCapabilityDependency(dependencyId) {
    const dependency = (labState.capabilityAssessment?.dependency_map || []).find((item) => item.dependency_id === dependencyId);
    if (!dependency || dependency.dependency_type !== "proposed_capability") return;
    const parentSessionId = labState.capabilityDesignSessionId;
    labState.capabilityAssessment = null;
    labState.capabilityDesignMessages = [];
    labState.capabilityDesignSessionId = null;
    labState.capabilityDesignParentSessionId = parentSessionId;
    labState.capabilityDraftBlueprint = null;
    labState.capabilityDraftDecision = null;
    $("#capability-requirement").value = `Design ${dependency.display_name}. It must ${dependency.purpose} It should provide ${dependency.provides}. Treat this as a dependency of saved design session ${parentSessionId}.`;
    renderCapabilityConversation();
    renderCapabilityBlueprint();
    $("#capability-requirement").focus();
    showToast("Dependency discussion prepared. The parent design remains saved and resumable.", "success");
  }

  function renderCapabilityInspector() {
    const tests = labState.capabilityInspectorView === "tests";
    $("#capability-tests-view").classList.toggle("hidden", !tests);
    $("#capability-description-view").classList.toggle("hidden", tests);
    $$('[data-capability-view]').forEach((button) => button.classList.toggle("active", button.dataset.capabilityView === labState.capabilityInspectorView));
    $$('[data-capability-description]').forEach((button) => button.classList.toggle("active", button.dataset.capabilityDescription === labState.capabilityDescriptionView));
    if (!tests) renderCapabilityDescription();
  }

  function renderCapabilityDescription() {
    const record = capabilityRecord();
    const target = $("#capability-description-content");
    if (!record || !target) return;
    const description = record.description || {};
    const view = labState.capabilityDescriptionView;
    if (view === "contract") {
      const contract = description.contract || {};
      target.innerHTML = `<article class="capability-description-panel"><header><div><span>Agent-facing contract</span><strong>${escapeHtml(record.name)}</strong></div><i>Read only</i></header><p>This is the instruction boundary supplied when an agent is allowed to use this capability.</p><pre><code>${escapeHtml(contract.agent_text || "No agent contract is available.")}</code></pre><dl><div><dt>Allowed effects</dt><dd>${(contract.allowed_effects || []).length ? escapeHtml(contract.allowed_effects.join(", ")) : "None"}</dd></div><div><dt>Human review</dt><dd>${contract.requires_human_review ? "Required" : "Not required"}</dd></div></dl></article>`;
    } else if (view === "script") {
      const script = description.script || {};
      target.innerHTML = `<article class="capability-description-panel capability-script-panel"><header><div><span>Registered implementation</span><strong>${escapeHtml(script.callable || record.name)}</strong></div><i>${script.available ? "Available" : "Missing"}</i></header><dl><div><dt>Module</dt><dd>${escapeHtml(script.module || "—")}</dd></div><div><dt>Source file</dt><dd>${escapeHtml(script.source_file || "—")}</dd></div><div><dt>Language</dt><dd>${escapeHtml(script.language || "—")}</dd></div></dl><pre><code>${escapeHtml(script.source || "No implementation is registered.")}</code></pre></article>`;
    } else {
      const human = description.human || {};
      const narrative = `${human.summary || record.purpose} It receives ${human.receives || record.input_contract} It returns ${human.returns || record.output_contract} ${human.how_it_runs || ""} Method: ${human.method || "—"}. Setup: ${human.setup || "—"}. ${human.setup_description || ""} ${human.review || ""}`;
      target.innerHTML = `<article class="capability-description-panel capability-human-panel"><header><div><span>Plain-language description</span><strong>${escapeHtml(record.name)}</strong></div><i>${escapeHtml(human.status || "Unknown")}</i></header><p class="capability-human-narrative">${escapeHtml(narrative)}</p></article>`;
    }
  }

  function selectCapability(capabilityId) {
    const record = capabilityRecord(capabilityId);
    if (!record) return;
    labState.selectedCapabilityId = record.capability_id;
    renderCapabilityLibrary();
    renderCapabilityRunOptions();
    renderCapabilityDescription();
    const gate = record.validation_gate || { passed: 0, required: 0, status: "tests_pending" };
    const tests = record.validation_tests || [];
    $("#capability-selection").innerHTML = `<header><div><span>Test preparation</span><strong>${escapeHtml(record.name)}</strong></div><i>${Number(gate.passed)} / ${Number(gate.required)} passed</i></header>
      <p>${escapeHtml(record.purpose)}</p>
      <div class="capability-test-plan">${tests.map((test) => `<div class="${escapeHtml(test.status)}"><b>${test.status === "passed" ? "✓" : test.status === "available" ? "→" : "!"}</b><span><strong>${escapeHtml(test.name)}</strong><small>${escapeHtml(test.evidence)}</small></span></div>`).join("")}</div>
      <button class="button primary" id="capability-run-fixture" type="button" ${record.test_health !== "fixture_ready" ? "disabled" : ""}>${record.test_health === "fixture_ready" ? "Run fixed tests" : "Implementation required"}</button>
      <small class="capability-validation-note">${gate.status === "ready_for_review" ? "All required automated checks passed. Human review can now decide validation." : "This capability cannot be validated until every required check passes."}</small>`;
    $("#capability-run-fixture")?.addEventListener("click", () => runCapabilityFixture().catch((error) => showToast(error.message, "error")));
  }

  function renderCapabilityPackageDetail() {
    const target = $("#capability-package-detail");
    if (!target) return;
    const packageId = labState.selectedCapabilityPackageId;
    const item = (labState.capabilityCatalogue?.packages || []).find((value) => value.package_id === packageId);
    target.classList.remove("hidden");
    if (!item) {
      target.innerHTML = '<div class="capability-empty">Select a package to review its description and B0 use.</div>';
      return;
    }
    target.innerHTML = `<article><header><div><span>Package description</span><strong>${escapeHtml(item.name)}</strong></div><i>${Number(item.members?.length || 0)} capabilities</i></header><p>${escapeHtml(item.description || item.purpose)}</p><p><strong>B0 use:</strong> ${escapeHtml(item.b0_role || "Define the package settings before the experiment starts.")}</p><small>${escapeHtml(item.members.join(" · "))}</small></article>`;
  }

  function selectCapabilityPackage(packageId) {
    labState.selectedCapabilityPackageId = packageId;
    renderCapabilityLibrary();
  }

  function renderCapabilityHostDetail() {
    const target = $("#capability-package-detail");
    if (!target) return;
    const item = (labState.capabilityCatalogue?.hosts || []).find((value) => value.host_id === labState.selectedCapabilityHostId);
    target.classList.remove("hidden");
    if (!item) {
      target.innerHTML = '<div class="capability-empty">Select a host to see what it provides, how a capability connects to it, and what it is allowed to change.</div>';
      return;
    }
    target.innerHTML = `<article><header><div><span>Host description</span><strong>${escapeHtml(item.display_name)}</strong></div><i>${escapeHtml(item.status.replaceAll("_", " "))}</i></header><p>${escapeHtml(item.description || "This host provides a controlled environment for a capability result.")}</p><p><strong>Capability integration:</strong> ${escapeHtml(item.capability_integration || item.connection_contract)}</p><p><strong>Effect boundary:</strong> ${escapeHtml(item.effect_boundary || item.write_boundary)}</p><small>${escapeHtml(item.connection_contract)} · ${escapeHtml(item.surface_kinds.join(", ").replaceAll("_", " "))}</small></article>`;
  }

  function selectCapabilityHost(hostId) {
    labState.selectedCapabilityHostId = hostId;
    renderCapabilityLibrary();
  }

  function renderCapabilityLibrary() {
    if (!labState.capabilityCatalogue) return;
    const tab = labState.capabilityLibraryTab;
    const search = $("#capability-library-search").value.trim().toLowerCase();
    const family = $("#capability-family-filter").value;
    const status = $("#capability-status-filter").value;
    $$('[data-capability-library-tab]').forEach((button) => button.classList.toggle("active", button.dataset.capabilityLibraryTab === tab));
    if (tab === "packages") {
      const packages = (labState.capabilityCatalogue.packages || []).filter((item) => !search || `${item.name} ${item.purpose} ${item.members.join(" ")}`.toLowerCase().includes(search));
      $("#capability-library-head").innerHTML = "<tr><th>Package</th><th>Purpose</th><th>B0 use</th><th>Members</th></tr>";
      $("#capability-library-body").innerHTML = packages.map((item) => `<tr tabindex="0" class="${item.package_id === labState.selectedCapabilityPackageId ? "active" : ""}" data-capability-package="${escapeHtml(item.package_id)}"><td><b>${escapeHtml(item.name)}</b><small>${escapeHtml(item.package_id)}</small></td><td>${escapeHtml(item.purpose)}</td><td>${escapeHtml(item.b0_role || "Set before run")}</td><td>${item.members.length}</td></tr>`).join("");
      $("#capability-library-count").textContent = `${packages.length} packages`;
      renderCapabilityPackageDetail();
      return;
    }
    if (tab === "hosts") {
      const hosts = (labState.capabilityCatalogue.hosts || []).filter((item) => !search || `${item.display_name} ${item.host_id} ${item.description || ""} ${item.surface_kinds.join(" ")} ${item.frameworks.join(" ")}`.toLowerCase().includes(search));
      $("#capability-library-head").innerHTML = "<tr><th>Host</th><th>Provides</th><th>Capability connection</th><th>Status</th></tr>";
      $("#capability-library-body").innerHTML = hosts.map((item) => `<tr tabindex="0" class="${item.host_id === labState.selectedCapabilityHostId ? "active" : ""}" data-capability-host="${escapeHtml(item.host_id)}"><td><b>${escapeHtml(item.display_name)}</b><small>${escapeHtml(item.host_id)}</small></td><td>${escapeHtml(item.description || item.surface_kinds.join(", "))}</td><td>${escapeHtml(item.connection_contract)}</td><td><i class="capability-health ready">${escapeHtml(item.status.replaceAll("_", " "))}</i><small>${escapeHtml(item.write_boundary)}</small></td></tr>`).join("");
      $("#capability-library-count").textContent = `${hosts.length} hosts`;
      renderCapabilityHostDetail();
      return;
    }
    $("#capability-package-detail").classList.add("hidden");
    const values = (labState.capabilityCatalogue.capabilities || []).filter((item) => {
      if (search && !`${item.name} ${item.capability_id} ${item.purpose}`.toLowerCase().includes(search)) return false;
      if (family && item.family !== family) return false;
      if (status && item.test_health !== status) return false;
      return true;
    });
    $("#capability-library-head").innerHTML = "<tr><th>Capability</th><th>Method</th><th>Setup</th><th>Tests</th></tr>";
    $("#capability-library-body").innerHTML = values.map((item) => `<tr tabindex="0" class="${item.capability_id === labState.selectedCapabilityId ? "active" : ""}" data-capability-row="${escapeHtml(item.capability_id)}"><td><b>${escapeHtml(item.name)}</b><small>${escapeHtml(item.capability_id)}</small></td><td><b>${escapeHtml(item.execution_profile?.kind_label || "—")}</b><small>${escapeHtml(item.execution_profile?.kind_description || "")}</small></td><td><b>${escapeHtml(item.execution_profile?.parameterisation_label || "—")}</b><small>${escapeHtml(item.execution_profile?.parameterisation_description || "")}</small></td><td><i class="capability-health ${item.validation_gate?.status === "ready_for_review" ? "ready" : ""}">${Number(item.validation_gate?.passed || 0)}/${Number(item.validation_gate?.required || 0)} passed</i><small>${item.test_case_status === "ready" ? "fixed tests ready" : "implementation required"}</small></td></tr>`).join("");
    $("#capability-library-count").textContent = `${values.length} capabilities`;
  }

  function renderCapabilityRun(result) {
    labState.selectedCapabilityRun = result;
    const manifest = result.manifest || {};
    const contents = result.contents || {};
    const presentation = contents["presentation.json"] || {};
    const stages = contents["stages.json"] || [];
    const resolution = contents["resolution.json"] || {};
    const effects = contents["effect-review.json"] || {};
    const fixedTests = contents["fixed-tests.json"] || contents["validation.json"]?.tests || (stages.length ? [
      { name: "Input contract", status: "passed", evidence: "The saved run contains a successful input-validation stage." },
      { name: "Registry resolution", status: "passed", evidence: "The saved run contains an exact capability-resolution record." },
      { name: "Execution", status: "passed", evidence: "The saved run contains a successful execution stage." },
      { name: "Output contract", status: "passed", evidence: "The saved run contains a successful output-validation stage." },
      { name: "Effect boundary", status: (effects.executed || []).length ? "failed" : "passed", evidence: (effects.executed || []).length ? "The saved run declares effects." : "The saved run produced no undeclared effects." },
    ] : []);
    const fixedTestsPassed = fixedTests.filter((test) => test.status === "passed").length;
    let primary = "";
    if (presentation.metrics?.length) primary += `<div class="capability-result-metrics">${presentation.metrics.map((item) => `<div><span>${escapeHtml(item.label)}</span><b>${escapeHtml(capabilityValue(item.value, item.format))}</b></div>`).join("")}</div>`;
    if (presentation.rows?.length) primary += `<div class="capability-result-table"><table><thead><tr>${presentation.columns.map((item) => `<th>${escapeHtml(item)}</th>`).join("")}</tr></thead><tbody>${presentation.rows.slice(0, 20).map((row) => `<tr>${row.map((item) => `<td>${escapeHtml(capabilityValue(item))}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    if (presentation.series?.length) {
      const points = presentation.series;
      const values = points.map((item) => Number(item.y));
      const min = Math.min(...values); const max = Math.max(...values); const range = max - min || 1;
      const polyline = points.map((item, index) => `${(index / Math.max(points.length - 1, 1)) * 600},${112 - ((Number(item.y) - min) / range) * 92}`).join(" ");
      primary += `<svg class="capability-series" viewBox="0 0 600 128" role="img" aria-label="Capability result series"><polyline points="${polyline}"></polyline></svg>`;
    }
    if (presentation.markdown) primary += `<div class="capability-markdown">${escapeHtml(presentation.markdown).replaceAll("\n", "<br>")}</div>`;
    if (!primary && presentation.fields?.length) primary = `<dl>${presentation.fields.map((item) => `<div><dt>${escapeHtml(item.name.replaceAll("_", " "))}</dt><dd>${escapeHtml(capabilityValue(item.value))}</dd></div>`).join("")}</dl>`;
    $("#capability-run-review").innerHTML = `<article class="capability-review-level level-one"><header><div><span>Level 1 · Result</span><strong>${escapeHtml(presentation.title || manifest.capability_id)}</strong></div><i>${fixedTestsPassed}/${fixedTests.length} fixed tests passed</i></header><p>${escapeHtml(presentation.premise || "")}</p>${primary}<div class="capability-test-plan">${fixedTests.map((test) => `<div class="${escapeHtml(test.status)}"><b>${test.status === "passed" ? "✓" : "!"}</b><span><strong>${escapeHtml(test.name)}</strong><small>${escapeHtml(test.evidence)}</small></span></div>`).join("")}</div><small>${escapeHtml(presentation.summary || "")}</small></article>
      <details class="capability-review-level"><summary><span>Level 2</span> Work trace <i>${stages.length} stages</i></summary><div class="capability-stage-list">${stages.map((item) => `<div><b>${item.sequence}</b><span><strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(item.summary)}</small></span><i>${Number(item.elapsed_ms || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })} ms</i></div>`).join("")}</div></details>
      <details class="capability-review-level"><summary><span>Level 3</span> Technical record <i>${(manifest.files || []).length} files</i></summary><dl><div><dt>Resolution</dt><dd>${escapeHtml(resolution.resolved_capability_id || "—")} · exact · canonical ServiceFabric</dd></div><div><dt>Effects</dt><dd>${(effects.executed || []).length ? escapeHtml((effects.executed || []).join(", ")) : "None"}</dd></div><div><dt>Source DB</dt><dd>${escapeHtml(effects.licensed_source_database || "read only")}</dd></div><div><dt>Folder</dt><dd>${escapeHtml(manifest.folder || "")}</dd></div></dl><div class="capability-files">${(manifest.files || []).map((item) => `<span><b>${escapeHtml(item.name)}</b><small>${Number(item.bytes || 0).toLocaleString()} B</small></span>`).join("")}</div></details>`;
    $("#capability-delete-run").disabled = false;
    $("#capability-run-select").value = manifest.run_id || "";
  }

  async function runCapabilityFixture() {
    const record = capabilityRecord();
    if (!record || record.test_health !== "fixture_ready") return;
    $("#capability-run-review").innerHTML = '<div class="capability-empty">Running the fixed tests…</div>';
    try {
      const result = await agentApi("/api/studios/capabilities/runs", { method: "POST", body: JSON.stringify({ capability_id: record.capability_id, fixture_id: "reviewed_synthetic" }) });
      await loadCapabilityRuns();
      renderCapabilityRun(result);
    } catch (error) {
      $("#capability-run-review").innerHTML = `<div class="capability-empty capability-run-error">The test case could not run. ${escapeHtml(error.message)}</div>`;
      throw error;
    }
  }

  async function loadCapabilityRuns() {
    const payload = await agentApi("/api/studios/capabilities/runs");
    labState.capabilityRuns = payload.runs || [];
    renderCapabilityRunOptions();
  }

  function renderCapabilityRunOptions() {
    const select = $("#capability-run-select");
    if (!select) return;
    const capabilityId = labState.selectedCapabilityId;
    const runs = (labState.capabilityRuns || []).filter((item) => item.capability_id === capabilityId);
    select.innerHTML = '<option value="">Saved fixed-test runs</option>' + runs.map((item) => `<option value="${escapeHtml(item.run_id)}">${escapeHtml(item.created_at.slice(0, 16).replace("T", " "))} · ${Number(item.elapsed_ms || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })} ms</option>`).join("");
    const selectedRunId = labState.selectedCapabilityRun?.manifest?.run_id || "";
    const selectedBelongsHere = runs.some((item) => item.run_id === selectedRunId);
    if (selectedBelongsHere) select.value = selectedRunId;
    else {
      labState.selectedCapabilityRun = null;
      $("#capability-delete-run").disabled = true;
      $("#capability-run-review").innerHTML = `<div class="capability-empty">${runs.length ? "Select a saved fixed-test run or run the tests again." : "No fixed-test runs have been saved for this capability."}</div>`;
    }
  }

  function agentStudioBaseBlueprint(agentClass) {
    const candidates = [labState.agentStudioCandidate, labState.agentBlueprint]
      .filter((item) => item?.agent_class === agentClass);
    if (candidates.length) return structuredClone(candidates[0]);
    const template = builtInRiskAgents().find((item) =>
      (item.agent_class || item.blueprint?.agent_class || "experimental_specialist") === agentClass
    );
    return template?.blueprint ? structuredClone(template.blueprint) : null;
  }

  function agentStudioBlueprintFacts(blueprint) {
    return {
      "Agent class": agentBuilderLabel(blueprint.agent_class),
      "Outcome": blueprint.purpose,
      "Receives": agentBuilderLabel(blueprint.input_contract),
      "Returns": agentBuilderLabel(blueprint.output_contract),
      "Route": agentBuilderLabel(blueprint.routing.strategy),
      "Memory": `${agentBuilderLabel(blueprint.memory_rules.scope)} · ${agentBuilderLabel(blueprint.memory_rules.checkpoint)}`,
      "Capabilities": blueprint.capability_latches.map((item) => item.capability_id).join(", "),
      "Output sections": blueprint.structured_output.fields.map((item) => item.title).join(", "),
      "Authority": blueprint.agent_class === "static_system" ? "Proposal only · human approval" : "Effect-free research · declared review boundary",
    };
  }

  function agentStudioChanges(before, after) {
    const prior = before ? agentStudioBlueprintFacts(before) : {};
    const next = agentStudioBlueprintFacts(after);
    return Object.entries(next)
      .filter(([key, value]) => prior[key] !== value)
      .map(([key, value]) => ({ key, before: prior[key] || "Not defined", after: value }));
  }

  function persistAgentStudioCompanion() {
    try {
      localStorage.setItem("servicefabric.agent-studio.companion.v1", JSON.stringify({
        messages: labState.agentStudioMessages.slice(-12),
        candidate: labState.agentStudioCandidate,
        candidateBase: labState.agentStudioCandidateBase,
        receipt: labState.agentStudioReceipt,
        validated: Boolean(labState.agentStudioCandidateValidated),
        applied: Boolean(labState.agentStudioCandidateApplied),
        review: labState.agentStudioReview,
        requirementMemory: labState.agentStudioRequirementMemory,
        pendingRequirements: labState.agentStudioPendingRequirements,
      }));
    } catch (_) {}
  }

  function restoreAgentStudioCompanion() {
    if (labState.agentStudioRestored) return;
    labState.agentStudioRestored = true;
    try {
      const payload = JSON.parse(localStorage.getItem("servicefabric.agent-studio.companion.v1") || "null");
      if (!payload) return;
      labState.agentStudioMessages = Array.isArray(payload.messages) ? payload.messages.slice(-12) : [];
      labState.agentStudioCandidate = payload.candidate || null;
      labState.agentStudioCandidateBase = payload.candidateBase || null;
      labState.agentStudioReceipt = payload.receipt || null;
      labState.agentStudioCandidateValidated = Boolean(payload.validated);
      // The Full Builder is an in-memory editing surface. Never restore an
      // "applied" claim after reload unless the blueprint is applied again.
      labState.agentStudioCandidateApplied = false;
      labState.agentStudioReview = payload.review || null;
      labState.agentStudioRequirementMemory = Array.isArray(payload.requirementMemory)
        ? payload.requirementMemory
        : (payload.review?.requirements || []);
      labState.agentStudioPendingRequirements = Array.isArray(payload.pendingRequirements)
        ? payload.pendingRequirements.slice(-4)
        : [];
    } catch (_) {}
  }

  function renderAgentStudioCompanion() {
    const existingSelect = $("#agent-companion-existing");
    if (existingSelect) {
      const selected = existingSelect.value;
      existingSelect.innerHTML = '<option value="">Start a new agent</option>' + labState.savedAgents.map((agent) =>
        `<option value="${escapeHtml(agent.id)}">${escapeHtml(agent.name)} · v${escapeHtml(agent.blueprint?.version || "0.1.0")}${agent.built_in ? " · reviewed template" : " · local draft"}</option>`
      ).join("");
      if (labState.savedAgents.some((agent) => agent.id === selected)) existingSelect.value = selected;
    }
    const welcome = `<div class="agent-companion-message assistant"><p>Describe the job you need. The proposed agent design and every consequential change will appear beside this discussion.</p></div>`;
    $("#agent-companion-messages").innerHTML = welcome + labState.agentStudioMessages.map((message) => `<div class="agent-companion-message ${escapeHtml(message.role)}">${message.role === "user" ? "<strong>You</strong>" : ""}<p>${escapeHtml(agentStudioDisplayCopy(message.content))}</p></div>`).join("");
    $("#agent-companion-messages").scrollTop = $("#agent-companion-messages").scrollHeight;
    const candidate = labState.agentStudioCandidate;
    if (!candidate) {
      $("#agent-companion-candidate").innerHTML = '<div class="agent-companion-empty"><strong>No agent design yet</strong><p>The proposed configuration, changes and unresolved limitations will appear here.</p></div>';
      labState.agentStudioReview = null;
      renderAgentConfigurationReview();
      return;
    }
    const changes = agentStudioChanges(labState.agentStudioCandidateBase, candidate);
    const facts = agentStudioBlueprintFacts(candidate);
    const receipt = labState.agentStudioReceipt || {};
    const validated = Boolean(labState.agentStudioCandidateValidated);
    $("#agent-companion-candidate").innerHTML = `<header><div><span>Agent design</span><strong>${escapeHtml(candidate.name)} · v${escapeHtml(candidate.version)}</strong><small>${escapeHtml(candidate.purpose)}</small></div><b class="${validated ? "passed" : ""}">${validated ? "Verified" : "Review next"}</b></header>
      <div class="agent-candidate-scroll">
      <section class="agent-candidate-premise"><span>What this agent will do</span><p>${escapeHtml(candidate.instructions.objective)}</p></section>
      <section><span>Important configuration</span><dl>${["Receives", "Returns", "Route", "Memory", "Authority"].map((key) => `<div><dt>${key}</dt><dd>${escapeHtml(facts[key])}</dd></div>`).join("")}</dl></section>
      <section><span>Capabilities</span><p>${escapeHtml(facts.Capabilities || "None")}</p></section>
      <section><span>Proposed changes</span><div class="agent-candidate-changes">${changes.length ? changes.map((item) => `<article><strong>${escapeHtml(item.key)}</strong><small>${escapeHtml(item.before)}</small><b>→</b><p>${escapeHtml(item.after)}</p></article>`).join("") : '<p>No consequential difference from the current blueprint. The design was clarified without changing its contract.</p>'}</div></section>
      <section class="agent-candidate-boundary"><span>What will not happen</span><p>No Registry write, activation, portfolio effect, code change or Codex session occurs from this proposal.</p></section>
      </div>
      <footer><button class="button primary" id="agent-candidate-review" type="button">Verify blueprint</button><button class="button ghost" id="agent-candidate-open" type="button">Edit advanced configuration</button></footer>
      <details class="agent-candidate-receipt"><summary>Technical details</summary><small>${escapeHtml(receipt.system_agent_id || "system-agent-agent-studio-architect")} · v${escapeHtml(receipt.system_agent_version || "0.1.0")} · ${Number(receipt.input_tokens || 0) + Number(receipt.output_tokens || 0)} tokens · ${escapeHtml(receipt.model || "gpt-5.6-luna")}</small></details>`;
    renderAgentConfigurationReview();
  }

  function reviewStatusLabel(status) {
    return {
      satisfied: "Satisfied",
      partial: "Partial",
      conflict: "Conflict",
      unproven: "Unproven",
      not_applicable: "Not applicable",
    }[status] || status;
  }

  function agentStudioDisplayCopy(value) {
    return String(value || "")
      .replaceAll("implementation_candidate", "repository implementation route")
      .replaceAll("Full Builder", "advanced configuration")
      .replaceAll("Agent Builder working draft", "agent design")
      .replaceAll("Blueprint Draft", "agent design")
      .replace(/\bcandidate\b/gi, "agent design");
  }

  function openAgentReviewRequirements(review) {
    const open = (review?.requirements || [])
      .filter((item) => ["partial", "conflict", "unproven"].includes(item.status) && ["critical", "high"].includes(item.materiality));
    const system = open.filter((item) => item.source !== "user");
    const user = open.filter((item) => item.source === "user");
    return [...system, ...(user.length ? [user[user.length - 1]] : [])];
  }

  function reviewRequirementRows(review, limit = 10) {
    return openAgentReviewRequirements(review)
      .slice(0, limit).map((item) => `
      <article class="agent-requirement-row ${escapeHtml(item.status)}">
        <div><b>${escapeHtml(reviewStatusLabel(item.status))}</b><span>${escapeHtml(item.source.replaceAll("_", " "))} · ${escapeHtml(item.materiality)}</span></div>
        <p>${escapeHtml(agentStudioDisplayCopy(item.statement))}</p>
        <small>${escapeHtml(agentStudioDisplayCopy(item.evidence))}</small>
        ${item.proposed_correction && item.status !== "satisfied" ? `<em>${escapeHtml(agentStudioDisplayCopy(item.proposed_correction))}</em>` : ""}
      </article>`).join("");
  }

  function renderAgentConfigurationReview() {
    const review = labState.agentStudioReview;
    const studioPanel = $("#agent-companion-review");
    if (!review) {
      if (studioPanel) studioPanel.classList.add("hidden");
      return;
    }
    const complexity = review.complexity || {};
    const luna = review.luna || {};
    const lunaReview = luna.review || {};
    const codexPrepared = labState.agentCodexProposal?.blueprint?.name === review.agent_name
      && labState.agentCodexProposal?.blueprint?.version === review.version;
    const summary = luna.status === "completed"
      ? agentStudioDisplayCopy(lunaReview.executive_assessment)
      : "Deterministic requirements and compilation checks completed. Luna review is unavailable; no semantic conclusion was fabricated.";
    const graphLabel = (review.graph?.recommendation || "not_required") === "consider_agent_graph" ? "Consider Agent Graph" : "Single agent remains suitable";
    const objectDependencies = review.object_capability_dependencies || [];
    const satisfiedCount = Number(review.satisfied_requirement_count || (review.requirements || []).filter((item) => item.status === "satisfied").length);
    const openRequirementCount = openAgentReviewRequirements(review).length;
    const dependencyRows = objectDependencies.length
      ? `<div class="agent-object-dependencies">${objectDependencies.map((item) => `<article class="${item.status === "ready" ? "ready" : "attention"}"><div><strong>${escapeHtml(item.label)}</strong><span>${item.status === "ready" ? "Capability ready" : "Binding needed"}</span></div><p>${escapeHtml(item.explanation)}</p>${item.status !== "ready" ? `<small>Reuse first: ${(item.compatible_capability_examples || []).map(escapeHtml).join(" · ")}</small>` : ""}</article>`).join("")}</div>`
      : "";
    const findingActions = openRequirementCount
      ? '<button class="button primary" type="button" data-agent-review-action="resolve">Resolve material finding</button>'
      : '<button class="button primary" type="button" data-agent-review-action="codex">Review development proposal</button>';
    const content = `<header><div><span>Configuration review</span><strong>${escapeHtml(review.agent_name)} · v${escapeHtml(review.version)}</strong><small>${escapeHtml(summary)}</small></div><b>${openRequirementCount} material finding${openRequirementCount === 1 ? "" : "s"}</b></header>
      <div class="agent-review-metrics">
        <div><span>Contract</span><strong>${review.compile?.checks?.length || 0} checks passed</strong><small>${escapeHtml(review.compile?.compiler_version || "Compiler unavailable")}</small></div>
        <div><span>Complexity</span><strong>${Number(complexity.score || 0)} · ${escapeHtml(complexity.band || "unknown")}</strong><small>${Number(complexity.node_count || 0)} nodes · ${Number(complexity.edge_count || 0)} edges</small></div>
        <div><span>Luna</span><strong>${escapeHtml(luna.status || "not requested")}</strong><small>Compact semantic configuration review</small></div>
        <div><span>Codex</span><strong>Terra · high${codexPrepared ? " · proposal ready" : ""}</strong><small>Automatic after job authorization · permission requests remain human-reviewed</small></div>
        <div><span>Composition</span><strong>${escapeHtml(graphLabel)}</strong><small>Graph promotion always requires approval</small></div>
      </div>
      <div class="agent-requirement-memory"><strong>${satisfiedCount} satisfied requirement${satisfiedCount === 1 ? "" : "s"} retained</strong><span>Only new or regressed material findings are shown below.</span></div>
      <div class="agent-requirement-ledger">${reviewRequirementRows(review) || '<div class="agent-review-empty">No open material finding. Previously satisfied requirements remain attached to this blueprint.</div>'}</div>
      ${dependencyRows}
      <footer>${findingActions}</footer>`;
    if (studioPanel) {
      studioPanel.classList.remove("hidden");
      studioPanel.innerHTML = content;
    }
  }

  function agentStudioCodexBrief(blueprint, includeBlueprint = true) {
    const scope = blueprint.static_system_scope?.codebase_scope || [
      "apps/portfolio-risk-workbench/labs/agent_studio.py",
      "apps/portfolio-risk-workbench/labs/index.html",
      "apps/portfolio-risk-workbench/labs/labs.js",
      "packages/risk_agents",
      "tests/application/test_agent_studio.py",
    ];
    const unresolved = openAgentReviewRequirements(labState.agentStudioReview);
    const reviewBlock = unresolved.length
      ? `\n\nConfiguration findings\n${unresolved.map((item) => `- [${item.materiality}] ${item.statement} Correction: ${item.proposed_correction || "Resolve explicitly."}`).join("\n")}`
      : "\n\nConfiguration findings\n- The authoritative Studio review has no material blockers.";
    const dependencies = (labState.agentStudioReview?.object_capability_dependencies || []).map((item) => `- ${item.label}: ${item.status}; ${item.explanation}`).join("\n") || "- No direct system-object interaction was inferred.";
    return `ServiceFabric Agent candidate brief\n\nGoal\nImplement the approved ${blueprint.agent_class.replaceAll("_", " ")} candidate ${blueprint.name}@${blueprint.version}.\n\nContext\n- Outcome: ${blueprint.purpose}\n- Input: ${blueprint.input_contract}\n- Output: ${blueprint.output_contract}\n- Capabilities: ${blueprint.capability_latches.map((item) => item.capability_id).join(", ")}\n- Routing: ${blueprint.routing.strategy}\n- Memory: ${blueprint.memory_rules.scope}\n- Skill: build-servicefabric-agent${reviewBlock}\n\nSystem-object and capability dependencies\n${dependencies}\n\nAllowed scope\n${scope.map((item) => `- ${item}`).join("\n")}\n\nConstraints\n- Reuse canonical contracts and existing definitions first.\n- Bind intended object interactions through compatible capabilities; create a new capability only when reuse cannot satisfy the contract.\n- Preserve the agent-class, effects, evidence and human-review boundaries.\n- Work in an isolated candidate worktree.\n- Do not register, activate, merge or delete the worktree automatically.\n\nDone when\n- Every material Studio requirement passes.\n- The blueprint validates and compiles.\n- Representative, failure-boundary and adversarial fixtures pass.\n- Focused tests pass and the handoff explains every change and limitation.${includeBlueprint ? `\n\nApproved blueprint\n${JSON.stringify(blueprint, null, 2)}` : ""}`;
  }

  async function initializeAgentStudioCompanion() {
    restoreAgentStudioCompanion();
    renderAgentStudioCompanion();
    initializeAgentCodexBridge().catch((error) => {
      $("#agent-codex-status").textContent = "Unavailable";
      $("#agent-codex-status-copy").textContent = error.message;
    });
    try {
      const payload = await agentApi("/api/agents/system-agents");
      labState.agentStudioSystemAgents = payload.agents || [];
      renderAgentStudioCompanion();
    } catch (error) {
      $("#agent-companion-identity").textContent = `Unavailable · ${error.message}`;
    }
  }

  async function submitAgentStudioCompanion(event) {
    event.preventDefault();
    if (labState.agentStudioBusy) return;
    const input = $("#agent-companion-input");
    const message = input.value.trim();
    const agentClass = $("#agent-companion-class").value;
    const intent = $("#agent-companion-intent").value;
    if (!message) return;
    if (!labState.agentRuntime?.openai?.available || !labState.agentRuntime?.openai?.key_configured) {
      labState.agentStudioMessages.push({
        role: "assistant",
        content: "Blueprint preparation is unavailable because the live Studio runtime does not have both the OpenAI SDK and its local credential. Restart the application with start_live_data.sh, then try again.",
      });
      renderAgentStudioCompanion();
      return;
    }
    const base = intent === "create"
      ? agentStudioBaseBlueprint(agentClass)
      : structuredClone(labState.agentStudioCandidate || agentStudioBaseBlueprint(agentClass));
    if (!base) {
      showToast("The selected agent-class recipe is still loading.", "error");
      return;
    }
    if (intent === "create") {
      labState.agentStudioRequirementMemory = [];
      labState.agentStudioPendingRequirements = [];
    }
    if (!labState.agentStudioPendingRequirements.includes(message)) {
      labState.agentStudioPendingRequirements.push(message);
      labState.agentStudioPendingRequirements = labState.agentStudioPendingRequirements.slice(-4);
    }
    labState.agentStudioMessages.push({ role: "user", content: message });
    labState.agentStudioBusy = true;
    input.value = "";
    renderAgentStudioCompanion();
    const intentInstruction = {
      create: "Create a new Agent Blueprint draft from this request. Treat the supplied draft as structural scaffolding, not as a purpose to preserve.",
      refine: "Revise the current Blueprint Draft only where the request materially improves its outcome, contracts, governance or evaluation.",
      review_codex: "Review the supplied Codex handoff against the authorized design. Convert only justified corrections into the Blueprint Draft and preserve all safety boundaries.",
    }[intent];
    try {
      const reviewFindings = (labState.agentStudioReview?.requirements || [])
        .filter((item) => ["partial", "conflict", "unproven"].includes(item.status) && ["critical", "high"].includes(item.materiality))
        .map((item) => ({
          requirement_id: item.requirement_id,
          statement: item.statement,
          status: item.status,
          materiality: item.materiality,
          evidence: item.evidence || "",
          proposed_correction: item.proposed_correction || "",
        }));
      const result = intent === "create"
        ? await agentApi("/api/agents/blueprint/plan", {
            method: "POST",
            body: JSON.stringify({
              description: `${intentInstruction}\n\nRequired agent class: ${agentClass}.\n\nUser request:\n${message}`,
              draft: base,
              model: "gpt-5.6-luna",
            }),
          })
        : await agentApi("/api/agents/blueprint/refine", {
            method: "POST",
            body: JSON.stringify({
              base,
              instruction: `${intentInstruction}\n\nUser request:\n${message}`,
              review_findings: reviewFindings,
              model: "gpt-5.6-luna",
            }),
          });
      labState.agentStudioCandidate = result.blueprint;
      labState.agentStudioCandidateBase = base;
      labState.agentStudioReceipt = result.receipt;
      labState.agentStudioCandidateValidated = false;
      labState.agentStudioCandidateApplied = false;
      if (labState.agentStudioReview?.requirements?.length) {
        labState.agentStudioRequirementMemory = labState.agentStudioReview.requirements;
      }
      labState.agentStudioReview = null;
      labState.agentDevelopmentHistory = null;
      labState.agentCodexProposal = null;
      labState.agentCodexSession = null;
      const facts = agentStudioBlueprintFacts(result.blueprint);
      const changeCount = agentStudioChanges(base, result.blueprint).length;
      labState.agentStudioMessages.push({
        role: "assistant",
        content: intent === "create"
          ? `I prepared ${result.blueprint.name} as an ${facts["Agent class"]}. It receives ${facts.Receives}, returns ${facts.Returns}, and proposes ${changeCount} consequential configuration change${changeCount === 1 ? "" : "s"}. Review the plain-language Blueprint Draft next.`
          : `I applied a validated diff with ${(result.diff?.applied_changes || []).length} changed section${(result.diff?.applied_changes || []).length === 1 ? "" : "s"}. Every unlisted section was preserved exactly. Run the single Studio review again to verify the result.`,
      });
      persistAgentStudioCompanion();
    } catch (error) {
      labState.agentStudioMessages.push({ role: "assistant", content: `I could not prepare a safe Blueprint Draft: ${error.message}` });
    } finally {
      labState.agentStudioBusy = false;
      renderAgentStudioCompanion();
    }
  }

  async function validateAgentStudioCandidate() {
    if (!labState.agentStudioCandidate) return;
    const result = await agentApi("/api/agents/blueprint/validate", {
      method: "POST",
      body: JSON.stringify(labState.agentStudioCandidate),
    });
    labState.agentStudioCandidateValidated = Boolean(result.valid);
    labState.agentStudioCandidateApplied = false;
    labState.agentStudioMessages.push({ role: "assistant", content: result.valid
      ? `The compiler accepted the Blueprint Draft and completed ${result.checks.length} contract checks. Advanced configuration remains optional; the Configuration Review is authoritative.`
      : "The Blueprint Draft did not pass compiler validation and remains unapplied." });
    persistAgentStudioCompanion();
    renderAgentStudioCompanion();
  }

  function currentAgentUserRequirements() {
    const retained = (labState.agentStudioRequirementMemory || [])
      .filter((item) => item.source === "user" && ["partial", "conflict", "unproven"].includes(item.status))
      .map((item) => item.statement);
    const pending = labState.agentStudioPendingRequirements || [];
    // A new instruction is a patch against the validated candidate and supersedes
    // earlier wording. Prior findings were already supplied to the diff planner.
    if (pending.length) return [pending[pending.length - 1]];
    return retained.length ? [retained[retained.length - 1]] : [];
  }

  async function reviewAgentConfiguration({ candidate = null, baseline = undefined, persist = true } = {}) {
    if (labState.agentStudioReviewBusy) return labState.agentStudioReview;
    const blueprint = candidate || labState.agentStudioCandidate || currentAgentBlueprint();
    const comparisonBase = baseline === undefined
      ? (labState.agentStudioCandidateBase || null)
      : baseline;
    labState.agentStudioReviewBusy = true;
    const loading = '<div class="agent-review-empty"><strong>Reviewing configuration</strong><span>Compiler checks, requirement coverage, complexity and Luna review are running.</span></div>';
    if ($("#agent-companion-review")) {
      $("#agent-companion-review").classList.remove("hidden");
      $("#agent-companion-review").innerHTML = loading;
    }
    try {
      labState.agentStudioReview = await agentApi("/api/agents/blueprint/review", {
        method: "POST",
        body: JSON.stringify({
          candidate: blueprint,
          baseline: comparisonBase,
          user_requirements: currentAgentUserRequirements(),
          include_luna: true,
          persist,
        }),
      });
      labState.agentStudioRequirementMemory = labState.agentStudioReview.requirements || [];
      labState.agentStudioPendingRequirements = [];
      labState.agentStudioCandidateValidated = true;
      persistAgentStudioCompanion();
      renderAgentConfigurationReview();
      await prepareAgentCodexProposal({
        scroll: false,
        quiet: true,
        purpose: openAgentReviewRequirements(labState.agentStudioReview).length ? "resolve_findings" : "build_candidate",
      });
      loadAgentDevelopmentHistory(blueprint).catch(() => {});
      return labState.agentStudioReview;
    } finally {
      labState.agentStudioReviewBusy = false;
    }
  }

  function refineFromConfigurationReview() {
    const review = labState.agentStudioReview;
    if (!review) return;
    const lunaBrief = review.luna?.review?.refinement_brief;
    const fallback = (review.requirements || [])
      .filter((item) => ["partial", "conflict", "unproven"].includes(item.status) && ["critical", "high"].includes(item.materiality))
      .map((item) => `${item.statement} Required correction: ${item.proposed_correction || "Resolve the finding explicitly."}`)
      .join("\n");
    if (labState.activeWorkspace !== "studio" || labState.selectedStudioId !== "agent") openStudio("agent");
    $("#agent-companion-intent").value = "refine";
    $("#agent-companion-input").value = lunaBrief || fallback || "Refine the current Blueprint Draft using the material configuration findings.";
    $("#agent-companion-input").focus();
    showToast("Material findings prepared as a refinement request. Review the text before submitting.");
  }

  async function resolveAgentConfigurationReview() {
    const review = labState.agentStudioReview;
    if (!review) return;
    const route = review.luna?.review?.codex_route || "read_only_review";
    const requiresRepositoryWork = route === "implementation_candidate"
      || review.complexity?.band === "high"
      || (review.object_capability_dependencies || []).some((item) => item.status !== "ready");
    if (requiresRepositoryWork) {
      await prepareAgentCodexProposal({ purpose: "resolve_findings" });
      return;
    }
    refineFromConfigurationReview();
  }

  async function loadAgentDevelopmentHistory(blueprint = null) {
    const value = blueprint || labState.agentStudioCandidate || currentAgentBlueprint();
    labState.agentDevelopmentHistory = await agentApi(`/api/agents/history?agent_name=${encodeURIComponent(value.name)}&version=${encodeURIComponent(value.version)}`);
    const history = labState.agentDevelopmentHistory;
    const historyCount = $("#agent-history-count");
    if (historyCount) historyCount.textContent = `${history.counts.reviews} review${history.counts.reviews === 1 ? "" : "s"} · ${history.counts.runs} run${history.counts.runs === 1 ? "" : "s"}`;
    const latestReviews = (history.reviews || []).slice(0, 4).map((item) => `<article><b>${escapeHtml(item.reviewed_at || "Review")}</b><span>${escapeHtml(item.complexity?.band || "unknown")} complexity · ${Number(item.material_requirement_count || 0)} material findings</span><p>${escapeHtml(item.summary)}</p></article>`).join("");
    const latestRuns = (history.runs || []).slice(0, 5).map((item) => `<article><b>${escapeHtml(item.run_id)}</b><span>${escapeHtml(item.data_mode || "unknown")} · ${escapeHtml(item.execution_mode || "unknown")}</span><p>${escapeHtml(item.scenario || "unspecified")} · ${escapeHtml(item.status || "unknown")}</p></article>`).join("");
    const historySummary = $("#agent-history-summary");
    if (historySummary) historySummary.innerHTML = `<div class="agent-memory-policy"><span>Active</span><b>Current blueprint and open findings</b><span>Indexed</span><b>Compact version summaries</b><span>Archived</span><b>Full artifacts by reference only</b></div><div class="agent-history-groups"><section><strong>Configuration reviews</strong>${latestReviews || '<div class="agent-review-empty">No retained configuration review.</div>'}</section><section><strong>Tests and runs</strong>${latestRuns || '<div class="agent-review-empty">No retained run for this exact version.</div>'}</section></div>`;
    return history;
  }

  async function continueAgentToFullBuilder() {
    if (!labState.agentStudioCandidate) return;
    if (!labState.agentStudioReview) await reviewAgentConfiguration();
    if (!labState.agentStudioCandidateValidated) return;
    if (!labState.agentStudioCandidateApplied) applyAgentStudioCandidate();
    switchWorkspace("agent", true, "system");
    showToast("Optional Advanced Builder opened. The Studio review remains the single authoritative gate.", "success");
  }

  async function loadExistingAgentForReview() {
    const id = $("#agent-companion-existing").value;
    const agent = labState.savedAgents.find((item) => item.id === id);
    if (!agent?.blueprint) {
      showToast("Choose an existing agent version first.", "error");
      return;
    }
    const blueprint = structuredClone(agent.blueprint);
    labState.agentStudioCandidate = blueprint;
    labState.agentStudioCandidateBase = structuredClone(blueprint);
    labState.agentStudioCandidateValidated = false;
    labState.agentStudioCandidateApplied = false;
    labState.agentStudioReview = null;
    labState.agentStudioRequirementMemory = [];
    labState.agentStudioPendingRequirements = [];
    labState.agentDevelopmentHistory = null;
    labState.agentStudioMessages.push({ role: "assistant", content: `${blueprint.name} v${blueprint.version} is loaded as a new Blueprint Draft. Its saved Agent Version remains unchanged until a later, explicit Registry Admission decision.` });
    persistAgentStudioCompanion();
    renderAgentStudioCompanion();
    await reviewAgentConfiguration({ candidate: blueprint, baseline: blueprint, persist: true });
  }

  function applyAgentStudioCandidate() {
    if (!labState.agentStudioCandidate || !labState.agentStudioCandidateValidated) return;
    applyAgentBlueprint(structuredClone(labState.agentStudioCandidate));
    labState.agentBuilderMeta.recipe_id = "companion-candidate";
    labState.agentBuilderMeta.provenance = "ai_suggestion_human_approved";
    labState.agentStudioCandidateApplied = true;
    labState.agentStudioMessages.push({ role: "assistant", content: "The verified Blueprint Draft is now available in advanced configuration. It remains editable, local and unregistered." });
    persistAgentStudioCompanion();
    renderAgentStudioCompanion();
    showToast("Applied to the local Agent Builder draft.");
  }

  function resetAgentStudioCompanion() {
    labState.agentStudioMessages = [];
    labState.agentStudioCandidate = null;
    labState.agentStudioCandidateBase = null;
    labState.agentStudioReceipt = null;
    labState.agentStudioCandidateValidated = false;
    labState.agentStudioCandidateApplied = false;
    labState.agentStudioReview = null;
    labState.agentStudioRequirementMemory = [];
    labState.agentStudioPendingRequirements = [];
    labState.agentDevelopmentHistory = null;
    labState.agentCodexProposal = null;
    labState.agentCodexSession = null;
    localStorage.removeItem("servicefabric.agent-studio.companion.v1");
    renderAgentStudioCompanion();
    renderAgentCodexBridge();
  }

  function agentCodexStage() {
    const session = labState.agentCodexSession;
    const status = session?.status;
    if (["planning", "queued_implementation", "awaiting_implementation_approval", "implementing", "correcting", "awaiting_review", "reviewing", "improving_skill", "awaiting_skill_review"].includes(status)) return "run";
    if (["review_complete", "archived"].includes(status)) return "admit";
    return "prepare";
  }

  function agentCodexEventDetail(event) {
    const payload = event.payload || {};
    const item = payload.item || {};
    if (item.type === "agentMessage") return item.text || "Agent message completed.";
    if (item.type === "plan") return item.text || "Plan updated.";
    if (item.type === "reasoning") return Array.isArray(item.summary) ? item.summary.join("\n") : item.summary || "A concise reasoning summary was recorded; private chain-of-thought is not retained.";
    if (item.type === "commandExecution") return `${item.command || "Command"}${item.status ? ` · ${item.status}` : ""}`;
    if (item.type === "fileChange") return `${(item.changes || []).length} file change${(item.changes || []).length === 1 ? "" : "s"} · ${item.status || "proposed"}`;
    if (item.type === "exitedReviewMode") return item.review || "Review completed.";
    if (event.method === "turn/plan/updated") return (payload.plan || []).map((entry) => `${entry.status}: ${entry.step}`).join("\n");
    if (event.method === "item/reasoning/summaryTextDelta") return payload.delta || "Reasoning summary updated.";
    if (event.method === "item/reasoning/textDelta") return "Private chain-of-thought is not retained; use plans, receipts and review evidence instead.";
    if (event.method === "turn/diff/updated") return "The candidate diff changed. Open the retained diff below for exact details.";
    if (event.method === "error") return payload.error?.message || "Codex reported an error.";
    return payload.reason || payload.message || "Recorded by the Codex app-server.";
  }

  function agentCodexStatusExplanation(status) {
    return {
      planning: "Inspecting the approved blueprint and repository. No files are being changed.",
      queued_implementation: "The plan is complete. This job will build as soon as the shared worktree is available.",
      awaiting_implementation_approval: "This legacy job is ready to continue through the automatic build sequence.",
      implementing: "Editing only the approved files and running the declared checks.",
      correcting: "Applying the bounded correction you requested, then re-running checks.",
      awaiting_review: "Implementation is complete. Independent review is starting automatically.",
      reviewing: "Reviewing the completed diff for defects, regressions and contract violations.",
      review_complete: "The durable work record, candidate diff and review are ready for your decision.",
      improving_skill: "Using this run's durable evidence to prepare a candidate improvement to the repository-owned skills.",
      awaiting_skill_review: "The skill candidate is complete and must be independently reviewed before handoff.",
      failed: "The current turn failed. The completed written record and last candidate diff remain available.",
      interrupted: "The current turn was stopped. Completed written records remain available.",
    }[status] || "Preparing a bounded Studio-Codex task.";
  }

  function agentCodexWrittenHtml(value) {
    return escapeHtml(String(value || ""))
      .replace(/^### (.+)$/gm, "<h5>$1</h5>")
      .replace(/^## (.+)$/gm, "<h4>$1</h4>")
      .replace(/^# (.+)$/gm, "<h3>$1</h3>")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/^[-*] (.+)$/gm, '<span class="agent-codex-list-item">$1</span>')
      .replace(/\n/g, "<br>");
  }

  function agentCodexRecord(event) {
    const item = event.payload?.item || {};
    const detail = agentCodexEventDetail(event);
    const time = escapeHtml(new Date(event.occurred_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    if (item.type === "agentMessage" || item.type === "exitedReviewMode" || event.method === "turn/plan/updated") {
      const kind = item.type === "agentMessage" ? "Codex" : item.type === "exitedReviewMode" ? "Review" : "Plan";
      return `<article class="agent-codex-record written"><i>${kind}</i><div><header><strong>${escapeHtml(event.label)}</strong><time>${time}</time></header><div class="agent-codex-written">${agentCodexWrittenHtml(detail)}</div></div></article>`;
    }
    if (["commandExecution", "fileChange", "mcpToolCall", "webSearch"].includes(item.type)) {
      return `<article class="agent-codex-record receipt"><i>Receipt</i><div><header><strong>${escapeHtml(event.label)}</strong><time>${time}</time></header><p>${escapeHtml(detail)}</p></div></article>`;
    }
    const className = event.method === "error" ? "error" : "milestone";
    return `<article class="agent-codex-record ${className}"><i>${event.method === "error" ? "Error" : "Step"}</i><div><header><strong>${escapeHtml(event.label)}</strong><time>${time}</time></header><p>${escapeHtml(detail)}</p></div></article>`;
  }

  function agentCodexReceipt(event) {
    const item = event.payload?.item || {};
    const detail = agentCodexEventDetail(event);
    const compact = detail.replace(/\s+/g, " ").trim();
    const preview = compact.length > 180 ? `${compact.slice(0, 177)}…` : compact;
    const status = item.status || (item.type === "fileChange" ? "recorded" : "complete");
    const kind = {
      commandExecution: "Command",
      fileChange: "Files",
      mcpToolCall: "Tool",
      webSearch: "Search",
    }[item.type] || "Operation";
    const time = escapeHtml(new Date(event.occurred_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    const fullReceipt = compact.length > 180
      ? `<details><summary>View full receipt</summary><pre>${escapeHtml(detail)}</pre></details>`
      : "";
    return `<article class="agent-codex-receipt"><span>${escapeHtml(kind)}</span><div><header><strong>${escapeHtml(event.label)}</strong><time>${time}</time></header><p>${escapeHtml(preview)}</p>${fullReceipt}</div><b class="${String(status).toLowerCase()}">${escapeHtml(status)}</b></article>`;
  }

  function agentCodexDocuments(session) {
    const documents = [...(session.documents || [])];
    if (session.latest_diff && !documents.some((item) => item.kind === "candidate_diff" && item.content === session.latest_diff)) {
      documents.push({ document_id: "latest-candidate-diff", kind: "candidate_diff", title: "Current candidate diff", created_at: session.updated_at, content: session.latest_diff });
    }
    if (!documents.length) return "";
    return `<details class="agent-codex-documents"><summary><span>Saved documents</span><b>${documents.length}</b><small>Final written artifacts persist with this session.</small></summary>${documents.map((document) => `<details><summary><strong>${escapeHtml(document.title || document.kind)}</strong><small>${escapeHtml(document.phase || "session")} · ${escapeHtml(document.digest?.slice(0, 12) || "current")}</small></summary><pre>${escapeHtml(document.content || "")}</pre></details>`).join("")}</details>`;
  }

  function renderAgentCodexBridge() {
    const status = labState.agentCodexStatus;
    const transport = status?.transport || {};
    const badge = $("#agent-codex-status");
    if (transport.process_active && transport.account?.authenticated) {
      badge.textContent = "Codex ready";
      badge.className = "ready";
      $("#agent-codex-status-copy").textContent = `${transport.version || "Codex"} · authenticated · development worktree`;
    } else if (status && transport.available) {
      badge.textContent = transport.account?.checked ? "Sign-in required" : "Available";
      badge.className = transport.account?.checked ? "warning" : "";
      $("#agent-codex-status-copy").textContent = transport.last_error || `${transport.version || "Codex CLI"} is installed; start only after proposal approval.`;
    } else if (status) {
      badge.textContent = "Unavailable";
      badge.className = "warning";
      $("#agent-codex-status-copy").textContent = transport.last_error || "The local Codex CLI was not found.";
    }
    $("#agent-codex-check").classList.toggle("hidden", Boolean(status && transport.available));
    const stage = agentCodexStage();
    const stages = ["prepare", "run", "admit"];
    const activeIndex = stages.indexOf(stage);
    $$('[data-codex-stage]').forEach((element) => {
      const index = stages.indexOf(element.dataset.codexStage);
      element.classList.toggle("active", index === activeIndex);
      element.classList.toggle("complete", index < activeIndex);
    });
    const proposal = labState.agentCodexProposal;
    const session = labState.agentCodexSession;
    $("#agent-codex-empty").classList.toggle("hidden", Boolean(proposal || session));
    $("#agent-codex-session").classList.toggle("hidden", !proposal && !session);
    if (!proposal && !session) return;
    const summary = $("#agent-codex-summary");
    const jobs = labState.agentCodexSessions || [];
    const jobPicker = jobs.length > 1 ? `<select class="agent-codex-job-picker" data-codex-session-picker aria-label="Studio Codex job">${jobs.map((job) => `<option value="${escapeHtml(job.session_id)}"${job.session_id === session?.session_id ? " selected" : ""}>${escapeHtml((job.status || "job").replaceAll("_", " "))} · ${escapeHtml(job.session_id.slice(-8))}</option>`).join("")}</select>` : "";
    summary.innerHTML = `<header><span>${session ? "Development job" : "Development proposal"}</span><strong>${escapeHtml(session?.session_id || proposal.proposal_id)}</strong><b>${escapeHtml((session?.status || proposal.status).replaceAll("_", " "))}</b>${jobPicker}</header>
      <dl><div><dt>Blueprint</dt><dd>${escapeHtml(proposal?.blueprint?.name || labState.agentStudioCandidate?.name || "Approved agent")}</dd></div><div><dt>Purpose</dt><dd>${escapeHtml((proposal?.purpose || "build_candidate").replaceAll("_", " "))}</dd></div><div><dt>Skill</dt><dd>${escapeHtml(session?.skill?.id || proposal?.skill?.id || "build-servicefabric-agent")}</dd></div><div><dt>Workspace</dt><dd>${escapeHtml(session?.workspace || status?.workspace?.path || "development worktree")}</dd></div><div><dt>Authority</dt><dd>Worktree only · approval on request · no network</dd></div></dl>
      ${session ? `<div class="agent-codex-now"><span>Now</span><p>${escapeHtml(agentCodexStatusExplanation(session.status))}</p></div>` : ""}
      ${proposal?.status === "draft" ? '<p>Authorization freezes the blueprint, allowed paths, verification commands and cost-bearing development boundary.</p>' : ""}`;
    const toolbar = $("#agent-codex-toolbar");
    if (!session) {
      const gate = proposal.readiness_gate || {};
      const blockers = gate.blockers || [];
      toolbar.innerHTML = proposal.status === "draft"
        ? (gate.ready_for_approval
          ? '<button class="button primary" type="button" data-codex-action="approve-proposal">Review and authorize job</button><small>This is the only required decision before Codex runs the bounded plan, implementation, tests and independent review.</small>'
          : `<button class="button ghost" type="button" data-codex-action="refine-findings">Resolve ${blockers.length} material finding${blockers.length === 1 ? "" : "s"}</button><small>The proposal carries every Studio requirement and cannot be approved until they pass.</small>`)
        : '<button class="button primary" type="button" data-codex-action="start-session">Start authorized job</button><small>Use this only for an approved proposal restored from an earlier session.</small>';
      const resolutionScope = gate.resolution_scope || [];
      $("#agent-codex-events").innerHTML = `<article><i>Prepared</i><div><strong>${proposal.purpose === "resolve_findings" ? "Codex resolution scope prepared" : gate.ready_for_approval ? "All configuration gates passed" : "Handoff retained with explicit blockers"}</strong><p>${escapeHtml((proposal.allowed_paths || []).length)} allowed paths · ${(proposal.verification_commands || []).length} verification commands · ${resolutionScope.length} finding${resolutionScope.length === 1 ? "" : "s"} in scope</p></div></article>${resolutionScope.map((item) => `<article><i>${proposal.purpose === "resolve_findings" ? "Scope" : "Blocked"}</i><div><strong>${escapeHtml(item.statement)}</strong><p>${escapeHtml(item.proposed_correction)}</p></div></article>`).join("")}`;
      return;
    }
    const active = ["planning", "queued_implementation", "awaiting_implementation_approval", "implementing", "correcting", "awaiting_review", "reviewing", "improving_skill", "awaiting_skill_review"].includes(session.status);
    const buttons = [];
    if (session.status === "review_complete") buttons.push('<button class="button ghost" type="button" data-codex-action="show-correction">Request correction</button><button class="button ghost" type="button" data-codex-action="skill-revision">Improve skills from this run</button><button class="button primary" type="button" data-codex-action="handoff">Prepare Registry admission</button>');
    if (active) buttons.push('<button class="button danger" type="button" data-codex-action="interrupt">Interrupt</button>');
    toolbar.innerHTML = `${buttons.join("")}<small>${active ? "Running asynchronously. You may switch jobs or continue using the Studio." : "The completed development job is waiting for Registry review or a bounded correction."}</small>`;
    const approvals = (session.pending_approvals || []).map((request) => `<article class="approval"><i>Approval</i><div><strong>${escapeHtml(request.method.includes("command") ? "Command request" : "File-change request")}</strong><p>${escapeHtml(request.reason || request.command || "Codex requests permission to continue.")}</p><footer><button class="button primary" type="button" data-codex-approval="accept" data-request-id="${escapeHtml(request.request_id)}">Accept once</button><button class="button ghost" type="button" data-codex-approval="decline" data-request-id="${escapeHtml(request.request_id)}">Decline</button></footer></div></article>`).join("");
    const live = active ? `<section class="agent-codex-live"><i></i><div><span>Working now</span><strong>${escapeHtml(session.live_activity?.label || agentCodexStatusExplanation(session.status))}</strong><small>Processing updates are temporary. Completed writing and work receipts are saved below.</small></div></section>` : "";
    const durableEvents = (session.events || []).slice(-120);
    const technicalTypes = new Set(["commandExecution", "fileChange", "mcpToolCall", "webSearch"]);
    const writtenEvents = durableEvents.filter((event) => !technicalTypes.has(event.payload?.item?.type));
    const technicalEvents = durableEvents.filter((event) => technicalTypes.has(event.payload?.item?.type));
    const record = writtenEvents.length ? `<section class="agent-codex-records"><header><span>Persistent work record</span><small>Plans, conclusions, reviews and decisions</small></header>${writtenEvents.map(agentCodexRecord).join("")}</section>` : "";
    const receipts = technicalEvents.length ? `<details class="agent-codex-receipts"><summary>Run details <b>${technicalEvents.length}</b></summary><div>${technicalEvents.map(agentCodexReceipt).join("")}</div></details>` : "";
    $("#agent-codex-events").innerHTML = live + approvals + record + receipts + agentCodexDocuments(session) || '<div class="agent-codex-empty"><strong>Waiting for Codex</strong><p>Completed plans, messages, changes and reviews will be retained here.</p></div>';
    $("#agent-codex-events").scrollTop = $("#agent-codex-events").scrollHeight;
    if (active) startAgentCodexPolling();
    else stopAgentCodexPolling();
  }

  async function initializeAgentCodexBridge() {
    const [status, proposals, sessions] = await Promise.all([
      agentApi("/api/studios/codex/status"),
      agentApi("/api/studios/codex/proposals"),
      agentApi("/api/studios/codex/sessions?recover=true"),
    ]);
    labState.agentCodexStatus = status;
    labState.agentCodexSessions = sessions.sessions || [];
    labState.agentCodexSession = labState.agentCodexSessions.find((item) => item.status !== "archived") || null;
    labState.agentCodexProposal = labState.agentCodexSession
      ? (proposals.proposals || []).find((item) => item.proposal_id === labState.agentCodexSession.proposal_id) || null
      : (proposals.proposals || []).at(-1) || null;
    renderAgentCodexBridge();
  }

  async function checkAgentCodex() {
    $("#agent-codex-status").textContent = "Checking";
    labState.agentCodexStatus = await agentApi("/api/studios/codex/status?probe=true");
    renderAgentCodexBridge();
  }

  async function prepareAgentCodexProposal({ scroll = true, quiet = false, purpose = null } = {}) {
    if (!labState.agentStudioCandidateValidated || !labState.agentStudioReview) {
      if (!quiet) showToast("Run the Studio configuration review first.", "error");
      return;
    }
    labState.agentCodexProposal = await agentApi("/api/studios/codex/proposals", {
      method: "POST",
      body: JSON.stringify({
        blueprint: labState.agentStudioCandidate,
        build_brief: agentStudioCodexBrief(labState.agentStudioCandidate, false),
        configuration_review: labState.agentStudioReview,
        purpose: purpose || (openAgentReviewRequirements(labState.agentStudioReview).length ? "resolve_findings" : "build_candidate"),
      }),
    });
    labState.agentCodexSession = null;
    renderAgentCodexBridge();
    renderAgentConfigurationReview();
    if (scroll) $("#agent-codex-bridge").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function showAgentCodexApproval() {
    const proposal = labState.agentCodexProposal;
    if (!proposal) return;
    if (!proposal.readiness_gate?.ready_for_approval) {
      showToast("This Codex proposal is not ready because its review identity or prerequisite review is incomplete.", "error");
      return;
    }
    $("#agent-codex-approval-form").classList.remove("hidden");
    $("#agent-codex-reviewer").focus();
  }

  async function approveAgentCodexProposal(event) {
    event.preventDefault();
    const proposal = labState.agentCodexProposal;
    const actorId = $("#agent-codex-reviewer").value.trim();
    const rationale = $("#agent-codex-rationale").value.trim();
    if (!proposal || !actorId || rationale.length < 10) return;
    labState.agentCodexProposal = await agentApi(`/api/studios/codex/proposals/${encodeURIComponent(proposal.proposal_id)}/approve`, {
      method: "POST",
      body: JSON.stringify({ actor_id: actorId, rationale }),
    });
    $("#agent-codex-approval-form").classList.add("hidden");
    await startAgentCodexSession();
  }

  async function startAgentCodexSession() {
    if (!labState.agentCodexProposal || labState.agentCodexProposal.status !== "approved") return;
    labState.agentCodexSession = await agentApi("/api/studios/codex/sessions", {
      method: "POST",
      body: JSON.stringify({ proposal_id: labState.agentCodexProposal.proposal_id }),
    });
    labState.agentCodexSessions = [labState.agentCodexSession, ...(labState.agentCodexSessions || []).filter((item) => item.session_id !== labState.agentCodexSession.session_id)];
    await checkAgentCodex();
    renderAgentCodexBridge();
  }

  async function refreshAgentCodexSession() {
    if (!labState.agentCodexSession) return;
    labState.agentCodexSession = await agentApi(`/api/studios/codex/sessions/${encodeURIComponent(labState.agentCodexSession.session_id)}`);
    labState.agentCodexSessions = (labState.agentCodexSessions || []).map((item) => item.session_id === labState.agentCodexSession.session_id ? labState.agentCodexSession : item);
    renderAgentCodexBridge();
  }

  async function selectAgentCodexSession(sessionId) {
    if (!sessionId) return;
    labState.agentCodexSession = await agentApi(`/api/studios/codex/sessions/${encodeURIComponent(sessionId)}`);
    labState.agentCodexProposal = (await agentApi("/api/studios/codex/proposals")).proposals.find((item) => item.proposal_id === labState.agentCodexSession.proposal_id) || null;
    renderAgentCodexBridge();
  }

  async function improveAgentCodexSkills() {
    const session = labState.agentCodexSession;
    if (!session || session.status !== "review_complete") return;
    labState.agentCodexSession = await agentApi(`/api/studios/codex/sessions/${encodeURIComponent(session.session_id)}/turns`, {
      method: "POST",
      body: JSON.stringify({
        phase: "skill_revision",
        instruction: "Use this completed run to propose only evidence-backed, reusable improvements to the repository-owned ServiceFabric skills. Keep one-off implementation details in the run record.",
      }),
    });
    renderAgentCodexBridge();
  }

  function startAgentCodexPolling() {
    if (labState.agentCodexPollTimer) return;
    labState.agentCodexPollTimer = window.setInterval(() => refreshAgentCodexSession().catch((error) => {
      stopAgentCodexPolling();
      showToast(error.message, "error");
    }), 1200);
  }

  function stopAgentCodexPolling() {
    if (!labState.agentCodexPollTimer) return;
    window.clearInterval(labState.agentCodexPollTimer);
    labState.agentCodexPollTimer = null;
  }

  async function implementAgentCodexPlan() {
    const session = labState.agentCodexSession;
    if (!session) return;
    labState.agentCodexSession = await agentApi(`/api/studios/codex/sessions/${encodeURIComponent(session.session_id)}/turns`, {
      method: "POST",
      body: JSON.stringify({ phase: "implementation", instruction: "Implement the approved plan and stop after focused verification and a complete handoff." }),
    });
    renderAgentCodexBridge();
  }

  async function reviewAgentCodexChanges() {
    const session = labState.agentCodexSession;
    if (!session) return;
    labState.agentCodexSession = await agentApi(`/api/studios/codex/sessions/${encodeURIComponent(session.session_id)}/review`, { method: "POST", body: "{}" });
    renderAgentCodexBridge();
  }

  async function interruptAgentCodex() {
    const session = labState.agentCodexSession;
    if (!session) return;
    labState.agentCodexSession = await agentApi(`/api/studios/codex/sessions/${encodeURIComponent(session.session_id)}/interrupt`, { method: "POST", body: "{}" });
    renderAgentCodexBridge();
  }

  async function resolveAgentCodexApproval(requestId, decision) {
    const session = labState.agentCodexSession;
    if (!session) return;
    labState.agentCodexSession = await agentApi(`/api/studios/codex/sessions/${encodeURIComponent(session.session_id)}/approvals`, {
      method: "POST",
      body: JSON.stringify({ request_id: requestId, decision }),
    });
    renderAgentCodexBridge();
  }

  async function submitAgentCodexCorrection(event) {
    event.preventDefault();
    const session = labState.agentCodexSession;
    const instruction = $("#agent-codex-correction").value.trim();
    if (!session || !instruction) return;
    labState.agentCodexSession = await agentApi(`/api/studios/codex/sessions/${encodeURIComponent(session.session_id)}/turns`, {
      method: "POST",
      body: JSON.stringify({ phase: "correction", instruction }),
    });
    $("#agent-codex-correction").value = "";
    $("#agent-codex-correction-form").classList.add("hidden");
    renderAgentCodexBridge();
  }

  function prepareAgentCodexHandoff() {
    const session = labState.agentCodexSession;
    if (!session) return;
    const handoff = `Studio–Codex development job ${session.session_id}\nDevelopment proposal: ${session.proposal_id}\nStatus: ${session.status}\nThread: ${session.thread_id}\nWorkspace: ${session.workspace}\nReview: ${session.review || "Review completed; inspect the retained event record and diff."}\n\nNo merge or Registry admission has been performed.`;
    navigator.clipboard.writeText(handoff).then(() => showToast("Registry Admission record copied. Admission remains a separate human decision.", "success"));
  }

  async function loadCapabilityRun(runId) {
    if (!runId) return;
    renderCapabilityRun(await agentApi(`/api/studios/capabilities/runs/${encodeURIComponent(runId)}`));
  }

  async function deleteCapabilityRun() {
    const runId = labState.selectedCapabilityRun?.manifest?.run_id;
    if (!runId || !window.confirm("Delete this temporary capability test run? This cannot be recovered.")) return;
    await agentApi(`/api/studios/capabilities/runs/${encodeURIComponent(runId)}`, { method: "DELETE" });
    labState.selectedCapabilityRun = null;
    await loadCapabilityRuns();
    $("#capability-run-review").innerHTML = '<div class="capability-empty">Run deleted.</div>';
    $("#capability-delete-run").disabled = true;
  }

  async function initializeCapabilityStudio(force = false) {
    if (!force && labState.capabilityCatalogue) return;
    const [catalogue] = await Promise.all([
      agentApi("/api/studios/capabilities/catalogue"),
      loadCapabilityProposals(),
      loadCapabilityRuns(),
      loadCapabilityDesignSessions(),
    ]);
    labState.capabilityCatalogue = catalogue;
    $("#capability-family-filter").innerHTML = '<option value="">All families</option>' + (catalogue.families || []).map((item) => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("");
    renderCapabilityLibrary();
    const first = (catalogue.capabilities || []).find((item) => item.test_health === "fixture_ready");
    if (first) selectCapability(first.capability_id);
  }

  function renderStudioProfile(resetDraft = false) {
    const profile = selectedStudioProfile();
    if (!profile) return;
    const select = $("#studio-profile-select");
    select.innerHTML = studioProfiles().map((item) => `<option value="${escapeHtml(item.studio_id)}">${escapeHtml(item.title)}</option>`).join("");
    select.value = profile.studio_id;
    $("#studio-availability").textContent = profile.availability.replaceAll("_", " ");
    const capabilityStudio = profile.studio_id === "capability";
    const agentStudio = profile.studio_id === "agent";
    const mandateStudio = profile.studio_id === "portfolio_mandate";
    $("#capability-studio").classList.toggle("hidden", !capabilityStudio);
    $("#agent-studio-companion").classList.toggle("hidden", !agentStudio);
    $("#mandate-studio").classList.toggle("hidden", !mandateStudio);
    $("#studio-generic-workbench").classList.toggle("hidden", capabilityStudio || agentStudio || mandateStudio);
    if (capabilityStudio) {
      initializeCapabilityStudio().catch((error) => renderCapabilityConversation(error.message));
      return;
    }
    if (agentStudio) {
      initializeAgentStudioCompanion().catch((error) => {
        $("#agent-companion-identity").textContent = `Unavailable · ${error.message}`;
      });
      return;
    }
    if (mandateStudio) {
      initializeMandateStudio(resetDraft).catch((error) => {
        $("#mandate-review").innerHTML = `<div class="mandate-empty"><strong>Mandate Studio unavailable</strong><p>${escapeHtml(error.message)}</p></div>`;
      });
      return;
    }
    const riskPackage = profile.studio_id === "risk_analysis" ? selectedRiskAnalysisPackage()?.definition : null;
    if (resetDraft || !$("#studio-object-brief").value) {
      $("#studio-object-name").value = riskPackage?.display_name || "";
      $("#studio-object-brief").value = riskPackage?.risk_question || profile.purpose;
      $("#studio-capability-brief").value = `${profile.companion_policy}\n\nCandidates: ${profile.companion_examples.join(", ")}`;
      $("#studio-test-brief").value = `Ask the selected agent to use the admitted capabilities to apply, challenge and explain the ${profile.definition_label}.`;
      labState.studioBuildBrief = null;
      $("#studio-codex-brief").textContent = "Prepare a build brief.";
      $("#studio-copy-brief").disabled = true;
    }
    if (profile.registry_kind) populateDefinitionSelect("#studio-saved-object", profile.registry_kind, `No saved ${profile.definition_label}`);
    else {
      $("#studio-saved-object").innerHTML = `<option value="">Registry support requires ${escapeHtml(profile.availability)}</option>`;
      $("#studio-saved-object").disabled = true;
    }
    populateDefinitionSelect("#studio-agent", "agent", "No saved agent");
    $("#studio-fixture").innerHTML = (labState.platformArchitecture.fixture_profiles || []).map((item) => `<option value="${escapeHtml(item.fixture_id)}">${escapeHtml(item.label)}</option>`).join("");
    $("#studio-portfolio").innerHTML = (labState.platformArchitecture.portfolios || []).map((item) => `<option value="${escapeHtml(item.portfolio_id)}">${escapeHtml(item.title)}</option>`).join("") || '<option value="">No portfolio</option>';
    $("#studio-prepare-application").disabled = !profile.registry_kind || $("#studio-saved-object").disabled || $("#studio-agent").disabled;
    renderRiskAnalysisPackage();
  }

  function openStudio(studioId) {
    if (!studioProfiles().some((item) => item.studio_id === studioId)) return;
    labState.selectedStudioId = studioId;
    switchWorkspace("studio", true, "system");
    renderStudioProfile(true);
  }

  function prepareStudioCodexBrief() {
    const profile = selectedStudioProfile();
    if (!profile) return;
    const name = $("#studio-object-name").value.trim() || `New ${profile.definition_label}`;
    const objectBrief = $("#studio-object-brief").value.trim();
    const capabilityBrief = $("#studio-capability-brief").value.trim();
    const riskPackage = profile.studio_id === "risk_analysis" ? selectedRiskAnalysisPackage()?.definition : null;
    const packageContext = riskPackage ? `\n\nReference package\n- Resolution: ${riskPackage.resolution_mode}\n- Output: ${riskPackage.output_boundary}\n- Data roles: ${riskPackage.data_roles.map((item) => item.role_id).join(", ")}\n- Analytical roles: ${riskPackage.capability_roles.map((item) => item.role_id).join(", ")}\n- ArchitectureOutput fields: ${riskPackage.output_fields.map((item) => item.section_id).join(", ")}\n- Temporal rule: ${riskPackage.temporal_envelope.eligibility_field} inside ${riskPackage.temporal_envelope.as_of_binding}\n- Admission rule: retain decision-value or research-value findings; empty output is valid.` : "";
    labState.studioBuildBrief = `ServiceFabric Studio build brief\n\nStudio: ${profile.title}\nObject: ${name}\nCanonical type: ${profile.definition_label}\nRequired skill: ${profile.skill_id}\nAvailability boundary: ${profile.availability}\n\nObject contract\n${objectBrief}\n\nCompanion capability contract\n${capabilityBrief}${packageContext}\n\nBuild together\n- Reuse existing canonical contracts and registries before adding a new type.\n- Implement the object model and only the capabilities needed to create, validate, lifecycle, modify or apply it.\n- Keep data preparation, typed inputs, results, receipts, authority and denied effects explicit.\n- Add representative, failure and adversarial fixtures.\n- Add focused tests, concise documentation and a Registry candidate projection.\n- Run in an isolated Git worktree; return diff, verification and merge handoff.\n- Do not publish, merge or remove the worktree without the declared review step.\n- External financial effects remain disabled.\n\nApplication test\n${$("#studio-test-brief").value.trim()}`;
    $("#studio-codex-brief").textContent = labState.studioBuildBrief;
    $("#studio-copy-brief").disabled = false;
  }

  async function copyStudioBrief() {
    if (!labState.studioBuildBrief) return;
    await navigator.clipboard.writeText(labState.studioBuildBrief);
    $("#studio-copy-brief").textContent = "Copied";
    setTimeout(() => { $("#studio-copy-brief").textContent = "Copy brief"; }, 1200);
  }

  function prepareStudioApplication() {
    const profile = selectedStudioProfile();
    if (!profile || !$("#studio-saved-object").value || !$("#studio-agent").value) return;
    switchWorkspace("application", true, "system");
    $("#application-agent").value = $("#studio-agent").value;
    $("#application-fixture").value = $("#studio-fixture").value;
    $("#application-portfolio").value = $("#studio-portfolio").value;
    labState.applicationStudioSelection = (labState.platformArchitecture.saved_definitions || []).find((item) => item.reference === $("#studio-saved-object").value) || null;
    const applicationSelector = {
      agent: "#application-agent",
      capability: "#application-capability",
      scenario: "#application-scenario",
    }[profile.registry_kind];
    if (applicationSelector) $(applicationSelector).value = $("#studio-saved-object").value;
    renderApplicationBoundary();
  }

  function renderDictionary() {
    const query = ($("#dictionary-search")?.value || "").trim().toLowerCase();
    const entries = Object.entries(labState.platformArchitecture?.terminology || {})
      .map(([term, meaning]) => ({ term: term.replaceAll("_", " "), meaning }))
      .filter((item) => !query || `${item.term} ${item.meaning}`.toLowerCase().includes(query))
      .sort((left, right) => left.term.localeCompare(right.term));
    $("#dictionary-count").textContent = String(entries.length);
    $("#dictionary-list").innerHTML = entries.length
      ? entries.map((item) => `<article><strong>${escapeHtml(item.term)}</strong><p>${escapeHtml(item.meaning)}</p></article>`).join("")
      : '<div class="empty-state">No matching term.</div>';
  }

  function mandateAssessmentValue(item) {
    if (item.observed_value === null || item.observed_value === undefined) return "Unavailable";
    if (["portfolio_weight", "annualized_return"].includes(item.unit)) return percent(item.observed_value, 2);
    return String(item.observed_value);
  }

  function renderMandateApplicationCatalogue() {
    const payload = labState.mandateApplicationCatalogue;
    if (!payload) return;
    const ready = Boolean(payload.registry?.ready);
    const selectedScenario = $("#mandate-application-scenario").value;
    $("#mandate-application-mandate").innerHTML = `<option value="${escapeHtml(payload.mandate.object_id)}">${escapeHtml(payload.mandate.name)}</option>`;
    $("#mandate-application-scenario").innerHTML = (payload.scenarios || []).map((item) => `<option value="${escapeHtml(item.scenario_id)}">${escapeHtml(item.label)}</option>`).join("");
    if ((payload.scenarios || []).some((item) => item.scenario_id === selectedScenario)) {
      $("#mandate-application-scenario").value = selectedScenario;
    }
    $("#mandate-application-run").disabled = !ready;
    $("#mandate-application-state").textContent = ready ? "Ready" : "Registration required";
    if (labState.mandateApplicationRun) return;
    const states = [payload.registry?.mandate, payload.registry?.risk_policy].filter(Boolean);
    $("#mandate-application-output").innerHTML = `<div class="mandate-application-premise">
      <div><span>Portfolio</span><strong>${escapeHtml(payload.portfolio.name)}</strong><small>${escapeHtml(payload.portfolio.data_truth.replaceAll("_", " "))} · ${escapeHtml(payload.portfolio.as_of)}</small></div>
      <div><span>Policy</span><strong>${escapeHtml(payload.mandate.policy_name)}</strong><small>${escapeHtml(states.map((item) => item.state.replaceAll("_", " ")).join(" · "))}</small></div>
      <div><span>Authority</span><strong>No effects</strong><small>No LLM call · human review remains separate</small></div>
    </div><div class="application-gate ${ready ? "ready" : ""}"><strong>${ready ? "Exact versions are available" : "Register both exact versions first"}</strong><span>${ready ? "The application will use canonical capabilities and retain their receipts." : "Open Mandate Studio, select Institutional diversified growth mandate, and choose Register versions. Validation alone does not admit it."}</span></div>`;
  }

  function renderMandateApplicationRun() {
    const run = labState.mandateApplicationRun;
    if (!run) return renderMandateApplicationCatalogue();
    const summary = run.summary || {};
    const assessmentCards = (run.assessments || []).map((item) => `<article class="mandate-assessment ${escapeHtml(item.status)}">
      <header><span>${escapeHtml(item.constraint_id.replaceAll("-", " "))}</span><b>${escapeHtml(item.status.replaceAll("_", " "))}</b></header>
      <strong>${escapeHtml(item.statement)}</strong>
      <div><span>Observed</span><b>${escapeHtml(mandateAssessmentValue(item))}</b><small>${escapeHtml(item.criterion)} · ${escapeHtml(item.evaluation_basis)}</small></div>
      <p>${escapeHtml(item.explanation)}</p>
      <footer><span>${escapeHtml(item.capability_id)} · ${escapeHtml(item.capability_status)}</span><span>${escapeHtml(item.governance.governance_level.replaceAll("_", " "))} · no effects</span></footer>
    </article>`).join("");
    const receipts = (run.capability_receipts || []).map((item) => `<div><b>${escapeHtml(item.capability_id)}</b><span>${escapeHtml(item.status)} · ${escapeHtml(item.input_contract)} → ${escapeHtml(item.output_contract || "no output")}</span><small>${item.warnings?.length ? escapeHtml(item.warnings.join(" ")) : "Typed request and result digests retained · effects none"}</small></div>`).join("");
    const proposals = (run.decision_proposals || []).map((item) => `<article class="mandate-decision-card">
      <span>Decision proposal · human review required</span><h3>${escapeHtml(item.question)}</h3><p>${escapeHtml(item.why_now)}</p>
      <dl><div><dt>Recommendation</dt><dd>${escapeHtml(item.recommendation.replaceAll("_", " "))}</dd></div><div><dt>Governance</dt><dd>D1 · human only</dd></div><div><dt>Consequence</dt><dd>${escapeHtml(item.downstream_workflow_preview)}</dd></div></dl>
      <small>Temporary application work product · not admitted to the Decision Repository</small>
    </article>`).join("") || '<div class="empty-state">No mandate result required a Decision Proposal.</div>';
    $("#mandate-application-state").textContent = run.status.replaceAll("_", " ");
    $("#mandate-application-output").innerHTML = `<div class="mandate-run-summary">
      <div><span>Compliant</span><strong>${summary.compliant || 0}</strong></div><div><span>Attention</span><strong>${summary.attention || 0}</strong></div><div><span>Breach</span><strong>${summary.breach || 0}</strong></div><div><span>Unable to assess</span><strong>${summary.unable_to_assess || 0}</strong></div>
    </div><div class="mandate-run-message"><strong>${escapeHtml(run.interpretation.message)}</strong><span>Deterministic explanation · LLM called: ${run.interpretation.llm_called ? "yes" : "no"}</span></div>
    <div class="mandate-assessment-grid">${assessmentCards}</div>
    <div class="mandate-run-lower"><section><header><span>Capability work record</span><b>${run.capability_receipts.length} calls</b></header>${receipts}</section><section><header><span>Decision review</span><b>${run.decision_proposals.length} proposal</b></header>${proposals}</section></div>
    <details class="mandate-run-input"><summary>Exact input boundary</summary><pre>${escapeHtml(JSON.stringify({run_id: run.run_id, data_truth: run.input.data_truth, portfolio: run.input.portfolio.reference, mandate: run.input.mandate.reference, risk_policy: run.input.risk_policy.reference, as_of: run.input.portfolio.as_of, point_in_time_rule: run.input.point_in_time_rule, eligible_market_observations: run.input.eligible_market_observations, required_positions: run.input.required_positions, effects: run.effects}, null, 2))}</pre></details>`;
  }

  async function initializeMandateApplication(force = false) {
    if (!force && labState.mandateApplicationCatalogue) return renderMandateApplicationCatalogue();
    labState.mandateApplicationCatalogue = await agentApi("/api/application/mandate");
    labState.mandateApplicationRun = null;
    renderMandateApplicationCatalogue();
  }

  async function executeMandateApplication() {
    const button = $("#mandate-application-run");
    button.disabled = true;
    button.textContent = "Running…";
    $("#mandate-application-state").textContent = "Calculating";
    try {
      labState.mandateApplicationRun = await agentApi("/api/application/mandate/run", {
        method: "POST",
        body: JSON.stringify({
          mandate_id: $("#mandate-application-mandate").value,
          scenario_id: $("#mandate-application-scenario").value,
        }),
      });
      renderMandateApplicationRun();
    } finally {
      button.disabled = !labState.mandateApplicationCatalogue?.registry?.ready;
      button.textContent = "Run mandate review";
    }
  }

  function renderPlatformWorkspaces(payload) {
    labState.platformArchitecture = payload;
    populateDefinitionSelect("#application-agent", "agent", "No saved agent definition");
    populateDefinitionSelect("#application-capability", "capability", "No saved capability definition");
    populateDefinitionSelect("#application-scenario", "scenario", "No saved scenario definition");
    $("#application-fixture").innerHTML = (payload.fixture_profiles || []).map((item) => `<option value="${escapeHtml(item.fixture_id)}">${escapeHtml(item.label)}</option>`).join("");
    $("#application-portfolio").innerHTML = (payload.portfolios || []).length
      ? payload.portfolios.map((item) => `<option value="${escapeHtml(item.portfolio_id)}">${escapeHtml(item.title)} · ${item.holdings?.length || 0} positions</option>`).join("")
      : '<option value="">No reviewed portfolio available</option>';
    $("#application-future-dependencies").innerHTML = (payload.future_dependencies || []).map((item) => `<article><b>${escapeHtml(item.phase)}</b><strong>${escapeHtml(item.capability)}</strong><span>${escapeHtml(item.unlocks)}</span></article>`).join("");
    const hasAgent = definitionOptions("agent").length > 0;
    $("#application-open-runner").disabled = !hasAgent;
    $("#application-status").textContent = hasAgent ? "Boundary ready" : "Index an agent first";
    renderApplicationBoundary();
    renderStudioProfile();
    renderDictionary();
    initializeMandateApplication().catch((error) => {
      $("#mandate-application-state").textContent = "Unavailable";
      $("#mandate-application-output").innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
    });
  }

  async function loadPlatformWorkspaces(force = false) {
    if (labState.platformArchitecture && !force) {
      renderPlatformWorkspaces(labState.platformArchitecture);
      return;
    }
    try {
      const payload = await agentApi("/api/platform/workspaces");
      renderPlatformWorkspaces(payload);
    } catch (error) {
      $("#application-status").textContent = "Unavailable";
      $("#dictionary-list").innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
    }
  }

  function selectedPlatformDefinition(selector) {
    const reference = $(selector)?.value;
    return (labState.platformArchitecture?.saved_definitions || []).find((item) => item.reference === reference) || null;
  }

  function renderApplicationBoundary() {
    if (!labState.platformArchitecture) return;
    const fixtureId = $("#application-fixture").value;
    const fixture = (labState.platformArchitecture.fixture_profiles || []).find((item) => item.fixture_id === fixtureId);
    const portfolio = (labState.platformArchitecture.portfolios || []).find((item) => item.portfolio_id === $("#application-portfolio").value);
    const selections = [
      ["Agent", selectedPlatformDefinition("#application-agent")],
      ["Studio object", labState.applicationStudioSelection],
      ["Capability", selectedPlatformDefinition("#application-capability")],
      ["Scenario", selectedPlatformDefinition("#application-scenario")],
    ];
    $("#application-preview").innerHTML = `<div class="panel-heading"><div><span class="panel-label">Exact application boundary</span><h2>${escapeHtml(fixture?.label || "No fixture selected")}</h2></div><span class="truth-chip">${escapeHtml(fixture?.data_truth || "unknown")}</span></div>
      <p class="application-premise">${escapeHtml(fixture?.description || "Select a fixture context.")}</p>
      <dl class="application-boundary-list"><div><dt>Portfolio</dt><dd>${escapeHtml(portfolio?.title || "Unavailable")}</dd></div>${selections.map(([label, item]) => `<div><dt>${escapeHtml(label)}</dt><dd>${item ? `${escapeHtml(item.display_name)}<small>${escapeHtml(item.reference)} · ${escapeHtml(item.lifecycle_state)}</small>` : "Not selected"}</dd></div>`).join("")}</dl>
      <div class="application-gate"><strong>${selections[0][1] ? "Boundary is reviewable" : "Blocked: no saved agent"}</strong><span>The current runner supports the same real and synthetic fixture modes, but does not yet compile the selected Registry AgentRole into its Studio blueprint. PLATFORM-P8 binds the selected agent and every selected definition into one executable vertical slice; until then, all unbound selections remain declared test intent.</span></div>`;
  }

  function openApplicationRunner() {
    const agent = selectedPlatformDefinition("#application-agent");
    if (!agent) {
      showToast("Save an agent definition in the Registry before opening Agent Application.", "error");
      return;
    }
    const fixture = $("#application-fixture").value;
    if (fixture === "simulated_intraday") {
      switchWorkspace("cycle", true, "application");
      return;
    }
    switchWorkspace("agent", true, "application");
    switchAgentOutputTab("run");
    setAgentRunDataMode(fixture === "licensed_real" ? "real_duckdb" : "synthetic_behavior_sample");
    const portfolioId = $("#application-portfolio").value;
    if (fixture === "licensed_real" && portfolioId && $("#agent-real-portfolio")) $("#agent-real-portfolio").value = portfolioId;
    setTimeout(() => $("#agent-output-run")?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
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

  async function refreshDefinitionConsumers() {
    labState.platformArchitecture = null;
    labState.experimentOptions = null;
    await loadPlatformWorkspaces(true);
  }

  async function indexRegistry(record) {
    const identity = registryIdentity(record);
    if (!window.confirm(`Index ${record.projection.display_name} as a local candidate?\n\nThis stores metadata, digests, and one lifecycle receipt. It does not copy, run, deploy, or publish the definition.`)) return;
    $("#registry-status").textContent = "Indexing";
    await agentApi("/api/registry/index", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ identity, actor: "local.developer" }) });
    await loadRegistryCatalogue();
    await refreshDefinitionConsumers();
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
    await refreshDefinitionConsumers();
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
    await refreshDefinitionConsumers();
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

  function resultDataLabel(value) {
    return ({
      licensed_real: "Historical data",
      public_real: "Public historical data",
      synthetic_sample: "Development-only sample",
      reviewed_synthetic: "Reviewed sample",
      simulated: "Simulation",
    })[value] || artifactLabel(value);
  }

  function filteredArtifacts() {
    const search = ($("#artifact-search")?.value || "").trim().toLowerCase();
    const view = $("#artifact-view-filter")?.value || "active";
    return labState.artifactRecords.filter((record) => {
      const manifest = record.manifest;
      const matchesSearch = !search || [manifest.title, manifest.artifact_id, manifest.run_id, manifest.created_by].some((item) => String(item || "").toLowerCase().includes(search));
      const matchesView = view === "all"
        || (view === "recovery" && ["tombstoned", "deleted"].includes(record.state))
        || record.state === view;
      return matchesSearch && matchesView;
    });
  }

  function renderArtifactSummary(summary = {}) {
    $("#artifact-summary").innerHTML = [
      [summary.retained_runs || 0, "saved runs"],
      [summary.artifacts || 0, "saved results"],
      [summary.files || 0, "files"],
      [artifactBytes(summary.total_size_bytes || 0), `${summary.need_attention || 0} need checking`],
    ].map(([value, label]) => `<div><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`).join("");
  }

  function renderArtifactCandidates() {
    const candidates = labState.artifactCandidates;
    $("#artifact-admission").classList.toggle("hidden", !candidates.length);
    $("#artifact-candidate-count").textContent = `${candidates.length} candidate${candidates.length === 1 ? "" : "s"}`;
    $("#artifact-candidates").innerHTML = candidates.map((candidate) => `<article class="artifact-candidate">
      <div><strong>${escapeHtml(candidate.run_id)}</strong><span class="registry-badge ${candidate.eligible ? "indexed" : ""}">${candidate.eligible ? "Can be saved" : "Cannot be saved"}</span><p>${candidate.eligible ? `${resultDataLabel(candidate.data_truth)} · ${candidate.file_count} files · ${artifactBytes(candidate.total_size_bytes)}` : artifactLabel(candidate.blockers?.[0])}</p>${(candidate.warnings || []).map((warning) => `<small>${escapeHtml(warning)}</small>`).join("")}</div>
      <button class="button ${candidate.eligible ? "primary" : "ghost"}" type="button" data-admit-run="${escapeHtml(candidate.run_id)}" ${candidate.eligible ? "" : "disabled"}>Review and save</button>
    </article>`).join("");
  }

  function renderArtifactList() {
    const records = filteredArtifacts();
    $("#artifact-result-count").textContent = `${records.length} result${records.length === 1 ? "" : "s"}`;
    if (!records.length) {
      $("#artifact-list").innerHTML = '<div class="empty-state">No saved results match this view.</div>';
      $("#artifact-detail").innerHTML = '<div class="empty-state">Select a saved result to open its files.</div>';
      return;
    }
    if (!records.some((item) => item.manifest.artifact_id === labState.selectedArtifactId)) labState.selectedArtifactId = records[0].manifest.artifact_id;
    $("#artifact-list").innerHTML = records.map((record) => {
      const manifest = record.manifest;
      return `<button class="registry-result ${manifest.artifact_id === labState.selectedArtifactId ? "selected" : ""}" type="button" data-artifact-id="${escapeHtml(manifest.artifact_id)}">
        <span class="registry-result-top"><b>${escapeHtml(manifest.kind)}</b><span class="registry-badge lifecycle">${escapeHtml(artifactLabel(record.state))}</span></span>
        <strong>${escapeHtml(manifest.title)}</strong><code>${escapeHtml(manifest.run_id || manifest.artifact_id)}</code>
        <small>${escapeHtml(resultDataLabel(manifest.data_truth))} · ${manifest.files.length} files · ${artifactBytes(manifest.total_size_bytes)}</small>
      </button>`;
    }).join("");
    selectArtifact(labState.selectedArtifactId, false);
  }

  async function selectArtifact(artifactId, reload = true) {
    labState.selectedArtifactId = artifactId;
    if (reload || !labState.selectedArtifactDetail || labState.selectedArtifactDetail.manifest.artifact_id !== artifactId) {
      $("#artifact-detail").innerHTML = '<div class="empty-state">Opening and checking the selected files.</div>';
      try {
        labState.selectedArtifactDetail = await agentApi(`/api/artifacts/${encodeURIComponent(artifactId)}`);
      } catch (error) {
        $("#artifact-detail").innerHTML = `<div class="empty-state"><strong>Saved result unavailable.</strong><br>${escapeHtml(error.message)}</div>`;
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
      <div><strong>${escapeHtml(file.path)}</strong><span>${artifactBytes(file.size_bytes)}</span></div>
      <div>${file.preview_mode !== "none" ? `<button class="text-button" data-preview-file="${escapeHtml(file.file_id)}" type="button">Open</button>` : '<span class="registry-badge">Cannot preview</span>'}${file.download_allowed ? `<button class="text-button" data-download-file="${escapeHtml(file.file_id)}" type="button">Download</button>` : ""}</div>
    </article>`).join("");
    const lifecycleAction = record.state === "active"
      ? '<button class="button ghost" id="artifact-archive" type="button">Archive</button>'
      : ["archived", "tombstoned"].includes(record.state)
        ? '<button class="button ghost" id="artifact-restore" type="button">Restore</button>'
        : "";
    const deletionAction = preview?.eligible
      ? `<button class="button danger" id="artifact-delete-action" type="button">${preview.operation === "finalize_delete" ? "Finalize deletion" : "Move to recovery"}</button>`
      : "";
    $("#artifact-detail").innerHTML = `<header class="registry-detail-header"><span class="panel-label">Saved result · ${escapeHtml(artifactLabel(record.state))}</span><h2>${escapeHtml(manifest.title)}</h2><p>${escapeHtml(manifest.run_id ? `Files from run ${manifest.run_id}` : "Files produced by one run")}</p></header>
      <div class="registry-detail-badges"><span class="registry-badge ${verification.valid ? "indexed" : ""}">${verification.valid ? "Files checked" : "Files need checking"}</span><span class="registry-badge">${escapeHtml(resultDataLabel(manifest.data_truth))}</span></div>
      <details open><summary>Files</summary><div class="artifact-files">${files}</div><pre class="artifact-preview hidden" id="artifact-file-preview"></pre></details>
      <details><summary>Technical details</summary><dl class="registry-facts"><div><dt>Created</dt><dd>${escapeHtml(new Date(manifest.created_at).toLocaleString())}</dd></div><div><dt>Created by</dt><dd>${escapeHtml(manifest.created_by)}</dd></div><div><dt>Method</dt><dd>${escapeHtml(manifest.creation_method)}</dd></div><div><dt>File ID</dt><dd><code>${escapeHtml(manifest.artifact_id)}</code></dd></div></dl><div class="registry-receipts">${receipts.map((receipt) => `<article><b>${escapeHtml(artifactLabel(receipt.operation))}</b><span>${escapeHtml(new Date(receipt.occurred_at).toLocaleString())}</span><p>${escapeHtml(receipt.rationale)}</p></article>`).join("")}</div></details>
      <div class="registry-actions"><button class="button" id="artifact-verify" type="button">Check files</button>${lifecycleAction}${deletionAction}${preview && !preview.eligible ? `<p class="registry-blocked">Cannot delete: ${escapeHtml(preview.blockers.join(" · "))}</p>` : ""}</div>`;
  }

  async function loadArtifactCatalogue() {
    if (labState.artifactLoading) return;
    labState.artifactLoading = true;
    $("#artifact-status").textContent = "Loading";
    try {
      const result = await agentApi("/api/artifacts/catalogue?include_deleted=true");
      const researchData = new Set(["licensed_real", "public_real"]);
      labState.artifactRecords = (result.records || []).filter((record) => researchData.has(record.manifest?.data_truth));
      labState.artifactCandidates = (result.candidates || []).filter((candidate) => researchData.has(candidate.data_truth));
      renderArtifactSummary({
        retained_runs: new Set(labState.artifactRecords.map((record) => record.manifest.run_id).filter(Boolean)).size,
        artifacts: labState.artifactRecords.length,
        files: labState.artifactRecords.reduce((total, record) => total + record.manifest.files.length, 0),
        total_size_bytes: labState.artifactRecords.reduce((total, record) => total + Number(record.manifest.total_size_bytes || 0), 0),
        need_attention: labState.artifactRecords.filter((record) => !record.verification?.valid).length,
      });
      renderArtifactCandidates();
      renderArtifactList();
      $("#artifact-status").textContent = "Ready";
    } catch (error) {
      $("#artifact-status").textContent = "Unavailable";
      $("#artifact-list").innerHTML = `<div class="empty-state"><strong>Saved results unavailable.</strong><br>${escapeHtml(error.message)}</div>`;
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

  function setExperimentDraftFeedback(kind, title, message) {
    const feedback = $("#experiment-draft-feedback");
    feedback.className = `experiment-draft-feedback visible ${kind}`;
    feedback.innerHTML = `<b>${escapeHtml(title)}</b><span>${escapeHtml(message)}</span>`;
  }

  function renderExperimentOptions() {
    const options = labState.experimentOptions || { system_assets: [], portfolios: [], defaults: {} };
    const mode = $("#experiment-mode").value;
    const kind = mode === "evaluation_only" ? "evaluation" : "workflow";
    const assets = (options.system_assets || []).filter((item) => item.identity.kind === kind);
    $("#experiment-system-asset").innerHTML = assets.length
      ? assets.map((item) => `<option value="${escapeHtml(item.reference)}">${escapeHtml(item.display_name)} · ${escapeHtml(item.lifecycle_state)} · ${escapeHtml(item.identity.version)}</option>`).join("")
      : `<option value="">No saved ${escapeHtml(kind)} definition · use System Development → Registry</option>`;
    const truth = $("#experiment-truth").value;
    const portfolios = (options.portfolios || []).filter((item) => item.data_truth === truth);
    $("#experiment-portfolio").innerHTML = portfolios.length
      ? portfolios.map((item) => `<option value="${escapeHtml(item.reference)}" data-revision="${escapeHtml(item.data_revision_reference)}">${escapeHtml(item.title || item.portfolio_id)}</option>`).join("")
      : '<option value="">No reviewed source is available for this truth class</option>';
    $("#experiment-data-revision").value = portfolios[0]?.data_revision_reference || "Unavailable until a reviewed source is configured";
    const defaults = options.defaults || {};
    if (defaults.snapshot_policy_reference) $("#experiment-snapshot-policy").value = defaults.snapshot_policy_reference;
    if (defaults.mandate_reference) $("#experiment-mandate").value = defaults.mandate_reference;
    $("#experiment-save-draft").disabled = false;
    if (!assets.length) {
      setExperimentDraftFeedback("blocked", "Draft needs one prerequisite.", `Save an exact ${kind} version in the Registry, then return and refresh this workspace.`);
    } else if (!portfolios.length) {
      setExperimentDraftFeedback("blocked", "Draft needs reviewed data.", `No portfolio is available for the ${experimentLabel(truth)} data-truth class.`);
    } else {
      setExperimentDraftFeedback("ready", "Ready to save.", `${assets[0].display_name} and ${portfolios[0].title || portfolios[0].portfolio_id} are pinned to this draft.`);
    }
  }

  function renderExperimentRunAudit() {
    const audit = labState.experimentRunAudit || { retained_runs: [], acceptance_records: [] };
    const runs = audit.retained_runs || [];
    const signature = runs.map((item) => item.artifact_id).join("|");
    if (labState.experimentRunSignature !== undefined && labState.experimentRunSignature !== signature) {
      $$('[data-run-variable]').forEach((item) => { item.checked = false; });
      labState.experimentRunComparison = null;
      $("#experiment-run-audit-result").innerHTML = '<div class="empty-state">Select two retained runs and declare the intended change before checking the pair.</div>';
    }
    labState.experimentRunSignature = signature;
    const option = (item) => `<option value="${escapeHtml(item.artifact_id)}">${escapeHtml(item.title)} · ${escapeHtml(item.run_id || item.artifact_id)} · ${item.file_count} files</option>`;
    const left = $("#experiment-run-left");
    const right = $("#experiment-run-right");
    const priorLeft = left.value;
    const priorRight = right.value;
    left.innerHTML = runs.length ? runs.map(option).join("") : '<option value="">No retained runs</option>';
    right.innerHTML = runs.length ? runs.map(option).join("") : '<option value="">No retained runs</option>';
    left.value = runs.some((item) => item.artifact_id === priorLeft) ? priorLeft : runs[0]?.artifact_id || "";
    right.value = runs.some((item) => item.artifact_id === priorRight) ? priorRight : runs[1]?.artifact_id || runs[0]?.artifact_id || "";
    $("#experiment-run-count").textContent = `${runs.length} retained run${runs.length === 1 ? "" : "s"}`;
    updateExperimentComparisonAvailability();
  }

  function updateExperimentComparisonAvailability() {
    const left = $("#experiment-run-left").value;
    const right = $("#experiment-run-right").value;
    const enabled = Boolean(left && right && left !== right);
    $("#experiment-run-compare").disabled = !enabled;
    $("#experiment-run-compare").setAttribute("aria-disabled", String(!enabled));
  }

  function matchingRunAcceptance(comparison) {
    const records = labState.experimentRunAudit?.acceptance_records || [];
    return records
      .filter((item) => new Set([item.left_artifact_id, item.right_artifact_id]).size === 2
        && [item.left_artifact_id, item.right_artifact_id].includes(comparison.left.artifact_id)
        && [item.left_artifact_id, item.right_artifact_id].includes(comparison.right.artifact_id))
      .sort((left, right) => Number(right.cycle || 0) - Number(left.cycle || 0))[0] || null;
  }

  function renderExperimentRunComparison(comparison) {
    labState.experimentRunComparison = comparison;
    const changedFiles = comparison.file_comparisons.filter((item) => item.status !== "same").length;
    const status = comparison.thesis_ready ? "Thesis-ready" : comparison.pair_comparable ? "Revision required" : "Rejected";
    const prior = matchingRunAcceptance(comparison);
    const list = (values, empty) => values.length ? `<ul>${values.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : `<p class="registry-helper">${escapeHtml(empty)}</p>`;
    $("#experiment-run-audit-result").innerHTML = `<header class="registry-detail-header"><span class="panel-label">Evidence gate · ${escapeHtml(status)}</span><h2>${escapeHtml(comparison.left.run_id || comparison.left.artifact_id)} → ${escapeHtml(comparison.right.run_id || comparison.right.artifact_id)}</h2><code>${escapeHtml(comparison.comparison_digest)}</code></header>
      <div class="registry-detail-badges"><span class="registry-badge ${comparison.pair_comparable ? "indexed" : "lifecycle"}">Pair ${comparison.pair_comparable ? "comparable" : "confounded"}</span><span class="registry-badge ${comparison.thesis_ready ? "indexed" : "lifecycle"}">Thesis ${comparison.thesis_ready ? "ready" : "not ready"}</span><span class="registry-badge">${comparison.file_comparisons.length} files classified</span><span class="registry-badge">${changedFiles} changed / one-sided</span></div>
      <details open><summary>Gate findings</summary><h3>Blockers</h3>${list(comparison.blockers, "No mechanical comparison blockers.")}<h3>Missing thesis design</h3>${list(comparison.missing_thesis_dimensions, "All thesis-design identities are explicit.")}<h3>Next revision</h3>${list(comparison.next_revision_requirements, "No apparatus revision is required by this gate.")}</details>
      <details><summary>Complete file classification</summary><div class="registry-receipts">${comparison.file_comparisons.map((item) => `<article><b>${escapeHtml(item.status)}</b><code>${escapeHtml(item.path)}</code><span>${escapeHtml(item.left_role || "—")} → ${escapeHtml(item.right_role || "—")}</span></article>`).join("")}</div></details>
      <div class="experiment-form-grid"><label class="field"><span>Acceptance verdict</span><select id="experiment-run-verdict"><option value="${escapeHtml(comparison.suggested_verdict)}">${escapeHtml(experimentLabel(comparison.suggested_verdict))}</option>${comparison.suggested_verdict !== "rejected" ? '<option value="rejected">Rejected</option>' : ""}</select></label><label class="field"><span>Reviewer</span><input id="experiment-run-reviewer" value="local.researcher"></label><label class="field experiment-wide"><span>Rationale</span><textarea id="experiment-run-rationale" rows="2">${escapeHtml(comparison.next_revision_requirements[0] || "Evidence gate reviewed; retain this decision for the next cycle.")}</textarea></label></div>
      <div class="action-row"><button class="button primary" id="experiment-run-record-acceptance" type="button">Record cycle ${Number(prior?.cycle || 0) + 1}</button><span class="action-hint">${prior ? `Supersedes ${escapeHtml(prior.artifact_id)} · ${escapeHtml(prior.verdict)}` : "Creates the first immutable acceptance record for this pair."}</span></div>`;
    $("#experiment-run-record-acceptance").addEventListener("click", () => recordExperimentRunAcceptance().catch((error) => { $("#experiment-status").textContent = error.message; }));
  }

  async function compareExperimentRuns() {
    const planned = $$('[data-run-variable]:checked').map((item) => item.value).sort();
    const comparison = await agentApi("/api/experiments/run-audit/compare", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
      left_artifact_id: $("#experiment-run-left").value,
      right_artifact_id: $("#experiment-run-right").value,
      planned_variable_dimensions: planned,
    }) });
    renderExperimentRunComparison(comparison);
  }

  async function recordExperimentRunAcceptance() {
    const comparison = labState.experimentRunComparison;
    if (!comparison) return;
    const prior = matchingRunAcceptance(comparison);
    await agentApi("/api/experiments/run-audit/acceptance", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
      left_artifact_id: comparison.left.artifact_id,
      right_artifact_id: comparison.right.artifact_id,
      planned_variable_dimensions: comparison.planned_variable_dimensions,
      expected_comparison_digest: comparison.comparison_digest,
      verdict: $("#experiment-run-verdict").value,
      actor: $("#experiment-run-reviewer").value,
      rationale: $("#experiment-run-rationale").value,
      prior_acceptance_artifact_id: prior?.artifact_id || null,
    }) });
    labState.experimentRunAudit = await agentApi("/api/experiments/run-audit");
    renderExperimentRunAudit();
    renderExperimentRunComparison(comparison);
    $("#experiment-status").textContent = "Acceptance recorded";
  }

  function renderExperimentWorkspace(result) {
    const summary = result.summary || {};
    $("#experiment-summary").innerHTML = [
      [summary.experiments || 0, "experiments"],
      [labState.experimentRecords.filter((item) => item.state === "ready").length, "prepared records"],
      [summary.experiment_sets || 0, "comparison sets"],
      [summary.issues || 0, "integrity issues"],
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
    $("#experiment-queue").innerHTML = '<div class="empty-state">No executable worker is attached. Prepared experiments stop here until the worker contract is implemented.</div>';
    $("#experiment-sets").innerHTML = labState.experimentSets.length ? labState.experimentSets.map((item) => `<article class="experiment-set-card ${item.issues?.length ? "attention" : ""}"><b>${escapeHtml(item.definition.name)}</b><span>${item.members.length} experiments · ${item.planned_runs} planned runs</span><small>${escapeHtml(item.issues?.[0]?.message || (item.comparison_ready ? "All results are ready to compare" : "Waiting for completed and reviewed members"))}</small></article>`).join("") : '<div class="empty-state">Group experiments only when they answer a shared research question.</div>';
    $("#experiment-create-set").disabled = !labState.experimentRecords.length;
  }

  function renderExperimentFixture(value) {
    labState.experimentFixture = value;
    const status = value.persisted ? "Resolved" : value.admitted ? "Accepted" : "Review pending";
    $("#experiment-fixture-status").textContent = status;
    $("#experiment-fixture-resolve").disabled = !value.admitted;
    $("#experiment-fixture-resolve").textContent = value.persisted ? "Verify same fixture again" : "Resolve accepted fixture";
    const claims = (value.prohibited_claims || []).map((item) => experimentLabel(item)).join(" · ");
    $("#experiment-fixture-content").innerHTML = `<div class="experiment-fixture-grid">
      <article class="experiment-fixture-card"><b>Question</b><p>${escapeHtml(value.question)}</p><code>${escapeHtml(value.fixture_context_digest)}</code></article>
      <article class="experiment-fixture-card"><b>Comparison</b><span>${escapeHtml(value.baseline)}</span><span>${escapeHtml(value.metric)}</span><span>${(value.outcome_states || []).map(escapeHtml).join(" → ")}</span></article>
      <article class="experiment-fixture-card"><b>Reachable context</b><span>${(value.reachable_datasets || []).length} exact datasets</span><span>${(value.reachable_capabilities || []).length} allowed capabilities</span><span>${Number(value.resolution_receipts || 0)} resolution receipts</span></article>
      <article class="experiment-fixture-card experiment-fixture-guard"><b>Calibration boundary</b><span>${escapeHtml(claims)}</span><span>Human-only · effects disabled · labels sealed</span></article>
    </div>`;
  }

  async function resolveExperimentFixture() {
    const button = $("#experiment-fixture-resolve");
    button.disabled = true;
    $("#experiment-fixture-status").textContent = "Verifying";
    try {
      const value = await agentApi("/api/experiments/fixture-context/resolve", { method: "POST" });
      renderExperimentFixture(value);
      $("#experiment-status").textContent = "Fixture resolved";
    } catch (error) {
      $("#experiment-fixture-status").textContent = "Blocked";
      $("#experiment-status").textContent = error.message;
      button.disabled = false;
    }
  }

  function renderExperimentRunTraces(value) {
    labState.experimentRunTraces = value;
    const traces = value.traces || [];
    const resolved = Boolean(labState.experimentFixture?.persisted);
    $("#experiment-trace-status").textContent = traces.length ? `${traces.length} retained` : resolved ? "Ready" : "Fixture required";
    $("#experiment-trace-create").disabled = !resolved;
    $("#experiment-trace-content").innerHTML = traces.length ? traces.map((record) => `<article class="experiment-trace-card"><b>${escapeHtml(record.manifest.title)}</b><code>${escapeHtml(record.manifest.run_id || record.manifest.artifact_id)}</code><span>Fixture trace retained in the Artifact Repository · ${escapeHtml(record.revision)}</span></article>`).join("") : `<div class="empty-state">${resolved ? "No trace yet. Record one bounded observation before building a general worker." : "Resolve the Fixture Context first."}</div>`;
  }

  function renderExperimentalProgram(value) {
    labState.experimentalProgram = value;
    const phases = value.phases || [];
    $("#experiment-program-status").textContent = phases.every((item) => item.status === "ready" || item.status === "admitted") ? "Ready" : "Qualification needed";
    $("#experiment-program-content").innerHTML = phases.map((item) => `<article class="experiment-program-card"><header><b>${escapeHtml(item.phase)} · ${escapeHtml(item.name)}</b><span class="truth-chip">${escapeHtml(experimentLabel(item.status))}</span></header><p>${escapeHtml(item.delivered)}</p><span><strong>Next:</strong> ${escapeHtml(item.next_decision)}</span></article>`).join("");
    const blockers = value.arm_plan?.blockers || [];
    $("#experiment-program-blockers").innerHTML = blockers.map((item) => `<div class="experiment-issue" role="status"><b>${escapeHtml(experimentLabel(item.issue_id))}</b><span>${escapeHtml(item.message)} <strong>Resolution:</strong> ${escapeHtml(item.resolution)}</span></div>`).join("");
  }

  async function createExperimentRunTrace() {
    const button = $("#experiment-trace-create");
    button.disabled = true;
    $("#experiment-trace-status").textContent = "Recording";
    try {
      await agentApi("/api/experiments/run-traces", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ actor: "local.researcher" }) });
      labState.experimentRunTraces = await agentApi("/api/experiments/run-traces");
      renderExperimentRunTraces(labState.experimentRunTraces);
      $("#experiment-status").textContent = "Trace retained";
    } catch (error) {
      $("#experiment-trace-status").textContent = "Blocked";
      $("#experiment-status").textContent = error.message;
      button.disabled = false;
    }
  }

  function renderExperimentIssues(issues = []) {
    $("#experiment-issues").innerHTML = issues.map((issue) => `<div class="experiment-issue" role="alert"><b>${escapeHtml(issue.label || "Integrity attention")}</b><span>${escapeHtml(issue.message || String(issue))}</span></div>`).join("");
  }

  function renderExperimentDetail() {
    const record = labState.experimentRecords.find((item) => item.definition.experiment_id === labState.selectedExperimentId);
    if (!record) {
      $("#experiment-detail").innerHTML = '<div class="empty-state">Select an experiment to inspect its exact definition.</div>';
      return;
    }
    const value = record.definition;
    const canPrepare = ["draft", "validated"].includes(record.state);
    const isLegacyLifecycle = !["draft", "validated", "ready"].includes(record.state);
    const sourceRows = value.source_bindings.map((item) => `<div><dt>${escapeHtml(experimentLabel(item.role))}</dt><dd><code>${escapeHtml(item.reference)}</code><small>${escapeHtml(item.revision)} · ${escapeHtml(item.digest)}</small></dd></div>`).join("");
    const assets = value.system_assets.map((item) => `<article><b>${escapeHtml(experimentLabel(item.kind))}</b><code>${escapeHtml(item.kind)}:${escapeHtml(item.namespace)}:${escapeHtml(item.asset_id)}@${escapeHtml(item.version)}</code></article>`).join("");
    $("#experiment-detail").innerHTML = `<header class="registry-detail-header"><span class="panel-label">${escapeHtml(experimentLabel(value.presentation_mode))} · ${escapeHtml(experimentLabel(record.state))}</span><h2>${escapeHtml(value.name)}</h2><code>${escapeHtml(value.experiment_id)}</code><p>${escapeHtml(value.purpose)}</p></header>
      <div class="registry-detail-badges"><span class="registry-badge indexed">${escapeHtml(experimentLabel(value.data_truth))}</span><span class="registry-badge">Effects ${escapeHtml(value.external_effects)}</span><span class="registry-badge">${value.budget.max_model_calls} model calls max</span><span class="registry-badge">$${Number(value.budget.max_cost_usd).toFixed(2)} max</span></div>
      <details open><summary>Question and temporal boundary</summary><p class="registry-helper"><strong>Hypothesis:</strong> ${escapeHtml(value.hypothesis)}</p><dl class="registry-facts"><div><dt>Period</dt><dd>${escapeHtml(value.temporal.start_date)} → ${escapeHtml(value.temporal.end_date)}</dd></div><div><dt>Eligibility</dt><dd>${escapeHtml(experimentLabel(value.temporal.as_of_policy))}</dd></div><div><dt>Replay</dt><dd>${escapeHtml(experimentLabel(value.temporal.replay_schedule))}</dd></div><div><dt>Definition digest</dt><dd><code>${escapeHtml(value.definition_digest)}</code></dd></div></dl></details>
      <details open><summary>Immutable source bindings</summary><dl class="registry-facts">${sourceRows}</dl></details>
      <details open><summary>Versioned system assets</summary><div class="registry-receipts">${assets}</div></details>
      <details><summary>Lifecycle receipts</summary><div class="registry-receipts">${record.receipts.map((receipt) => `<article><b>${escapeHtml(experimentLabel(receipt.to_state))}</b><span>${escapeHtml(receipt.actor)} · ${escapeHtml(new Date(receipt.occurred_at).toLocaleString())}</span><p>${escapeHtml(receipt.rationale)}</p></article>`).join("")}</div></details>
      <div class="registry-actions">${canPrepare ? '<button class="button primary" type="button" data-experiment-prepare>Prepare experiment</button><p class="registry-helper">One decision runs deterministic binding validation and records the experiment as ready for a future worker.</p>' : ""}${record.state === "ready" ? '<div class="experiment-worker-placeholder"><b>Prepared · worker unavailable</b><span>The immutable definition is ready, but execution cannot begin until a compatible worker is attached.</span></div>' : ""}${isLegacyLifecycle ? '<div class="experiment-worker-placeholder"><b>Historical lifecycle record</b><span>This record predates worker enforcement. It cannot be advanced or treated as executed evidence from this workspace.</span></div>' : ""}</div>`;
  }

  function updateReplayNotes() {
    const setup = labState.historicalReplaySetup;
    if (!setup) return;
    const workflow = setup.workflows.find((item) => item.id === $("#replay-workflow").value);
    const portfolio = setup.portfolio_mandates.find((item) => item.id === $("#replay-portfolio").value);
    const evaluation = setup.evaluations.find((item) => item.id === $("#replay-evaluation").value);
    const requiresModelConsent = workflow && workflow.id !== "B0";
    $("#replay-model-consent").classList.toggle("hidden", !requiresModelConsent);
    if (!requiresModelConsent) $("#replay-authorize-model").checked = false;
    $("#replay-workflow-note").textContent = workflow ? `${workflow.type}. ${workflow.note}` : "";
    $("#replay-portfolio-note").textContent = portfolio ? `${portfolio.positions} named holdings · ${portfolio.mandate.name} ${portfolio.mandate.version}. Holdings are held fixed across the replay.` : "";
    $("#replay-evaluation-note").textContent = evaluation?.note || "";
    const consentGranted = !requiresModelConsent || $("#replay-authorize-model").checked;
    $("#replay-run").disabled = !setup.ready || !workflow?.runnable || !consentGranted;
    $("#replay-run-hint").textContent = workflow?.runnable
      ? workflow.id === "B0"
        ? "Runs the fixed-rule reference locally with no model calls."
        : consentGranted
          ? `${workflow.id} uses live ${workflow.type.toLowerCase()} inference on each daily workflow cycle. Pilot limit: 20 model calls per run.`
          : "Review and accept the per-run OpenAI context authorization to enable this treatment."
      : "Choose a workflow marked available for this replay.";
  }

  function renderHistoricalReplaySetup(setup) {
    labState.historicalReplaySetup = setup;
    $("#replay-datasets").innerHTML = setup.datasets.map((item) => `<article class="${item.available ? "ready" : "missing"}"><div><b>${escapeHtml(item.label)}</b><span>${item.available ? "Connected" : "Unavailable"}</span></div><p>${item.start_date ? `${escapeHtml(item.start_date)} to ${escapeHtml(item.end_date)}` : "No usable rows"}</p><small>${Number(item.rows || 0).toLocaleString()} licensed rows · read only</small></article>`).join("");
    $("#replay-workflow").innerHTML = setup.workflows.map((item) => `<option value="${escapeHtml(item.id)}" ${item.runnable ? "" : "disabled"}>${escapeHtml(item.type)} — ${escapeHtml(item.label)}${item.runnable ? "" : " (not yet available)"}</option>`).join("");
    $("#replay-portfolio").innerHTML = setup.portfolio_mandates.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)} — ${escapeHtml(item.mandate.name)}</option>`).join("");
    $("#replay-evaluation").innerHTML = setup.evaluations.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`).join("");
    ["#replay-workflow", "#replay-portfolio", "#replay-evaluation", "#replay-start", "#replay-end"].forEach((selector) => { $(selector).disabled = !setup.ready; });
    const period = setup.period;
    $("#replay-start").min = period.minimum;
    $("#replay-start").max = period.maximum;
    $("#replay-start").value = period.default_start;
    $("#replay-end").min = period.minimum;
    $("#replay-end").max = period.maximum;
    $("#replay-end").value = period.default_end;
    $("#replay-period-note").textContent = `${period.minimum} to ${period.maximum}. Maximum ${period.maximum_calendar_days} calendar days in this first slice.`;
    $("#replay-notice").innerHTML = setup.ready
      ? `<b>Ready for a real-data apparatus run.</b><span>${escapeHtml(setup.methodology_note)}</span>`
      : '<b>The replay cannot run.</b><span>One or more licensed datasets or reviewed portfolio definitions are unavailable.</span>';
    $("#experiment-status").textContent = setup.ready ? "Ready" : "Unavailable";
    updateReplayNotes();
  }

  function renderHistoricalReplayResult(result) {
    const evaluation = result.evaluation;
    const hierarchy = result.hierarchy || null;
    const architectureOutput = result.run_record?.architecture_output || null;
    const cycleOutputs = result.run_record?.architecture_outputs || [];
    const findingEpisodes = result.run_record?.finding_episodes || [];
    const metricSpecifications = result.run_record?.metric_specifications || result.evaluation?.metric_specifications || [];
    const instrumentHistories = result.portfolio?.instrument_lifetime_metrics || [];
    const processingReceipts = result.run_record?.processing_receipts || [];
    const resourceUsage = result.execution_regime?.resource_usage || null;
    const eventRecords = result.clock.flatMap((row) => (row.ravenpack_events?.event_stream || []).map((item) => ({ ...item, market_session: row.market_observation_session || row.date })));
    const percent = (value) => value == null ? "—" : `${(Number(value) * 100).toFixed(2)}%`;
    const money = (value) => Number(value).toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
    $("#replay-results").classList.remove("hidden");
    const statusLabel = (value) => value.replaceAll("_", " ");
    const score = (value) => value == null ? "—" : Number(value).toFixed(2);
    const hierarchyHtml = hierarchy ? `<section class="replay-hierarchy">
        <div><span>Study</span><b>${escapeHtml(hierarchy.study.title)}</b></div>
        <div><span>Experiment</span><b>${escapeHtml(hierarchy.experiment.experiment_id)}</b></div>
        <div><span>Case</span><b>${escapeHtml(hierarchy.case.case_id)}</b></div>
        <div><span>Run</span><b>${escapeHtml(hierarchy.run.run_id)}</b></div>
        <div class="replay-regimes"><span>Regime</span><p>${hierarchy.regimes.map((item) => `<i>${escapeHtml(item.dimension)}: ${escapeHtml(item.value)}</i>`).join("") || "Not classified"}</p></div>
      </section>` : `<div class="replay-legacy">Saved before the experimental hierarchy was introduced. The original result remains available unchanged.</div>`;
    const architectureHtml = architectureOutput ? `<section class="replay-architecture-output">
        <header><span>Latest architecture output</span><b>${cycleOutputs.length || 1} dated workflow cycle${cycleOutputs.length === 1 ? "" : "s"}</b></header>
        <div class="replay-output-summary"><article><span>Assessment</span><b>${escapeHtml(architectureOutput.assessment_state)}</b></article><article><span>Severity</span><b>${architectureOutput.severity} / 3</b></article><article><span>Confidence</span><b>${percent(architectureOutput.confidence)}</b></article><article><span>Decision</span><b>${escapeHtml(statusLabel(architectureOutput.decision.monitoring_action))}</b></article></div>
        <p>${escapeHtml(architectureOutput.risk_interpretation)}</p>
        <small>${escapeHtml(architectureOutput.confidence_method)}</small>
      </section>
      ${cycleOutputs.length ? `<details class="replay-clock"><summary>Architecture outputs by workflow cycle <small>${cycleOutputs.length} immutable outputs</small></summary><div class="replay-table-wrap"><table class="replay-table"><thead><tr><th>As of</th><th>State</th><th>Change</th><th>Severity</th><th>Confidence</th><th>Findings</th><th>Decision</th></tr></thead><tbody>${cycleOutputs.map((output) => `<tr><td>${escapeHtml(output.as_of || "—")}</td><td>${escapeHtml(output.assessment_state)}</td><td>${escapeHtml(statusLabel(output.change_since_previous || "initial"))}</td><td>${output.severity} / 3</td><td>${percent(output.confidence)}</td><td>${output.findings.length}</td><td>${escapeHtml(statusLabel(output.decision.monitoring_action))}</td></tr>`).join("")}</tbody></table></div></details>` : ""}
      ${findingEpisodes.length ? `<section class="replay-rules"><header><span>Finding episodes</span><b>Repeated daily warnings consolidated</b></header><table class="replay-table"><thead><tr><th>Risk</th><th>Rule</th><th>First detected</th><th>Last detected</th><th>Cycles</th><th>Maximum severity</th><th>State</th></tr></thead><tbody>${findingEpisodes.map((episode) => `<tr><td>${escapeHtml(episode.risk_type)}</td><td>${escapeHtml(episode.rule_id)}</td><td>${escapeHtml(episode.first_detected_at)}</td><td>${escapeHtml(episode.last_detected_at)}</td><td>${episode.observation_count}</td><td>${episode.maximum_severity} / 3</td><td>${escapeHtml(episode.state)}</td></tr>`).join("")}</tbody></table></section>` : ""}` : "";
    const metricSpecificationsHtml = metricSpecifications.length ? `<details class="replay-clock"><summary>Metric definitions <small>Full-history and point-in-time policies</small></summary><div class="replay-metric-specs">${metricSpecifications.map((item) => `<article><b>${escapeHtml(item.label)}</b><span>${escapeHtml(statusLabel(item.history_policy))} · ${escapeHtml(item.unit)}</span><p>${escapeHtml(item.formula)}</p><small>${escapeHtml(item.adjustment_policy)}</small></article>`).join("")}</div></details>` : "";
    const instrumentHistoryHtml = instrumentHistories.length ? `<details class="replay-clock"><summary>Instrument history used before the experiment window <small>${instrumentHistories.length} holdings</small></summary><div class="replay-table-wrap"><table class="replay-table"><thead><tr><th>Instrument</th><th>History</th><th>Returns</th><th>Lifetime volatility</th><th>Maximum drawdown</th><th>Quality</th></tr></thead><tbody>${instrumentHistories.map((item) => `<tr><td>${escapeHtml(item.instrument)}</td><td>${escapeHtml(item.history_start || "—")} to ${escapeHtml(item.history_end || "—")}</td><td>${Number(item.return_observations).toLocaleString()}</td><td>${percent(item.annualised_volatility)}</td><td>${percent(item.maximum_drawdown)}</td><td>${escapeHtml(item.quality)}</td></tr>`).join("")}</tbody></table></div></details>` : "";
    const processingHtml = processingReceipts.length ? `<details class="replay-clock"><summary>Trigger-to-output processing <small>${processingReceipts.length} blocked workflow cycles</small></summary><p class="replay-detail-note">Replay time remains fixed from trigger until the final validated architecture output. Wall-clock time includes context preparation, capabilities, every model call and output validation. ${resourceUsage ? `Total busy processing: ${(Number(resourceUsage.processing_wall_ms) / 1000).toFixed(3)} seconds · Cost: ${resourceUsage.estimated_cost_usd == null ? "unpriced" : `$${Number(resourceUsage.estimated_cost_usd).toFixed(6)}`}.` : ""} Cost remains unavailable rather than guessed when no reviewed pricing snapshot matches the model.</p><div class="replay-table-wrap"><table class="replay-table"><thead><tr><th>Replay time</th><th>Wall time</th><th>Capabilities</th><th>Model calls</th><th>Input tokens</th><th>Output tokens</th><th>Cost</th><th>Capability time</th><th>Model time</th><th>Validation</th></tr></thead><tbody>${processingReceipts.map((item) => `<tr><td>${escapeHtml(item.replay_triggered_at)}</td><td>${Number(item.processing_wall_ms).toFixed(0)} ms</td><td>${item.capability_calls}</td><td>${item.model_calls}</td><td>${Number(item.input_tokens || 0).toLocaleString()}</td><td>${Number(item.output_tokens || 0).toLocaleString()}</td><td>${item.estimated_cost_usd == null ? "Unpriced" : `$${Number(item.estimated_cost_usd).toFixed(6)}`}</td><td>${Number(item.capability_processing_ms).toFixed(0)} ms</td><td>${Number(item.model_processing_ms).toFixed(0)} ms</td><td>${Number(item.validation_processing_ms).toFixed(0)} ms</td></tr>`).join("")}</tbody></table></div></details>` : "";
    const eventTimingHtml = eventRecords.length ? `<details class="replay-clock"><summary>Chronological event processing <small>${eventRecords.length} eligible event clusters</small></summary><p class="replay-detail-note">Event time is distinct from information availability. Relevance time identifies when the admitted relevance signal became available. Agent analysis may wait for its workflow cycle; any portfolio action remains deferred to the first eligible end-of-day close.</p><div class="replay-table-wrap"><table class="replay-table"><thead><tr><th>Company</th><th>Event time</th><th>Available</th><th>Relevance identified</th><th>Analysis triggered</th><th>Processing</th><th>Earliest execution</th></tr></thead><tbody>${eventRecords.map((item) => `<tr><td>${escapeHtml(item.company_name || "—")}</td><td>${escapeHtml(item.event_time || "—")}</td><td>${escapeHtml(item.information_available_at || "—")}</td><td>${escapeHtml(item.relevance_identified_at || "—")}</td><td>${escapeHtml(item.analysis_triggered_at || "Not run by B0")}</td><td>${item.analysis_processing_ms == null ? "—" : `${Number(item.analysis_processing_ms).toFixed(0)} ms`}</td><td>${escapeHtml(item.earliest_end_of_day_execution_at || "First eligible daily close")}</td></tr>`).join("")}</tbody></table></div></details>` : "";
    const executionEffect = evaluation.end_of_day_execution_effect;
    const executionEffectHtml = executionEffect ? `<section class="replay-method-note"><b>End-of-day execution effect</b><span>${escapeHtml(executionEffect.interpretation)} Current measurable target: ${escapeHtml(executionEffect.measurable_with_current_data)}.</span></section>` : "";
    $("#replay-results").innerHTML = `<header><div><span class="panel-label">Completed real-data run</span><h2>Results</h2><p>${escapeHtml(result.run_id)} · ${escapeHtml(result.period.start)} to ${escapeHtml(result.period.end)}</p></div><span class="truth-chip">${result.saved ? "Saved" : "Not saved"}</span></header>
      ${hierarchyHtml}
      <div class="replay-summary"><article><b>${evaluation.trading_days}</b><span>Trading days</span></article><article><b>${result.workflow.model_calls || 0}</b><span>Model calls</span></article><article><b>${evaluation.warnings}</b><span>Rule warnings</span></article><article><b>${evaluation.ravenpack_events.toLocaleString()}</b><span>Eligible event records</span></article><article><b>${evaluation.missing_position_observations}</b><span>Missing price observations</span></article><article><b>${evaluation.compustat_companies_available}</b><span>Companies with accounts</span></article></div>
      <section class="replay-context"><div><span>Portfolio</span><b>${escapeHtml(result.portfolio.id)}</b><p>${result.portfolio.holdings.map((item) => `${escapeHtml(item.company_name)} (${escapeHtml(item.ticker)})`).join(" · ")}</p></div><div><span>Mandate</span><b>${escapeHtml(result.mandate.name)} ${escapeHtml(result.mandate.version)}</b><p>${escapeHtml(result.mandate.objective)}</p></div></section>
      ${architectureHtml}
      ${processingHtml}
      ${eventTimingHtml}
      ${executionEffectHtml}
      ${metricSpecificationsHtml}
      ${instrumentHistoryHtml}
      <section class="replay-dimensions"><header><span>Independent evaluation</span><b>Nine dimensions · scored after the architecture output is fixed</b></header>${evaluation.dimensions.map((item) => `<article class="${escapeHtml(item.status)}"><div><b>${escapeHtml(item.label)}</b><span>${escapeHtml(statusLabel(item.status))}${item.score == null ? "" : ` · ${score(item.score)}`}</span></div><p>${escapeHtml(item.summary)}</p></article>`).join("")}</section>
      <section class="replay-rules"><header><span>Mandate checks</span><b>${escapeHtml(result.mandate.name)}</b></header><table class="replay-table"><thead><tr><th>Rule</th><th>Clause</th><th>Passed</th><th>Breached</th><th>Unavailable</th></tr></thead><tbody>${evaluation.rule_summary.map((item) => `<tr><td><b>${escapeHtml(item.label)}</b></td><td>${escapeHtml(item.clause)}</td><td>${item.passed}</td><td>${item.breached}</td><td>${item.unable_to_assess}</td></tr>`).join("")}</tbody></table></section>
      <div class="replay-method-note"><b>What this result means</b><span>${escapeHtml(evaluation.interpretation)} ${escapeHtml(result.methodology_note)} Evaluation targets the retained ArchitectureOutput.</span></div>
      <details class="replay-clock"><summary>Daily calculations <small>${evaluation.trading_days} trading days</small></summary><div class="replay-table-wrap"><table class="replay-table"><thead><tr><th>Date</th><th>Portfolio value</th><th>Daily change</th><th>Volatility</th><th>Drawdown</th><th>Events</th><th>Warnings</th></tr></thead><tbody>${result.clock.map((row) => `<tr><td>${escapeHtml(row.date)}</td><td>${money(row.portfolio_value)}</td><td>${percent(row.daily_return)}</td><td>${percent(row.annualised_volatility)}</td><td>${percent(row.drawdown)}</td><td>${Number(row.ravenpack_events.count).toLocaleString()}</td><td>${row.warnings.length ? row.warnings.map((item) => `<span class="replay-warning ${escapeHtml(item.level)}">${escapeHtml(item.reason)}</span>`).join("") : "—"}</td></tr>`).join("")}</tbody></table></div></details>`;
    $("#experiment-status").textContent = "Run completed";
    $("#replay-results").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function loadSavedHistoricalReplays() {
    const result = await agentApi("/api/experiments/replay-runs");
    const select = $("#replay-saved-select");
    select.innerHTML = result.runs.length
      ? `<option value="">Choose a saved run</option>${result.runs.map((item) => `<option value="${escapeHtml(item.artifact_id)}">${escapeHtml(item.portfolio_id)} · ${escapeHtml(item.period.start)} to ${escapeHtml(item.period.end)}</option>`).join("")}`
      : '<option value="">No saved runs</option>';
    $("#replay-load-saved").disabled = true;
  }

  async function loadSelectedHistoricalReplay() {
    const artifactId = $("#replay-saved-select").value;
    if (!artifactId) return;
    $("#experiment-status").textContent = "Loading saved run";
    try {
      const result = await agentApi(`/api/experiments/replay-runs/${encodeURIComponent(artifactId)}`);
      renderHistoricalReplayResult(result);
      $("#replay-run-hint").textContent = "Saved run loaded. No calculation was repeated.";
    } catch (error) {
      $("#experiment-status").textContent = "Load failed";
      $("#replay-run-hint").textContent = error.message;
    }
  }

  async function runHistoricalReplay(event) {
    event.preventDefault();
    const button = $("#replay-run");
    button.disabled = true;
    button.textContent = "Running…";
    let completionMessage = "";
    $("#experiment-status").textContent = "Running";
    $("#replay-run-hint").textContent = "Reading each trading day from CRSP, Compustat and RavenPack.";
    try {
      const result = await agentApi("/api/experiments/replay-runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
        workflow_id: $("#replay-workflow").value,
        portfolio_id: $("#replay-portfolio").value,
        start_date: $("#replay-start").value,
        end_date: $("#replay-end").value,
        evaluation_id: $("#replay-evaluation").value,
        save_result: $("#replay-save").checked,
        authorize_external_model_calls: $("#replay-authorize-model").checked,
      }) });
      renderHistoricalReplayResult(result);
      if (result.saved) await loadSavedHistoricalReplays();
      completionMessage = result.saved ? "Run complete and saved. It can now be reloaded." : "Run complete. This result was not saved.";
    } catch (error) {
      $("#experiment-status").textContent = "Run failed";
      $("#replay-run-hint").textContent = error.message;
    } finally {
      button.textContent = "Run historical replay";
      updateReplayNotes();
      if (completionMessage) $("#replay-run-hint").textContent = completionMessage;
    }
  }

  async function loadExperimentWorkspace() {
    if (labState.experimentLoading) return;
    labState.experimentLoading = true;
    $("#experiment-status").textContent = "Loading";
    try {
      renderExperimentIssues([]);
      const setup = await agentApi("/api/experiments/replay-setup");
      renderHistoricalReplaySetup(setup);
      await loadSavedHistoricalReplays();
    } catch (error) {
      $("#experiment-status").textContent = "Unavailable";
      $("#replay-notice").innerHTML = `<b>Readiness could not be checked.</b><span>${escapeHtml(error.message)} No synthetic fallback was used.</span>`;
      $("#replay-run").disabled = true;
    } finally {
      labState.experimentLoading = false;
    }
  }

  async function createExperimentDraft(event) {
    event.preventDefault();
    const submit = $("#experiment-save-draft");
    const originalLabel = submit.textContent;
    const reference = $("#experiment-system-asset").value;
    const asset = (labState.experimentOptions?.system_assets || []).find((item) => item.reference === reference);
    const portfolio = $("#experiment-portfolio").value;
    const required = [
      ["Experiment name", $("#experiment-name").value],
      ["Purpose", $("#experiment-purpose").value],
      ["Testable hypothesis", $("#experiment-hypothesis").value],
      ["Start date", $("#experiment-start").value],
      ["End date", $("#experiment-end").value],
      ["Mandate version", $("#experiment-mandate").value],
      ["Snapshot policy", $("#experiment-snapshot-policy").value],
      ["Data revision", $("#experiment-data-revision").value],
    ];
    const missing = required.filter(([, value]) => !String(value || "").trim()).map(([label]) => label);
    if (missing.length) {
      setExperimentDraftFeedback("error", "Draft not saved.", `Complete: ${missing.join(", ")}.`);
      $("#experiment-status").textContent = "Needs input";
      return;
    }
    if (!asset) {
      setExperimentDraftFeedback("blocked", "Draft not saved.", "Select a saved workflow or evaluation definition. Use Open Registry if no version is available.");
      $("#experiment-status").textContent = "Registry definition required";
      $("#experiment-open-registry").focus();
      return;
    }
    if (!portfolio) {
      setExperimentDraftFeedback("blocked", "Draft not saved.", "Select a reviewed portfolio for the declared data-truth class.");
      $("#experiment-status").textContent = "Reviewed portfolio required";
      return;
    }
    if ($("#experiment-start").value > $("#experiment-end").value) {
      setExperimentDraftFeedback("error", "Draft not saved.", "The observation start date must be on or before the end date.");
      $("#experiment-status").textContent = "Invalid date window";
      return;
    }
    const slug = $("#experiment-name").value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 70) || "experiment";
    const id = `${slug}-${Date.now().toString(36)}`;
    submit.disabled = true;
    submit.textContent = "Saving…";
    setExperimentDraftFeedback("ready", "Saving draft…", "Recording the immutable composition outside Git.");
    try {
      const created = await agentApi("/api/experiments/draft", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
        experiment_id: id,
        name: $("#experiment-name").value,
        purpose: $("#experiment-purpose").value,
        hypothesis: $("#experiment-hypothesis").value,
        start_date: $("#experiment-start").value,
        end_date: $("#experiment-end").value,
        presentation_mode: $("#experiment-mode").value,
        data_truth: $("#experiment-truth").value,
        portfolio_reference: portfolio,
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
      setExperimentDraftFeedback("success", "Immutable draft saved.", `${created.definition.name} is selected below and ready for validation.`);
      $("#experiment-status").textContent = "Draft saved";
      $("#experiment-catalogue").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      setExperimentDraftFeedback("error", "Draft not saved.", error.message);
      $("#experiment-status").textContent = "Save failed";
    } finally {
      submit.disabled = false;
      submit.textContent = originalLabel;
    }
  }

  async function prepareExperiment() {
    let record = labState.experimentRecords.find((item) => item.definition.experiment_id === labState.selectedExperimentId);
    if (!record || !["draft", "validated"].includes(record.state)) return;
    const experimentId = record.definition.experiment_id;
    const transition = async (toState, rationale) => agentApi(`/api/experiments/${encodeURIComponent(experimentId)}/transition`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        to_state: toState,
        actor: "local.researcher",
        rationale,
        idempotency_key: `${toState}-${experimentId}`,
        expected_revision: record.revision,
      }),
    });
    $("#experiment-status").textContent = "Preparing";
    if (record.state === "draft") {
      record = await transition("validated", "Required bindings and the canonical Registry asset passed deterministic validation.");
    }
    if (record.state === "validated") {
      record = await transition("ready", "The immutable definition is prepared for a compatible future worker.");
    }
    await loadExperimentWorkspace();
    $("#experiment-status").textContent = "Prepared · worker unavailable";
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
    $$(".operating-zone-tab").forEach((button) => button.addEventListener("click", () => switchZone(button.dataset.zone)));
    $$(".workspace-tab").forEach((button) => button.addEventListener("click", () => switchWorkspace(button.dataset.workspace, true, button.dataset.zone)));
    $$('[data-workbench-workspace]').forEach((button) => button.addEventListener("click", () => switchWorkspace(button.dataset.workbenchWorkspace, true, "system")));
    $$('[data-open-workspace]').forEach((button) => button.addEventListener("click", () => switchWorkspace(button.dataset.openWorkspace)));
    $$('[data-open-studio]').forEach((control) => {
      control.addEventListener("click", () => openStudio(control.dataset.openStudio));
      control.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        openStudio(control.dataset.openStudio);
      });
    });
    $$('[data-open-registry-kind]').forEach((button) => button.addEventListener("click", () => {
      switchWorkspace("registry", true, "system");
      $("#registry-kind-filter").value = button.dataset.openRegistryKind;
      renderRegistryList();
    }));
    window.addEventListener("popstate", () => {
      const params = new URLSearchParams(window.location.search);
      const workspace = params.get("workspace") || "system";
      const zone = params.get("zone");
      if (["system", "studio", "application", "dictionary", "dataset", "portfolio", "agent", "graph", "registry", "artifacts", "experiments", "decisions", "decision-diligence", "full"].includes(workspace)) switchWorkspace(workspace, false, zoneDefaults[normalizedZone(zone)] ? normalizedZone(zone) : null);
    });
    $("#studio-profile-select").addEventListener("change", (event) => { labState.selectedStudioId = event.target.value; renderStudioProfile(true); });
    $("#studio-prepare-brief").addEventListener("click", prepareStudioCodexBrief);
    $("#studio-copy-brief").addEventListener("click", () => copyStudioBrief().catch(() => showToast("The brief could not be copied.", "error")));
    $("#studio-prepare-application").addEventListener("click", prepareStudioApplication);
    $("#mandate-library-list").addEventListener("click", (event) => {
      const button = event.target.closest("[data-mandate-id]");
      if (!button) return;
      labState.selectedMandateId = button.dataset.mandateId;
      renderMandateLibrary();
      renderMandateReview();
      populateMandateDesigner();
    });
    $("#mandate-review").addEventListener("click", (event) => {
      const gapRuleId = event.target.closest("[data-mandate-capability-gap]")?.dataset.mandateCapabilityGap;
      if (gapRuleId) {
        const record = selectedMandateRecord();
        const candidate = record?.validation?.capability_proposal_candidates?.find((item) => item.rule_id === gapRuleId);
        if (candidate) {
          openStudio("capability");
          $("#capability-requirement").value = candidate.requirement;
          $("#capability-requirement").focus();
          showToast("Metric gap loaded into Capability Studio. Discuss and approve it before backlog registration.", "success");
        }
        return;
      }
      const action = event.target.closest("[data-mandate-action]")?.dataset.mandateAction;
      if (action === "validate") validateSelectedMandate().catch((error) => showToast(error.message, "error"));
      if (action === "register") registerSelectedMandate().catch((error) => showToast(error.message, "error"));
      if (action === "registry") openSelectedMandateInRegistry();
    });
    $("#mandate-design-form").addEventListener("submit", (event) => prepareMandateDesignPreview(event).catch((error) => showToast(error.message, "error")));
    $("#mandate-design-base").addEventListener("change", () => {
      labState.selectedMandateId = $("#mandate-design-base").value;
      const record = selectedMandateRecord();
      if (!record) return;
      $("#mandate-design-name").value = `${record.mandate.name} — new version`;
      $("#mandate-design-objective").value = record.mandate.objective;
    });
    $("#mandate-design-preview").addEventListener("click", (event) => {
      if (!event.target.closest('[data-mandate-design-action="copy"]') || !labState.mandateDesignPreview) return;
      navigator.clipboard.writeText(labState.mandateDesignPreview.studio_codex_brief)
        .then(() => showToast("Mandate diff brief copied for Studio–Codex.", "success"))
        .catch(() => showToast("The Studio–Codex brief could not be copied.", "error"));
    });
    $("#agent-companion-form").addEventListener("submit", submitAgentStudioCompanion);
    $("#agent-companion-reset").addEventListener("click", resetAgentStudioCompanion);
    $("#agent-companion-load-existing").addEventListener("click", () => loadExistingAgentForReview().catch((error) => showToast(error.message, "error")));
    $("#agent-companion-candidate").addEventListener("click", (event) => {
      if (event.target.closest("#agent-candidate-review")) reviewAgentConfiguration().catch((error) => showToast(error.message, "error"));
      if (event.target.closest("#agent-candidate-open")) continueAgentToFullBuilder().catch((error) => showToast(error.message, "error"));
    });
    [$("#agent-companion-review")].filter(Boolean).forEach((panel) => panel.addEventListener("click", (event) => {
      const action = event.target.closest("[data-agent-review-action]")?.dataset.agentReviewAction;
      if (action === "resolve") resolveAgentConfigurationReview().catch((error) => showToast(error.message, "error"));
      if (action === "codex") $("#agent-codex-bridge").scrollIntoView({ behavior: "smooth", block: "start" });
    }));
    $("#agent-codex-check").addEventListener("click", () => checkAgentCodex().catch((error) => showToast(error.message, "error")));
    $("#agent-codex-bridge").addEventListener("click", (event) => {
      const action = event.target.closest("[data-codex-action]")?.dataset.codexAction;
      if (action === "approve-proposal") showAgentCodexApproval();
      if (action === "refine-findings") refineFromConfigurationReview();
      if (action === "start-session") startAgentCodexSession().catch((error) => showToast(error.message, "error"));
      if (action === "implement") implementAgentCodexPlan().catch((error) => showToast(error.message, "error"));
      if (action === "review") reviewAgentCodexChanges().catch((error) => showToast(error.message, "error"));
      if (action === "skill-revision") improveAgentCodexSkills().catch((error) => showToast(error.message, "error"));
      if (action === "interrupt") interruptAgentCodex().catch((error) => showToast(error.message, "error"));
      if (action === "show-correction") $("#agent-codex-correction-form").classList.remove("hidden");
      if (action === "handoff") prepareAgentCodexHandoff();
      const approval = event.target.closest("[data-codex-approval]");
      if (approval) resolveAgentCodexApproval(approval.dataset.requestId, approval.dataset.codexApproval).catch((error) => showToast(error.message, "error"));
    });
    $("#agent-codex-bridge").addEventListener("change", (event) => {
      const picker = event.target.closest("[data-codex-session-picker]");
      if (picker) selectAgentCodexSession(picker.value).catch((error) => showToast(error.message, "error"));
    });
    $("#agent-codex-approval-form").addEventListener("submit", (event) => approveAgentCodexProposal(event).catch((error) => showToast(error.message, "error")));
    $("#agent-codex-cancel-approval").addEventListener("click", () => $("#agent-codex-approval-form").classList.add("hidden"));
    $("#agent-codex-correction-form").addEventListener("submit", (event) => submitAgentCodexCorrection(event).catch((error) => showToast(error.message, "error")));
    $("#capability-prompt").addEventListener("submit", assessCapabilityRequirement);
    $("#capability-conclude-design").addEventListener("click", () => concludeCapabilityDesign().catch((error) => showToast(error.message, "error")));
    $("#capability-reset-chat").addEventListener("click", resetCapabilityDesign);
    $("#capability-session-select").addEventListener("change", (event) => {
      $("#capability-load-session").disabled = !event.target.value;
      $("#capability-delete-session").disabled = !event.target.value;
    });
    $("#capability-load-session").addEventListener("click", () => resumeCapabilityDesignSession().catch((error) => showToast(error.message, "error")));
    $("#capability-delete-session").addEventListener("click", () => deleteCapabilityDesignSession().catch((error) => showToast(error.message, "error")));
    $("#capability-decisions").addEventListener("click", (event) => {
      const button = event.target.closest("[data-capability-decision]");
      if (button) decideCapability(button.dataset.capabilityDecision).catch((error) => showToast(error.message, "error"));
    });
    $("#capability-chat").addEventListener("click", (event) => {
      const button = event.target.closest("[data-select-capability]");
      if (button) selectCapability(button.dataset.selectCapability);
      const option = event.target.closest("[data-capability-quiz-option]");
      if (option && labState.capabilityAssessment?.quiz) {
        const selected = labState.capabilityAssessment.quiz.options[Number(option.dataset.capabilityQuizOption)];
        if (selected) {
          $("#capability-requirement").value = selected.answer;
          $("#capability-requirement").focus();
        }
      }
      if (event.target.closest("[data-capability-quiz-other]")) {
        $("#capability-requirement").value = "";
        $("#capability-requirement").focus();
      }
      const dependency = event.target.closest("[data-capability-dependency]");
      if (dependency) discussCapabilityDependency(dependency.dataset.capabilityDependency);
    });
    $("#capability-blueprint").addEventListener("click", (event) => {
      const transition = event.target.closest("[data-capability-transition]");
      if (transition) transitionCapabilityProposal(transition.dataset.capabilityTransition).catch((error) => showToast(error.message, "error"));
      const draft = event.target.closest("[data-capability-draft-action]");
      if (draft?.dataset.capabilityDraftAction === "approve") approveCapabilityDraft().catch((error) => showToast(error.message, "error"));
      if (draft?.dataset.capabilityDraftAction === "revise") reviseCapabilityDraft();
      if (event.target.closest("[data-capability-delete-proposal]")) deleteCapabilityProposal().catch((error) => showToast(error.message, "error"));
      if (event.target.closest("[data-capability-studio-handoff]")) sendCapabilityDesignToStudio().catch((error) => showToast(error.message, "error"));
      if (event.target.closest("#capability-copy-codex")) {
        const proposal = labState.capabilityProposals.find((item) => item.proposal_id === labState.selectedCapabilityProposalId);
        if (proposal?.studio_codex?.build_brief) navigator.clipboard.writeText(proposal.studio_codex.build_brief).then(() => showToast("Studio–Codex brief copied.", "success"));
      }
    });
    $("#capability-proposal-list").addEventListener("click", (event) => {
      const button = event.target.closest("[data-capability-proposal]");
      if (!button) return;
      labState.selectedCapabilityProposalId = button.dataset.capabilityProposal;
      const proposal = labState.capabilityProposals.find((item) => item.proposal_id === labState.selectedCapabilityProposalId);
      renderCapabilityProposals();
      renderCapabilityBlueprint(proposal);
    });
    $("#capability-library-body").addEventListener("click", (event) => {
      const row = event.target.closest("[data-capability-row]");
      if (row) selectCapability(row.dataset.capabilityRow);
      const packageRow = event.target.closest("[data-capability-package]");
      if (packageRow) selectCapabilityPackage(packageRow.dataset.capabilityPackage);
      const hostRow = event.target.closest("[data-capability-host]");
      if (hostRow) selectCapabilityHost(hostRow.dataset.capabilityHost);
    });
    $("#capability-library-body").addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      const row = event.target.closest("[data-capability-row]");
      if (row) { event.preventDefault(); selectCapability(row.dataset.capabilityRow); }
      const packageRow = event.target.closest("[data-capability-package]");
      if (packageRow) { event.preventDefault(); selectCapabilityPackage(packageRow.dataset.capabilityPackage); }
      const hostRow = event.target.closest("[data-capability-host]");
      if (hostRow) { event.preventDefault(); selectCapabilityHost(hostRow.dataset.capabilityHost); }
    });
    $$('[data-capability-library-tab]').forEach((button) => button.addEventListener("click", () => {
      labState.capabilityLibraryTab = button.dataset.capabilityLibraryTab;
      renderCapabilityLibrary();
    }));
    $$('[data-capability-view]').forEach((button) => button.addEventListener("click", () => {
      labState.capabilityInspectorView = button.dataset.capabilityView;
      renderCapabilityInspector();
    }));
    $$('[data-capability-description]').forEach((button) => button.addEventListener("click", () => {
      labState.capabilityDescriptionView = button.dataset.capabilityDescription;
      renderCapabilityInspector();
    }));
    ["#capability-library-search", "#capability-family-filter", "#capability-status-filter"].forEach((selector) => $(selector).addEventListener(selector.includes("search") ? "input" : "change", renderCapabilityLibrary));
    $("#capability-run-select").addEventListener("change", (event) => loadCapabilityRun(event.target.value).catch((error) => showToast(error.message, "error")));
    $("#capability-delete-run").addEventListener("click", () => deleteCapabilityRun().catch((error) => showToast(error.message, "error")));
    $("#dictionary-search").addEventListener("input", renderDictionary);
    $("#application-review").addEventListener("click", renderApplicationBoundary);
    $("#application-open-runner").addEventListener("click", openApplicationRunner);
    $("#mandate-application-run").addEventListener("click", () => executeMandateApplication().catch((error) => showToast(error.message, "error")));
    $("#mandate-application-scenario").addEventListener("change", () => {
      labState.mandateApplicationRun = null;
      renderMandateApplicationCatalogue();
    });
    ["#application-agent", "#application-fixture", "#application-portfolio", "#application-capability", "#application-scenario"].forEach((selector) => $(selector).addEventListener("change", renderApplicationBoundary));
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
    ["#artifact-search", "#artifact-view-filter"].forEach((selector) => {
      $(selector).addEventListener(selector === "#artifact-search" ? "input" : "change", renderArtifactList);
    });
    $("#artifact-clear-filters").addEventListener("click", () => {
      $("#artifact-search").value = "";
      $("#artifact-view-filter").value = "active";
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
    // Keep the visible research journey aligned with the numbered Kernel path.
    const experimentKernel = $(".experiment-advanced");
    ["#experiment-fixture-context", "#experiment-design", "#experiment-catalogue", "#experiment-run-trace", "#experiment-program", "#experiment-run-audit"].forEach((selector) => {
      const section = $(selector);
      if (section) experimentKernel.appendChild(section);
    });
    $("#experiment-refresh").addEventListener("click", loadExperimentWorkspace);
    $("#replay-form").addEventListener("submit", (event) => runHistoricalReplay(event));
    ["#replay-workflow", "#replay-portfolio", "#replay-evaluation"].forEach((selector) => $(selector).addEventListener("change", updateReplayNotes));
    $("#replay-authorize-model").addEventListener("change", updateReplayNotes);
    $("#replay-saved-select").addEventListener("change", () => { $("#replay-load-saved").disabled = !$("#replay-saved-select").value; });
    $("#replay-load-saved").addEventListener("click", loadSelectedHistoricalReplay);
    $("#experiment-fixture-resolve").addEventListener("click", () => resolveExperimentFixture());
    $("#experiment-trace-create").addEventListener("click", () => createExperimentRunTrace());
    $("#experiment-tutorial-open").addEventListener("click", () => {
      const tutorial = $("#experiment-tutorial");
      if (typeof tutorial.showModal === "function") tutorial.showModal();
      else tutorial.setAttribute("open", "");
    });
    $$('[data-experiment-jump]').forEach((button) => button.addEventListener("click", () => {
      const tutorial = $("#experiment-tutorial");
      if (tutorial.open && typeof tutorial.close === "function") tutorial.close();
      const target = $(button.dataset.experimentJump);
      target?.scrollIntoView({ behavior: "smooth", block: "start" });
      target?.focus({ preventScroll: true });
    }));
    $("#experiment-run-compare").addEventListener("click", () => compareExperimentRuns().catch((error) => { $("#experiment-status").textContent = error.message; }));
    $("#experiment-open-artifacts").addEventListener("click", () => switchWorkspace("artifacts", true, "research"));
    $("#experiment-open-registry").addEventListener("click", () => switchWorkspace("registry", true, "system"));
    $("#experiment-run-left").addEventListener("change", updateExperimentComparisonAvailability);
    $("#experiment-run-right").addEventListener("change", updateExperimentComparisonAvailability);
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
        issues: labState.experimentSets.reduce((count, item) => count + (item.issues?.length || 0), 0),
      } });
    });
    $("#experiment-detail").addEventListener("click", (event) => {
      if (event.target.closest("[data-experiment-prepare]")) prepareExperiment().catch((error) => { $("#experiment-status").textContent = error.message; });
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
    $("#cycle-open-decision-review").addEventListener("click", () => {
      labState.selectedDecisionId = $("#cycle-decision-panel").dataset.proposalId || null;
      switchWorkspace("decisions");
    });
    $("#decision-refresh").addEventListener("click", () => loadDecisionWorkspace());
    $("#decision-card-list").addEventListener("click", (event) => {
      const card = event.target.closest("[data-decision-id]");
      if (!card) return;
      labState.selectedDecisionId = card.dataset.decisionId;
      renderDecisionWorkspace();
    });
    $("#decision-detail-panel").addEventListener("click", (event) => {
      const diligenceButton = event.target.closest("[data-open-due-diligence]");
      if (diligenceButton) {
        openDecisionDueDiligence();
        return;
      }
      const button = event.target.closest("[data-decision-outcome]");
      if (!button) return;
      event.preventDefault();
      resolveDecisionWorkspace(button.dataset.decisionOutcome).catch((error) => showToast(error.message, "error"));
    });
    $("#diligence-workspace").addEventListener("submit", (event) => {
      if (event.target.id === "diligence-run-form") runDecisionDueDiligence(event).catch((error) => showToast(error.message, "error"));
    });
    $("#diligence-back").addEventListener("click", () => switchWorkspace("decisions"));
    $("#cycle-attach-agent").addEventListener("click", () => attachCycleAgent().catch((error) => { $("#cycle-runtime-status").textContent = error.message; }));
    $("#open-cycle-from-agent").addEventListener("click", () => {
      const selectedPortfolio = $("#agent-real-portfolio").value;
      switchWorkspace("cycle");
      if (selectedPortfolio && [...$("#cycle-portfolio").options].some((item) => item.value === selectedPortfolio)) $("#cycle-portfolio").value = selectedPortfolio;
    });
    $$("[data-agent-builder-mode]").forEach((button) => button.addEventListener("click", () => setAgentBuilderMode(button.dataset.agentBuilderMode)));
    $$("[data-basic-agent-step]").forEach((button) => button.addEventListener("click", () => setBasicAgentStep(button.dataset.basicAgentStep)));
    $$("[data-agent-class]").forEach((button) => button.addEventListener("click", () => setAgentClass(button.dataset.agentClass)));
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
    $("#basic-agent-experimental-role").addEventListener("change", () => {
      labState.agentExperimentalRole = $("#basic-agent-experimental-role").value;
      $("#agent-experimental-role").value = labState.agentExperimentalRole;
      labState.agentBlueprint = null;
      renderAgentContract();
      renderBasicBuilder();
    });
    $("#agent-experimental-role").addEventListener("change", () => {
      labState.agentExperimentalRole = $("#agent-experimental-role").value;
      labState.agentBlueprint = null;
      renderAgentContract();
      renderBasicBuilder();
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
    $("#retain-agent-run").addEventListener("click", () => retainSelectedAgentRun().catch((error) => {
      $("#agent-live-state").textContent = "Retention failed";
      $("#agent-run-file-content").textContent = error.message;
    }));
    $("#open-agent-artifacts").addEventListener("click", () => switchWorkspace("artifacts"));
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
    loadPlatformWorkspaces();
    const requestParams = new URLSearchParams(window.location.search);
    const requestedWorkspace = requestParams.get("workspace");
    const requestedZone = requestParams.get("zone");
    const requestedProposal = requestParams.get("proposal");
    if (requestedProposal) labState.selectedDecisionId = requestedProposal;
    if (["system", "studio", "application", "dictionary", "dataset", "portfolio", "agent", "graph", "registry", "artifacts", "experiments", "decisions", "decision-diligence", "full"].includes(requestedWorkspace)) switchWorkspace(requestedWorkspace, false, zoneDefaults[normalizedZone(requestedZone)] ? normalizedZone(requestedZone) : null);
    else switchZone("system", "system", false);
  }

  try {
    initialize();
  } catch (error) {
    console.error("ServiceFabric Lab initialization failed", error);
    const sourceChip = document.querySelector("#source-chip");
    if (sourceChip) sourceChip.textContent = `Interface initialization failed · ${error.message}`;
  }
})();
