import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  ArrowLeft,
  CheckCircle2,
  Save,
  Mail,
  Loader2,
  ClipboardCheck,
  AlertCircle,
  Send,
  MessageSquare,
  CheckCheck,
  FastForward,
  ChevronDown,
} from "lucide-react";
import { PageHeader, Card, StatusLine } from "../components/UI.jsx";
import { api, extractError } from "../lib/api.js";
import { useAppState } from "../state/AppState.jsx";

export default function ReviewQueue() {
  const { campaignId: paramId } = useParams();
  const { state, update } = useAppState();
  const navigate = useNavigate();

  const campaignId = paramId || state.currentCampaignId;
  const [campaign, setCampaign] = useState(null);
  const [drafts, setDrafts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [delivery, setDelivery] = useState("local");
  const [busyBulk, setBusyBulk] = useState("");
  const [showSkipped, setShowSkipped] = useState(false);
  const [statusBar, setStatusBar] = useState({ tone: "muted", text: "Ready." });

  const load = useCallback(async () => {
    if (!campaignId) return;
    setLoading(true);
    setError("");
    try {
      const res = await api.get(`/campaigns/${campaignId}`);
      setCampaign(res.data);
      setDrafts(res.data.drafts || []);
    } catch (e) {
      setError(extractError(e));
    } finally {
      setLoading(false);
    }
  }, [campaignId]);

  useEffect(() => {
    if (paramId) update({ currentCampaignId: paramId });
  }, [paramId, update]);

  useEffect(() => {
    load();
  }, [load]);

  const deliveryMode = campaign?.campaign?.delivery_mode || "draft";
  const hasStages = (campaign?.campaign?.stages || []).length > 0;
  const skipped = campaign ? Object.entries(campaign.skipped || {}) : [];
  const pendingCount = drafts.filter((d) => !d.approved).length;

  const totals = {
    drafts: drafts.length,
    approved: drafts.filter((d) => d.approved).length,
    sent: drafts.filter((d) => d.sent_at).length,
    replied: drafts.filter((d) => d.replied).length,
    skipped: skipped.length,
  };

  async function bulkApprove() {
    setBusyBulk("approve");
    setStatusBar({ tone: "info", text: "Approving all pending drafts…" });
    try {
      const pending = drafts.filter((d) => !d.approved);
      for (const d of pending) {
        await api.patch(`/campaigns/${campaignId}/drafts/${d.draft_id}/approve`, {
          approved_by: "dashboard",
          notes: "Bulk approved",
        });
      }
      setStatusBar({ tone: "success", text: `Approved ${pending.length} draft(s).` });
      await load();
    } catch (e) {
      setStatusBar({ tone: "danger", text: `Bulk approve failed: ${extractError(e)}` });
    } finally {
      setBusyBulk("");
    }
  }

  async function advanceSequence() {
    setBusyBulk("advance");
    setStatusBar({ tone: "info", text: "Generating due follow-ups…" });
    try {
      const res = await api.post(`/campaigns/${campaignId}/advance`, {});
      const created = res.data.created_count || 0;
      setStatusBar({
        tone: created ? "success" : "muted",
        text: created
          ? `Generated ${created} follow-up draft(s); they're now pending approval below.`
          : "No follow-ups are due yet (leads must be sent, unanswered, and past the offset).",
      });
      await load();
    } catch (e) {
      setStatusBar({ tone: "danger", text: `Advance failed: ${extractError(e)}` });
    } finally {
      setBusyBulk("");
    }
  }

  if (!campaignId) {
    return (
      <>
        <PageHeader eyebrow="Review queue" title="No active campaign" />
        <Card>
          <div className="text-center py-10">
            <ClipboardCheck size={28} className="mx-auto text-zinc-600 mb-3" />
            <p className="text-sm text-zinc-500 mb-4">
              Generate a campaign or open one from history to start reviewing drafts.
            </p>
            <div className="flex items-center justify-center gap-2">
              <Link to="/leads" className="btn-primary">Generate drafts</Link>
              <Link to="/campaigns" className="btn-secondary">Open from history</Link>
            </div>
          </div>
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader
        eyebrow="Review queue"
        title={campaign?.campaign?.name || campaignId}
        description={`${campaignId} · ${deliveryMode === "auto_send" ? "auto-send campaign" : "draft-only campaign"}`}
        actions={
          <div className="flex items-center gap-2">
            <button onClick={() => navigate("/campaigns")} className="btn-secondary">
              <ArrowLeft size={14} /> All campaigns
            </button>
            <select
              className="input-base !w-auto"
              value={delivery}
              onChange={(e) => setDelivery(e.target.value)}
              data-testid="review-delivery-select"
            >
              <option value="local">Local artifact</option>
              <option value="gmail_api">Live Gmail draft</option>
              <option value="outlook_graph">Live Outlook draft</option>
            </select>
          </div>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-5">
        <Stat label="Drafts" value={totals.drafts} testid="review-stat-drafts" />
        <Stat label="Approved" value={totals.approved} tone="success" testid="review-stat-approved" />
        <Stat label="Sent" value={totals.sent} tone="info" testid="review-stat-sent" />
        <Stat label="Replied" value={totals.replied} tone="success" testid="review-stat-replied" />
        <Stat label="Skipped" value={totals.skipped} tone="warning" testid="review-stat-skipped" />
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-5">
        <button
          onClick={bulkApprove}
          disabled={!pendingCount || busyBulk === "approve"}
          className="btn-secondary"
          data-testid="review-bulk-approve"
        >
          {busyBulk === "approve" ? <Loader2 size={14} className="animate-spin" /> : <CheckCheck size={14} />}
          Approve all ({pendingCount})
        </button>
        {hasStages ? (
          <button onClick={advanceSequence} disabled={busyBulk === "advance"} className="btn-secondary" data-testid="review-advance">
            {busyBulk === "advance" ? <Loader2 size={14} className="animate-spin" /> : <FastForward size={14} />}
            Generate due follow-ups
          </button>
        ) : null}
        {skipped.length ? (
          <button onClick={() => setShowSkipped((s) => !s)} className="btn-ghost ml-auto" data-testid="review-toggle-skipped">
            <ChevronDown size={14} className={showSkipped ? "rotate-180 transition-transform" : "transition-transform"} />
            {showSkipped ? "Hide" : "Show"} {skipped.length} skipped
          </button>
        ) : null}
      </div>

      {showSkipped && skipped.length ? (
        <Card eyebrow="Not drafted" title="Skipped leads" className="mb-5" dataTestId="review-skipped-card">
          <div className="overflow-x-auto -mx-6">
            <table className="w-full text-sm">
              <tbody>
                {skipped.map(([email, reason]) => (
                  <tr key={email} className="border-b border-line">
                    <td className="px-6 py-2 font-mono text-xs text-zinc-100">{email}</td>
                    <td className="px-6 py-2 text-right">
                      <span className="badge-muted">{reason}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}

      {error ? <StatusLine tone="danger">{error}</StatusLine> : null}
      <StatusLine tone={statusBar.tone} dataTestId="review-status">
        {statusBar.text}
      </StatusLine>

      {loading && !drafts.length ? (
        <div className="flex items-center justify-center py-12 text-zinc-500 gap-2">
          <Loader2 className="animate-spin" size={16} /> Loading drafts…
        </div>
      ) : null}

      {!loading && !drafts.length && !error ? (
        <Card>
          <p className="text-sm text-zinc-500">
            No drafts available. The campaign may have skipped all leads on compliance or scoring rules.
          </p>
        </Card>
      ) : null}

      <div className="space-y-5 mt-6">
        {drafts.map((d) => (
          <DraftCard
            key={d.draft_id}
            draft={d}
            campaignId={campaignId}
            delivery={delivery}
            deliveryMode={deliveryMode}
            onChange={(updater) =>
              setDrafts((prev) => prev.map((x) => (x.draft_id === d.draft_id ? updater(x) : x)))
            }
            onReload={load}
            setStatusBar={setStatusBar}
          />
        ))}
      </div>
    </>
  );
}

function Stat({ label, value, tone = "default", testid }) {
  const cls =
    tone === "success"
      ? "text-emerald-400"
      : tone === "info"
      ? "text-cobalt-500"
      : tone === "warning"
      ? "text-amber-400"
      : "text-zinc-100";
  return (
    <div className="panel p-4" data-testid={testid}>
      <div className="text-[11px] uppercase tracking-overline font-semibold text-zinc-500 mb-1">
        {label}
      </div>
      <div className={`font-display text-3xl font-medium ${cls}`}>{value}</div>
    </div>
  );
}

function DraftCard({ draft, campaignId, delivery, deliveryMode, onChange, onReload, setStatusBar }) {
  const [subject, setSubject] = useState(draft.subject);
  const [body, setBody] = useState(draft.body);
  const [busy, setBusy] = useState("");

  useEffect(() => {
    setSubject(draft.subject);
    setBody(draft.body);
  }, [draft.subject, draft.body]);

  const status = draft.review_status || (draft.approved ? "approved" : "pending");
  const dirty = subject !== draft.subject || body !== draft.body;

  async function approve() {
    setBusy("approve");
    setStatusBar({ tone: "info", text: `Approving ${draft.draft_id}…` });
    try {
      await api.patch(`/campaigns/${campaignId}/drafts/${draft.draft_id}/approve`, {
        approved_by: "dashboard",
        notes: "Approved in dashboard",
      });
      setStatusBar({ tone: "success", text: `Draft ${draft.draft_id} approved.` });
      await onReload();
    } catch (e) {
      setStatusBar({ tone: "danger", text: `Approve failed: ${extractError(e)}` });
    } finally {
      setBusy("");
    }
  }

  async function saveEdits() {
    setBusy("edit");
    setStatusBar({ tone: "info", text: `Saving edits to ${draft.draft_id}…` });
    try {
      await api.patch(`/campaigns/${campaignId}/drafts/${draft.draft_id}/edit`, {
        subject,
        body,
        edited_by: "dashboard",
      });
      setStatusBar({ tone: "success", text: `Edits saved; re-approval required.` });
      await onReload();
    } catch (e) {
      setStatusBar({ tone: "danger", text: `Save edits failed: ${extractError(e)}` });
    } finally {
      setBusy("");
    }
  }

  async function createMailbox(provider) {
    if (!draft.approved) {
      setStatusBar({ tone: "warning", text: `Approve draft ${draft.draft_id} before creating a mailbox draft.` });
      return;
    }
    setBusy(`mailbox-${provider}`);
    const useDelivery =
      (delivery === "gmail_api" && provider !== "gmail") || (delivery === "outlook_graph" && provider !== "outlook")
        ? "local"
        : delivery;
    setStatusBar({ tone: "info", text: `Creating ${provider} mailbox draft (${useDelivery})…` });
    try {
      const res = await api.post(`/campaigns/${campaignId}/drafts/${draft.draft_id}/mailbox-drafts`, { provider, delivery: useDelivery });
      setStatusBar({ tone: "success", text: `${provider} ${useDelivery} draft created: ${res.data?.draft_id || res.data?.id || "ok"}` });
    } catch (e) {
      setStatusBar({ tone: "danger", text: `${provider} draft failed: ${extractError(e)}` });
    } finally {
      setBusy("");
    }
  }

  async function sendLive(provider) {
    setBusy(`send-${provider}`);
    setStatusBar({ tone: "info", text: `Sending ${draft.draft_id} via ${provider}…` });
    try {
      await api.post(`/campaigns/${campaignId}/drafts/${draft.draft_id}/send`, { provider });
      setStatusBar({ tone: "success", text: `Sent via ${provider}. Recorded in the send log and contacted store.` });
      await onReload();
    } catch (e) {
      setStatusBar({ tone: "danger", text: `Send blocked: ${extractError(e)}` });
    } finally {
      setBusy("");
    }
  }

  async function markSent() {
    setBusy("mark-sent");
    setStatusBar({ tone: "info", text: "Marking sent…" });
    try {
      await api.patch(`/campaigns/${campaignId}/drafts/${draft.draft_id}/mark-sent`);
      setStatusBar({ tone: "success", text: "Marked as sent — follow-ups can now advance for this lead." });
      await onReload();
    } catch (e) {
      setStatusBar({ tone: "danger", text: `Mark-sent failed: ${extractError(e)}` });
    } finally {
      setBusy("");
    }
  }

  return (
    <article className="panel scroll-fade-in" id={draft.draft_id} data-testid={`draft-card-${draft.draft_id}`}>
      <header className="px-6 py-4 border-b border-line flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <span className="text-[11px] uppercase tracking-overline font-semibold text-zinc-500 font-mono">{draft.draft_id}</span>
            <StatusPill status={status} />
            {draft.stage > 0 ? <span className="badge-info">follow-up {draft.stage}</span> : null}
            {draft.generated_by === "llm" ? <span className="badge-info" title="Written by the AI model">AI</span> : null}
            {draft.generated_by === "fallback" ? (
              <span className="badge-warning" title={draft.llm_error || "Deterministic template output (no LLM used)"}>template</span>
            ) : null}
            {draft.approved ? <span className="badge-success"><CheckCircle2 size={11} /> approved</span> : null}
            {draft.sent_at ? <span className="badge-info"><Send size={11} /> sent</span> : null}
            {draft.replied ? <span className="badge-success"><MessageSquare size={11} /> replied</span> : null}
            {dirty ? <span className="badge-warning">unsaved edits</span> : null}
          </div>
          <h3 className="font-display text-lg font-medium text-zinc-100 truncate">{draft.subject}</h3>
          <div className="mt-1 text-xs text-zinc-500 font-mono">
            To: {draft.lead.first_name} {draft.lead.last_name} &lt;{draft.lead.email}&gt; · {draft.lead.company_name} · score {draft.lead_score?.score ?? "—"}
          </div>
          {draft.reply_summary ? (
            <div className="mt-1.5 text-xs text-emerald-400">Reply: {draft.reply_summary}</div>
          ) : null}
        </div>
      </header>

      <div className="p-6 space-y-4">
        <div>
          <label className="label-base">Subject</label>
          <input
            className="input-base"
            value={subject}
            onChange={(e) => {
              setSubject(e.target.value);
              onChange((d) => ({ ...d, subject: e.target.value }));
            }}
            data-testid={`draft-subject-${draft.draft_id}`}
          />
        </div>
        <div>
          <label className="label-base">Body</label>
          <textarea
            className="input-base min-h-[180px] font-mono text-[13px] leading-relaxed"
            value={body}
            onChange={(e) => {
              setBody(e.target.value);
              onChange((d) => ({ ...d, body: e.target.value }));
            }}
            data-testid={`draft-body-${draft.draft_id}`}
          />
        </div>

        {draft.render_warnings?.length ? (
          <WarnBlock title="Template warnings" items={draft.render_warnings} />
        ) : null}
        {draft.compliance?.warnings?.length ? (
          <WarnBlock title="Compliance warnings" items={draft.compliance.warnings} />
        ) : null}

        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-line">
          <button onClick={approve} disabled={busy === "approve"} className="btn-primary" data-testid={`draft-approve-${draft.draft_id}`}>
            {busy === "approve" ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
            Approve
          </button>
          <button onClick={saveEdits} disabled={!dirty || busy === "edit"} className="btn-secondary" data-testid={`draft-save-${draft.draft_id}`}>
            {busy === "edit" ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            Save edits
          </button>
          {draft.approved && !draft.sent_at ? (
            <button onClick={markSent} disabled={busy === "mark-sent"} className="btn-ghost" title="Record that you sent this from your own mail client — enables follow-ups" data-testid={`draft-mark-sent-${draft.draft_id}`}>
              {busy === "mark-sent" ? <Loader2 size={14} className="animate-spin" /> : <CheckCheck size={14} />}
              Mark sent
            </button>
          ) : null}

          <span className="ml-auto flex items-center gap-2">
            {deliveryMode === "auto_send" ? (
              <>
                <button onClick={() => sendLive("gmail")} disabled={!draft.approved || draft.sent_at || busy.startsWith("send")} className="btn-primary" data-testid={`draft-send-gmail-${draft.draft_id}`}>
                  {busy === "send-gmail" ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />} Send · Gmail
                </button>
                <button onClick={() => sendLive("outlook")} disabled={!draft.approved || draft.sent_at || busy.startsWith("send")} className="btn-primary" data-testid={`draft-send-outlook-${draft.draft_id}`}>
                  {busy === "send-outlook" ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />} Send · Outlook
                </button>
              </>
            ) : (
              <>
                <button onClick={() => createMailbox("gmail")} disabled={busy.startsWith("mailbox")} className="btn-secondary" data-testid={`draft-mailbox-gmail-${draft.draft_id}`}>
                  <Mail size={14} /> Gmail draft
                </button>
                <button onClick={() => createMailbox("outlook")} disabled={busy.startsWith("mailbox")} className="btn-secondary" data-testid={`draft-mailbox-outlook-${draft.draft_id}`}>
                  <Mail size={14} /> Outlook draft
                </button>
              </>
            )}
          </span>
        </div>
      </div>
    </article>
  );
}

function WarnBlock({ title, items }) {
  return (
    <div className="rounded-md border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-400 flex items-start gap-2">
      <AlertCircle size={14} className="mt-0.5 shrink-0" />
      <div>
        <div className="font-semibold uppercase tracking-overline text-[10px] mb-1">{title}</div>
        <ul className="list-disc list-inside space-y-0.5">
          {items.map((w, i) => (
            <li key={i}>{w}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function StatusPill({ status }) {
  if (status === "approved") return <span className="badge-success">{status}</span>;
  if (status === "edited") return <span className="badge-warning">{status}</span>;
  if (status === "pending") return <span className="badge-info">{status}</span>;
  return <span className="badge-muted">{status}</span>;
}
