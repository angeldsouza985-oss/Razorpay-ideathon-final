"use client";

import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  ChevronRight,
  CircleDollarSign,
  FileSearch,
  LayoutDashboard,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Wallet,
} from "lucide-react";

/* =========================================================
   API
========================================================= */

const API =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

/* =========================================================
   TYPES
========================================================= */

type Case = {
  id: number;
  customer_id: number;
  contract_id: number;
  invoice_id: number;

  leakage_type: string;

  expected_amount: string;
  actual_amount: string;
  leakage_amount: string;

  confidence: string;
  recoverability: string;

  status: string;
  recommended_action: string;

  classification?: string;
  root_cause?: string;
  investigation_summary?: string;
  reasoning?: string;

  recovered_amount?: string;
  investigated_at?: string;
};

type Metrics = {
  total_revenue_expected: string;
  total_revenue_invoiced: string;

  potential_leakage: string;
  validated_leakage: string;
  recoverable_revenue: string;
  recovered_revenue: string;

  total_cases: number;
  confirmed_cases: number;
  legitimate_cases: number;
  human_review_cases: number;
  stopped_cases: number;

  recovery_rate: string;
};

type AuditEvent = {
  id: number;
  timestamp: string;
  event_type: string;
  actor: string;
  description: string;
  result: string;
};

type Evidence = {
  source: string;
  fact: string;
};

type Investigation = {
  classification?: string;
  root_cause?: string;
  investigation_summary?: string;
  reasoning?: string;

  evidence?: Evidence[];

  confidence?: string;
  recoverability?: string;
  recommended_action?: string;
};

/* =========================================================
   HELPERS
========================================================= */

const money = (
  value?: string | number | null
) => {
  if (
    value === undefined ||
    value === null ||
    value === ""
  ) {
    return "—";
  }

  const n = Number(value);

  if (!Number.isFinite(n)) {
    return "—";
  }

  return `₹${n.toLocaleString("en-IN", {
    maximumFractionDigits: 0,
  })}`;
};

/*
 * Backend returns recovery_rate as:
 *
 * 100.00 = 100%
 * 91.52  = 91.52%
 *
 * Therefore DO NOT multiply by 100 here.
 */
const percent = (
  value?: string | number | null
) => {
  if (
    value === undefined ||
    value === null ||
    value === ""
  ) {
    return "—";
  }

  const n = Number(value);

  if (!Number.isFinite(n)) {
    return "—";
  }

  return `${n.toFixed(2)}%`;
};

const ratioPercent = (
  value?: string | number | null
) => {
  if (
    value === undefined ||
    value === null ||
    value === ""
  ) {
    return "—";
  }

  const n = Number(value);

  if (!Number.isFinite(n)) {
    return "—";
  }

  return `${(n * 100).toFixed(0)}%`;
};

const readable = (
  value?: string
) => {
  return (value || "UNKNOWN")
    .replaceAll("_", " ");
};

/* =========================================================
   API HELPER
========================================================= */

async function api(
  path: string,
  options: RequestInit = {}
) {
  const url = `${API}${path}`;

  console.log(
    "[API REQUEST]",
    url
  );

  try {
    const response = await fetch(
      url,
      {
        method:
          options.method || "GET",

        headers: {
          Accept:
            "application/json",
          ...(options.headers || {}),
        },

        body: options.body,

        cache: "no-store",
      }
    );

    console.log(
      "[API RESPONSE]",
      response.status,
      url
    );

    if (!response.ok) {
      const text =
        await response.text();

      let message =
        text ||
        `Request failed: ${response.status}`;

      try {
        const parsed =
          JSON.parse(text);

        if (parsed?.detail) {
          message =
            typeof parsed.detail ===
            "string"
              ? parsed.detail
              : JSON.stringify(
                  parsed.detail
                );
        }
      } catch {
        // Keep response text.
      }

      throw new Error(
        `${response.status}: ${message}`
      );
    }

    return await response.json();
  } catch (error) {
    console.error(
      "[API FAILED]",
      url,
      error
    );

    throw error;
  }
}

/* =========================================================
   PAGE
========================================================= */

export default function Page() {
  const [metrics, setMetrics] =
    useState<Metrics | null>(null);

  const [cases, setCases] =
    useState<Case[]>([]);

  const [selected, setSelected] =
    useState<Case | null>(null);

  const [investigation, setInvestigation] =
    useState<Investigation | null>(
      null
    );

  const [audit, setAudit] =
    useState<AuditEvent[]>([]);

  const [loading, setLoading] =
    useState(false);

  const [dashboardLoading, setDashboardLoading] =
    useState(true);

  const [message, setMessage] =
    useState("");

  const [error, setError] =
    useState("");

  /*
   * Prevent an older dashboard request from
   * overwriting newer data.
   */
  const dashboardRequest =
    useRef(0);

  /* =======================================================
     LOAD DASHBOARD
  ======================================================= */

  async function loadDashboard() {
    const requestId =
      ++dashboardRequest.current;

    try {
      setDashboardLoading(true);
      setError("");

      /*
       * Sequential requests are intentional.
       *
       * SQLite can become locked if several
       * operations hit the DB simultaneously.
       */
      const metricData =
        await api(
          "/dashboard/metrics"
        );

      if (
        requestId !==
        dashboardRequest.current
      ) {
        return;
      }

      setMetrics(metricData);

      const caseData =
        await api(
          "/leakage-cases?limit=20&offset=0"
        );

      if (
        requestId !==
        dashboardRequest.current
      ) {
        return;
      }

      setCases(
        caseData.cases || []
      );

      /*
       * Keep currently selected case
       * synchronized with fresh dashboard data.
       */
      setSelected(
        (current) => {
          if (!current) {
            return null;
          }

          const fresh =
            (caseData.cases || []).find(
              (c: Case) =>
                c.id === current.id
            );

          return fresh || current;
        }
      );
    } catch (e) {
      console.error(
        "LOAD DASHBOARD ERROR:",
        e
      );

      setError(
        e instanceof Error
          ? e.message
          : "Unable to connect to BillGuard backend."
      );
    } finally {
      if (
        requestId ===
        dashboardRequest.current
      ) {
        setDashboardLoading(false);
      }
    }
  }

  /* =======================================================
     LOAD CASE
  ======================================================= */

  async function loadCase(
    c: Case
  ) {
    setSelected(c);

    setMessage("");

    setError("");

    setInvestigation(null);

    setAudit([]);

    try {
      /*
       * Case details
       */
      const detail =
        await api(
          `/leakage-cases/${c.id}`
        );

      setSelected(
        detail.case
      );

      /*
       * Audit trail
       */
      const auditData =
        await api(
          `/leakage-cases/${c.id}/audit`
        );

      setAudit(
        auditData || []
      );

      /*
       * Investigation.
       *
       * A 404 here simply means the case
       * has not been investigated yet.
       */
      try {
        const investigationData =
          await api(
            `/leakage-cases/${c.id}/investigation`
          );

        setInvestigation(
          investigationData
        );
      } catch (investigationError) {
        console.log(
          "Investigation not available yet:",
          investigationError
        );

        setInvestigation(
          null
        );
      }
    } catch (e) {
      console.error(
        "LOAD CASE ERROR:",
        e
      );

      setError(
        e instanceof Error
          ? e.message
          : "Unable to load case."
      );
    }
  }

  /* =======================================================
     REFRESH SELECTED CASE
  ======================================================= */

  async function refreshSelectedCase(
    caseId: number
  ) {
    try {
      const updated =
        await api(
          `/leakage-cases/${caseId}`
        );

      setSelected(
        updated.case
      );

      const auditData =
        await api(
          `/leakage-cases/${caseId}/audit`
        );

      setAudit(
        auditData || []
      );

      try {
        const inv =
          await api(
            `/leakage-cases/${caseId}/investigation`
          );

        setInvestigation(inv);
      } catch {
        setInvestigation(null);
      }
    } catch (e) {
      console.error(
        "REFRESH CASE ERROR:",
        e
      );
    }
  }

  /* =======================================================
     ACTION
  ======================================================= */

  async function runAction(
    label: string,
    path: string,
    refresh = true
  ) {
    if (
      !selected ||
      loading
    ) {
      return;
    }

    const caseId =
      selected.id;

    try {
      setLoading(true);

      setError("");

      setMessage(
        `${label}...`
      );

      const result =
        await api(
          path,
          {
            method: "POST",
          }
        );

      setMessage(
        `${label} completed${
          result?.status
            ? ` — ${result.status}`
            : ""
        }.`
      );

      if (refresh) {
        await loadDashboard();

        await refreshSelectedCase(
          caseId
        );
      }
    } catch (e) {
      console.error(
        `${label} ERROR:`,
        e
      );

      setError(
        e instanceof Error
          ? e.message
          : "Action failed."
      );

      setMessage("");
    } finally {
      setLoading(false);
    }
  }

  /* =======================================================
     RUN DETECTION
  ======================================================= */

  async function seedAndAnalyze() {
    if (loading) {
      return;
    }

    try {
      setLoading(true);

      setError("");

      setMessage(
        "Seeding synthetic billing data..."
      );

      /*
       * Seed is intentionally kept because
       * this is the existing demo workflow.
       *
       * The backend seed endpoint is idempotent.
       */
      await api(
        "/seed",
        {
          method: "POST",
        }
      );

      setMessage(
        "Running deterministic revenue analysis..."
      );

      const result =
        await api(
          "/engine/analyze",
          {
            method: "POST",
          }
        );

      setMessage(
        `Analysis complete — ${
          result.cases_created || 0
        } leakage cases detected.`
      );

      await loadDashboard();

      setSelected(null);

      setInvestigation(null);

      setAudit([]);
    } catch (e) {
      console.error(
        "RUN DETECTION ERROR:",
        e
      );

      setError(
        e instanceof Error
          ? e.message
          : "Pipeline failed. Check the backend terminal."
      );

      setMessage("");
    } finally {
      setLoading(false);
    }
  }

  /* =======================================================
     INITIAL LOAD
  ======================================================= */

  useEffect(() => {
    loadDashboard();
  }, []);

  /* =======================================================
     DERIVED STATE
  ======================================================= */

  const confirmed =
    cases.filter(
      (c) =>
        c.classification ===
        "CONFIRMED_LEAKAGE"
    ).length;

  const recoveryQueue =
    cases.filter((c) => {
      return (
        c.classification ===
          "CONFIRMED_LEAKAGE" ||
        c.status ===
          "RECOVERY_PENDING" ||
        c.status === "APPROVED" ||
        c.status === "RECOVERED"
      );
    });

  const isInvestigated =
    !!investigation ||
    !!selected?.investigated_at ||
    !!selected?.classification;

  const isPendingApproval =
    selected?.status ===
    "RECOVERY_PENDING";

  const isApproved =
    selected?.status ===
    "APPROVED";

  const isRecovered =
    selected?.status ===
    "RECOVERED";

  const isRejected =
    selected?.status ===
    "REJECTED";

  const canRecommend =
    !!selected &&
    isInvestigated &&
    !isPendingApproval &&
    !isApproved &&
    !isRecovered &&
    !isRejected;

  const canApprove =
    !!selected &&
    isPendingApproval;

  const canRecover =
    !!selected &&
    isApproved;

  /*
   * Determine current pipeline stage.
   */

  let pipelineStage = 0;

  if (selected) {
    if (isRecovered) {
      pipelineStage = 5;
    } else if (isApproved) {
      pipelineStage = 4;
    } else if (isPendingApproval) {
      pipelineStage = 4;
    } else if (isInvestigated) {
      pipelineStage = 3;
    } else {
      pipelineStage = 2;
    }
  } else if (
    cases.length > 0
  ) {
    pipelineStage = 1;
  }

  /* =======================================================
     RENDER
  ======================================================= */

  return (
    <main className="min-h-screen bg-[#07111f] text-white">

      <style jsx global>{`
        * {
          box-sizing: border-box;
        }

        html {
          background: #07111f;
        }

        body {
          margin: 0;
          background: #07111f;
          color: white;
          font-family:
            Inter,
            ui-sans-serif,
            system-ui,
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            sans-serif;
        }

        button {
          font: inherit;
        }

        ::-webkit-scrollbar {
          width: 8px;
          height: 8px;
        }

        ::-webkit-scrollbar-track {
          background: #0b1728;
        }

        ::-webkit-scrollbar-thumb {
          background: #26364d;
          border-radius: 8px;
        }
      `}</style>

      <div className="flex min-h-screen">

        {/* =================================================
            SIDEBAR
        ================================================= */}

        <aside className="hidden w-64 shrink-0 border-r border-white/10 bg-[#091525] p-5 lg:block">

          {/* LOGO */}

          <div className="mb-10 flex items-center gap-3">

            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-400 text-slate-950">
              <ShieldCheck size={22} />
            </div>

            <div>

              <div className="text-lg font-bold tracking-tight">
                BillGuard
              </div>

              <div className="text-xs text-slate-400">
                Revenue Intelligence
              </div>

            </div>

          </div>

          {/* NAVIGATION */}

          <nav className="space-y-2">

            <NavItem
              icon={
                <LayoutDashboard
                  size={18}
                />
              }
              label="Dashboard"
              active
            />

            <NavItem
              icon={
                <AlertTriangle
                  size={18}
                />
              }
              label="Leakage Cases"
            />

            <NavItem
              icon={
                <BrainCircuit
                  size={18}
                />
              }
              label="AI Investigation"
            />

            <NavItem
              icon={
                <Wallet
                  size={18}
                />
              }
              label="Recovery Queue"
            />

            <NavItem
              icon={
                <FileSearch
                  size={18}
                />
              }
              label="Audit Trail"
            />

          </nav>

          {/* SYSTEM */}

          <div className="mt-10 rounded-2xl border border-cyan-400/20 bg-cyan-400/5 p-4">

            <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-cyan-300">

              <Sparkles size={14} />

              System

            </div>

            <div className="flex items-center gap-2 text-sm text-slate-300">

              <span className="h-2 w-2 rounded-full bg-emerald-400" />

              API connected

            </div>

          </div>

        </aside>

        {/* =================================================
            MAIN
        ================================================= */}

        <section className="min-w-0 flex-1">

          {/* HEADER */}

          <header className="sticky top-0 z-20 border-b border-white/10 bg-[#07111f]/90 px-5 py-4 backdrop-blur-xl md:px-8">

            <div className="mx-auto flex max-w-[1500px] items-center justify-between">

              <div>

                <div className="text-sm text-slate-400">
                  Revenue Protection
                </div>

                <h1 className="text-xl font-bold">
                  BillGuard AI Control Center
                </h1>

              </div>

              <button
                onClick={seedAndAnalyze}
                disabled={loading}
                className="flex items-center gap-2 rounded-xl bg-cyan-400 px-4 py-2.5 text-sm font-bold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-50"
              >

                <RefreshCw
                  size={16}
                  className={
                    loading
                      ? "animate-spin"
                      : ""
                  }
                />

                {loading
                  ? "Running..."
                  : "Run Detection"}

              </button>

            </div>

          </header>

          {/* CONTENT */}

          <div className="mx-auto max-w-[1500px] space-y-6 p-5 md:p-8">

            {/* =================================================
                ALERTS
            ================================================= */}

            {message && (

              <div className="rounded-xl border border-cyan-400/20 bg-cyan-400/10 px-4 py-3 text-sm text-cyan-200">

                {message}

              </div>

            )}

            {error && (

              <div className="rounded-xl border border-red-400/20 bg-red-400/10 px-4 py-3 text-sm text-red-200">

                {error}

              </div>

            )}

            {/* =================================================
                METRICS
            ================================================= */}

            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">

              <MetricCard
                icon={
                  <CircleDollarSign
                    size={20}
                  />
                }
                label="Potential Leakage"
                value={
                  metrics
                    ? money(
                        metrics.potential_leakage
                      )
                    : "Loading..."
                }
                sub={
                  metrics
                    ? `${metrics.total_cases} detected cases`
                    : "Loading dashboard data"
                }
              />

              <MetricCard
                icon={
                  <CheckCircle2
                    size={20}
                  />
                }
                label="Validated Leakage"
                value={
                  metrics
                    ? money(
                        metrics.validated_leakage
                      )
                    : "Loading..."
                }
                sub={
                  metrics
                    ? `${metrics.confirmed_cases} confirmed`
                    : "Loading dashboard data"
                }
              />

              <MetricCard
                icon={
                  <Wallet
                    size={20}
                  />
                }
                label="Recoverable Revenue"
                value={
                  metrics
                    ? money(
                        metrics.recoverable_revenue
                      )
                    : "Loading..."
                }
                sub={
                  metrics
                    ? `${metrics.human_review_cases} need human review`
                    : "Loading dashboard data"
                }
              />

              <MetricCard
                icon={
                  <ShieldCheck
                    size={20}
                  />
                }
                label="Recovered Revenue"
                value={
                  metrics
                    ? money(
                        metrics.recovered_revenue
                      )
                    : "Loading..."
                }
                sub={
                  metrics
                    ? `${percent(
                        metrics.recovery_rate
                      )} recovery rate`
                    : "Loading dashboard data"
                }
              />

            </div>

            {/* =================================================
                LIVE PIPELINE
            ================================================= */}

            <section className="rounded-2xl border border-white/10 bg-[#0b1728] p-5 md:p-6">

              <div className="mb-6 flex flex-wrap items-end justify-between gap-4">

                <div>

                  <div className="text-xs font-semibold uppercase tracking-widest text-cyan-300">
                    Autonomous Detection Pipeline
                  </div>

                  <h2 className="mt-1 text-lg font-bold">
                    Evidence → Investigation → Governance → Recovery
                  </h2>

                  <p className="mt-1 text-sm text-slate-500">

                    {selected
                      ? isRecovered
                        ? `Case #${selected.id} has completed the recovery lifecycle.`
                        : isApproved
                        ? `Case #${selected.id} is approved and ready for recovery.`
                        : isPendingApproval
                        ? `Case #${selected.id} is waiting for human approval.`
                        : isInvestigated
                        ? `Case #${selected.id} has completed investigation.`
                        : `Case #${selected.id} is under investigation.`
                      : "Select a case to view its live lifecycle."}

                  </p>

                </div>

                {selected && (

                  <StatusBadge
                    status={
                      selected.status
                    }
                    classification={
                      selected.classification
                    }
                  />

                )}

              </div>

              <div className="grid gap-3 md:grid-cols-5">

                <PipelineStep
                  number="01"
                  title="Detect"
                  text="Contract vs invoice"
                  state={
                    pipelineStage >= 1
                      ? "complete"
                      : "active"
                  }
                />

                <PipelineStep
                  number="02"
                  title="Collect"
                  text="Evidence package"
                  state={
                    pipelineStage >= 2
                      ? "complete"
                      : pipelineStage === 1
                      ? "active"
                      : "idle"
                  }
                />

                <PipelineStep
                  number="03"
                  title="Investigate"
                  text="AI + deterministic facts"
                  state={
                    pipelineStage >= 3
                      ? "complete"
                      : pipelineStage === 2
                      ? "active"
                      : "idle"
                  }
                />

                <PipelineStep
                  number="04"
                  title="Govern"
                  text={
                    isPendingApproval
                      ? "Human approval required"
                      : isApproved ||
                        isRecovered
                      ? "Approval completed"
                      : "Human approval"
                  }
                  state={
                    pipelineStage >= 4
                      ? "complete"
                      : pipelineStage === 3
                      ? "active"
                      : "idle"
                  }
                />

                <PipelineStep
                  number="05"
                  title="Recover"
                  text={
                    isRecovered
                      ? "Recovery completed"
                      : isApproved
                      ? "Ready for recovery"
                      : "Simulated adjustment"
                  }
                  state={
                    pipelineStage >= 5
                      ? "complete"
                      : pipelineStage === 4
                      ? "active"
                      : "idle"
                  }
                />

              </div>

            </section>

            {/* =================================================
                RECOVERY COMMAND CENTER
            ================================================= */}

            <section className="grid gap-6 xl:grid-cols-[1.25fr_0.75fr]">

              {/* =================================================
                  CASES
              ================================================= */}

              <section className="rounded-2xl border border-white/10 bg-[#0b1728]">

                <div className="flex items-center justify-between border-b border-white/10 p-5">

                  <div>

                    <h2 className="font-bold">
                      Leakage Cases
                    </h2>

                    <p className="mt-1 text-sm text-slate-400">
                      Live data from the FastAPI revenue engine
                    </p>

                  </div>

                  <button
                    onClick={
                      loadDashboard
                    }
                    disabled={
                      loading ||
                      dashboardLoading
                    }
                    className="rounded-lg border border-white/10 p-2 text-slate-400 hover:bg-white/5 hover:text-white disabled:opacity-50"
                    title="Refresh dashboard"
                  >

                    <RefreshCw
                      size={16}
                      className={
                        dashboardLoading
                          ? "animate-spin"
                          : ""
                      }
                    />

                  </button>

                </div>

                <div className="divide-y divide-white/10">

                  {dashboardLoading &&
                    cases.length === 0 && (

                    <div className="p-10 text-center text-slate-400">

                      <RefreshCw
                        size={28}
                        className="mx-auto mb-3 animate-spin text-cyan-400"
                      />

                      Loading leakage cases...

                    </div>

                  )}

                  {!dashboardLoading &&
                    cases.length === 0 && (

                    <div className="p-10 text-center text-slate-400">

                      No leakage cases yet.

                      <div className="mt-2 text-sm">
                        Click{" "}
                        <b>
                          Run Detection
                        </b>{" "}
                        to seed and analyze data.
                      </div>

                    </div>

                  )}

                  {cases
                    .slice(0, 12)
                    .map((c) => (

                    <button
                      key={c.id}
                      onClick={() =>
                        loadCase(c)
                      }
                      className={`w-full p-5 text-left transition hover:bg-white/[0.03] ${
                        selected?.id ===
                        c.id
                          ? "bg-cyan-400/[0.05]"
                          : ""
                      }`}
                    >

                      <div className="flex items-center justify-between gap-4">

                        <div className="min-w-0">

                          <div className="flex items-center gap-2">

                            <span className="font-bold">
                              Case #{c.id}
                            </span>

                            <StatusBadge
                              status={
                                c.status
                              }
                              classification={
                                c.classification
                              }
                            />

                          </div>

                          <div className="mt-2 text-sm text-slate-400">
                            {readable(
                              c.leakage_type
                            )}
                          </div>

                        </div>

                        <div className="text-right">

                          <div className="font-bold text-cyan-300">
                            {money(
                              c.leakage_amount
                            )}
                          </div>

                          <div className="mt-1 text-xs text-slate-500">
                            potential recovery
                          </div>

                        </div>

                        <ChevronRight
                          size={18}
                          className="shrink-0 text-slate-600"
                        />

                      </div>

                    </button>

                  ))}

                </div>

              </section>

              {/* =================================================
                  CASE DETAIL
              ================================================= */}

              <section className="rounded-2xl border border-white/10 bg-[#0b1728]">

                <div className="border-b border-white/10 p-5">

                  <div className="text-xs font-semibold uppercase tracking-widest text-cyan-300">
                    Investigation Console
                  </div>

                  <h2 className="mt-1 font-bold">

                    {selected
                      ? `Case #${selected.id}`
                      : "Select a case"}

                  </h2>

                </div>

                {!selected ? (

                  <div className="flex min-h-[400px] items-center justify-center p-8 text-center text-slate-500">

                    <div>

                      <FileSearch
                        className="mx-auto mb-3"
                        size={38}
                      />

                      <p>
                        Select a leakage case to investigate.
                      </p>

                    </div>

                  </div>

                ) : (

                  <div className="space-y-5 p-5">

                    {/* STATUS */}

                    <div className="flex items-center justify-between gap-3">

                      <StatusBadge
                        status={
                          selected.status
                        }
                        classification={
                          selected.classification
                        }
                      />

                      {isRecovered && (

                        <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-emerald-300">

                          <CheckCircle2
                            size={12}
                          />

                          Revenue recovered

                        </span>

                      )}

                    </div>

                    {/* LEAKAGE */}

                    <div className="rounded-xl border border-cyan-400/20 bg-cyan-400/5 p-4">

                      <div className="text-xs uppercase tracking-wider text-slate-400">
                        Leakage Amount
                      </div>

                      <div className="mt-1 text-3xl font-black text-cyan-300">
                        {money(
                          selected.leakage_amount
                        )}
                      </div>

                    </div>

                    {/* STATS */}

                    <div className="grid grid-cols-2 gap-3">

                      <SmallStat
                        label="Expected"
                        value={money(
                          selected.expected_amount
                        )}
                      />

                      <SmallStat
                        label="Actual"
                        value={money(
                          selected.actual_amount
                        )}
                      />

                      <SmallStat
                        label="Confidence"
                        value={ratioPercent(
                          investigation?.confidence ||
                          selected.confidence
                        )}
                      />

                      <SmallStat
                        label="Recoverability"
                        value={ratioPercent(
                          investigation?.recoverability ||
                          selected.recoverability
                        )}
                      />

                    </div>

                    {/* INVESTIGATION */}

                    {investigation ? (

                      <>

                        <div>

                          <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                            Classification
                          </div>

                          <StatusBadge
                            status={
                              selected.status
                            }
                            classification={
                              investigation.classification
                            }
                          />

                        </div>

                        <InfoBlock
                          title="Root Cause"
                          text={
                            investigation.root_cause
                          }
                        />

                        <InfoBlock
                          title="Investigation Summary"
                          text={
                            investigation.investigation_summary ||
                            "No summary available."
                          }
                        />

                        <InfoBlock
                          title="Reasoning"
                          text={
                            investigation.reasoning ||
                            "No reasoning available."
                          }
                        />

                        <div>

                          <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                            Evidence
                          </div>

                          <div className="space-y-2">

                            {(
                              investigation.evidence ||
                              []
                            ).map(
                              (
                                item,
                                i
                              ) => (

                                <div
                                  key={i}
                                  className="rounded-lg border border-white/10 bg-[#07111f] p-3"
                                >

                                  <div className="text-xs font-bold uppercase text-cyan-300">
                                    {
                                      item.source
                                    }
                                  </div>

                                  <div className="mt-1 text-sm text-slate-300">
                                    {
                                      item.fact
                                    }
                                  </div>

                                </div>

                              )
                            )}

                          </div>

                        </div>

                      </>

                    ) : (

                      <div className="rounded-xl border border-amber-400/20 bg-amber-400/5 p-4 text-sm text-amber-200">

                        This case has not been investigated yet.

                      </div>

                    )}

                    {/* ACTIONS */}

                    <div className="space-y-2 border-t border-white/10 pt-5">

                      <ActionButton
                        primary
                        disabled={
                          loading ||
                          isInvestigated
                        }
                        onClick={() =>
                          runAction(
                            "AI Investigation",
                            `/leakage-cases/${selected.id}/investigate`
                          )
                        }
                      >

                        <BrainCircuit
                          size={17}
                        />

                        {isInvestigated
                          ? "Investigation Completed"
                          : "Investigate Case"}

                      </ActionButton>

                      <ActionButton
                        disabled={
                          loading ||
                          !investigation ||
                          !canRecommend
                        }
                        onClick={() =>
                          runAction(
                            "Recovery Recommendation",
                            `/leakage-cases/${selected.id}/recommend-recovery`
                          )
                        }
                      >

                        <Wallet
                          size={17}
                        />

                        {isPendingApproval
                          ? "Recovery Awaiting Approval"
                          : isApproved ||
                            isRecovered
                          ? "Recovery Already Approved"
                          : "Recommend Recovery"}

                      </ActionButton>

                      <ActionButton
                        disabled={
                          loading ||
                          !canApprove
                        }
                        onClick={() =>
                          runAction(
                            "Human Approval",
                            `/leakage-cases/${selected.id}/approve-recovery`
                          )
                        }
                      >

                        <ShieldCheck
                          size={17}
                        />

                        {isApproved ||
                        isRecovered
                          ? "Recovery Approved"
                          : "Approve Recovery"}

                      </ActionButton>

                      <ActionButton
                        disabled={
                          loading ||
                          !canRecover
                        }
                        onClick={() =>
                          runAction(
                            "Simulated Recovery",
                            `/leakage-cases/${selected.id}/recover`
                          )
                        }
                      >

                        <CircleDollarSign
                          size={17}
                        />

                        {isRecovered
                          ? "Recovery Completed"
                          : "Execute Simulated Recovery"}

                      </ActionButton>

                    </div>

                  </div>

                )}

              </section>

            </section>

            {/* =================================================
                RECOVERY IMPACT
            ================================================= */}

            {metrics && (

              <section className="rounded-2xl border border-white/10 bg-[#0b1728] p-5 md:p-6">

                <div className="mb-5">

                  <div className="text-xs font-semibold uppercase tracking-widest text-cyan-300">
                    Recovery Impact
                  </div>

                  <h2 className="mt-1 text-lg font-bold">
                    Revenue Protected
                  </h2>

                  <p className="mt-1 text-sm text-slate-500">
                    Financial impact from validated leakage
                  </p>

                </div>

                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">

                  <ImpactStat
                    label="Leakage Detected"
                    value={money(
                      metrics.potential_leakage
                    )}
                    sub={`Across ${metrics.total_cases} cases`}
                  />

                  <ImpactStat
                    label="Validated"
                    value={money(
                      metrics.validated_leakage
                    )}
                    sub={`${metrics.confirmed_cases} confirmed cases`}
                  />

                  <ImpactStat
                    label="Recovered"
                    value={money(
                      metrics.recovered_revenue
                    )}
                    sub="Successfully recovered"
                  />

                  <ImpactStat
                    label="Recovery Rate"
                    value={percent(
                      metrics.recovery_rate
                    )}
                    sub="Validated revenue recovered"
                  />

                </div>

              </section>

            )}

            {/* =================================================
                GOVERNANCE CONTROL
            ================================================= */}

            <section className="rounded-2xl border border-white/10 bg-[#0b1728] p-5 md:p-6">

              <div className="mb-6">

                <div className="text-xs font-semibold uppercase tracking-widest text-cyan-300">
                  Governance Control
                </div>

                <h2 className="mt-1 text-lg font-bold">
                  Bounded Recovery Authority
                </h2>

                <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-400">

                  BillGuard does not give the recovery engine unrestricted authority.
                  Evidence, investigation, approval, and recovery are separate gates,
                  with every decision recorded in the audit trail.

                </p>

              </div>

              <div className="grid gap-3 md:grid-cols-4">

                <GovernanceStep
                  number="01"
                  title="Evidence Gate"
                  text="Evidence package must be available before recovery is considered."
                />

                <GovernanceStep
                  number="02"
                  title="Investigation Gate"
                  text="Deterministic facts and investigation must support the leakage classification."
                />

                <GovernanceStep
                  number="03"
                  title="Approval Gate"
                  text="Cases awaiting approval cannot execute recovery."
                />

                <GovernanceStep
                  number="04"
                  title="Recovery Gate"
                  text="Recovery execution is enabled only after the case reaches APPROVED."
                />

              </div>

              {selected && (

                <div className="mt-5 rounded-xl border border-cyan-400/20 bg-cyan-400/5 p-4">

                  <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Current Governance Decision
                  </div>

                  <div className="mt-2 flex flex-wrap items-center justify-between gap-3">

                    <div>

                      <div className="font-bold">
                        Case #{selected.id}
                      </div>

                      <div className="mt-1 text-xs text-slate-400">
                        {readable(
                          selected.classification ||
                          selected.status
                        )}
                      </div>

                    </div>

                    <div className="text-right">

                      <div className="text-xs text-slate-500">
                        Recovery authority
                      </div>

                      <div className="mt-1 font-bold text-cyan-300">
                        {isRecovered
                          ? "COMPLETED"
                          : isApproved
                          ? "APPROVED"
                          : isPendingApproval
                          ? "HUMAN REVIEW"
                          : "LOCKED"}
                      </div>

                    </div>

                  </div>

                </div>

              )}

            </section>

            {/* =================================================
                AUDIT
            ================================================= */}

            {selected && (

              <section className="rounded-2xl border border-white/10 bg-[#0b1728]">

                <div className="border-b border-white/10 p-5">

                  <div className="text-xs font-semibold uppercase tracking-widest text-cyan-300">
                    Governance Audit
                  </div>

                  <h2 className="mt-1 font-bold">
                    Case #{selected.id} lifecycle
                  </h2>

                  <p className="mt-1 text-sm text-slate-500">
                    Immutable decision trail from detection to recovery
                  </p>

                </div>

                <div className="p-5">

                  {audit.length === 0 ? (

                    <div className="text-sm text-slate-500">
                      No audit events found.
                    </div>

                  ) : (

                    <div className="space-y-3">

                      {audit.map(
                        (event) => (

                          <div
                            key={
                              event.id
                            }
                            className="flex gap-4 rounded-xl border border-white/10 bg-[#07111f] p-4"
                          >

                            <div className="mt-1">

                              {event.result ===
                                "RECOVERED" ||
                              event.result ===
                                "APPROVED" ||
                              event.result ===
                                "AUTO_APPROVED" ? (

                                <CheckCircle2
                                  size={18}
                                  className="text-emerald-400"
                                />

                              ) : event.result ===
                                "HUMAN_REVIEW" ? (

                                <AlertTriangle
                                  size={18}
                                  className="text-amber-400"
                                />

                              ) : (

                                <BrainCircuit
                                  size={18}
                                  className="text-cyan-400"
                                />

                              )}

                            </div>

                            <div className="min-w-0 flex-1">

                              <div className="flex flex-wrap items-center justify-between gap-2">

                                <span className="font-semibold">

                                  {readable(
                                    event.event_type
                                  )}

                                </span>

                                <span className="text-xs text-slate-600">

                                  {new Date(
                                    event.timestamp
                                  ).toLocaleString()}

                                </span>

                              </div>

                              <div className="mt-1 text-sm text-slate-400">
                                {
                                  event.description
                                }
                              </div>

                              <div className="mt-2 text-xs text-slate-600">

                                Actor:{" "}
                                {
                                  event.actor
                                }

                                {" · "}

                                Result:{" "}
                                {
                                  event.result
                                }

                              </div>

                            </div>

                          </div>

                        )
                      )}

                    </div>

                  )}

                </div>

              </section>

            )}

          </div>

        </section>

      </div>

    </main>
  );
}

/* =========================================================
   NAV ITEM
========================================================= */

function NavItem({
  icon,
  label,
  active,
}: {
  icon: ReactNode;
  label: string;
  active?: boolean;
}) {
  return (
    <div
      className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm ${
        active
          ? "bg-cyan-400/10 font-semibold text-cyan-300"
          : "text-slate-400"
      }`}
    >
      {icon}

      {label}
    </div>
  );
}

/* =========================================================
   METRIC CARD
========================================================= */

function MetricCard({
  icon,
  label,
  value,
  sub,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-[#0b1728] p-5">

      <div className="mb-5 flex items-center justify-between">

        <div className="text-sm text-slate-400">
          {label}
        </div>

        <div className="rounded-lg bg-cyan-400/10 p-2 text-cyan-300">
          {icon}
        </div>

      </div>

      <div
        className={`text-2xl font-black tracking-tight ${
          value === "Loading..."
            ? "animate-pulse text-slate-500"
            : ""
        }`}
      >
        {value}
      </div>

      <div className="mt-1 text-xs text-slate-500">
        {sub}
      </div>

    </div>
  );
}

/* =========================================================
   PIPELINE STEP
========================================================= */

function PipelineStep({
  number,
  title,
  text,
  state = "idle",
}: {
  number: string;
  title: string;
  text: string;
  state?: "idle" | "active" | "complete";
}) {
  const stateClass =
    state === "complete"
      ? "border-emerald-400/30 bg-emerald-400/5"
      : state === "active"
      ? "border-cyan-400/30 bg-cyan-400/5"
      : "border-white/10 bg-[#07111f]";

  return (
    <div
      className={`rounded-xl border p-4 transition ${stateClass}`}
    >

      <div className="flex items-center justify-between">

        <div className="text-xs font-bold text-cyan-400">
          {number}
        </div>

        {state ===
          "complete" && (

          <CheckCircle2
            size={15}
            className="text-emerald-400"
          />

        )}

      </div>

      <div className="mt-2 font-bold">
        {title}
      </div>

      <div className="mt-1 text-xs text-slate-500">
        {text}
      </div>

    </div>
  );
}

/* =========================================================
   SMALL STAT
========================================================= */

function SmallStat({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#07111f] p-3">

      <div className="text-xs text-slate-500">
        {label}
      </div>

      <div className="mt-1 font-bold">
        {value}
      </div>

    </div>
  );
}

/* =========================================================
   INFO BLOCK
========================================================= */

function InfoBlock({
  title,
  text,
}: {
  title: string;
  text?: string;
}) {
  return (
    <div>

      <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
        {title}
      </div>

      <div className="rounded-xl border border-white/10 bg-[#07111f] p-3 text-sm leading-6 text-slate-300">
        {text ||
          "Unavailable"}
      </div>

    </div>
  );
}

/* =========================================================
   IMPACT STAT
========================================================= */

function ImpactStat({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#07111f] p-4">

      <div className="text-xs uppercase tracking-wider text-slate-500">
        {label}
      </div>

      <div className="mt-2 text-xl font-black text-cyan-300">
        {value}
      </div>

      <div className="mt-1 text-xs text-slate-500">
        {sub}
      </div>

    </div>
  );
}

/* =========================================================
   GOVERNANCE STEP
========================================================= */

function GovernanceStep({
  number,
  title,
  text,
}: {
  number: string;
  title: string;
  text: string;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#07111f] p-4">

      <div className="flex items-center justify-between">

        <div className="text-xs font-bold text-cyan-400">
          {number}
        </div>

        <ShieldCheck
          size={15}
          className="text-cyan-400"
        />

      </div>

      <div className="mt-2 font-bold">
        {title}
      </div>

      <div className="mt-1 text-xs leading-5 text-slate-500">
        {text}
      </div>

    </div>
  );
}

/* =========================================================
   STATUS BADGE
========================================================= */

function StatusBadge({
  status,
  classification,
}: {
  status?: string;
  classification?: string;
}) {
  const text =
    classification ||
    status ||
    "UNKNOWN";

  let style =
    "border-slate-500/20 bg-slate-500/10 text-slate-400";

  if (
    text.includes(
      "CONFIRMED"
    ) ||
    text === "RECOVERED" ||
    text === "APPROVED"
  ) {
    style =
      "border-emerald-400/20 bg-emerald-400/10 text-emerald-300";
  } else if (
    text.includes("PENDING") ||
    text ===
      "POTENTIAL LEAKAGE" ||
    text === "HUMAN_REVIEW"
  ) {
    style =
      "border-amber-400/20 bg-amber-400/10 text-amber-300";
  } else if (
    text === "STOPPED" ||
    text === "REJECTED"
  ) {
    style =
      "border-red-400/20 bg-red-400/10 text-red-300";
  }

  return (
    <span
      className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-bold uppercase tracking-wide ${style}`}
    >
      {readable(text)}
    </span>
  );
}

/* =========================================================
   ACTION BUTTON
========================================================= */

function ActionButton({
  children,
  onClick,
  disabled,
  primary,
}: {
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  primary?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-bold transition ${
        primary
          ? "bg-cyan-400 text-slate-950 hover:bg-cyan-300"
          : "border border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.07]"
      } disabled:cursor-not-allowed disabled:opacity-40`}
    >
      {children}
    </button>
  );
}