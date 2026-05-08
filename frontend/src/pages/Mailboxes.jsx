import { useEffect, useState } from "react";
import { Mail, RefreshCw, Plug, ShieldCheck, Loader2 } from "lucide-react";
import { PageHeader, Card, StatusLine } from "../components/UI.jsx";
import { api, extractError } from "../lib/api.js";

export default function Mailboxes() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [connecting, setConnecting] = useState("");
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

  return (
    <>
      <PageHeader
        eyebrow="Integrations"
        title="Mailbox connections"
        description="Connect Gmail or Outlook to create real drafts after approval. Without OAuth, the app still creates safe local Gmail/Outlook-shaped artifacts."
        actions={
          <button onClick={load} className="btn-secondary" disabled={loading} data-testid="mailboxes-refresh">
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh status
          </button>
        }
      />

      <div className="mb-6 panel p-4 flex items-start gap-3 border-cobalt-600/30 bg-cobalt-600/5 text-sm text-zinc-300">
        <ShieldCheck size={18} className="text-cobalt-400 shrink-0 mt-0.5" />
        <div>
          Live integrations create <span className="text-zinc-100 font-medium">drafts only</span> — they
          never call Gmail send or Microsoft Graph send. Approval is required server-side before any
          mailbox draft is created.
        </div>
      </div>

      {error ? <StatusLine tone="danger">{error}</StatusLine> : null}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <ProviderCard
          provider="gmail"
          label="Gmail"
          envHint="Set GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, APP_BASE_URL"
          scope="https://www.googleapis.com/auth/gmail.compose"
          info={data?.providers?.gmail}
          onConnect={() => connect("gmail")}
          loading={connecting === "gmail"}
        />
        <ProviderCard
          provider="outlook"
          label="Outlook"
          envHint="Set MICROSOFT_OAUTH_CLIENT_ID, MICROSOFT_OAUTH_CLIENT_SECRET, APP_BASE_URL"
          scope="Microsoft Graph: Mail.ReadWrite"
          info={data?.providers?.outlook}
          onConnect={() => connect("outlook")}
          loading={connecting === "outlook"}
        />
      </div>

      <StatusLine tone={statusBar.tone} dataTestId="mailbox-status-line">
        {statusBar.text}
      </StatusLine>
    </>
  );
}

function ProviderCard({ provider, label, envHint, scope, info, onConnect, loading }) {
  const connected = info?.connected;
  const configured = info?.configured;
  return (
    <Card
      eyebrow={provider === "gmail" ? "Google" : "Microsoft"}
      title={label}
      dataTestId={`mailbox-card-${provider}`}
      action={
        <button
          className="btn-primary"
          onClick={onConnect}
          disabled={!configured || loading}
          data-testid={`mailbox-connect-${provider}`}
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Plug size={14} />}
          {connected ? "Reconnect" : "Connect"}
        </button>
      }
    >
      <div className="space-y-3 text-sm">
        <div className="flex items-center gap-3">
          <span
            className={`w-10 h-10 rounded-md flex items-center justify-center border ${
              connected
                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                : "bg-ink-700 text-zinc-400 border-line"
            }`}
          >
            <Mail size={18} />
          </span>
          <div>
            <div className="font-medium text-zinc-100">
              {connected ? "Connected" : "Not connected"}
            </div>
            <div className="text-xs text-zinc-500">
              OAuth client: {configured ? "configured" : "missing — see env hint below"}
            </div>
          </div>
        </div>

        <div className="border-t border-line pt-3 space-y-1.5 text-xs">
          <div>
            <span className="text-zinc-500">Required scope: </span>
            <span className="font-mono text-zinc-300 break-all">{scope}</span>
          </div>
          <div>
            <span className="text-zinc-500">Env: </span>
            <span className="font-mono text-zinc-300">{envHint}</span>
          </div>
        </div>
      </div>
    </Card>
  );
}
