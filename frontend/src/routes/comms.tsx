import { createFileRoute } from "@tanstack/react-router";
import { Hash, Bot, Send, User } from "lucide-react";
import { MeshLayout } from "@/components/mesh/Layout";
import { agentChatter as initialChatter } from "@/lib/mock-mesh";
import { useState, useRef, useEffect } from "react";
import { toast } from "sonner";

export const Route = createFileRoute("/comms")({
  head: () => ({
    meta: [
      { title: "Agent Comm Link · Mesh" },
      { name: "description", content: "Live stream of OpenClaw agent chatter across Slack, Discord and Telegram." },
    ],
  }),
  component: Comms,
});

const channels = ["#ops-mesh", "#ci-cd", "#agent-bus", "#data-pipes"];

function Comms() {
  const [activeChannel, setActiveChannel] = useState("#ops-mesh");
  const [messages, setMessages] = useState(initialChatter);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const filteredMessages = messages.filter(m => m.channel === activeChannel);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [filteredMessages, isTyping]);

  const handleSend = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim()) return;

    const userMsg = {
      agent: "Human Operator",
      channel: "#ops-mesh",
      message: input,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      isUser: true
    };

    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setIsTyping(true);

    // Simulate Agent Response
    setTimeout(() => {
      setIsTyping(false);
      const agentMsg = {
        agent: "k8s-healer-v3",
        channel: "#ops-mesh",
        message: `Instruction received. Executing diagnostic probe on the requested resource. Confidence level 0.98.`,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      };
      setMessages(prev => [...prev, agentMsg]);
      toast.success("Agent acknowledged instruction");
    }, 1500);
  };

  return (
    <MeshLayout title="Agent Comm Link" subtitle="Realtime OpenClaw chatter · Slack · Discord · Telegram">
      <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
        <aside className="space-y-1 rounded-xl border border-border/60 bg-card/40 p-3 panel-shadow">
          <div className="px-2 py-1 text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">Channels</div>
          {channels.map((c) => (
            <button 
              key={c} 
              onClick={() => setActiveChannel(c)}
              className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm transition hover:bg-primary/5 ${activeChannel === c ? "bg-primary/10 text-primary" : ""}`}
            >
              <Hash className="h-3.5 w-3.5" /> {c.replace("#", "")}
              {activeChannel === c && <span className="ml-auto h-2 w-2 rounded-full bg-success pulse-ring" />}
            </button>
          ))}
        </aside>

        <section className="flex h-[calc(100vh-10rem)] flex-col rounded-xl border border-border/60 bg-card/40 panel-shadow">
          <div className="flex items-center justify-between border-b border-border/60 px-5 py-3">
            <div className="flex items-center gap-2">
              <Hash className="h-4 w-4 text-muted-foreground" />
              <span className="font-semibold">{activeChannel.replace("#", "")}</span>
              <span className="text-xs text-muted-foreground">· 14 agents · 3 humans</span>
            </div>
            <span className="rounded-full border border-success/30 bg-success/10 px-2 py-0.5 text-[10px] uppercase tracking-wider text-success">live</span>
          </div>

          <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-5 scroll-smooth">
            {filteredMessages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center text-muted-foreground opacity-50">
                <Bot className="mb-2 h-8 w-8" />
                <p className="text-xs">No chatter detected on this channel yet...</p>
              </div>
            ) : (
              filteredMessages.map((m: any, i) => (
                <div key={i} className={`flex gap-3 ${m.isUser ? "flex-row-reverse" : ""}`}>
                  <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg shadow-sm ${
                    m.isUser 
                      ? "bg-primary text-primary-foreground" 
                      : "bg-gradient-to-br from-primary/30 to-primary-glow/30 text-primary border border-primary/20"
                  }`}>
                    {m.isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                  </div>
                  <div className={`flex-1 ${m.isUser ? "text-right" : ""}`}>
                    <div className={`flex items-baseline gap-2 ${m.isUser ? "flex-row-reverse" : ""}`}>
                      <span className={`font-mono text-xs font-semibold ${m.isUser ? "text-foreground" : "text-primary"}`}>{m.agent}</span>
                      <span className="text-[9px] uppercase tracking-wider text-muted-foreground/70">{m.channel}</span>
                      <span className="font-mono text-[9px] text-muted-foreground/60">{m.time}</span>
                    </div>
                    <div className={`mt-1 flex ${m.isUser ? "justify-end" : ""}`}>
                      <div className={`max-w-[85%] rounded-2xl px-4 py-2 text-sm shadow-sm transition-all ${
                        m.isUser 
                          ? "bg-primary text-primary-foreground rounded-tr-none hover:bg-primary/95" 
                          : "bg-background/60 text-foreground/90 border border-border/40 rounded-tl-none hover:bg-background/80"
                      }`}>
                        {m.message}
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
            {isTyping && (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary animate-bounce" />
                k8s-healer-v3 is responding…
              </div>
            )}
          </div>

          <form onSubmit={handleSend} className="border-t border-border/60 p-3">
            <div className="flex items-center gap-2 rounded-lg border border-border/60 bg-background/40 px-3 py-2 focus-within:border-primary/50 transition">
              <input 
                value={input}
                onChange={(e) => setInput(e.target.value)}
                className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground" 
                placeholder="Send instruction to agents…" 
              />
              <button 
                type="submit"
                className="rounded-md bg-gradient-to-br from-primary to-primary-glow p-2 text-primary-foreground transition hover:opacity-95"
              >
                <Send className="h-3.5 w-3.5" />
              </button>
            </div>
          </form>
        </section>
      </div>
    </MeshLayout>
  );
}
