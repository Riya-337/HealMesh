import { Link, useRouterState } from "@tanstack/react-router";
import { Activity, AlertTriangle, ScrollText, Radio, Hexagon } from "lucide-react";
import {
  Sidebar, SidebarContent, SidebarGroup, SidebarGroupContent, SidebarGroupLabel,
  SidebarMenu, SidebarMenuButton, SidebarMenuItem, SidebarHeader, SidebarFooter, useSidebar,
} from "@/components/ui/sidebar";

const items = [
  { title: "Mesh Pulse", url: "/", icon: Activity, badge: null },
  { title: "Incident Triage", url: "/triage", icon: AlertTriangle, badge: "2" },
  { title: "Audit Logs", url: "/audit", icon: ScrollText, badge: null },
  { title: "Agent Comm Link", url: "/comms", icon: Radio, badge: "live" },
];

export function AppSidebar() {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  const path = useRouterState({ select: (r) => r.location.pathname });

  return (
    <Sidebar collapsible="icon" className="border-r border-sidebar-border">
      <SidebarHeader className="px-3 py-4">
        <Link to="/" className="flex items-center gap-3">
          <div className="relative flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-primary-glow shadow-[0_0_24px_oklch(0.82_0.17_195/0.5)]">
            <Hexagon className="h-5 w-5 text-primary-foreground" strokeWidth={2.5} />
          </div>
          {!collapsed && (
            <div className="leading-tight">
              <div className="text-sm font-semibold tracking-wide">MESH</div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Control Center</div>
            </div>
          )}
        </Link>
      </SidebarHeader>

      <SidebarContent className="px-2">
        <SidebarGroup>
          <SidebarGroupLabel className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground/70">
            Operations
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {items.map((item) => {
                const active = path === item.url;
                return (
                  <SidebarMenuItem key={item.url}>
                    <SidebarMenuButton asChild isActive={active} tooltip={item.title}>
                      <Link to={item.url} className="group relative">
                        <item.icon className="h-4 w-4" />
                        {!collapsed && <span className="text-sm">{item.title}</span>}
                        {!collapsed && item.badge && (
                          <span className={`ml-auto rounded-full px-2 py-0.5 text-[10px] font-medium ${
                            item.badge === "live"
                              ? "bg-success/20 text-success"
                              : "bg-destructive/20 text-destructive"
                          }`}>
                            {item.badge}
                          </span>
                        )}
                        {active && (
                          <span className="absolute left-0 top-1/2 h-5 w-[2px] -translate-y-1/2 rounded-r bg-primary shadow-[0_0_12px_oklch(0.82_0.17_195/0.8)]" />
                        )}
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="px-3 py-3">
        {!collapsed ? (
          <div className="rounded-lg border border-sidebar-border bg-sidebar-accent/40 p-3">
            <div className="flex items-center gap-2 text-xs">
              <span className="h-2 w-2 rounded-full bg-success pulse-ring" />
              <span className="font-medium">OpenClaw online</span>
            </div>
            <div className="mt-1 text-[10px] text-muted-foreground">Ollama · llama3.1:70b · 4 agents</div>
          </div>
        ) : (
          <span className="mx-auto h-2 w-2 rounded-full bg-success pulse-ring" />
        )}
      </SidebarFooter>
    </Sidebar>
  );
}
