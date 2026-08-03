(() => {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];

  const portfolios = {
    diversified: {
      title: "Diversified research portfolio",
      cash: 4000000,
      holdings: [
        ["real-diversified-01", 4500000, 12.40],
        ["real-diversified-02", 430000, 64.20],
        ["real-diversified-03", 650000, 42.80],
        ["real-diversified-04", 453900, 51.10],
        ["real-diversified-05", 320000, 77.40],
        ["real-diversified-06", 120000, 118.20],
        ["real-diversified-07", 700000, 32.60],
        ["real-diversified-08", 100000, 91.70],
      ],
    },
    technology: {
      title: "Technology-concentrated research portfolio",
      cash: 1200000,
      holdings: [
        ["real-technology-concentrated-01", 120000, 141.20],
        ["real-technology-concentrated-02", 430000, 37.80],
        ["real-technology-concentrated-03", 370000, 59.40],
        ["real-technology-concentrated-04", 60000, 208.10],
        ["real-technology-concentrated-05", 350000, 48.30],
      ],
    },
    defensive: {
      title: "Defensive research portfolio",
      cash: 5400000,
      holdings: [
        ["real-defensive-multi-asset-01", 120000, 93.60],
        ["real-defensive-multi-asset-02", 650000, 31.20],
        ["real-defensive-multi-asset-03", 430000, 44.10],
        ["real-defensive-multi-asset-04", 200000, 68.40],
        ["real-defensive-multi-asset-05", 12000, 312.00],
      ],
    },
  };

  const metricDefinitions = [
    {
      id: "daily_return",
      name: "Daily portfolio return",
      short: "Change in total portfolio value since the prior replay date",
      formula: "rₜ = (Vₜ / Vₜ₋₁) − 1",
      input: "Two consecutive portfolio valuations, including cash.",
      meaning: "A negative value means the portfolio lost value during the latest replay interval.",
      limitation: "One day is not a risk estimate; it is a realised observation.",
    },
    {
      id: "annualized_volatility",
      name: "Annualized volatility",
      short: "Typical variability of daily portfolio returns, scaled to one year",
      formula: "σannual = stdev(r₁ … rₙ) × √252",
      input: "At least 20 daily portfolio returns; 60 are preferred.",
      meaning: "Higher volatility means the portfolio value has moved less predictably.",
      limitation: "Assumes the selected historical window is representative and uses the square-root-of-time convention.",
    },
    {
      id: "maximum_drawdown",
      name: "Maximum drawdown",
      short: "Largest peak-to-trough decline observed so far",
      formula: "MDD = maxₜ [(running peakₜ − Vₜ) / running peakₜ]",
      input: "The complete portfolio valuation path up to the replay timestamp.",
      meaning: "A 6% drawdown means the portfolio fell 6% from its prior high before recovering or reaching the current date.",
      limitation: "Path-dependent and backward-looking; it does not forecast the next loss.",
    },
    {
      id: "historical_var_95",
      name: "Historical VaR (95%)",
      short: "Loss threshold exceeded by the worst 5% of observed daily returns",
      formula: "VaR₉₅ = − percentile₅%(r₁ … rₙ)",
      input: "Historical daily portfolio returns.",
      meaning: "A 1.8% VaR means roughly 5% of observed days lost more than 1.8%.",
      limitation: "Does not describe how bad losses beyond the threshold were.",
    },
    {
      id: "historical_expected_shortfall_95",
      name: "Expected shortfall (95%)",
      short: "Average loss on days worse than the historical VaR threshold",
      formula: "ES₉₅ = mean(−rₜ | rₜ ≤ percentile₅%)",
      input: "Historical daily returns and the corresponding VaR threshold.",
      meaning: "Complements VaR by describing the average severity of tail observations.",
      limitation: "Can be unstable with a short sample because very few observations fall in the tail.",
    },
  ];

  const nodeContracts = {
    context: {
      name: "Overall Default Context",
      purpose: "The deterministic, point-in-time information boundary shared by every architecture.",
      input: "PortfolioSnapshot + MetricPack + eligible events + evidence references.",
      output: "ArchitectureInputBundle.",
      tools: "None. This node assembles validated data.",
    },
    rules: {
      name: "Deterministic rules",
      purpose: "Apply reviewed thresholds and produce the B0 reference decision.",
      input: "Selected metric observations and readiness state.",
      output: "Finding + ReviewItem + DecisionPoint.",
      tools: "Canonical risk capabilities only.",
    },
    synthesizer: {
      name: "Single synthesizer",
      purpose: "Interpret the complete default context in one structured model call.",
      input: "All model-safe context fields.",
      output: "Summary, severity, evidence references, uncertainty, and next steps.",
      tools: "No model tools in the current provider configuration.",
    },
    market: {
      name: "Market-data interpreter",
      purpose: "Explain what the calculated return, volatility, drawdown, and tail metrics imply.",
      input: "Metrics, warnings, limitations, and evidence references.",
      output: "Bounded specialist interpretation.",
      tools: "Metric lookup only; no free-form database access.",
    },
    exposure: {
      name: "Portfolio-exposure interpreter",
      purpose: "Identify concentration and affected positions using the portfolio context.",
      input: "Holdings, weights, cash, and exposure summaries.",
      output: "Affected positions and exposure observations.",
      tools: "Portfolio exposure capability.",
    },
    news: {
      name: "Event/news interpreter",
      purpose: "Interpret only events eligible at the replay timestamp.",
      input: "Governed events with available_at ≤ replay time.",
      output: "Event relevance, uncertainty, and citations.",
      tools: "Not connected in this experiment; the role must report unavailable.",
    },
    synthesis: {
      name: "Alert synthesis",
      purpose: "Combine specialist outputs into one review recommendation.",
      input: "Deterministic finding + specialist outputs + permitted next steps.",
      output: "Structured review output. Effects must be empty.",
      tools: "No execution capability.",
    },
    critic: {
      name: "Deterministic critic",
      purpose: "Reject unsupported claims, invalid evidence references, and schema violations.",
      input: "Agent output + original default context.",
      output: "Pass or forced abstention.",
      tools: "Schema and evidence validators.",
    },
    event_retrieval: {
      name: "Event retrieval capability",
      purpose: "Query governed events that were actually available by the replay timestamp.",
      input: "Instrument aliases + as_of timestamp.",
      output: "Eligible EventContext with citations and availability times.",
      tools: "Designed read-only event-store adapter; not connected in this browser prototype.",
    },
    fundamental_change: {
      name: "Fundamental change capability",
      purpose: "Compare point-in-time fundamental observations without using future filings.",
      input: "Instrument aliases + current and prior available observations.",
      output: "Versioned fundamental change observations.",
      tools: "Designed read-only Compustat adapter; not connected in this browser prototype.",
    },
    scenario_stress: {
      name: "Scenario stress capability",
      purpose: "Apply a reviewed deterministic shock to the current snapshot.",
      input: "PortfolioSnapshot + named scenario parameters.",
      output: "ScenarioResult; never a portfolio mutation.",
      tools: "Deterministic scenario calculator.",
    },
  };

  const runtimeOptions = {
    custom_python: { label: "Custom typed Python", available: true },
    langgraph: { label: "LangGraph checkpointed adapter (planned)", available: false },
    openai_agents_sdk: { label: "OpenAI Agents SDK", available: false },
  };

  const topologyOptions = {
    rules: { label: "Deterministic rules", architecture: "B0" },
    single_agent: { label: "Single structured agent", architecture: "B1" },
    specialist_team: { label: "Specialist agent team", architecture: "A1" },
  };

  const resultOptions = {
    risk_review: "Daily Portfolio Risk Review",
    morning_review: "Morning Review",
    portfolio_brief: "Portfolio Brief",
  };

  const workflowIntentions = {
    risk_review: {
      question: "Has portfolio risk changed enough to require attention, why, and what should the human decide?",
      audience: "Portfolio manager / risk reviewer",
      attention: "Pause on REVIEW, URGENT REVIEW, blocked execution, or insufficient evidence.",
      evidence: "Valuation, metric history, position attribution, concentration, scenarios, events and fundamentals when available.",
    },
    morning_review: {
      question: "What changed since the prior review and what deserves attention today?",
      audience: "Portfolio manager",
      attention: "Pause only when a material risk or evidence-quality exception is found.",
      evidence: "Portfolio movement, risk metrics, exposure changes and eligible events.",
    },
    portfolio_brief: {
      question: "What is the current portfolio story, its supporting evidence, and its unresolved questions?",
      audience: "Research analyst / thesis evaluator",
      attention: "Deliver as a narrative document; escalate contradictions or missing material evidence.",
      evidence: "Portfolio context, fundamentals, events, metrics and prior review history.",
    },
  };

  const defaultWorkflows = [
    {
      id: "daily_portfolio_risk_review",
      name: "Daily Portfolio Risk Review",
      resultType: "risk_review",
      runtime: "custom_python",
      topology: "specialist_team",
      enabled: true,
    },
    {
      id: "morning_review",
      name: "Morning Review",
      resultType: "morning_review",
      runtime: "custom_python",
      topology: "specialist_team",
      enabled: false,
    },
    {
      id: "research_brief",
      name: "Research Brief",
      resultType: "portfolio_brief",
      runtime: "custom_python",
      topology: "single_agent",
      enabled: false,
    },
  ];

  const state = {
    step: "experiment",
    completed: new Set(),
    portfolioKey: "diversified",
    holdings: [],
    cash: 4000000,
    openingHoldings: [],
    openingCash: 4000000,
    selectedMetrics: new Set(metricDefinitions.map((metric) => metric.id)),
    metrics: null,
    priceSeries: [],
    fullSeries: [],
    warmupCount: 60,
    dates: [],
    workflows: defaultWorkflows.map((workflow) => ({ ...workflow })),
    selectedWorkflowId: "daily_portfolio_risk_review",
    customCapabilities: [],
    replayIndex: -1,
    cycleIndex: 0,
    preparedDateIndex: -1,
    pendingDecision: null,
    appliedThisDate: [],
    replayTimer: null,
    decisions: [],
    proposedEvents: [],
    ledger: [],
    experimentDraftApproved: false,
    policyControls: {
      dailyLossLimit: .02,
      concentrationLimit: .22,
      historicalVarLimit: .025,
      scenarioLossLimit: .06,
      minimumCash: .05,
      staleDataHours: 24,
    },
    policyExceptions: [],
    policyBaseline: null,
  };

  function clonePortfolio(key) {
    const source = portfolios[key];
    state.portfolioKey = key;
    state.cash = source.cash;
    state.holdings = source.holdings.map(([id, quantity, price]) => ({ id, quantity, price }));
    captureOpeningState();
  }

  function captureOpeningState() {
    state.openingHoldings = state.holdings.map((holding) => ({ ...holding }));
    state.openingCash = state.cash;
  }

  function money(value) {
    return Number(value || 0).toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
  }

  function percent(value, digits = 2) {
    return `${(Number(value || 0) * 100).toFixed(digits)}%`;
  }

  function prettyDate(value) {
    return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(`${value}T12:00:00Z`));
  }

  function businessDates(start, end, cadence = "daily") {
    const result = [];
    const cursor = new Date(`${start}T12:00:00Z`);
    const finish = new Date(`${end}T12:00:00Z`);
    while (cursor <= finish) {
      const day = cursor.getUTCDay();
      if (day !== 0 && day !== 6 && (cadence === "daily" || day === 5)) result.push(cursor.toISOString().slice(0, 10));
      cursor.setUTCDate(cursor.getUTCDate() + 1);
    }
    return result;
  }

  function priorBusinessDates(start, count) {
    const result = [];
    const cursor = new Date(`${start}T12:00:00Z`);
    while (result.length < count) {
      cursor.setUTCDate(cursor.getUTCDate() - 1);
      const day = cursor.getUTCDay();
      if (day !== 0 && day !== 6) result.unshift(cursor.toISOString().slice(0, 10));
    }
    return result;
  }

  function seedFor(value) {
    return [...value].reduce((total, character) => (total * 31 + character.charCodeAt(0)) % 9973, 17);
  }

  function makePriceSeries() {
    state.dates = businessDates($("#start-date").value, $("#end-date").value, $("#cadence").value);
    const warmupDates = priorBusinessDates($("#start-date").value, state.warmupCount);
    const allDates = [...warmupDates, ...state.dates];
    const factorPaths = Object.fromEntries(state.holdings.map((holding, holdingIndex) => {
      let factor = 1;
      const values = allDates.map((date, index) => {
        const replayIndex = index - state.warmupCount;
        const fraction = state.dates.length && replayIndex >= 0 ? replayIndex / state.dates.length : 0;
        const seed = seedFor(holding.id);
        const ordinary = Math.sin((seed + index) * .43) * .005 + Math.cos((holdingIndex + index) * .31) * .0025;
        const shock = replayIndex >= 0 && fraction > .48 && fraction < .56 ? -(0.009 + (holdingIndex % 3) * .0035) : 0;
        const recovery = replayIndex >= 0 && fraction > .70 && fraction < .78 ? .006 : 0;
        factor *= 1 + ordinary + shock + recovery;
        return factor;
      });
      const startFactor = values[state.warmupCount] || 1;
      return [holding.id, values.map((value) => holding.price * value / startFactor)];
    }));
    const series = allDates.map((date, index) => {
      const prices = Object.fromEntries(state.holdings.map((holding) => [holding.id, Math.max(.1, factorPaths[holding.id][index])]));
      const nav = state.cash + state.holdings.reduce((sum, holding) => sum + holding.quantity * prices[holding.id], 0);
      return { date, prices, nav };
    });
    state.fullSeries = series;
    state.priceSeries = series.slice(state.warmupCount);
    return state.priceSeries;
  }

  function metricHistoryAtReplayIndex(index) {
    const end = state.warmupCount + Math.max(0, index) + 1;
    return state.fullSeries.slice(Math.max(0, end - 61), end);
  }

  function calculateMetricValues(series) {
    if (!series.length) return {};
    const navs = series.map((point) => point.nav);
    const returns = navs.slice(1).map((nav, index) => nav / navs[index] - 1);
    const latestReturn = returns.at(-1) || 0;
    const mean = returns.length ? returns.reduce((sum, value) => sum + value, 0) / returns.length : 0;
    const variance = returns.length > 1
      ? returns.reduce((sum, value) => sum + (value - mean) ** 2, 0) / (returns.length - 1)
      : 0;
    let peak = navs[0];
    let maxDrawdown = 0;
    navs.forEach((nav) => {
      peak = Math.max(peak, nav);
      maxDrawdown = Math.max(maxDrawdown, peak ? (peak - nav) / peak : 0);
    });
    const sorted = [...returns].sort((a, b) => a - b);
    const index = Math.max(0, Math.floor(sorted.length * .05));
    const threshold = sorted[index] || 0;
    const tail = sorted.filter((value) => value <= threshold);
    return {
      daily_return: latestReturn,
      annualized_volatility: Math.sqrt(variance) * Math.sqrt(252),
      maximum_drawdown: maxDrawdown,
      historical_var_95: Math.max(0, -threshold),
      historical_expected_shortfall_95: tail.length ? Math.max(0, -(tail.reduce((sum, value) => sum + value, 0) / tail.length)) : 0,
      nav: navs.at(-1),
      observations: returns.length,
    };
  }

  function metricValueLabel(id, value) {
    return percent(value, id === "daily_return" ? 3 : 2);
  }

  function showStep(step) {
    state.step = step;
    $$(".stage").forEach((section) => section.classList.toggle("active", section.id === step));
    $$(".step-link").forEach((button) => {
      button.classList.toggle("active", button.dataset.step === step);
      button.classList.toggle("complete", state.completed.has(button.dataset.step));
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function completeStep(step) {
    state.completed.add(step);
    $(`.step-link[data-step="${step}"]`)?.classList.add("complete");
  }

  function choosePortfolioFromDescription(description) {
    const text = description.toLowerCase();
    const unsupported = /(bond|high[- ]?yield|credit|european corporate|fixed income)/.test(text);
    if (unsupported) return { unsupported: true, key: null };
    if (/(diversified|balanced|cross-sector|multi-sector)/.test(text)) return { unsupported: false, key: "diversified" };
    if (/(technology-concentrated|technology concentrated|software|semiconductor|growth)/.test(text)) return { unsupported: false, key: "technology" };
    if (/(defensive|low volatility|conservative|multi.asset)/.test(text)) return { unsupported: false, key: "defensive" };
    return { unsupported: false, key: "diversified" };
  }

  function controlValue(id) {
    return Math.max(0, Number($(id).value) || 0) / 100;
  }

  function controlsFromForm() {
    return {
      dailyLossLimit: controlValue("#daily-loss-limit"),
      concentrationLimit: controlValue("#concentration-limit"),
      historicalVarLimit: controlValue("#var-limit"),
      scenarioLossLimit: controlValue("#scenario-loss-limit"),
      minimumCash: controlValue("#minimum-cash"),
      staleDataHours: Math.max(1, Number($("#stale-data-hours").value) || 24),
    };
  }

  function openingPolicyCheck(controls) {
    const positionValues = state.holdings.map((holding) => holding.quantity * holding.price);
    const total = state.cash + positionValues.reduce((sum, value) => sum + value, 0);
    const topWeight = total ? Math.max(...positionValues, 0) / total : 0;
    const cashWeight = total ? state.cash / total : 0;
    const exceptions = [];
    if (topWeight > controls.concentrationLimit) exceptions.push(`Largest position ${percent(topWeight, 1)} exceeds ${percent(controls.concentrationLimit, 1)}`);
    if (cashWeight < controls.minimumCash) exceptions.push(`Opening cash ${percent(cashWeight, 1)} is below ${percent(controls.minimumCash, 1)}`);
    return { topWeight, cashWeight, exceptions };
  }

  function renderPlannerResult() {
    const requestedDates = businessDates($("#start-date").value, $("#end-date").value, $("#cadence").value);
    const panel = $("#planner-result");
    state.experimentDraftApproved = false;
    $("#experiment-next").disabled = true;
    $("#experiment-next").textContent = "Approve the draft to continue";
    if (!requestedDates.length) {
      panel.classList.remove("hidden", "success");
      panel.classList.add("blocked");
      panel.innerHTML = `<h3>The selected period has no eligible replay dates</h3><p>Choose an end date on or after the start date and include at least one business day.</p>`;
      $("#experiment-status").textContent = "Needs revision";
      $("#experiment-status").classList.add("warning");
      return;
    }
    if ($("#planning-path").value === "openai") {
      panel.classList.remove("hidden", "success");
      panel.classList.add("blocked");
      panel.innerHTML = `
        <div class="planner-heading">
          <div><span class="panel-label">Server-side path</span><h3>OpenAI structured planner is adapter-ready, not connected</h3></div>
          <span class="readiness">No model call made</span>
        </div>
        <p>The safe route is: send the objective, IPS and dates to a server-side OpenAI Responses call; require structured output shaped as the existing canonical fields; validate those fields; resolve candidate securities through read-only database capabilities; then pause for human portfolio review. Only that human action may materialize a RealPortfolioSelectionManifest with reviewed=true. This static page cannot hold a secret API key or query the private database.</p>
        <div class="adapter-flow" aria-label="OpenAI and LangGraph experiment planning flow">
          <span><b>1</b>User request<small>objective · IPS · dates</small></span><i>→</i>
          <span><b>2</b>Responses API<small>structured proposal</small></span><i>→</i>
          <span><b>3</b>Canonical validation<small>existing schemas only</small></span><i>→</i>
          <span><b>4</b>Human interrupt<small>reviewed selection manifest</small></span><i>→</i>
          <span><b>5</b>Freeze revisions<small>immutable replay inputs</small></span>
        </div>
        <div class="readiness-grid">
          <div class="ready"><strong>Canonical field map</strong><span>Ready</span><small>Policy, reviewed selection, portfolio and replay contracts identified.</small></div>
          <div class="ready"><strong>Structured output boundary</strong><span>Ready</span><small>The model proposes fields; canonical validation remains deterministic.</small></div>
          <div><strong>Server credential binding</strong><span>Not connected</span><small>The key is not visible to this process and must stay off the browser.</small></div>
          <div><strong>LangGraph runtime</strong><span>Not installed</span><small>Add only after the dependency and execution-path change is reviewed.</small></div>
          <div><strong>Checkpoint store</strong><span>Not configured</span><small>Required to resume safely after the human approval interrupt.</small></div>
          <div><strong>Private-data capability</strong><span>Not connected here</span><small>Must return governed candidate aliases, never fabricated holdings.</small></div>
        </div>
        <div class="result-actions">
          <button class="button ghost" type="button" data-use-local-preview>Use the runnable local preview</button>
        </div>`;
      $("#experiment-status").textContent = "Adapter not connected";
      $("#experiment-status").classList.add("warning");
      return;
    }
    const result = choosePortfolioFromDescription($("#portfolio-description").value);
    panel.classList.remove("hidden", "success", "blocked");
    if (result.unsupported) {
      panel.classList.add("blocked");
      panel.innerHTML = `
        <h3>Portfolio request is outside the connected database</h3>
        <p>The description asks for bond or European corporate-credit exposure. CRSP/Compustat in this workspace is an equity research source, so the system will not invent bond holdings or claim an equity proxy is equivalent.</p>
        <div class="result-meta"><span>Result: blocked</span><span>Required next capability: bond security master + prices</span></div>`;
      $("#experiment-status").textContent = "Needs revision";
      $("#experiment-status").classList.add("warning");
      return;
    }
    clonePortfolio(result.key);
    renderHoldings();
    makePriceSeries();
    panel.classList.add("success");
    const policyOwner = escapeHtml($("#policy-owner").value.trim() || "Unassigned policy owner");
    const mandate = escapeHtml($("#mandate-description").value.trim() || "No mandate narrative supplied.");
    const benchmark = $("#benchmark-id").value === "unavailable" ? "Unavailable, explicitly disclosed" : "U.S. equity research benchmark";
    const cadence = $("#cadence").value;
    const controls = controlsFromForm();
    const compliance = openingPolicyCheck(controls);
    const riskControls = [
      `daily loss review ${escapeHtml($("#daily-loss-limit").value)}%`,
      `single position ≤ ${escapeHtml($("#concentration-limit").value)}%`,
      `historical VaR ≤ ${escapeHtml($("#var-limit").value)}%`,
      `scenario loss ≤ ${escapeHtml($("#scenario-loss-limit").value)}%`,
      `minimum cash ${escapeHtml($("#minimum-cash").value)}%`,
      `data age ≤ ${escapeHtml($("#stale-data-hours").value)}h`,
    ];
    const complianceMarkup = compliance.exceptions.length
      ? `<div class="mandate-check exception"><strong>${compliance.exceptions.length} opening mandate exceptions require explicit human review</strong><ul>${compliance.exceptions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul><small>The portfolio remains governed by the IPS, but it is not represented as compliant. Approval records the exceptions as warnings in the existing selection manifest.</small></div>`
      : `<div class="mandate-check compliant"><strong>Opening portfolio passes the immediately testable IPS controls</strong><span>Largest position ${percent(compliance.topWeight, 1)} · cash ${percent(compliance.cashWeight, 1)}</span></div>`;
    panel.innerHTML = `
      <div class="planner-heading">
        <div><span class="panel-label">Canonical composition preview</span><h3>A governed experiment draft is ready for review</h3></div>
        <span class="readiness">Deterministic preview</span>
      </div>
      <p><strong>${portfolios[result.key].title}</strong> was selected from the approved private-neutral research universe. The replay contains ${state.dates.length} eligible ${cadence === "daily" ? "business-day" : "weekly"} timestamps from ${prettyDate(state.dates[0])} to ${prettyDate(state.dates.at(-1))}. No model call was made.</p>
      <div class="canonical-object-grid">
        <article>
          <span>Existing canonical object</span>
          <h4>MonitoringPolicy</h4>
          <dl><div><dt>Purpose</dt><dd>${mandate}</dd></div><div><dt>Owner</dt><dd>${policyOwner}</dd></div><div><dt>Human review</dt><dd>Required</dd></div></dl>
        </article>
        <article>
          <span>Existing canonical object</span>
          <h4>MonitoringPolicyVersion</h4>
          <dl><div><dt>Cadence</dt><dd>${cadence}</dd></div><div><dt>Controls</dt><dd>${riskControls.join(" · ")}</dd></div><div><dt>Revision</dt><dd>Candidate revision; frozen only after approval</dd></div></dl>
        </article>
        <article>
          <span>Existing canonical object</span>
          <h4>PortfolioDefinition</h4>
          <dl><div><dt>Opening state</dt><dd>${state.holdings.length} holdings · ${money(state.cash)} cash · USD</dd></div><div><dt>Benchmark</dt><dd>${benchmark}</dd></div><div><dt>Mandate binding</dt><dd>Portfolio thresholds mirror the approved policy controls</dd></div></dl>
        </article>
        <article>
          <span>Existing canonical object</span>
          <h4>RealPortfolioSelectionManifest</h4>
          <dl><div><dt>Reviewed state</dt><dd>False while this proposal is on screen; only the human approval below may set reviewed=true</dd></div><div><dt>Warnings</dt><dd>${compliance.exceptions.length ? compliance.exceptions.map(escapeHtml).join(" · ") : "No opening mandate exception"}</dd></div><div><dt>Materialization</dt><dd>ReviewedPortfolioSelection becomes the approved PortfolioDefinition input</dd></div></dl>
        </article>
        <article>
          <span>Existing canonical object</span>
          <h4>ReplaySpecification</h4>
          <dl><div><dt>Period</dt><dd>${prettyDate(state.dates[0])} → ${prettyDate(state.dates.at(-1))}</dd></div><div><dt>Point-in-time rule</dt><dd>Only information available by each replay timestamp</dd></div><div><dt>Policy binding</dt><dd>Approved MonitoringPolicyVersion revision and evidence digest</dd></div></dl>
        </article>
      </div>
      <div class="langgraph-preview">
        <div>
          <span class="panel-label">LangGraph adapter boundary</span>
          <h4>Orchestration state carries canonical objects; it does not become a new domain object</h4>
        </div>
        <div class="adapter-flow">
          <span><b>1</b>Parse request<small>LLM structured proposal</small></span><i>→</i>
          <span><b>2</b>Resolve candidates<small>read-only data capability</small></span><i>→</i>
          <span><b>3</b>Validate<small>canonical Pydantic contracts</small></span><i>→</i>
          <span class="interrupt"><b>4</b>Interrupt<small>human selection review</small></span><i>→</i>
          <span><b>5</b>Freeze<small>immutable revisions</small></span>
        </div>
      </div>
      ${complianceMarkup}
      <div class="result-meta"><span>${state.holdings.length} opening holdings</span><span>${money(state.cash)} cash</span><span>${state.dates.length} replay dates</span><span>Human approval required</span></div>
      <div class="result-actions">
        <button class="button primary" type="button" data-approve-experiment>${compliance.exceptions.length ? "Approve with disclosed exceptions" : "Approve policy, period and opening portfolio"}</button>
        <button class="button ghost" type="button" data-revise-experiment>Revise inputs</button>
      </div>`;
    $("#experiment-status").textContent = "Awaiting approval";
    $("#experiment-status").classList.remove("warning");
  }

  function approveExperimentDraft() {
    state.experimentDraftApproved = true;
    state.policyControls = controlsFromForm();
    const openingCheck = openingPolicyCheck(state.policyControls);
    state.policyExceptions = openingCheck.exceptions;
    state.policyBaseline = { topWeight: openingCheck.topWeight, cashWeight: openingCheck.cashWeight };
    captureOpeningState();
    completeStep("experiment");
    $("#experiment-status").textContent = "Approved";
    $("#experiment-status").classList.remove("warning");
    $("#experiment-next").disabled = false;
    $("#experiment-next").textContent = "Continue to holdings →";
    const actions = $("#planner-result .result-actions");
    if (actions) actions.innerHTML = `<span class="approval-confirmation">Selection review recorded${state.policyExceptions.length ? ` with ${state.policyExceptions.length} disclosed exception${state.policyExceptions.length === 1 ? "" : "s"}` : ""} · reviewed manifest and canonical revisions may now be frozen for replay</span><button class="button next-button" type="button" data-approved-next>Continue to holdings →</button>`;
  }

  function renderHoldings() {
    const values = state.holdings.map((holding) => holding.quantity * holding.price);
    const total = state.cash + values.reduce((sum, value) => sum + value, 0);
    $("#cash-balance").value = state.cash;
    $("#portfolio-title").textContent = portfolios[state.portfolioKey]?.title || "Custom research portfolio";
    $("#portfolio-subtitle").textContent = "Private-neutral aliases from the approved research universe";
    $("#holdings-status").textContent = `${state.holdings.length} holdings`;
    $("#holdings-body").innerHTML = state.holdings.map((holding, index) => {
      const value = values[index];
      const weight = total ? value / total : 0;
      return `<tr>
        <td>${holding.id}</td>
        <td><input type="number" min="0" step="1" value="${holding.quantity}" data-holding-index="${index}" data-field="quantity" aria-label="Quantity for ${holding.id}"></td>
        <td><input type="number" min=".01" step=".01" value="${holding.price.toFixed(2)}" data-holding-index="${index}" data-field="price" aria-label="Opening price for ${holding.id}"></td>
        <td>${money(value)}</td>
        <td><span class="weight-track"><i style="width:${Math.min(100, weight * 100)}%"></i></span>${percent(weight, 1)}</td>
        <td><button class="remove-button" type="button" data-remove-holding="${index}" aria-label="Remove ${holding.id}">×</button></td>
      </tr>`;
    }).join("");
    $("#opening-value").textContent = money(total);
    $("#cash-weight").textContent = `Cash ${percent(total ? state.cash / total : 0, 1)}`;
    $("#calculation-inputs").textContent = `${state.dates.length || businessDates($("#start-date").value, $("#end-date").value, $("#cadence").value).length} replay dates · ${state.holdings.length} holdings · synthetic deterministic price path`;
  }

  function renderMetricCatalog() {
    $("#metric-catalog").innerHTML = metricDefinitions.map((metric) => `
      <button class="metric-row" type="button" data-metric="${metric.id}">
        <input type="checkbox" ${state.selectedMetrics.has(metric.id) ? "checked" : ""} aria-label="Include ${metric.name}">
        <div><strong>${metric.name}</strong><small>${metric.short}</small></div>
        <code>${metric.formula}</code>
      </button>`).join("");
    $("#metric-status").textContent = `${state.selectedMetrics.size} selected`;
  }

  function inspectMetric(id) {
    const metric = metricDefinitions.find((item) => item.id === id);
    if (!metric) return;
    $$(".metric-row").forEach((row) => row.classList.toggle("active", row.dataset.metric === id));
    $("#metric-explainer").innerHTML = `
      <span class="panel-label">Metric definition</span>
      <h3>${metric.name}</h3>
      <p>${metric.short}.</p>
      <div class="formula">${metric.formula}</div>
      <div class="definition-list">
        <div><strong>Inputs</strong><span>${metric.input}</span></div>
        <div><strong>How to interpret it</strong><span>${metric.meaning}</span></div>
        <div><strong>Limitation</strong><span>${metric.limitation}</span></div>
        <div><strong>Agent use</strong><span>The number enters RiskContext. The model may interpret it, but cannot recalculate or overwrite it.</span></div>
      </div>`;
  }

  function calculateAndRenderMetrics() {
    makePriceSeries();
    state.metrics = calculateMetricValues(metricHistoryAtReplayIndex(state.priceSeries.length - 1));
    const selected = metricDefinitions.filter((definition) => state.selectedMetrics.has(definition.id));
    $("#calculation-result").classList.remove("hidden");
    $("#calculation-result").innerHTML = `
      <div class="calculated-grid">${selected.map((metric) => `
        <div class="calculated-metric">
          <span>${metric.name}</span>
          <strong>${metricValueLabel(metric.id, state.metrics[metric.id])}</strong>
          <small>${state.metrics.observations} return observations</small>
        </div>`).join("")}</div>`;
    completeStep("metrics");
  }

  function holdingWeightsAt(point) {
    const values = state.holdings.map((holding) => ({ id: holding.id, value: holding.quantity * point.prices[holding.id] }));
    const total = state.cash + values.reduce((sum, item) => sum + item.value, 0);
    return values.map((item) => ({ ...item, weight: total ? item.value / total : 0 })).sort((a, b) => b.weight - a.weight);
  }

  function readableMetricSentence(metric, value) {
    const descriptions = {
      daily_return: `The latest replay interval changed portfolio value by ${metricValueLabel(metric, value)}.`,
      annualized_volatility: `Observed daily variability scales to ${metricValueLabel(metric, value)} per year under the √252 convention.`,
      maximum_drawdown: `The largest decline from a previous portfolio-value peak is ${metricValueLabel(metric, value)}.`,
      historical_var_95: `On roughly 5% of observed days, the loss was worse than ${metricValueLabel(metric, value)}.`,
      historical_expected_shortfall_95: `The average loss among those tail days is ${metricValueLabel(metric, value)}.`,
    };
    return descriptions[metric];
  }

  function buildContext() {
    if (!state.experimentDraftApproved) {
      $("#context-preview").classList.remove("hidden");
      $("#brief-title").textContent = "Approval required";
      $("#brief-readiness").textContent = "Blocked";
      $("#brief-summary").innerHTML = `<strong>The experiment is not governed yet.</strong> Return to Stage 1 and complete the human portfolio-and-policy review before constructing an agent-facing context.`;
      $("#context-holdings").innerHTML = `<div class="empty-state">No approved PortfolioDefinition revision.</div>`;
      $("#context-mandate").innerHTML = `<div class="mandate-check exception"><strong>No approved MonitoringPolicyVersion revision</strong><span>The mandate must be reviewed before it can control workflow attention.</span></div>`;
      $("#context-metrics").innerHTML = `<div class="empty-state">Metrics are not assembled into context until the policy and opening portfolio are approved.</div>`;
      $("#context-status").textContent = "Approval required";
      $("#context-status").classList.add("warning");
      return;
    }
    if (!state.priceSeries.length) makePriceSeries();
    if (!state.metrics) state.metrics = calculateMetricValues(metricHistoryAtReplayIndex(state.priceSeries.length - 1));
    const point = state.priceSeries[0];
    const values = calculateMetricValues(metricHistoryAtReplayIndex(0));
    const weights = holdingWeightsAt(point);
    const top = weights.slice(0, 5);
    $("#context-preview").classList.remove("hidden");
    $("#brief-title").textContent = `${portfolios[state.portfolioKey]?.title || "Custom portfolio"} · ${prettyDate(point.date)}`;
    $("#brief-readiness").textContent = state.dates.length >= 20 ? "Qualified" : "Limited history";
    $("#brief-summary").innerHTML = `At <strong>${prettyDate(point.date)}</strong>, the sandbox portfolio contains <strong>${state.holdings.length} holdings</strong> and <strong>${money(state.cash)} cash</strong>. Its opening value is <strong>${money(point.nav)}</strong>. Metrics below are deterministic calculations from a clearly labelled synthetic price path; the event/news component is unavailable and will be passed to agents as a limitation.`;
    $("#context-holdings").innerHTML = `<div class="holding-bars">${top.map((holding) => `
      <div class="holding-bar"><span>${holding.id}</span><div><i style="width:${Math.min(100, holding.weight * 100)}%"></i></div><b>${percent(holding.weight, 1)}</b></div>`).join("")}</div>`;
    const controls = state.policyControls;
    $("#context-mandate").innerHTML = `
      <div class="mandate-context">
        <div><span>MonitoringPolicy</span><strong>${escapeHtml($("#policy-owner").value.trim() || "Unassigned owner")}</strong><small>Human review required</small></div>
        <div><span>Daily loss</span><strong>${percent(controls.dailyLossLimit, 1)}</strong><small>Maximum before review</small></div>
        <div><span>Historical VaR</span><strong>${percent(controls.historicalVarLimit, 1)}</strong><small>Maximum before review</small></div>
        <div><span>Single position</span><strong>${percent(controls.concentrationLimit, 1)}</strong><small>Maximum weight</small></div>
        <div><span>Scenario loss</span><strong>${percent(controls.scenarioLossLimit, 1)}</strong><small>Maximum reviewed sensitivity</small></div>
        <div><span>Cash</span><strong>${percent(controls.minimumCash, 1)}</strong><small>Minimum portfolio weight</small></div>
      </div>
      ${state.policyExceptions.length ? `<div class="mandate-check exception"><strong>Approved exceptions remain visible</strong><ul>${state.policyExceptions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>` : ""}`;
    $("#context-metrics").innerHTML = metricDefinitions.filter((metric) => state.selectedMetrics.has(metric.id)).map((metric) => `
      <div class="metric-sentence"><strong>${metricValueLabel(metric.id, values[metric.id])}</strong> ${readableMetricSentence(metric.id, values[metric.id])}</div>`).join("");
    const contextId = `CTX-${point.date.replaceAll("-", "")}-001`;
    $("#audit-identities").innerHTML = `
      <div>Human identity: ${contextId}</div>
      <div>Portfolio snapshot: SNAP-${point.date.replaceAll("-", "")}-OPENING</div>
      <div>Metric pack: MP-RISK-CORE-V1</div>
      <div>Integrity digest: sha256:${seedFor(contextId).toString(16).padStart(8, "0")}… (shortened in UI)</div>
      <div>Why a digest exists: it proves the context was not changed after the agent ran.</div>`;
    $("#context-status").textContent = "Ready for review";
    $("#context-status").classList.remove("warning");
    completeStep("context");
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    })[character]);
  }

  function activeWorkflows() {
    return state.workflows.filter((workflow) => workflow.enabled);
  }

  function selectedWorkflow() {
    return state.workflows.find((workflow) => workflow.id === state.selectedWorkflowId) || state.workflows[0];
  }

  function architectureFor(workflow) {
    return topologyOptions[workflow?.topology]?.architecture || "B0";
  }

  function workflowNodes(workflow = selectedWorkflow()) {
    if (!workflow || workflow.topology === "rules") return ["context", "rules", "critic"];
    if (workflow.topology === "single_agent") return ["context", "synthesizer", "critic"];
    if (workflow.resultType === "risk_review") {
      return ["context", "rules", "market", "exposure", "fundamental_change", "event_retrieval", "scenario_stress", ...state.customCapabilities, "synthesis", "critic"];
    }
    return ["context", "market", "exposure", "news", ...state.customCapabilities, "synthesis", "critic"];
  }

  function optionMarkup(options, selected) {
    return Object.entries(options).map(([value, metadata]) => {
      const label = typeof metadata === "string" ? metadata : metadata.label;
      return `<option value="${value}" ${value === selected ? "selected" : ""}>${label}</option>`;
    }).join("");
  }

  function renderWorkflowCycleList() {
    $("#workflow-cycle-list").innerHTML = state.workflows.map((workflow, index) => `
      <div class="workflow-config-row ${workflow.id === state.selectedWorkflowId ? "selected" : ""}" data-workflow-row="${workflow.id}">
        <button class="workflow-config-identity" type="button" data-select-workflow="${workflow.id}">
          <strong>${index + 1}. ${escapeHtml(workflow.name)}</strong>
          <small>${workflow.enabled ? "Scheduled on every replay date" : "Optional · currently disabled"} · routine output auto-clears</small>
        </button>
        <label class="workflow-config-field"><span>Result sought</span>
          <select data-workflow-field="resultType" data-workflow-id="${workflow.id}">${optionMarkup(resultOptions, workflow.resultType)}</select>
        </label>
        <label class="workflow-config-field"><span>Runtime / framework</span>
          <select data-workflow-field="runtime" data-workflow-id="${workflow.id}">${optionMarkup(runtimeOptions, workflow.runtime)}</select>
        </label>
        <label class="workflow-config-field"><span>Agent topology</span>
          <select data-workflow-field="topology" data-workflow-id="${workflow.id}">${optionMarkup(topologyOptions, workflow.topology)}</select>
        </label>
        <label class="workflow-enabled"><input type="checkbox" data-workflow-field="enabled" data-workflow-id="${workflow.id}" ${workflow.enabled ? "checked" : ""}><span>Enabled</span></label>
      </div>`).join("");
  }

  function renderWorkflow() {
    const workflow = selectedWorkflow();
    if (!workflow) return;
    const nodes = workflowNodes(workflow);
    const runtime = runtimeOptions[workflow.runtime];
    const topology = topologyOptions[workflow.topology];
    const intention = workflowIntentions[workflow.resultType];
    $("#workflow-intent").innerHTML = `
      <div><span>Question this workflow must answer</span><strong>${escapeHtml(intention.question)}</strong></div>
      <div><span>Audience and deliverable</span><p>${escapeHtml(intention.audience)} · ${resultOptions[workflow.resultType]}</p><span>Evidence required</span><p>${escapeHtml(intention.evidence)}</p></div>
      <div><span>Human attention policy</span><p>${escapeHtml(intention.attention)}</p></div>`;
    $("#workflow-canvas").innerHTML = `
      <div class="workflow-definition-banner ${runtime.available ? "" : "warning"}">
        <strong>${escapeHtml(workflow.name)} → ${resultOptions[workflow.resultType]}</strong>
        <span>${runtime.label}${runtime.available ? " · runnable" : " · design only"}</span>
        <span>${topology.label} · ${topology.architecture}</span>
      </div>
      <div class="workflow-flow">${nodes.map((id, index) => `
        ${index ? '<span class="workflow-arrow">→</span>' : ""}
        <button class="workflow-node" type="button" data-node="${id}">
          <span>${id === "context" ? "Input" : id === "critic" ? "Guardrail" : "Capability"}</span>
          <strong>${nodeContracts[id].name}</strong>
          <small>${nodeContracts[id].purpose}</small>
        </button>`).join("")}</div>`;
    inspectNode(nodes[0]);
  }

  function inspectNode(id) {
    const node = nodeContracts[id];
    if (!node) return;
    $$(".workflow-node").forEach((button) => button.classList.toggle("selected", button.dataset.node === id));
    $("#node-inspector").innerHTML = `
      <span class="panel-label">Selected node</span>
      <h3>${node.name}</h3>
      <p>${node.purpose}</p>
      <div class="contract-block"><strong>Receives</strong><span>${node.input}</span></div>
      <div class="contract-block"><strong>Produces</strong><span>${node.output}</span></div>
      <div class="contract-block"><strong>Capability grant</strong><span>${node.tools}</span></div>`;
  }

  function applyQueuedEvents(date) {
    const pending = state.ledger.filter((event) => !event.applied && event.effectiveDate <= date);
    pending.forEach((event) => {
      const holding = state.holdings.find((item) => item.id === event.instrumentId);
      if (holding) holding.quantity = Math.max(0, holding.quantity * (1 - event.reduction));
      event.applied = true;
      event.appliedDate = date;
    });
    return pending;
  }

  function revalueFromReplayIndex(index) {
    state.priceSeries.slice(index).forEach((point, offset) => {
      point.nav = state.cash + state.holdings.reduce((sum, holding) => sum + holding.quantity * point.prices[holding.id], 0);
      state.fullSeries[state.warmupCount + index + offset].nav = point.nav;
    });
  }

  function policyAssessment(metrics, point = state.priceSeries[Math.max(0, state.replayIndex)]) {
    const controls = state.policyControls;
    const weights = point ? holdingWeightsAt(point) : [];
    const topWeight = weights[0]?.weight || 0;
    const topThreeWeight = weights.slice(0, 3).reduce((sum, item) => sum + item.weight, 0);
    const investedWeight = weights.reduce((sum, item) => sum + item.weight, 0);
    const cashWeight = Math.max(0, 1 - investedWeight);
    const scenarioLoss = Math.max(topWeight * .05, topThreeWeight * .05, investedWeight * .03);
    const acceptedConcentration = state.policyExceptions.some((item) => item.startsWith("Largest position"));
    const acceptedCash = state.policyExceptions.some((item) => item.startsWith("Opening cash"));
    const concentrationBoundary = acceptedConcentration
      ? Math.max(controls.concentrationLimit, (state.policyBaseline?.topWeight || 0) + .0025)
      : controls.concentrationLimit;
    const cashBoundary = acceptedCash
      ? Math.min(controls.minimumCash, Math.max(0, (state.policyBaseline?.cashWeight || 0) - .0025))
      : controls.minimumCash;
    const observations = [
      { id: "daily_loss", label: "Daily loss", value: Math.max(0, -metrics.daily_return), limit: controls.dailyLossLimit, direction: "max" },
      { id: "historical_var", label: "Historical VaR", value: metrics.historical_var_95, limit: controls.historicalVarLimit, direction: "max" },
      { id: "concentration", label: "Largest position", value: topWeight, limit: concentrationBoundary, statedLimit: controls.concentrationLimit, direction: "max" },
      { id: "scenario_loss", label: "Largest reviewed scenario loss", value: scenarioLoss, limit: controls.scenarioLossLimit, direction: "max" },
      { id: "minimum_cash", label: "Cash weight", value: cashWeight, limit: cashBoundary, statedLimit: controls.minimumCash, direction: "min" },
    ];
    const breached = observations.filter((item) => item.direction === "max" ? item.value > item.limit : item.value < item.limit);
    const near = observations.filter((item) => {
      if (breached.includes(item) || !item.limit) return false;
      return item.direction === "max" ? item.value >= item.limit * .75 : item.value <= item.limit * 1.25;
    });
    return { observations, breached, near, topWeight, topThreeWeight, investedWeight, cashWeight, scenarioLoss };
  }

  function decisionFor(metrics) {
    const assessment = policyAssessment(metrics);
    if (assessment.breached.length) return "URGENT_REVIEW";
    if (assessment.near.length) return "REVIEW";
    return "NO_ISSUE";
  }

  function instrumentName(id) {
    const parts = String(id).split("-");
    const number = parts.at(-1) || id;
    const family = parts.slice(1, -1).join(" ").replace(/\b\w/g, (letter) => letter.toUpperCase()) || "Research";
    return `${family} position ${number}`;
  }

  function signedPercent(value, digits = 2) {
    const number = Number(value || 0);
    return `${number >= 0 ? "+" : ""}${(number * 100).toFixed(digits)}%`;
  }

  function contributionBps(value) {
    const number = Number(value || 0) * 10000;
    return `${number >= 0 ? "+" : ""}${number.toFixed(1)} bps`;
  }

  function previousMetricsAt(index) {
    const end = state.warmupCount + Math.max(0, index);
    const series = state.fullSeries.slice(Math.max(0, end - 61), end);
    return calculateMetricValues(series);
  }

  function buildDailyRiskReview(index, metrics, decision) {
    const point = state.priceSeries[index];
    const previousPoint = state.fullSeries[state.warmupCount + index - 1] || point;
    const weights = holdingWeightsAt(point);
    const previousMetrics = previousMetricsAt(index);
    const attribution = state.holdings.map((holding) => {
      const previousPrice = previousPoint.prices[holding.id] || point.prices[holding.id];
      const currentPrice = point.prices[holding.id];
      const pnl = holding.quantity * (currentPrice - previousPrice);
      return {
        id: holding.id,
        name: instrumentName(holding.id),
        assetReturn: previousPrice ? currentPrice / previousPrice - 1 : 0,
        contribution: previousPoint.nav ? pnl / previousPoint.nav : 0,
        pnl,
        weight: weights.find((item) => item.id === holding.id)?.weight || 0,
      };
    }).sort((a, b) => a.contribution - b.contribution);
    const largestDetractor = attribution[0];
    const largestContributor = attribution.at(-1);
    const topThreeWeight = weights.slice(0, 3).reduce((sum, item) => sum + item.weight, 0);
    const investedWeight = weights.reduce((sum, item) => sum + item.weight, 0);
    const hhi = weights.reduce((sum, item) => sum + item.weight ** 2, 0);
    const assessment = policyAssessment(metrics, point);
    const triggers = assessment.breached.map((item) =>
      `${item.label.toLowerCase()} ${percent(item.value, 2)} breached its approved ${item.direction === "max" ? "maximum" : "minimum"} of ${percent(item.statedLimit ?? item.limit, 2)}`);
    assessment.near.forEach((item) => triggers.push(
      `${item.label.toLowerCase()} ${percent(item.value, 2)} is approaching its approved ${item.direction === "max" ? "maximum" : "minimum"} of ${percent(item.statedLimit ?? item.limit, 2)}`));
    const triggerSentence = triggers.length
      ? triggers.join("; ")
      : "none of the approved daily-loss, historical-VaR, concentration, scenario-loss, or cash controls were breached";
    const statusLead = decision === "URGENT_REVIEW"
      ? "Portfolio risk has moved into urgent review."
      : decision === "REVIEW"
        ? "Portfolio risk has moved from routine monitoring to active review."
        : "Portfolio risk remains within the routine monitoring range.";
    const direction = metrics.daily_return < 0 ? "lost" : "gained";
    const mainDriver = largestDetractor?.contribution < 0
      ? `${largestDetractor.name} was the largest detractor, contributing ${contributionBps(largestDetractor.contribution)}`
      : `${largestContributor.name} was the largest contributor, adding ${contributionBps(largestContributor.contribution)}`;
    const narrative = `${statusLead} The portfolio ${direction} ${percent(Math.abs(metrics.daily_return), 2)} on ${prettyDate(point.date)}. ${triggerSentence[0].toUpperCase()}${triggerSentence.slice(1)}. ${mainDriver}. The top three positions represent ${percent(topThreeWeight, 1)} of portfolio value, so the review considers both the immediate move and the portfolio's capacity to absorb a concentrated shock.`;
    const counterEvidence = metrics.daily_return >= 0 && decision !== "NO_ISSUE"
      ? "Today’s return was positive, which argues against treating the signal as a one-day sell-off; another approved mandate control is driving the escalation."
      : largestContributor?.contribution > 0
        ? `${largestContributor.name} offset part of the adverse movement with ${contributionBps(largestContributor.contribution)} of positive contribution.`
        : "There was little offsetting positive contribution among current holdings.";
    const scenarios = [
      {
        name: "Largest-position shock",
        assumption: `${instrumentName(weights[0]?.id)} falls 5% with other prices unchanged`,
        impact: -(weights[0]?.weight || 0) * .05,
      },
      {
        name: "Top-three concentration shock",
        assumption: "The three largest positions fall 5% together",
        impact: -topThreeWeight * .05,
      },
      {
        name: "Broad portfolio shock",
        assumption: "Every invested position falls 3%; cash is unchanged",
        impact: -investedWeight * .03,
      },
    ].map((scenario) => ({ ...scenario, dollarImpact: scenario.impact * point.nav }));
    const recommendation = decision === "URGENT_REVIEW"
      ? `Open an immediate investigation into ${largestDetractor.name}; verify market and issuer-specific causes before approving any sandbox PortfolioEvent.`
      : decision === "REVIEW"
        ? `Open a targeted investigation into ${largestDetractor.name} and the drawdown path. Continue monitoring while the missing event and fundamental evidence is collected.`
        : "Record no portfolio action. Continue the scheduled replay and preserve the current attention thresholds.";
    return {
      date: point.date,
      decision,
      headline: statusLead,
      narrative,
      confidence: "Moderate",
      triggerSentence,
      whatChanged: [
        `Portfolio value moved ${signedPercent(metrics.daily_return)} to ${money(metrics.nav)}.`,
        `Annualized volatility is ${percent(metrics.annualized_volatility, 2)} (${signedPercent(metrics.annualized_volatility - (previousMetrics.annualized_volatility ?? metrics.annualized_volatility), 2)} versus the prior review).`,
        `Maximum drawdown is ${percent(metrics.maximum_drawdown, 2)} (${signedPercent(metrics.maximum_drawdown - (previousMetrics.maximum_drawdown ?? metrics.maximum_drawdown), 2)} versus the prior review).`,
      ],
      whyItMatters: [
        `${mainDriver}.`,
        `The largest position is ${percent(weights[0]?.weight || 0, 1)} of portfolio value; the top three are ${percent(topThreeWeight, 1)}.`,
        counterEvidence,
      ],
      attribution: [...attribution].sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution)).slice(0, 5),
      concentration: { topOne: weights[0]?.weight || 0, topThree: topThreeWeight, hhi },
      scenarios,
      evidence: [
        { label: "Portfolio valuation", value: `${money(metrics.nav)} at ${prettyDate(point.date)}`, source: "Revalued holdings and cash", quality: "Deterministic" },
        { label: "Approved mandate controls", value: `${assessment.breached.length} breaches · ${assessment.near.length} approaching`, source: "MonitoringPolicyVersion + PortfolioDefinition risk thresholds", quality: "Deterministic" },
        { label: "Risk history", value: `${metrics.observations} daily return observations`, source: "Point-in-time synthetic replay path", quality: "Qualified with limitation" },
        { label: "Position attribution", value: `${state.holdings.length} holdings reconciled to the daily portfolio move`, source: "Quantity × price change", quality: "Deterministic" },
        { label: "Events and news", value: "No governed event source connected", source: "Capability readiness check", quality: "Unavailable" },
      ],
      uncertainties: [
        "The displayed price path is deterministic and synthetic; it demonstrates workflow behavior rather than historical investment performance.",
        "No governed news or event source is connected, so the system cannot establish a market or issuer-specific cause.",
        "Point-in-time fundamental-change retrieval is designed but not connected to this browser prototype.",
        "Scenario results are deterministic sensitivities, not forecasts or probability estimates.",
      ],
      capabilityTrace: [
        { name: "Risk metrics", status: "Complete", detail: "Return, volatility, drawdown, VaR and expected shortfall calculated." },
        { name: "Position attribution", status: "Complete", detail: "Daily P&L reconciled across every holding." },
        { name: "Concentration analysis", status: "Complete", detail: "Top-one, top-three and HHI exposure calculated." },
        { name: "Scenario stress", status: "Complete", detail: "Three reviewed deterministic shocks evaluated." },
        { name: "Events and fundamentals", status: "Unavailable", detail: "The review discloses the gap instead of inventing a cause." },
        { name: "Evidence critic", status: "Passed", detail: "Every numerical statement is derived from the frozen replay context." },
      ],
      recommendation,
      humanQuestion: decision === "NO_ISSUE"
        ? "Do you agree that this date can be recorded without portfolio action?"
        : "Do you accept the recommendation to investigate while leaving the sandbox portfolio unchanged?",
    };
  }

  function reviewDocumentHtml(record) {
    const review = record.deepReview;
    if (!review) return `<div class="empty-state">No narrative review is available for this workflow output.</div>`;
    const statusClass = review.decision.toLowerCase().replaceAll("_", "-");
    return `
      <header class="review-header">
        <div>
          <span class="panel-label">Daily Portfolio Risk Review · ${prettyDate(review.date)}</span>
          <h2>${escapeHtml(review.headline)}</h2>
        </div>
        <div class="review-badges">
          <span class="decision-status ${statusClass}">${review.decision.replaceAll("_", " ")}</span>
          <span>Evidence confidence · ${review.confidence}</span>
        </div>
      </header>
      <section class="executive-assessment">
        <strong>Executive assessment</strong>
        <p>${escapeHtml(review.narrative)}</p>
      </section>
      <div class="review-columns">
        <section><h3>What changed</h3><ul>${review.whatChanged.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></section>
        <section><h3>Why it matters</h3><ul>${review.whyItMatters.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></section>
      </div>
      <section class="review-section">
        <div class="review-section-heading"><div><span>Attribution</span><h3>Which positions explain today’s move?</h3></div><small>Contribution reconciles quantity × price change to prior portfolio value.</small></div>
        <div class="attribution-table">
          ${review.attribution.map((item) => `<div>
            <strong>${escapeHtml(item.name)}</strong>
            <span>${percent(item.weight, 1)} weight</span>
            <span>${signedPercent(item.assetReturn)} position return</span>
            <b class="${item.contribution < 0 ? "negative" : "positive"}">${contributionBps(item.contribution)}</b>
          </div>`).join("")}
        </div>
      </section>
      <section class="review-section">
        <div class="review-section-heading"><div><span>Deterministic scenarios</span><h3>How sensitive is the current portfolio?</h3></div><small>Sensitivities, not forecasts.</small></div>
        <div class="scenario-grid">${review.scenarios.map((scenario) => `<article>
          <strong>${escapeHtml(scenario.name)}</strong>
          <p>${escapeHtml(scenario.assumption)}</p>
          <b>${signedPercent(scenario.impact)} · ${money(scenario.dollarImpact)}</b>
        </article>`).join("")}</div>
      </section>
      <section class="review-section">
        <div class="review-section-heading"><div><span>Evidence quality</span><h3>What supports this review?</h3></div><small>Missing evidence remains visible.</small></div>
        <div class="evidence-grid">${review.evidence.map((item) => `<article>
          <span>${escapeHtml(item.quality)}</span>
          <strong>${escapeHtml(item.label)}</strong>
          <p>${escapeHtml(item.value)}</p>
          <small>${escapeHtml(item.source)}</small>
        </article>`).join("")}</div>
      </section>
      <div class="review-columns">
        <section class="uncertainty-panel"><h3>Uncertainties and limitations</h3><ul>${review.uncertainties.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></section>
        <section class="recommendation-panel"><span>Recommendation</span><h3>${escapeHtml(review.recommendation)}</h3><p>${escapeHtml(review.humanQuestion)}</p></section>
      </div>
      <details class="capability-trace">
        <summary>How the workflow produced this review</summary>
        ${review.capabilityTrace.map((item) => `<div><strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(item.status)}</span><p>${escapeHtml(item.detail)}</p></div>`).join("")}
      </details>`;
  }

  function summaryForWorkflow(workflow, metrics, decision, affected) {
    if (!runtimeOptions[workflow.runtime].available) {
      return `${runtimeOptions[workflow.runtime].label} is configured for this cycle, but its adapter is not installed in the thesis runner. The cycle is blocked rather than silently falling back.`;
    }
    if (workflow.resultType === "risk_review") {
      return decision === "NO_ISSUE"
        ? "The reviewed risk thresholds were not triggered by the current deterministic context."
        : `${affected} is the largest current exposure and the deterministic risk thresholds require review.`;
    }
    if (workflow.resultType === "morning_review") {
      return `Morning review assembled from portfolio value ${money(metrics.nav)}, ${percent(metrics.annualized_volatility, 2)} volatility, ${percent(metrics.maximum_drawdown, 2)} drawdown, and the explicit event-source limitation.`;
    }
    return `Portfolio brief created for ${affected}, the largest current exposure. It separates deterministic metrics from model interpretation and retains the missing-event-source warning.`;
  }

  function decisionForWorkflow(workflow, metrics) {
    if (!runtimeOptions[workflow.runtime].available) return "BLOCKED";
    if (workflow.resultType === "portfolio_brief") return "BRIEF_READY";
    return decisionFor(metrics);
  }

  function requiresAttention(record) {
    if (record.decision === "BLOCKED" || record.decision === "URGENT_REVIEW") return true;
    return record.decision === "REVIEW" && record.resultType !== "portfolio_brief";
  }

  function advanceReplayCursor() {
    state.cycleIndex += 1;
    const workflows = activeWorkflows();
    if (state.cycleIndex >= workflows.length) {
      state.cycleIndex = 0;
      state.replayIndex += 1;
      state.preparedDateIndex = -1;
      state.appliedThisDate = [];
      $$("#date-pipeline span").forEach((item) => item.classList.remove("complete"));
    }
  }

  function prepareCurrentReplayDate() {
    if (state.preparedDateIndex === state.replayIndex) return;
    const point = state.priceSeries[state.replayIndex];
    state.appliedThisDate = applyQueuedEvents(point.date);
    if (state.appliedThisDate.length) revalueFromReplayIndex(state.replayIndex);
    state.preparedDateIndex = state.replayIndex;
    $$("#date-pipeline span").forEach((item) => item.classList.add("complete"));
  }

  function processCurrentWorkflowCycle(options = {}) {
    if (state.pendingDecision) return "pending";
    if (!state.priceSeries.length) makePriceSeries();
    const workflows = activeWorkflows();
    if (!workflows.length) {
      $("#replay-status").textContent = "No cycles enabled";
      return "blocked";
    }
    if (state.replayIndex < 0) state.replayIndex = 0;
    if (state.replayIndex >= state.priceSeries.length) {
      $("#replay-status").textContent = "Complete";
      renderReplayPosition();
      return "complete";
    }
    if (state.cycleIndex >= workflows.length) state.cycleIndex = 0;
    prepareCurrentReplayDate();
    const point = state.priceSeries[state.replayIndex];
    const workflow = workflows[state.cycleIndex];
    const metrics = calculateMetricValues(metricHistoryAtReplayIndex(state.replayIndex));
    const weights = holdingWeightsAt(point);
    const affected = weights[0]?.id || state.holdings[0]?.id;
    const decision = decisionForWorkflow(workflow, metrics);
    const deepReview = workflow.resultType === "risk_review" && runtimeOptions[workflow.runtime].available
      ? buildDailyRiskReview(state.replayIndex, metrics, decision)
      : null;
    const record = {
      id: `DP-${point.date.replaceAll("-", "")}-${workflow.id}-${state.decisions.length + 1}`,
      date: point.date,
      workflowId: workflow.id,
      workflowName: workflow.name,
      resultType: workflow.resultType,
      runtime: workflow.runtime,
      topology: workflow.topology,
      architecture: architectureFor(workflow),
      decision,
      humanStatus: "pending",
      summary: deepReview?.narrative || summaryForWorkflow(workflow, metrics, decision, affected),
      nav: metrics.nav,
      dailyReturn: metrics.daily_return,
      volatility: metrics.annualized_volatility,
      drawdown: metrics.maximum_drawdown,
      affected,
      deepReview,
    };
    record.requiresAttention = requiresAttention(record);
    state.decisions.push(record);
    if (options.autonomous && !record.requiresAttention) {
      record.humanStatus = "auto-cleared";
      advanceReplayCursor();
      renderReplayStep(record);
      renderResults();
      completeStep("replay");
      return "auto-cleared";
    }
    state.pendingDecision = record;
    renderReplayStep(record);
    renderResults();
    completeStep("replay");
    return "attention";
  }

  function renderCycleTrack() {
    const workflows = activeWorkflows();
    const date = state.priceSeries[state.replayIndex]?.date;
    $("#cycle-position").textContent = workflows.length
      ? `${Math.min(state.cycleIndex + 1, workflows.length)} / ${workflows.length} cycles`
      : "0 / 0 cycles";
    $("#cycle-track").innerHTML = workflows.length ? workflows.map((workflow, index) => {
      const record = [...state.decisions].reverse().find((item) => item.date === date && item.workflowId === workflow.id);
      const status = record?.humanStatus === "pending"
        ? "pending"
        : record?.humanStatus
          ? "reviewed"
          : index === state.cycleIndex
            ? "current"
            : "";
      return `<div class="cycle-chip ${status}">
        <span>${status === "pending" ? "Paused for attention" : record?.humanStatus === "auto-cleared" ? "Auto-cleared" : status === "reviewed" ? "Human reviewed" : index === state.cycleIndex ? "Next cycle" : "Queued"}</span>
        <strong>${escapeHtml(workflow.name)}</strong>
        <small>${runtimeOptions[workflow.runtime].label} · ${topologyOptions[workflow.topology].architecture}</small>
      </div>`;
    }).join("") : `<div class="empty-state">Enable at least one workflow cycle.</div>`;
  }

  function renderDateDecisionStream() {
    const date = state.priceSeries[state.replayIndex]?.date;
    const records = state.decisions.filter((record) => record.date === date);
    $("#date-decision-list").innerHTML = records.length ? records.map((record) => `
      <div class="date-decision-item">
        <strong>${escapeHtml(record.workflowName)}</strong>
        <span>${resultOptions[record.resultType]}</span>
        <span>${runtimeOptions[record.runtime].label} · ${record.architecture}</span>
        <span class="human-status ${record.humanStatus}">${record.humanStatus === "pending" ? "Needs attention" : record.humanStatus === "auto-cleared" ? "Auto-cleared" : record.humanStatus}</span>
      </div>`).join("") : `<div class="empty-state">No Workflow Cycle has completed for this date.</div>`;
  }

  function renderDecisionGate() {
    const record = state.pendingDecision;
    if (!record) {
      $("#decision-gate").className = "decision-gate waiting";
      $("#decision-gate").innerHTML = `
        <div><span class="panel-label">Human attention gate</span><h3>No decision requires attention</h3><p>Routine outputs pass automatically and remain visible in the audit trail.</p></div>`;
      return;
    }
    $("#decision-gate").className = "decision-gate";
    const review = record.deepReview;
    $("#decision-gate").innerHTML = `
      <div>
        <span class="panel-label">Human attention required · Replay paused</span>
        <h3>${escapeHtml(review?.humanQuestion || `${record.workflowName} produced ${record.decision.replaceAll("_", " ")}`)}</h3>
        <p>${escapeHtml(review?.recommendation || record.summary)}</p>
        <div class="decision-metadata">
          <span>${resultOptions[record.resultType]}</span>
          <span>${runtimeOptions[record.runtime].label}</span>
          <span>${topologyOptions[record.topology].label} · ${record.architecture}</span>
          <span>${record.id}</span>
        </div>
      </div>
      <div class="decision-gate-actions">
        <button class="button primary" type="button" data-review-decision="accepted">Accept recommendation</button>
        <button class="button" type="button" data-review-decision="escalated">Open investigation</button>
        <button class="button ghost" type="button" data-review-decision="rejected">Reject finding</button>
      </div>`;
  }

  function renderReplayPosition() {
    const count = state.priceSeries.length;
    const completedDates = Math.min(Math.max(state.replayIndex, 0), count);
    const point = state.priceSeries[Math.min(state.replayIndex, count - 1)];
    $("#clock-date").textContent = point ? prettyDate(point.date) : "Not started";
    $("#clock-position").textContent = state.replayIndex >= count
      ? `${count} dates complete`
      : state.replayIndex >= 0
        ? `Date ${state.replayIndex + 1} of ${count}`
        : "No date loaded";
    $("#progress-label").textContent = `${completedDates} / ${count} dates complete`;
    $("#progress-bar").style.width = `${count ? completedDates / count * 100 : 0}%`;
    const workflows = activeWorkflows();
    $("#cycle-name").textContent = state.pendingDecision?.workflowName
      || workflows[state.cycleIndex]?.name
      || (state.replayIndex >= count ? "All Workflow Cycles complete" : "Waiting to start");
    renderCycleTrack();
    renderDecisionGate();
    renderDateDecisionStream();
  }

  function renderReplayStep(record) {
    $("#replay-status").textContent = record.humanStatus === "pending" ? "Paused — attention required" : "Running autonomously";
    const changeText = record.dailyReturn < 0 ? "lost" : "gained";
    $("#live-narrative").innerHTML = `
      <span class="panel-label">Workflow Cycle output</span>
      <h3>${escapeHtml(record.workflowName)} · ${record.decision.replaceAll("_", " ")}</h3>
      <p>${state.appliedThisDate.length ? `${state.appliedThisDate.length} approved PortfolioEvent was applied before the first cycle. ` : ""}The portfolio ${changeText} ${percent(Math.abs(record.dailyReturn), 2)}. ${escapeHtml(record.summary)}</p>`;
    $("#live-values").innerHTML = [
      ["Portfolio value", money(record.nav)],
      ["Latest return", percent(record.dailyReturn, 2)],
      ["Volatility", percent(record.volatility, 2)],
      ["Drawdown", percent(record.drawdown, 2)],
    ].map(([label, value]) => `<div class="live-value"><span>${label}</span><strong>${value}</strong></div>`).join("");
    const deepReview = $("#deep-review");
    if (record.deepReview) {
      deepReview.classList.remove("hidden");
      deepReview.innerHTML = reviewDocumentHtml(record);
    } else {
      deepReview.classList.add("hidden");
      deepReview.innerHTML = "";
    }
    renderReplayPosition();
  }

  function proposeEventFromAcceptedDecision(record) {
    if (record.resultType !== "risk_review" || record.decision !== "URGENT_REVIEW") return;
    const previous = [...state.decisions]
      .reverse()
      .find((item) => item.id !== record.id && item.workflowId === record.workflowId && item.humanStatus === "accepted");
    const previousAlert = previous && ["REVIEW", "URGENT_REVIEW"].includes(previous.decision);
    if (previousAlert || state.proposedEvents.some((event) => event.date === record.date)) return;
    state.proposedEvents.push({
      id: `PE-${record.date.replaceAll("-", "")}-${state.proposedEvents.length + 1}`,
      date: record.date,
      instrumentId: record.affected,
      reduction: record.decision === "URGENT_REVIEW" ? .10 : .05,
      status: "pending",
    });
  }

  function resolvePendingDecision(humanStatus) {
    const record = state.pendingDecision;
    if (!record) return;
    record.humanStatus = humanStatus;
    if (humanStatus === "accepted") proposeEventFromAcceptedDecision(record);
    state.pendingDecision = null;
    advanceReplayCursor();
    renderResults();
    if (state.replayIndex >= state.priceSeries.length) {
      $("#replay-status").textContent = "Complete";
      renderReplayPosition();
      return;
    }
    startReplay();
  }

  function startReplay() {
    if (state.pendingDecision) return;
    $("#replay-status").textContent = "Running autonomously";
    let outcome = "auto-cleared";
    let safety = 0;
    const maximumCycles = Math.max(1, state.priceSeries.length * Math.max(1, activeWorkflows().length) + 1);
    while (outcome === "auto-cleared" && safety < maximumCycles) {
      outcome = processCurrentWorkflowCycle({ autonomous: true });
      safety += 1;
    }
    if (outcome === "complete" || state.replayIndex >= state.priceSeries.length) {
      $("#replay-status").textContent = "Complete — no attention pending";
      renderReplayPosition();
    }
  }

  function stopReplay() {
    if (state.replayTimer) window.clearInterval(state.replayTimer);
    state.replayTimer = null;
    $("#start-replay").textContent = "Run clock alone";
  }

  function resetReplay() {
    stopReplay();
    state.holdings = state.openingHoldings.map((holding) => ({ ...holding }));
    state.cash = state.openingCash;
    state.replayIndex = -1;
    state.cycleIndex = 0;
    state.preparedDateIndex = -1;
    state.pendingDecision = null;
    state.appliedThisDate = [];
    state.decisions = [];
    state.proposedEvents = [];
    state.ledger = [];
    makePriceSeries();
    renderHoldings();
    $("#clock-date").textContent = "Not started";
    $("#clock-position").textContent = "No date loaded";
    $("#progress-label").textContent = `0 / ${state.priceSeries.length} dates`;
    $("#progress-bar").style.width = "0%";
    $("#replay-status").textContent = "Ready";
    $("#cycle-name").textContent = "Waiting to start";
    $("#live-narrative").innerHTML = `<span class="panel-label">What is happening</span><h3>Waiting for the first Workflow Cycle</h3><p>Run the clock alone. Routine outputs will be logged automatically; the clock stops only when something requires attention.</p>`;
    $("#live-values").innerHTML = "";
    $("#deep-review").classList.add("hidden");
    $("#deep-review").innerHTML = "";
    $$("#date-pipeline span").forEach((item) => item.classList.remove("complete"));
    renderReplayPosition();
    renderResults();
  }

  function renderResults() {
    const alerts = state.decisions.filter((record) => record.decision !== "NO_ISSUE");
    const urgent = state.decisions.filter((record) => record.decision === "URGENT_REVIEW");
    const workflowIds = activeWorkflows().map((workflow) => workflow.id);
    const completedDates = new Set(state.decisions.map((record) => record.date).filter((date) =>
      workflowIds.every((workflowId) => state.decisions.some((record) =>
        record.date === date && record.workflowId === workflowId && record.humanStatus !== "pending"))));
    $("#result-status").textContent = `${state.decisions.length} decisions`;
    $("#result-summary").innerHTML = [
      ["Dates completed", completedDates.size],
      ["Workflow decisions", state.decisions.length],
      ["Urgent reviews", urgent.length],
      ["Approved sandbox events", state.ledger.length],
    ].map(([label, value]) => `<div class="result-stat"><span>${label}</span><strong>${value}</strong></div>`).join("");
    $("#decision-list").innerHTML = state.decisions.length ? [...state.decisions].reverse().map((record) => `
      <div class="decision-row">
        <time>${prettyDate(record.date)}</time>
        <strong>${escapeHtml(record.workflowName)}</strong>
        <span class="decision-status ${record.decision.toLowerCase().replaceAll("_", "-")}">${record.decision.replaceAll("_", " ")}</span>
        <p>${escapeHtml(record.summary)}</p>
        <b>${record.architecture} · ${record.humanStatus}</b>
        ${record.deepReview ? `<button class="text-button" type="button" data-open-review="${record.id}">Open narrative review →</button>` : ""}
      </div>`).join("") : `<div class="empty-state">Run the replay to populate decisions.</div>`;
    const pending = state.proposedEvents.filter((event) => event.status === "pending");
    $("#event-queue").innerHTML = pending.length ? pending.map((event) => `
      <div class="event-card">
        <h4>${event.id} · simulated reduction</h4>
        <p>Candidate event: reduce ${event.instrumentId} by ${percent(event.reduction, 0)} on the next replay date. This is a sandbox proposal, not an order.</p>
        <div class="event-actions">
          <button class="button primary" type="button" data-approve-event="${event.id}">Approve for branch replay</button>
          <button class="button ghost" type="button" data-reject-event="${event.id}">Reject</button>
        </div>
      </div>`).join("") : `<div class="empty-state">No pending event proposal.</div>`;
    $("#event-ledger").innerHTML = state.ledger.length ? state.ledger.map((event) => `
      <div class="ledger-item">
        <strong>${event.id}</strong> · ${event.applied ? `applied on the sandbox branch ${prettyDate(event.appliedDate)}` : `approved; effective ${prettyDate(event.effectiveDate)}`}
        ${event.applied ? "" : `<button class="text-button" type="button" data-run-branch="${event.id}">Replay branch with this event →</button>`}
      </div>`).join("") : `<span>No events approved.</span>`;
    if (state.decisions.length) completeStep("results");
  }

  function approveEvent(id) {
    const event = state.proposedEvents.find((item) => item.id === id);
    if (!event) return;
    const eventIndex = state.dates.indexOf(event.date);
    const nextDate = state.dates[Math.min(eventIndex + 1, state.dates.length - 1)] || event.date;
    event.status = "approved";
    state.ledger.push({ ...event, effectiveDate: nextDate, applied: false });
    renderResults();
  }

  function replayApprovedBranch(id) {
    const approved = state.ledger.find((event) => event.id === id);
    if (!approved) return;
    stopReplay();
    state.holdings = state.openingHoldings.map((holding) => ({ ...holding }));
    state.cash = state.openingCash;
    state.ledger.forEach((event) => {
      event.applied = false;
      delete event.appliedDate;
    });
    state.replayIndex = -1;
    state.cycleIndex = 0;
    state.preparedDateIndex = -1;
    state.pendingDecision = null;
    state.appliedThisDate = [];
    state.decisions = [];
    state.proposedEvents = state.proposedEvents.filter((event) => event.status === "approved");
    makePriceSeries();
    renderHoldings();
    renderResults();
    showStep("replay");
    renderReplayPosition();
    startReplay();
  }

  function rejectEvent(id) {
    const event = state.proposedEvents.find((item) => item.id === id);
    if (event) event.status = "rejected";
    renderResults();
  }

  function openReviewDialog(id) {
    const record = state.decisions.find((item) => item.id === id);
    if (!record?.deepReview) return;
    $("#review-dialog-body").innerHTML = reviewDocumentHtml(record);
    $("#review-dialog").showModal();
  }

  function bind() {
    $$(".step-link").forEach((button) => button.addEventListener("click", () => showStep(button.dataset.step)));
    $$("[data-next]").forEach((button) => button.addEventListener("click", () => {
      completeStep(state.step);
      showStep(button.dataset.next);
    }));
    $("#generate-experiment").addEventListener("click", renderPlannerResult);
    $("#planning-path").addEventListener("change", (event) => {
      const openai = event.target.value === "openai";
      $("#planning-path-hint").textContent = openai
        ? "Shows the server-side Responses API and LangGraph adapter boundary. No browser-side model call or secret is permitted."
        : "Runs locally now. It exercises the same validated output boundary intended for the server-side LLM planner.";
      $("#generate-experiment").textContent = openai ? "Inspect OpenAI planner readiness" : "Draft canonical experiment";
    });
    $("#planner-result").addEventListener("click", (event) => {
      if (event.target.closest("[data-approve-experiment]")) approveExperimentDraft();
      if (event.target.closest("[data-revise-experiment]")) {
        $("#portfolio-description").focus();
        $("#experiment-status").textContent = "Draft";
      }
      if (event.target.closest("[data-use-local-preview]")) {
        $("#planning-path").value = "deterministic";
        $("#planning-path").dispatchEvent(new Event("change"));
        renderPlannerResult();
      }
      if (event.target.closest("[data-approved-next]")) showStep("holdings");
    });
    $("#cash-balance").addEventListener("change", (event) => {
      state.cash = Math.max(0, Number(event.target.value) || 0);
      renderHoldings();
    });
    $("#holdings-body").addEventListener("change", (event) => {
      const index = Number(event.target.dataset.holdingIndex);
      const field = event.target.dataset.field;
      if (!Number.isInteger(index) || !field) return;
      state.holdings[index][field] = Math.max(field === "price" ? .01 : 0, Number(event.target.value) || 0);
      renderHoldings();
    });
    $("#holdings-body").addEventListener("click", (event) => {
      const button = event.target.closest("[data-remove-holding]");
      if (!button) return;
      state.holdings.splice(Number(button.dataset.removeHolding), 1);
      renderHoldings();
    });
    $("#freeze-holdings").addEventListener("click", () => {
      captureOpeningState();
      makePriceSeries();
      completeStep("holdings");
    });
    $("#metric-catalog").addEventListener("click", (event) => {
      const row = event.target.closest("[data-metric]");
      if (!row) return;
      const id = row.dataset.metric;
      if (event.target.matches("input")) {
        if (event.target.checked) state.selectedMetrics.add(id);
        else state.selectedMetrics.delete(id);
        $("#metric-status").textContent = `${state.selectedMetrics.size} selected`;
      }
      inspectMetric(id);
    });
    $("#calculate-metrics").addEventListener("click", calculateAndRenderMetrics);
    $("#build-context").addEventListener("click", buildContext);
    $("#workflow-cycle-list").addEventListener("click", (event) => {
      const button = event.target.closest("[data-select-workflow]");
      if (!button) return;
      state.selectedWorkflowId = button.dataset.selectWorkflow;
      renderWorkflowCycleList();
      renderWorkflow();
      completeStep("workflow");
    });
    $("#workflow-cycle-list").addEventListener("change", (event) => {
      const id = event.target.dataset.workflowId;
      const field = event.target.dataset.workflowField;
      const workflow = state.workflows.find((item) => item.id === id);
      if (!workflow || !field) return;
      workflow[field] = field === "enabled" ? event.target.checked : event.target.value;
      state.selectedWorkflowId = workflow.id;
      renderWorkflowCycleList();
      renderWorkflow();
      renderReplayPosition();
      completeStep("workflow");
    });
    $("#workflow-canvas").addEventListener("click", (event) => {
      const node = event.target.closest("[data-node]");
      if (node) inspectNode(node.dataset.node);
    });
    $("#toggle-code").addEventListener("click", () => {
      $("#code-view").classList.toggle("hidden");
      $("#toggle-code").textContent = $("#code-view").classList.contains("hidden") ? "See how workflows execute" : "Hide execution details";
    });
    $("#add-capability").addEventListener("click", () => $("#capability-dialog").showModal());
    $("#capability-dialog").addEventListener("click", (event) => {
      const button = event.target.closest("[data-capability]");
      if (!button) return;
      if (!state.customCapabilities.includes(button.dataset.capability)) state.customCapabilities.push(button.dataset.capability);
      const workflow = selectedWorkflow();
      if (workflow) workflow.topology = "specialist_team";
      $("#capability-dialog").close();
      renderWorkflowCycleList();
      renderWorkflow();
    });
    $("#close-capability").addEventListener("click", () => $("#capability-dialog").close());
    $("#start-replay").addEventListener("click", startReplay);
    $("#step-replay").addEventListener("click", () => processCurrentWorkflowCycle());
    $("#reset-replay").addEventListener("click", resetReplay);
    $("#decision-gate").addEventListener("click", (event) => {
      const button = event.target.closest("[data-review-decision]");
      if (button) resolvePendingDecision(button.dataset.reviewDecision);
    });
    $("#decision-list").addEventListener("click", (event) => {
      const button = event.target.closest("[data-open-review]");
      if (button) openReviewDialog(button.dataset.openReview);
    });
    $("#close-review-dialog").addEventListener("click", () => $("#review-dialog").close());
    $("#event-queue").addEventListener("click", (event) => {
      const approve = event.target.closest("[data-approve-event]");
      const reject = event.target.closest("[data-reject-event]");
      if (approve) approveEvent(approve.dataset.approveEvent);
      if (reject) rejectEvent(reject.dataset.rejectEvent);
    });
    $("#event-ledger").addEventListener("click", (event) => {
      const runBranch = event.target.closest("[data-run-branch]");
      if (runBranch) replayApprovedBranch(runBranch.dataset.runBranch);
    });
    $("#open-system-map").addEventListener("click", () => $("#system-map-dialog").showModal());
    $("#close-system-map").addEventListener("click", () => $("#system-map-dialog").close());
    $("#add-holding").addEventListener("click", () => $("#holding-dialog").showModal());
    $("#close-holding").addEventListener("click", () => $("#holding-dialog").close());
    $("#confirm-holding").addEventListener("click", () => {
      state.holdings.push({
        id: $("#new-holding-name").value.trim() || "custom-research-instrument",
        quantity: Math.max(1, Number($("#new-holding-quantity").value) || 1),
        price: Math.max(.01, Number($("#new-holding-price").value) || 1),
      });
      $("#holding-dialog").close();
      renderHoldings();
    });
    $("#add-workflow-cycle").addEventListener("click", () => $("#workflow-dialog").showModal());
    $("#close-workflow-dialog").addEventListener("click", () => $("#workflow-dialog").close());
    $("#confirm-workflow").addEventListener("click", () => {
      const name = $("#new-workflow-name").value.trim() || "New workflow";
      const id = `${name.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") || "workflow"}_${state.workflows.length + 1}`;
      state.workflows.push({
        id,
        name,
        resultType: $("#new-workflow-result").value,
        runtime: "custom_python",
        topology: $("#new-workflow-topology").value,
        enabled: true,
      });
      state.selectedWorkflowId = id;
      $("#workflow-dialog").close();
      renderWorkflowCycleList();
      renderWorkflow();
      renderReplayPosition();
      completeStep("workflow");
    });
  }

  window.PortfolioReplayLab = {
    getCurrentPortfolio() {
      return {
        id: state.portfolioKey,
        title: portfolios[state.portfolioKey]?.title || "Custom research portfolio",
        cash: state.cash,
        holdings: state.holdings.map((holding) => ({ ...holding })),
      };
    },
    loadPortfolioCandidate(candidate) {
      const holdings = Array.isArray(candidate?.holdings) ? candidate.holdings : [];
      if (!holdings.length) return false;
      portfolios.local_builder = {
        title: String(candidate.title || "Locally built research portfolio"),
        cash: Math.max(0, Number(candidate.cash) || 0),
        holdings: holdings.map((holding) => [
          String(holding.id),
          Math.max(0, Number(holding.quantity) || 0),
          Math.max(.01, Number(holding.price) || 1),
        ]),
      };
      clonePortfolio("local_builder");
      state.experimentDraftApproved = false;
      state.policyExceptions = [];
      state.policyBaseline = null;
      $("#portfolio-description").value = `${portfolios.local_builder.title}, assembled from reviewed private-neutral research instruments.`;
      $("#experiment-status").textContent = "Portfolio review required";
      $("#experiment-status").classList.add("warning");
      $("#experiment-next").disabled = true;
      $("#experiment-next").textContent = "Approve the draft to continue";
      renderHoldings();
      makePriceSeries();
      showStep("holdings");
      return true;
    },
  };

  function initialize() {
    clonePortfolio("diversified");
    makePriceSeries();
    renderHoldings();
    renderMetricCatalog();
    inspectMetric("daily_return");
    renderWorkflowCycleList();
    renderWorkflow();
    renderResults();
    $("#progress-label").textContent = `0 / ${state.priceSeries.length} dates`;
    renderReplayPosition();
    bind();
  }

  initialize();
})();
