import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, RefreshCw, History as HistoryIcon } from "lucide-react";
import { PageHeader, Card, StatusLine } from "../components/UI.jsx";
import { api, extractError } from "../lib/api.js";

export default function Campaigns() {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const res = await api.get("/campaigns");
      setCampaigns(res.data.campaigns || []);
    } catch (e) {
      setError(extractError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <>
      <PageHeader
        eyebrow="History"
        title="Campaigns"
        description="Every draft campaign is persisted server-side. Reopen any campaign to review or continue approving its drafts."
        actions={
          <button onClick={load} className="btn-secondary" disabled={loading} data-testid="campaigns-refresh">
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
        }
      />

      <Card eyebrow="Saved" title={`${campaigns.length} campaign(s)`} dataTestId="campaigns-list-card">
        {error ? <StatusLine tone="danger">Loading failed: {error}</StatusLine> : null}

        {!campaigns.length && !loading && !error ? (
          <div className="text-center py-12">
            <HistoryIcon size={28} className="mx-auto text-zinc-600 mb-3" />
            <p className="text-sm text-zinc-500 mb-4">No saved campaigns yet.</p>
            <Link to="/leads" className="btn-primary">Generate your first campaign <ArrowRight size={14} /></Link>
          </div>
        ) : null}

        {campaigns.length ? (
          <div className="overflow-x-auto -mx-6">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-overline text-zinc-500 border-y border-line">
                  <th className="px-6 py-3 font-medium">Campaign</th>
                  <th className="px-3 py-3 font-medium">ID</th>
                  <th className="px-3 py-3 font-medium">Mode</th>
                  <th className="px-3 py-3 font-medium text-right">Drafts</th>
                  <th className="px-3 py-3 font-medium text-right">Approved</th>
                  <th className="px-3 py-3 font-medium text-right">Sent</th>
                  <th className="px-3 py-3 font-medium text-right">Replied</th>
                  <th className="px-6 py-3 font-medium text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.map((c) => (
                  <tr
                    key={c.campaign_id}
                    className="border-b border-line hover:bg-ink-700/50 transition-colors"
                    data-testid={`campaign-row-${c.campaign_id}`}
                  >
                    <td className="px-6 py-3 text-zinc-100 font-medium">{c.name}</td>
                    <td className="px-3 py-3 text-zinc-400 font-mono text-xs">{c.campaign_id}</td>
                    <td className="px-3 py-3">
                      <span className={c.delivery_mode === "auto_send" ? "badge-warning" : "badge-muted"}>
                        {c.delivery_mode === "auto_send" ? "auto-send" : "draft"}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-right text-zinc-300">{c.draft_count}</td>
                    <td className="px-3 py-3 text-right text-emerald-400">{c.approved_count}</td>
                    <td className="px-3 py-3 text-right text-cobalt-500">{c.sent_count ?? 0}</td>
                    <td className="px-3 py-3 text-right text-emerald-400">{c.replied_count ?? 0}</td>
                    <td className="px-6 py-3 text-right">
                      <Link
                        to={`/review/${c.campaign_id}`}
                        className="btn-secondary"
                        data-testid={`campaign-open-${c.campaign_id}`}
                      >
                        Open <ArrowRight size={14} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </Card>
    </>
  );
}

function StatusBadge({ status }) {
  if (!status) return <span className="badge-muted">unknown</span>;
  if (status === "ready") return <span className="badge-success">{status}</span>;
  if (status === "approved") return <span className="badge-success">{status}</span>;
  if (status === "draft") return <span className="badge-info">{status}</span>;
  return <span className="badge-muted">{status}</span>;
}
