import { useEffect, useState } from "react";
import { ShieldOff, RefreshCw, Plus, Loader2, Users } from "lucide-react";
import { PageHeader, Card, Field, StatusLine } from "../components/UI.jsx";
import { api, extractError } from "../lib/api.js";

export default function Compliance() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [email, setEmail] = useState("");
  const [reason, setReason] = useState("manual");
  const [adding, setAdding] = useState(false);
  const [status, setStatus] = useState({ tone: "muted", text: "Suppressed addresses never receive a draft, send, or follow-up." });

  async function load() {
    setLoading(true);
    setError("");
    try {
      const res = await api.get("/compliance/overview");
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

  async function suppress() {
    if (!email.trim()) return;
    setAdding(true);
    setStatus({ tone: "info", text: `Suppressing ${email}…` });
    try {
      await api.post("/compliance/suppress", { email, reason: reason || "manual" });
      setStatus({ tone: "success", text: `${email.trim().toLowerCase()} suppressed permanently.` });
      setEmail("");
      await load();
    } catch (e) {
      setStatus({ tone: "danger", text: `Failed: ${extractError(e)}` });
    } finally {
      setAdding(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Compliance"
        title="Suppression & contact record"
        description="Everyone who unsubscribed, replied 'not relevant', or was manually opted out. This list is permanent and enforced in code across drafting, sending, and follow-ups."
        actions={
          <button onClick={load} className="btn-secondary" disabled={loading} data-testid="compliance-refresh">
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-6">
        <div className="panel p-5" data-testid="compliance-suppressed-metric">
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase tracking-overline font-semibold text-zinc-500">Suppressed</span>
            <ShieldOff size={15} className="text-zinc-600" />
          </div>
          <div className="mt-2 font-display text-3xl font-medium text-amber-400">
            {data ? data.suppression_count : "—"}
          </div>
        </div>
        <div className="panel p-5" data-testid="compliance-contacted-metric">
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase tracking-overline font-semibold text-zinc-500">Contacted (all campaigns)</span>
            <Users size={15} className="text-zinc-600" />
          </div>
          <div className="mt-2 font-display text-3xl font-medium text-cobalt-500">
            {data ? data.contacted_count : "—"}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <Card eyebrow="Manual opt-out" title="Suppress an address" dataTestId="compliance-add-card">
          <div className="space-y-4">
            <Field label="Email">
              <input
                className="input-base"
                placeholder="person@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                data-testid="compliance-email-input"
              />
            </Field>
            <Field label="Reason" hint="For your own audit trail.">
              <input className="input-base" value={reason} onChange={(e) => setReason(e.target.value)} data-testid="compliance-reason-input" />
            </Field>
            <button onClick={suppress} className="btn-primary w-full justify-center" disabled={adding} data-testid="compliance-suppress-button">
              {adding ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />} Add to suppression
            </button>
            <StatusLine tone={status.tone}>{status.text}</StatusLine>
          </div>
        </Card>

        <Card eyebrow="Permanent list" title="Suppressed addresses" dataTestId="compliance-list-card" className="lg:col-span-2">
          {error ? <StatusLine tone="danger">Loading failed: {error}</StatusLine> : null}
          {data && !data.suppression.length ? (
            <div className="text-center py-10">
              <ShieldOff size={26} className="mx-auto text-zinc-600 mb-3" />
              <p className="text-sm text-zinc-500">No suppressed addresses yet.</p>
            </div>
          ) : null}
          {data && data.suppression.length ? (
            <div className="overflow-x-auto -mx-6">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[11px] uppercase tracking-overline text-zinc-500 border-y border-line">
                    <th className="px-6 py-3 font-medium">Email</th>
                    <th className="px-3 py-3 font-medium">Reason</th>
                    <th className="px-6 py-3 font-medium">When</th>
                  </tr>
                </thead>
                <tbody>
                  {data.suppression.map((row) => (
                    <tr key={row.email} className="border-b border-line" data-testid={`compliance-row-${row.email}`}>
                      <td className="px-6 py-2.5 font-mono text-xs text-zinc-100">{row.email}</td>
                      <td className="px-3 py-2.5 text-zinc-400">{row.reason || "—"}</td>
                      <td className="px-6 py-2.5 text-zinc-500 font-mono text-xs">{formatTs(row.ts)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </Card>
      </div>
    </>
  );
}

function formatTs(ts) {
  if (!ts) return "—";
  try {
    return new Date(ts).toLocaleString();
  } catch (_) {
    return ts;
  }
}
