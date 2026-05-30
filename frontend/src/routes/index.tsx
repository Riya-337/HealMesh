import { useEffect, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { ShieldCheck, Bot, Zap, AlertTriangle, ArrowUpRight, CheckCircle2, Clock, Sparkles, Command, Cpu, Network, Activity } from "lucide-react";
import { MeshLayout } from "@/components/mesh/Layout";
import { KpiCard } from "@/components/mesh/KpiCard";
import { Topology } from "@/components/mesh/Topology";
import { initialIncidents, auditEntries } from "@/lib/mock-mesh";
import type { Incident } from "@/lib/mock-mesh";
import { toast } from "sonner";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Mesh Pulse · Self-Healing Automation Mesh" },
      { name: "description", content: "Real-time control center for the n8n + OpenClaw self-healing automation mesh." },
    ],
  }),
  component: MeshPulse,
});

function Sparkline({ data }: { data: number[] }) {
  const max = Math.max(...data), min = Math.min(...data);
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * 100;
    const y = 30 - ((v - min) / (max - min || 1)) * 28 - 1;
    return `${x},${y}`;
  }).join(" ");
  return (
    <svg viewBox="0 0 100 30" className="h-14 w-full" preserveAspectRatio="none">
      <defs>
        <linearGradient id="sg" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="oklch(0.82 0.17 195)" stopOpacity="0.55" />
          <stop offset="100%" stopColor="oklch(0.82 0.17 195)" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="sl" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0%" stopColor="oklch(0.82 0.17 195)" />
          <stop offset="100%" stopColor="oklch(0.74 0.24 340)" />
        </linearGradient>
      </defs>
      <polygon points={`0,30 ${points} 100,30`} fill="url(#sg)" />
      <polyline points={points} fill="none" stroke="url(#sl)" strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

const tickerItems = [
  { k: "k8s-healer-v3", v: "scaled payment-gateway → 3 replicas" },
  { k: "cicd-doctor-v2", v: "patched build #4421 (pandas 1.5.3)" },
  { k: "openclaw-router", v: "routed ERR-992 · conf 0.94" },
  { k: "data-steward", v: "auto-generated ETL patch on events.v3" },
  { k: "rollback-agent", v: "restored notifier-svc to rev 14" },
  { k: "policy-guard", v: "blocked unsafe egress on prod-eu-west" },
];

function MeshPulse() {
  const [incidents, setIncidents] = useState<Incident[]>(initialIncidents);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    // Only fetch on the client to prevent SSR 500 errors
    if (typeof window !== "undefined") {
      fetch("http://localhost:8082/v1/incidents")
        .then(res => res.json())
        .then(data => {
          if (Array.isArray(data) && data.length > 0) setIncidents(data);
        })
        .catch(err => {
          console.warn("Live backend connection failed. Using resilient mock data.", err);
        });
    }
  }, []);

  const pendingIncidents = incidents.filter(i => i.status === "pending");
  return (
    <MeshLayout title="Mesh Pulse" subtitle="Realtime health · n8n × OpenClaw × Kubernetes">
      <div className="space-y-6">
        {/* Hero */}
        <div className="relative overflow-hidden rounded-3xl border border-border/60 bg-gradient-to-br from-card/80 via-card/40 to-background p-6 md:p-8 panel-shadow">
          <div className="grid-bg pointer-events-none absolute inset-0 opacity-30" />
          <div className="pointer-events-none absolute -left-32 -top-32 h-80 w-80 rounded-full bg-primary/20 blur-3xl float-slow" />
          <div className="pointer-events-none absolute -right-32 top-10 h-80 w-80 rounded-full bg-[oklch(0.74_0.24_340/0.18)] blur-3xl float-slow" style={{ animationDelay: "2s" }} />
          <div className="pointer-events-none absolute inset-0 noise opacity-30" />
          <div className="relative flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-[11px] font-medium uppercase tracking-[0.18em] text-primary">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inset-0 rounded-full bg-primary pulse-ring" />
                  <span className="relative h-2 w-2 rounded-full bg-primary" />
                </span>
                Mesh nominal · 12 services healing autonomously
              </div>
              <h2 className="mt-4 max-w-2xl font-display text-4xl font-semibold leading-[1.05] tracking-tight md:text-5xl">
                Diagnose. Rewrite. Redeploy.{" "}
                <span className="text-aurora">Before you wake up.</span>
              </h2>
              <p className="mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground md:text-base">
                Agentic remediation across CI/CD pipelines, Helm releases, and live clusters. Approve fixes from one cockpit.
              </p>
              <div className="mt-5 flex flex-wrap items-center gap-2">
                {[
                  { i: Cpu, l: "OpenClaw router" },
                  { i: Network, l: "n8n orchestrator" },
                  { i: Sparkles, l: "Ollama · llama3.1:70b" },
                ].map(({ i: I, l }) => (
                  <span key={l} className="inline-flex items-center gap-1.5 rounded-full border border-border/60 bg-background/40 px-3 py-1 text-[11px] text-muted-foreground">
                    <I className="h-3 w-3 text-primary" /> {l}
                  </span>
                ))}
              </div>
            </div>
            <div className="flex flex-col items-stretch gap-3 sm:flex-row md:flex-col md:items-end">
              {/* Health ring */}
              <div className="relative flex items-center gap-4 rounded-2xl border border-border/60 bg-background/40 p-4 backdrop-blur-sm">
                <svg viewBox="0 0 80 80" className="h-20 w-20 -rotate-90">
                  <circle cx="40" cy="40" r="34" stroke="oklch(0.32 0.02 250 / 0.6)" strokeWidth="6" fill="none" />
                  <circle cx="40" cy="40" r="34" stroke="url(#ring)" strokeWidth="6" fill="none" strokeLinecap="round" strokeDasharray={2 * Math.PI * 34} strokeDashoffset={(1 - 0.984) * 2 * Math.PI * 34} />
                  <defs>
                    <linearGradient id="ring" x1="0" x2="1" y1="0" y2="1">
                      <stop offset="0%" stopColor="oklch(0.82 0.17 195)" />
                      <stop offset="100%" stopColor="oklch(0.74 0.24 340)" />
                    </linearGradient>
                  </defs>
                </svg>
                <div className="leading-tight">
                  <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Mesh health</div>
                  <div className="font-display text-3xl font-semibold text-aurora">98.4%</div>
                  <div className="text-[10px] text-muted-foreground">SLA · 99.9% target</div>
                </div>
              </div>
              <div className="flex gap-2">
                <Link to="/triage" className="group inline-flex flex-1 items-center justify-center gap-2 rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-2.5 text-sm font-medium text-destructive transition hover:bg-destructive/20">
                  <AlertTriangle className="h-4 w-4" /> 2 awaiting
                </Link>
                <Link to="/audit" className="group inline-flex flex-1 items-center justify-center gap-2 rounded-xl bg-gradient-to-br from-primary via-[oklch(0.78_0.2_240)] to-[oklch(0.74_0.24_340)] px-4 py-2.5 text-sm font-semibold text-primary-foreground panel-glow transition hover:opacity-95">
                  Audit <ArrowUpRight className="h-4 w-4 transition group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                </Link>
              </div>
            </div>
          </div>

          {/* Live ticker */}
          <div className="relative mt-6 overflow-hidden rounded-xl border border-border/60 bg-background/40">
            <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-16 bg-gradient-to-r from-card to-transparent" />
            <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-16 bg-gradient-to-l from-card to-transparent" />
            <div className="flex w-max gap-8 whitespace-nowrap py-2 ticker">
              {[...tickerItems, ...tickerItems].map((t, i) => (
                <span key={i} className="inline-flex items-center gap-2 text-xs">
                  <span className="h-1.5 w-1.5 rounded-full bg-success" />
                  <span className="font-mono text-primary">{t.k}</span>
                  <span className="text-muted-foreground">{t.v}</span>
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* KPIs */}
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <KpiCard label="Health Score" value="98.4%" delta="+1.2 vs 24h" icon={ShieldCheck} accent="success" />
          <KpiCard label="Auto-Heal Rate" value="91.7%" delta="+4.8% this week" icon={Zap} accent="primary" />
          <KpiCard label="Active Interventions" value={pendingIncidents.length.toString()} delta={`${pendingIncidents.length} pending approval`} trend="down" icon={AlertTriangle} accent="warning" />
          <KpiCard label="Agents Online" value="14" delta="OpenClaw · Ollama" icon={Bot} accent="primary" />
        </div>

        {/* Main grid */}
        <div className="grid gap-6 xl:grid-cols-3">
          <div className="xl:col-span-2"><Topology /></div>

          <div className="relative overflow-hidden rounded-2xl border border-border/60 bg-card/40 p-5 backdrop-blur-sm panel-shadow">
            <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-[oklch(0.74_0.24_340/0.18)] blur-3xl" />
            <div className="mb-4 flex items-center justify-between">
              <div>
                <div className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">Throughput</div>
                <h3 className="mt-1 font-display text-lg font-semibold">Remediations / hour</h3>
              </div>
              <div className="font-display text-3xl font-semibold text-aurora">42</div>
            </div>
            <Sparkline data={[12, 18, 14, 22, 28, 24, 30, 36, 32, 40, 38, 42]} />
            <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
              {[
                { l: "p50", v: "8s" },
                { l: "p95", v: "21s" },
                { l: "max", v: "1m04s" },
              ].map((s) => (
                <div key={s.l} className="rounded-lg border border-border/60 bg-background/40 py-2 transition hover:border-primary/40">
                  <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{s.l}</div>
                  <div className="mt-1 font-mono text-sm text-primary">{s.v}</div>
                </div>
              ))}
            </div>

            <div className="mt-5 rounded-xl border border-primary/20 bg-primary/5 p-3">
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-primary">
                <Command className="h-3 w-3" /> Quick actions
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                <Link to="/triage" className="rounded-lg border border-border/60 bg-background/40 px-3 py-2 transition hover:border-primary/50">Review queue</Link>
                <Link to="/comms" className="rounded-lg border border-border/60 bg-background/40 px-3 py-2 transition hover:border-primary/50">Open comms</Link>
                <Link to="/audit" className="rounded-lg border border-border/60 bg-background/40 px-3 py-2 transition hover:border-primary/50">Audit log</Link>
                <button 
                  onClick={() => {
                    const next = !paused;
                    setPaused(next);
                    toast[next ? "warning" : "success"](`Autonomous healing ${next ? "paused" : "resumed"}`, {
                      description: next ? "Manual intervention required for all incidents." : "Agents are now monitoring the mesh.",
                    });
                  }}
                  className={`rounded-lg border px-3 py-2 text-left transition ${
                    paused 
                      ? "border-destructive/50 bg-destructive/10 text-destructive" 
                      : "border-border/60 bg-background/40 hover:border-primary/50"
                  }`}
                >
                  {paused ? "Resume healing" : "Pause healing"}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom split */}
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="relative overflow-hidden rounded-2xl border border-border/60 bg-card/40 p-5 backdrop-blur-sm panel-shadow">
            <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/60 to-transparent" />
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-primary" />
                <h3 className="font-display text-lg font-semibold">Active Incidents</h3>
              </div>
              <Link to="/triage" className="text-xs text-primary hover:underline">View all →</Link>
            </div>
            <div className="space-y-3">
              {incidents.slice(0, 3).map((i) => (
                <Link key={i.id} to="/triage" className="group relative block overflow-hidden rounded-xl border border-border/60 bg-background/40 p-4 transition hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-[0_12px_30px_-15px_oklch(0.82_0.17_195/0.5)]">
                  <span className={`absolute left-0 top-0 h-full w-[3px] ${i.severity === "critical" ? "bg-destructive" : "bg-warning"}`} />
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className={`h-2 w-2 rounded-full ${i.severity === "critical" ? "bg-destructive pulse-ring" : "bg-warning"}`} />
                        <span className="font-mono text-xs text-muted-foreground">{i.id}</span>
                        <span className="font-medium">{i.service}</span>
                      </div>
                      <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">{i.diagnosis}</p>
                      <div className="mt-2 flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground">
                        <Bot className="h-3 w-3 text-primary" /> {i.agent} · {i.cluster}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-display text-lg font-semibold text-aurora">{Math.round(i.confidence * 100)}%</div>
                      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">confidence</div>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </div>

          <div className="relative overflow-hidden rounded-2xl border border-border/60 bg-card/40 p-5 backdrop-blur-sm panel-shadow">
            <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-success/60 to-transparent" />
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-success" />
                <h3 className="font-display text-lg font-semibold">Recent Healings</h3>
              </div>
              <Link to="/audit" className="text-xs text-primary hover:underline">Audit log →</Link>
            </div>
            <div className="space-y-2">
              {auditEntries.slice(0, 5).map((a) => (
                <div key={a.id} className="group flex items-center justify-between rounded-xl border border-border/40 bg-background/30 px-3 py-2.5 text-sm transition hover:border-primary/40">
                  <div className="flex items-center gap-3">
                    <span className={`flex h-7 w-7 items-center justify-center rounded-lg border ${a.status === "resolved" ? "border-success/30 bg-success/10 text-success" : "border-destructive/30 bg-destructive/10 text-destructive"}`}>
                      {a.status === "resolved" ? <CheckCircle2 className="h-3.5 w-3.5" /> : <AlertTriangle className="h-3.5 w-3.5" />}
                    </span>
                    <div>
                      <div className="font-medium">{a.service}</div>
                      <div className="text-xs text-muted-foreground">{a.action}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 rounded-md border border-border/40 bg-background/40 px-2 py-0.5 font-mono text-xs text-muted-foreground">
                    <Clock className="h-3 w-3" /> {a.duration}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </MeshLayout>
  );
}
