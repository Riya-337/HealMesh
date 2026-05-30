import { SidebarTrigger } from "@/components/ui/sidebar";
import { Wifi, Bell, Search, Command as CommandIcon } from "lucide-react";
import { toast } from "sonner";
import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";

export function TopBar({ title, subtitle }: { title: string; subtitle?: string }) {
  const [syncing, setSyncing] = useState(false);
  const navigate = useNavigate();

  const handleSync = () => {
    setSyncing(true);
    toast.promise(new Promise((resolve) => setTimeout(resolve, 1500)), {
      loading: "Synchronizing with Kubernetes cluster...",
      success: "Mesh synchronized successfully",
      error: "Sync failed",
    }).finally(() => setSyncing(false));
  };

  const [query, setQuery] = useState("");

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    const lowerQuery = query.toLowerCase();
    
    // 1. Audit / Log Search
    if (lowerQuery.includes("audit") || lowerQuery.includes("log")) {
      toast.success("Audit Log Found", { description: "Navigating to global audit trail..." });
      navigate({ to: "/audit" });
    } 
    // 2. Comms / Chat Search
    else if (lowerQuery.includes("comm") || lowerQuery.includes("chat") || lowerQuery.includes("talk")) {
      toast.success("Comm Link Found", { description: "Opening secure agent channel..." });
      navigate({ to: "/comms" });
    }
    // 3. Incident / Agent / Service Search
    else if (
      lowerQuery.includes("err") || lowerQuery.includes("inc") || 
      lowerQuery.includes("99") || lowerQuery.includes("gate") || 
      lowerQuery.includes("pay") || lowerQuery.includes("heal") || 
      lowerQuery.includes("doct")
    ) {
      toast.success(`Incident Found!`, { description: `Navigating to triage view for "${query}"...` });
      navigate({ to: "/triage" });
    } 
    // 4. Fallback
    else {
      toast.info(`Searching for: "${query}"`, {
        description: "No local matches found. Expanding search to cluster logs...",
      });
    }
    setQuery("");
  };

  const handleNotifications = () => {
    toast("System Notifications", {
      description: "2 critical incidents detected in prod-eu-west. 1 remediation pending approval.",
      action: {
        label: "View Triage",
        onClick: () => window.location.href = "/triage",
      },
    });
  };

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-4 border-b border-border/60 bg-background/80 px-6 backdrop-blur-xl">
      <SidebarTrigger className="text-muted-foreground hover:text-foreground" />
      <div className="flex-1">
        <h1 className="text-base font-semibold tracking-wide">{title}</h1>
        {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
      </div>

      <form 
        onSubmit={handleSearch}
        className="hidden items-center gap-2 rounded-md border border-border/60 bg-card/40 px-3 py-1.5 text-xs text-muted-foreground md:flex focus-within:border-primary/50 transition"
      >
        <Search className="h-3.5 w-3.5" />
        <input 
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="bg-transparent outline-none placeholder:text-muted-foreground w-48"
          placeholder="Search incidents, agents…" 
        />
        <kbd className="ml-2 rounded bg-muted px-1.5 py-0.5 font-mono text-[10px]">↵</kbd>
      </form>

      <button 
        onClick={handleNotifications}
        className="relative rounded-md border border-border/60 bg-card/40 p-2 text-muted-foreground transition hover:text-foreground hover:border-primary/50"
      >
        <Bell className="h-4 w-4" />
        <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-destructive animate-pulse" />
      </button>

      <button 
        onClick={handleSync}
        disabled={syncing}
        className={`flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] font-medium uppercase tracking-wider transition ${
          syncing 
            ? "border-primary/30 bg-primary/10 text-primary" 
            : "border-success/30 bg-success/10 text-success hover:bg-success/20"
        }`}
      >
        <Wifi className={`h-3.5 w-3.5 ${syncing ? "animate-spin" : ""}`} />
        {syncing ? "Syncing..." : "Live Sync"}
      </button>
    </header>
  );
}
