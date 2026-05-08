import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  FileText,
  CheckCircle2,
  XCircle,
  Sparkles,
  Building2,
  Megaphone,
  Users,
  ClipboardCheck,
  Mailbox,
} from "lucide-react";
import { PageHeader, Card } from "../components/UI.jsx";
import { api, extractError } from "../lib/api.js";
import { useAppState } from "../state/AppState.jsx";

export default function Dashboard() {
  const { state } = useAppState();
  const [campaigns, setCampaigns] = useState([]);
  const [mailboxes, setMailboxes] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api.get("/campaigns").then((r) => setCampaigns(r.data.campaigns || [])).catch((e) => setError(extractError(e))),
      api.get("/mailboxes/status").then((r) => setMailboxes(r.data)).catch(() => {}),
    ]);
  }, []);

  const totals = campaigns.reduce(
    (acc, c) => {
      acc.drafts += Number(c.draft_count || 0);
      acc.approved += Number(c.approved_count || 0);
      return acc;
    },
    { drafts: 0, approved: 0 }
  );

  return (
    <>
      <PageHeader
        eyebrow="Campaign workspace"
        title="Create, review, and approve personalized outreach drafts."
        description="Define your company, target ICP, and lead source. The backend generates safe drafts; you edit and approve them before any local or live mailbox draft creation."
        actions={
          <Link to="/leads" className="btn-primary" data-testid="dashboard-cta-generate">
            <Sparkles size={16} /> Generate drafts <ArrowRight size={14} />
          </Link>
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-8">
        <Metric icon={FileText} label="Drafts created" value={totals.drafts} testid="metric-drafts" />
        <Metric icon={CheckCircle2} label="Approved" value={totals.approved} tone="success" testid="metric-approved" />
        <Metric icon={XCircle} label="Saved campaigns" value={campaigns.length} tone="info" testid="metric-campaigns" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <Card eyebrow="Quick actions" title="Pick up where you left off" className="lg:col-span-2">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <QuickLink to="/company" icon={Building2} label="Edit company profile" sub={state.company.name || "—"} testid="quick-link-company" />
            <QuickLink to="/campaign" icon={Megaphone} label="Configure campaign" sub={state.campaign.name || "—"} testid="quick-link-campaign" />
            <QuickLink to="/leads" icon={Users} label="Manage leads" sub={state.leadSource === "apollo" ? `Apollo: ${state.apolloLeads.length} leads` : "CSV source"} testid="quick-link-leads" />
            <QuickLink to="/review" icon={ClipboardCheck} label="Review drafts" sub={state.currentCampaignId || "no active campaign"} testid="quick-link-review" />
          </div>
        </Card>

        <Card eyebrow="Mailboxes" title="Connection status" dataTestId="mailbox-status-card">
          <div className="space-y-3 text-sm">
            <MailboxRow label="Gmail" provider="gmail" data={mailboxes?.providers?.gmail} />
            <MailboxRow label="Outlook" provider="outlook" data={mailboxes?.providers?.outlook} />
            <Link to="/mailboxes" className="btn-ghost mt-2">
              <Mailbox size={14} /> Manage connections <ArrowRight size={12} />
            </Link>
          </div>
        </Card>

        <Card eyebrow="History" title="Recent campaigns" className="lg:col-span-3" action={<Link to="/campaigns" className="btn-secondary">All campaigns</Link>}>
          {error ? <p className="text-sm text-red-400">{error}</p> : null}
          {!campaigns.length ? (
            <p className="text-sm text-zinc-500">No saved campaigns yet. Generate your first draft from the Leads page.</p>
          ) : (
            <ul className="divide-y divide-line">
              {campaigns.slice(0, 6).map((c) => (
                <li key={c.campaign_id} className="py-3 flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <div className="font-medium text-zinc-100 truncate">{c.name}</div>
                    <div className="text-xs text-zinc-500 font-mono truncate">
                      {c.campaign_id} · {c.status} · drafts {c.draft_count} · approved {c.approved_count}
                    </div>
                  </div>
                  <Link
                    to={`/review/${c.campaign_id}`}
                    className="btn-secondary"
                    data-testid={`open-campaign-${c.campaign_id}`}
                  >
                    Open <ArrowRight size={14} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}

function Metric({ icon: Icon, label, value, tone = "default", testid }) {
  const toneCls =
    tone === "success"
      ? "text-emerald-400"
      : tone === "info"
      ? "text-cobalt-400"
      : "text-zinc-200";
  return (
    <div className="panel p-5" data-testid={testid}>
      <div className="flex items-center justify-between">
        <span className="text-[11px] uppercase tracking-overline font-semibold text-zinc-500">
          {label}
        </span>
        <Icon size={16} className="text-zinc-600" />
      </div>
      <div className={`mt-3 font-display text-4xl font-medium ${toneCls}`}>{value}</div>
    </div>
  );
}

function QuickLink({ to, icon: Icon, label, sub, testid }) {
  return (
    <Link
      to={to}
      data-testid={testid}
      className="flex items-center justify-between gap-3 panel panel-hover p-4 group"
    >
      <div className="flex items-center gap-3 min-w-0">
        <span className="w-9 h-9 rounded-md bg-ink-700 border border-line flex items-center justify-center text-cobalt-400">
          <Icon size={16} />
        </span>
        <div className="min-w-0">
          <div className="text-sm font-medium text-zinc-100">{label}</div>
          <div className="text-xs text-zinc-500 truncate">{sub}</div>
        </div>
      </div>
      <ArrowRight size={14} className="text-zinc-600 group-hover:text-cobalt-400 transition-colors" />
    </Link>
  );
}

function MailboxRow({ label, provider, data }) {
  if (!data) {
    return (
      <div className="flex items-center justify-between">
        <span className="text-zinc-300">{label}</span>
        <span className="badge-muted">checking…</span>
      </div>
    );
  }
  return (
    <div className="flex items-center justify-between" data-testid={`mailbox-row-${provider}`}>
      <span className="text-zinc-300">{label}</span>
      <span className="flex items-center gap-1.5">
        <span className={data.connected ? "badge-success" : "badge-muted"}>
          {data.connected ? "connected" : "disconnected"}
        </span>
        <span className={data.configured ? "badge-info" : "badge-warning"}>
          {data.configured ? "configured" : "needs OAuth"}
        </span>
      </span>
    </div>
  );
}
