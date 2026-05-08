export function PageHeader({ eyebrow, title, description, actions }) {
  return (
    <div className="flex items-start justify-between gap-6 mb-8">
      <div className="min-w-0">
        {eyebrow ? (
          <div className="text-[11px] uppercase tracking-overline font-semibold text-cobalt-400 mb-2">
            {eyebrow}
          </div>
        ) : null}
        <h1 className="font-display text-3xl md:text-4xl font-medium tracking-tight text-zinc-50">
          {title}
        </h1>
        {description ? (
          <p className="mt-3 text-zinc-400 max-w-2xl text-[15px] leading-relaxed">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? <div className="flex items-center gap-2 shrink-0">{actions}</div> : null}
    </div>
  );
}

export function Card({ children, className = "", title, eyebrow, action, dataTestId }) {
  return (
    <section
      className={`panel panel-hover ${className}`}
      data-testid={dataTestId}
    >
      {(title || action || eyebrow) && (
        <header className="flex items-start justify-between gap-4 px-6 pt-5 pb-4 border-b border-line">
          <div>
            {eyebrow ? (
              <div className="text-[11px] uppercase tracking-overline font-semibold text-zinc-500 mb-1">
                {eyebrow}
              </div>
            ) : null}
            {title ? (
              <h2 className="font-display text-lg font-medium text-zinc-100">{title}</h2>
            ) : null}
          </div>
          {action}
        </header>
      )}
      <div className="p-6">{children}</div>
    </section>
  );
}

export function Field({ label, htmlFor, hint, children }) {
  return (
    <div>
      {label ? (
        <label htmlFor={htmlFor} className="label-base">
          {label}
        </label>
      ) : null}
      {children}
      {hint ? <p className="mt-1.5 text-xs text-zinc-500">{hint}</p> : null}
    </div>
  );
}

export function StatusLine({ tone = "muted", children, dataTestId }) {
  const toneCls =
    tone === "danger"
      ? "text-red-400 border-red-500/30 bg-red-500/5"
      : tone === "success"
      ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/5"
      : tone === "info"
      ? "text-cobalt-400 border-cobalt-500/30 bg-cobalt-500/5"
      : "text-zinc-400 border-line bg-ink-900";
  return (
    <div
      data-testid={dataTestId}
      className={`mt-2 border rounded-md px-4 py-3 text-sm font-mono whitespace-pre-wrap ${toneCls}`}
    >
      {children}
    </div>
  );
}
