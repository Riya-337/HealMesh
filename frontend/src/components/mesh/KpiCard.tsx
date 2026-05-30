import { LucideIcon, TrendingUp, TrendingDown } from "lucide-react";

interface Props {
  label: string;
  value: string;
  delta?: string;
  trend?: "up" | "down" | "flat";
  icon: LucideIcon;
  accent?: "primary" | "success" | "warning" | "destructive";
}

const accentMap = {
  primary: { glow: "from-primary/30 via-primary/10 to-transparent", text: "text-primary", ring: "oklch(0.82 0.17 195)" },
  success: { glow: "from-success/30 via-success/10 to-transparent", text: "text-success", ring: "oklch(0.78 0.18 155)" },
  warning: { glow: "from-warning/30 via-warning/10 to-transparent", text: "text-warning", ring: "oklch(0.82 0.16 80)" },
  destructive: { glow: "from-destructive/30 via-destructive/10 to-transparent", text: "text-destructive", ring: "oklch(0.65 0.22 22)" },
};

export function KpiCard({ label, value, delta, trend = "up", icon: Icon, accent = "primary" }: Props) {
  const a = accentMap[accent];
  return (
    <div className="group relative overflow-hidden rounded-2xl border border-border/60 bg-card/60 p-5 backdrop-blur-sm transition-all duration-300 hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-[0_18px_50px_-20px_oklch(0.82_0.17_195/0.55)]">
      <div className={`pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full bg-gradient-to-br ${a.glow} blur-2xl opacity-70 transition-opacity group-hover:opacity-100`} />
      <div className="pointer-events-none absolute inset-0 noise opacity-40" />
      <div className="pointer-events-none absolute inset-x-5 top-0 h-px bg-gradient-to-r from-transparent via-primary/60 to-transparent" />
      <div className="relative flex items-start justify-between">
        <div>
          <div className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">{label}</div>
          <div className={`mt-3 font-display text-4xl font-semibold tracking-tight ${a.text}`} style={{ textShadow: `0 0 28px ${a.ring}55` }}>{value}</div>
          {delta && (
            <div className={`mt-2 inline-flex items-center gap-1 rounded-full border border-border/40 bg-background/40 px-2 py-0.5 text-[11px] ${trend === "down" ? "text-destructive" : "text-success"}`}>
              {trend === "down" ? <TrendingDown className="h-3 w-3" /> : <TrendingUp className="h-3 w-3" />}
              {delta}
            </div>
          )}
        </div>
        <div className={`relative rounded-xl border border-border/60 bg-background/60 p-2.5 ${a.text}`}>
          <Icon className="h-4 w-4" />
          <span className="absolute inset-0 rounded-xl ring-1 ring-inset ring-primary/20" />
        </div>
      </div>
      <div className="relative mt-4 h-px w-full overflow-hidden bg-border/40">
        <span className="absolute inset-y-0 left-0 w-1/3 shimmer" />
      </div>
    </div>
  );
}
