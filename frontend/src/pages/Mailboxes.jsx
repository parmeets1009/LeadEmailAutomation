import { useEffect, useState } from "react";
import { Mail, RefreshCw, Plug, ShieldCheck, Loader2, Inbox, Radar, CheckCircle2, XCircle } from "lucide-react";
import { PageHeader, Card, Field, StatusLine } from "../components/UI.jsx";
import { api, extractError } from "../lib/api.js";

export default function Mailboxes() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [connecting, setConnecting] = useState("");
  const [syncing, setSyncing] = useState("");
  const [statusBar, setStatusBar] = useState({ tone: "muted", text: "Ready." });

  async function load() {
    setLoading(true);
    setError("");
    try {
      const res = await api.get("/mailboxes/status");
      setData(res.data);
    } catch (e) {
      setError(extractError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function connect(provider) {
    setConnecting(provider);
    setStatusBar({ tone: "info", text: `Starting ${provider} OAuth…` });
    try {
      const res = await api.get(`/oauth/${provider}/start`);
      if (res.data?.auth_url) {
        window.location.href = res.data.auth_url;
      } else {
        setStatusBar({ tone: "warning", text: `OAuth started but no auth_url returned.` });
      }
    } catch (e) {
      setStatusBar({
        tone: "danger",
        text: `${provider} OAuth not ready: ${extractError(e)}. Configure ${
          provider === "gmail" ? "GOOGLE_OAUTH_*" : "MICROSOFT_OAUTH_*"
        } env vars on the backend.`,
      });
    } finally {
      setConnecting("");
    }
  }

  async function syncReplies(provider) {
    setSyncing(provider);
    setStatusBar({ tone: "info", text: `Syncing ${provider} replies…` });
    try {
      const res = await api.post(`/mailboxes/${provider}/sync-replies`, { newer_than_days: 7 });
      setStatusBar({
        tone: "success",
        text: `${provider}: ${res.data.matched_count} reply/replies matched to contacted leads, ${res.data.ignored_count} ignored. Unsubscribe intent was suppressed automatically.`,
      });
    } catch (e) {
      setStatusBar({ tone: "danger", text: `${provider} reply sync failed: ${extractError(e)}` });
    } finally {
      setSyncing("");
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Integrations"
        title="Mailbox connections"
        description="Connect Gmail or Outlook to create real drafts (or send, for auto-send campaigns) after approval, and to sync replies. Without OAuth, the app still creates safe local Gmail/Outlook-shaped artifacts."
        actions={
          <button onClick={load} className="btn-secondary" disabled={loading} data-testid="mailboxes-refresh">
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh status
          </button>
        }
      />

      <div className="mb-6 panel p-4 flex items-start gap-3 border-cobalt-600/30 bg-cobalt-600/5 text-sm text-zinc-600">
        <ShieldCheck size={18} className="text-cobalt-500 shrink-0 mt-0.5" />
        <div>
          Default campaigns create <span className="text-zinc-100 font-medium">drafts only</span>. Live
          sending is opt-in per campaign (delivery mode: auto-send), always gated on approval,
          capped per day, and blocked for suppressed or already-sent recipients.
        </div>
      </div>

      {error ? <StatusLine tone="danger">{error}</StatusLine> : null}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <ProviderCard
          provider="gmail"
          label="Gmail"
          envHint="Set GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, APP_BASE_URL"
          scope="gmail.compose + gmail.send + gmail.readonly"
          info={data?.providers?.gmail}
          onConnect={() => connect("gmail")}
          onSync={() => syncReplies("gmail")}
          loading={connecting === "gmail"}
          syncing={syncing === "gmail"}
        />
        <ProviderCard
          provider="outlook"
          label="Outlook"
          envHint="Set MICROSOFT_OAUTH_CLIENT_ID, MICROSOFT_OAUTH_CLIENT_SECRET, APP_BASE_URL"
          scope="Mail.ReadWrite + Mail.Send + Mail.Read"
          info={data?.providers?.outlook}
          onConnect={() => connect("outlook")}
          onSync={() => syncReplies("outlook")}
          loading={connecting === "outlook"}
          syncing={syncing === "outlook"}
        />
      </div>

      <DeliverabilityCard />

      <StatusLine tone={statusBar.tone} dataTestId="mailbox-status-line">
        {statusBar.text}
      </StatusLine>
    </>
  );
}

function ProviderCard({ provider, label, envHint, scope, info, onConnect, onSync, loading, syncing }) {
  const connected = info?.connected;
  const configured = info?.configured;
  return (
    <Card
      eyebrow={provider === "gmail" ? "Google" : "Microsoft"}
      title={label}
      dataTestId={`mailbox-card-${provider}`}
      action={
        <div className="flex items-center gap-2">
          <button className="btn-secondary" onClick={onSync} disabled={!connected || syncing} data-testid={`mailbox-sync-${provider}`}>
            {syncing ? <Loader2 size={14} className="animate-spin" /> : <Inbox size={14} />} Sync replies
          </button>
          <button className="btn-primary" onClick={onConnect} disabled={!configured || loading} data-testid={`mailbox-connect-${provider}`}>
            {loading ? <Loader2 size={14} className="animate-spin" /> : <Plug size={14} />}
            {connected ? "Reconnect" : "Connect"}
          </button>
        </div>
      }
    >
      <div className="space-y-3 text-sm">
        <div className="flex items-center gap-3">
          <span
            className={`w-10 h-10 rounded-md flex items-center justify-center border ${
              connected ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30" : "bg-ink-700 text-zinc-400 border-line"
            }`}
          >
            <Mail size={18} />
          </span>
          <div>
            <div className="font-medium text-zinc-100">{connected ? "Connected" : "Not connected"}</div>
            <div className="text-xs text-zinc-500">OAuth client: {configured ? "configured" : "missing — see env hint below"}</div>
          </div>
        </div>
        <div className="border-t border-line pt-3 space-y-1.5 text-xs">
          <div>
            <span className="text-zinc-500">Scopes: </span>
            <span className="font-mono text-zinc-600 break-all">{scope}</span>
          </div>
          <div>
            <span className="text-zinc-500">Env: </span>
            <span className="font-mono text-zinc-600">{envHint}</span>
          </div>
        </div>
      </div>
    </Card>
  );
}

function DeliverabilityCard() {
  const [domain, setDomain] = useState("");
  const [result, setResult] = useState(null);
  const [checking, setChecking] = useState(false);
  const [err, setErr] = useState("");

  async function check() {
    if (!domain.trim()) return;
    setChecking(true);
    setErr("");
    setResult(null);
    try {
      const res = await api.get(`/deliverability/${domain.trim()}`);
      setResult(res.data);
    } catch (e) {
      setErr(extractError(e));
    } finally {
      setChecking(false);
    }
  }

  return (
    <Card
      eyebrow="Sender reputation"
      title="Deliverability check"
      dataTestId="deliverability-card"
      className="mt-5"
      action={
        <div className="flex items-center gap-2">
          <input
            className="input-base !w-56"
            placeholder="your-sending-domain.com"
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && check()}
            data-testid="deliverability-domain-input"
          />
          <button className="btn-primary" onClick={check} disabled={checking} data-testid="deliverability-check-button">
            {checking ? <Loader2 size={14} className="animate-spin" /> : <Radar size={14} />} Check
          </button>
        </div>
      }
    >
      <p className="text-sm text-zinc-500 mb-4">
        Confirm SPF, DKIM, and DMARC are published for your sending domain before any real campaign.
        All three should be green.
      </p>
      {err ? <StatusLine tone="danger">{err}</StatusLine> : null}
      {result ? (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <RecordRow label="SPF" ok={result.spf?.found} detail={result.spf?.record} />
          <RecordRow label="DKIM" ok={result.dkim_found} detail={result.dkim_found ? "selector found" : "no common selector found"} />
          <RecordRow label="DMARC" ok={result.dmarc?.found} detail={result.dmarc?.record} />
        </div>
      ) : (
        <p className="text-sm text-zinc-500">Enter your domain and press Check.</p>
      )}
    </Card>
  );
}

function RecordRow({ label, ok, detail }) {
  return (
    <div className="panel p-3">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[11px] uppercase tracking-overline font-semibold text-zinc-500">{label}</span>
        {ok ? <CheckCircle2 size={16} className="text-emerald-400" /> : <XCircle size={16} className="text-red-400" />}
      </div>
      <div className="text-xs font-mono text-zinc-600 break-all line-clamp-2">{detail || "—"}</div>
    </div>
  );
}
