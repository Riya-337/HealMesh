import { createFileRoute } from "@tanstack/react-router";
import { CheckCircle2, XCircle, Search, Filter, Clock } from "lucide-react";
import { MeshLayout } from "@/components/mesh/Layout";
import { useEffect, useState } from "react";

export const Route = createFileRoute("/audit")({
  head: () => ({
    meta: [
      { title: "Audit Logs · Mesh" },
      { name: "description", content: "Historical record of every AI-driven remediation across the mesh." },
    ],
  }),
  component: Audit,
});

function Audit() {
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("http://localhost:8082/v1/incidents")
      .then(res => res.json())
      .then(data => {
        // Show only the non-pending ones in the audit log
        const nonPending = data.filter((i: any) => i.status !== "pending");
        setEntries(nonPending);
      })
      .catch(err => console.error("Audit fetch error:", err))
      .finally(() => setLoading(false));
  }, []);

  return (
    <MeshLayout title="Audit Logs" subtitle="Every AI fix, every redeploy, fully traceable">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border/60 bg-card/40 p-3 panel-shadow">
          <div className="flex flex-1 items-center gap-2 rounded-lg border border-border/60 bg-background/40 px-3 py-2 text-sm">
            <Search className="h-4 w-4 text-muted-foreground" />
            <input className="w-full bg-transparent outline-none placeholder:text-muted-foreground" placeholder="Search by service, agent, or YAML diff…" />
          </div>
          <button className="inline-flex items-center gap-2 rounded-lg border border-border/60 bg-background/40 px-3 py-2 text-sm">
            <Filter className="h-4 w-4" /> Last 24h
          </button>
        </div>

        <div className="overflow-hidden rounded-xl border border-border/60 bg-card/40 panel-shadow">
          {loading ? (
            <div className="flex h-32 items-center justify-center">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            </div>
          ) : entries.length === 0 ? (
            <div className="flex h-32 flex-col items-center justify-center gap-2 text-muted-foreground">
              <Clock className="h-8 w-8 opacity-20" />
              <p className="text-xs">No remediations have been recorded in the audit log yet.</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="border-b border-border/60 bg-background/40 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 text-left">ID</th>
                  <th className="px-4 py-3 text-left">Service</th>
                  <th className="px-4 py-3 text-left">Cluster</th>
                  <th className="px-4 py-3 text-left">Agent</th>
                  <th className="px-4 py-3 text-left">Status</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((a, i) => (
                  <tr key={a.id} className={`border-b border-border/30 transition hover:bg-primary/5 ${i % 2 ? "bg-background/20" : ""}`}>
                    <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{a.id}</td>
                    <td className="px-4 py-3 font-medium">{a.service}</td>
                    <td className="px-4 py-3 text-muted-foreground">{a.cluster}</td>
                    <td className="px-4 py-3"><span className="rounded-md bg-muted px-2 py-0.5 font-mono text-[11px]">{a.agent}</span></td>
                    <td className="px-4 py-3">
                      {a.status === "resolved" ? (
                        <span className="inline-flex items-center gap-1 rounded-md bg-success/15 px-2 py-0.5 text-[11px] font-medium text-success">
                          <CheckCircle2 className="h-3 w-3" /> resolved
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-md bg-destructive/15 px-2 py-0.5 text-[11px] font-medium text-destructive">
                          <XCircle className="h-3 w-3" /> rejected
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </MeshLayout>
  );
}
