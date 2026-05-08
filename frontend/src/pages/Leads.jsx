import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Sparkles, Search, FileSpreadsheet, Globe, Loader2 } from "lucide-react";
import { PageHeader, Card, Field, StatusLine } from "../components/UI.jsx";
import {
  useAppState,
  csvToLeads,
  buildDraftPayload,
  listFromString,
} from "../state/AppState.jsx";
import { api, extractError } from "../lib/api.js";

export default function Leads() {
  const navigate = useNavigate();
  const { state, update, updateSection } = useAppState();
  const [generating, setGenerating] = useState(false);
  const [searching, setSearching] = useState(false);
  const [status, setStatus] = useState({ tone: "muted", text: "Ready." });

  const csvLeads = csvToLeads(state.leadCsv);
  const activeLeads =
    state.leadSource === "apollo" && state.apolloLeads.length
      ? state.apolloLeads
      : csvLeads;

  async function generate() {
    setGenerating(true);
    setStatus({ tone: "info", text: "Generating drafts…" });
    try {
      const payload = buildDraftPayload(state);
      if (!payload.leads.length) throw new Error("No leads found in current source");
      const res = await api.post("/campaigns/draft", payload);
      const data = res.data;
      update({ currentCampaignId: data.campaign_id });
      setStatus({
        tone: "success",
        text: `Created ${(data.drafts || []).length} draft(s) using ${data.llm_provider}/${data.llm_model}. Skipped ${
          Object.keys(data.skipped || {}).length
        }.`,
      });
      setTimeout(() => navigate(`/review/${data.campaign_id}`), 600);
    } catch (e) {
      setStatus({ tone: "danger", text: `Draft generation failed: ${extractError(e)}` });
    } finally {
      setGenerating(false);
    }
  }

  async function searchApollo() {
    setSearching(true);
    setStatus({ tone: "info", text: "Searching Apollo…" });
    try {
      const body = {
        titles: listFromString(state.campaign.target_titles),
        industries: listFromString(state.campaign.target_industries),
        locations: listFromString(state.apolloQuery.locations),
        company_domains: listFromString(state.apolloQuery.company_domains),
        company_names: listFromString(state.apolloQuery.company_names),
        keywords: state.apolloQuery.keywords,
        max_leads: Number(state.apolloQuery.max_leads || 10),
      };
      const res = await api.post("/leads/apollo/search", body);
      update({ apolloLeads: res.data.leads || [] });
      setStatus({
        tone: "success",
        text: `Imported ${res.data.leads?.length || 0} Apollo lead(s). They will be used in the next draft generation.`,
      });
    } catch (e) {
      update({ apolloLeads: [] });
      setStatus({ tone: "danger", text: `Apollo search failed: ${extractError(e)}. CSV fallback is still available.` });
    } finally {
      setSearching(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Step 4"
        title="Leads"
        description="Choose a lead source — paste a CSV or pull from Apollo when configured. Then generate the draft campaign."
        actions={
          <button
            onClick={generate}
            className="btn-primary"
            disabled={generating}
            data-testid="leads-generate-drafts"
          >
            {generating ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            {generating ? "Generating…" : "Generate drafts"}
          </button>
        }
      />

      <div className="flex items-center gap-2 mb-5">
        <SourceTab
          label="Paste CSV"
          icon={FileSpreadsheet}
          active={state.leadSource === "csv"}
          onClick={() => update({ leadSource: "csv" })}
          testid="lead-source-csv"
        />
        <SourceTab
          label="Search Apollo"
          icon={Globe}
          active={state.leadSource === "apollo"}
          onClick={() => update({ leadSource: "apollo" })}
          testid="lead-source-apollo"
        />
        <span className="ml-auto text-xs text-zinc-500">
          Active source has <span className="text-zinc-200 font-medium">{activeLeads.length}</span> lead(s)
        </span>
      </div>

      {state.leadSource === "csv" ? (
        <Card eyebrow="Paste CSV" title="Lead CSV" dataTestId="lead-csv-card">
          <p className="text-sm text-zinc-500 mb-3">
            Columns:{" "}
            <span className="font-mono text-zinc-300">
              first_name, last_name, email, title, company_name, country, industry, website, context
            </span>
          </p>
          <textarea
            className="input-base min-h-[260px] font-mono text-[12px] leading-relaxed"
            value={state.leadCsv}
            onChange={(e) => update({ leadCsv: e.target.value })}
            data-testid="lead-csv-input"
          />
          <div className="text-xs text-zinc-500 mt-2">
            {csvLeads.length} parsed row(s) ready for draft generation.
          </div>
        </Card>
      ) : (
        <Card eyebrow="Apollo" title="Search Apollo" dataTestId="lead-apollo-card"
          action={
            <button onClick={searchApollo} className="btn-secondary" disabled={searching} data-testid="lead-apollo-search">
              {searching ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
              {searching ? "Searching…" : "Run Apollo search"}
            </button>
          }
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Locations" hint="Comma-separated">
              <input
                className="input-base"
                value={state.apolloQuery.locations}
                onChange={(e) => updateSection("apolloQuery", { locations: e.target.value })}
              />
            </Field>
            <Field label="Max leads">
              <input
                type="number"
                min="1"
                max="100"
                className="input-base"
                value={state.apolloQuery.max_leads}
                onChange={(e) => updateSection("apolloQuery", { max_leads: e.target.value })}
              />
            </Field>
            <Field label="Company domains" hint="Optional, comma-separated">
              <input
                className="input-base"
                value={state.apolloQuery.company_domains}
                onChange={(e) => updateSection("apolloQuery", { company_domains: e.target.value })}
              />
            </Field>
            <Field label="Company names" hint="Optional, comma-separated">
              <input
                className="input-base"
                value={state.apolloQuery.company_names}
                onChange={(e) => updateSection("apolloQuery", { company_names: e.target.value })}
              />
            </Field>
            <Field label="Keywords" hint="Optional free-text" >
              <input
                className="input-base"
                value={state.apolloQuery.keywords}
                onChange={(e) => updateSection("apolloQuery", { keywords: e.target.value })}
              />
            </Field>
          </div>
          <div className="mt-5 border-t border-line pt-4">
            <div className="text-[11px] uppercase tracking-overline font-semibold text-zinc-500 mb-2">
              Apollo lead preview
            </div>
            {state.apolloLeads.length ? (
              <ul className="space-y-1.5 text-sm font-mono text-zinc-300 max-h-64 overflow-y-auto pr-2">
                {state.apolloLeads.map((l, i) => (
                  <li key={i}>
                    {l.first_name} {l.last_name} · {l.title} · {l.company_name} · {l.email}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-zinc-500">
                Apollo lead preview is empty. Run a search above, or use CSV fallback.
              </p>
            )}
          </div>
        </Card>
      )}

      <StatusLine tone={status.tone} dataTestId="leads-status">{status.text}</StatusLine>
    </>
  );
}

function SourceTab({ label, icon: Icon, active, onClick, testid }) {
  return (
    <button
      onClick={onClick}
      data-testid={testid}
      className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-md text-sm border transition-colors ${
        active
          ? "bg-cobalt-600/10 border-cobalt-600/40 text-cobalt-400"
          : "bg-transparent border-line text-zinc-400 hover:border-line2 hover:text-zinc-200"
      }`}
    >
      <Icon size={14} /> {label}
    </button>
  );
}
