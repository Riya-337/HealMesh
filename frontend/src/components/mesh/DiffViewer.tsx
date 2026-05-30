function diffLines(oldText: string, newText: string) {
  const a = oldText.split("\n");
  const b = newText.split("\n");
  const setA = new Set(a);
  const setB = new Set(b);
  return {
    left: a.map((line) => ({ line, kind: setB.has(line) ? "same" : "removed" as const })),
    right: b.map((line) => ({ line, kind: setA.has(line) ? "same" : "added" as const })),
  };
}

export function DiffViewer({ oldText, newText }: { oldText: string; newText: string }) {
  const { left, right } = diffLines(oldText, newText);
  return (
    <div className="grid grid-cols-2 gap-3 font-mono text-[12px]">
      <pre className="overflow-x-auto rounded-lg border border-destructive/30 bg-destructive/5 p-4">
        <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-destructive">— current</div>
        {left.map((l, i) => (
          <div key={i} className={l.kind === "removed" ? "bg-destructive/15 text-destructive" : "text-muted-foreground"}>
            <span className="mr-2 select-none opacity-50">{l.kind === "removed" ? "-" : " "}</span>{l.line || " "}
          </div>
        ))}
      </pre>
      <pre className="overflow-x-auto rounded-lg border border-success/30 bg-success/5 p-4">
        <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-success">+ agent fix</div>
        {right.map((l, i) => (
          <div key={i} className={l.kind === "added" ? "bg-success/15 text-success" : "text-muted-foreground"}>
            <span className="mr-2 select-none opacity-50">{l.kind === "added" ? "+" : " "}</span>{l.line || " "}
          </div>
        ))}
      </pre>
    </div>
  );
}
