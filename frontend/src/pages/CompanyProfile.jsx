import { useState } from "react";
import { Eye, Save, Target, CheckCircle2 } from "lucide-react";
import { PageHeader, Card, Field, StatusLine } from "../components/UI.jsx";
import { useAppState } from "../state/AppState.jsx";
import { api, extractError } from "../lib/api.js";

export default function CompanyProfile() {
  const { state, updateSection } = useAppState();
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [icpStatus, setIcpStatus] = useState(null);

  const update = (patch) => updateSection("company", patch);
  const updateDetails = (patch) =>
    updateSection("company", { details: { ...state.company.details, ...patch } });

  function companyPayload() {
    return {
      name: state.company.name,
      website: state.company.website,
      description: state.company.description,
      details: state.company.details || {},
    };
  }

  async function previewProfile() {
    setLoading(true);
    setError("");
    setPreview(null);
    try {
      const res = await api.post("/companies/profile", companyPayload());
      setPreview(res.data);
    } catch (e) {
      setError(extractError(e));
    } finally {
      setLoading(false);
    }
  }

  async function saveIcp() {
    setIcpStatus({ tone: "info", text: "Saving ICP…" });
    try {
      await api.post("/icp", { company: companyPayload(), exclusions: [] });
      setIcpStatus({ tone: "success", text: "ICP saved server-side — it can prefill Apollo targeting." });
    } catch (e) {
      setIcpStatus({ tone: "danger", text: `Save failed: ${extractError(e)}` });
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Step 1"
        title="Company profile"
        description="Describe your business so the AI can extract your ICP, value props, and Apollo-style filter suggestions for downstream targeting."
        actions={
          <div className="flex items-center gap-2">
            <button onClick={saveIcp} className="btn-secondary" data-testid="company-save-icp">
              <Target size={15} /> Save as ICP
            </button>
            <button
              onClick={previewProfile}
              className="btn-primary"
              disabled={loading}
              data-testid="company-preview-button"
            >
              <Eye size={16} /> {loading ? "Generating…" : "Preview profile"}
            </button>
          </div>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card eyebrow="Profile" title="Company details" dataTestId="company-form-card">
          <div className="space-y-4">
            <Field label="Company name" htmlFor="company-name">
              <input
                id="company-name"
                data-testid="company-name-input"
                className="input-base"
                value={state.company.name}
                onChange={(e) => update({ name: e.target.value })}
              />
            </Field>
            <Field label="Website" htmlFor="company-website" hint="Used for optional public lead website enrichment.">
              <input
                id="company-website"
                data-testid="company-website-input"
                className="input-base"
                value={state.company.website}
                onChange={(e) => update({ website: e.target.value })}
              />
            </Field>
            <Field label="Description" htmlFor="company-description">
              <textarea
                id="company-description"
                data-testid="company-description-input"
                className="input-base min-h-[120px] font-mono text-[13px]"
                value={state.company.description}
                onChange={(e) => update({ description: e.target.value })}
              />
            </Field>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Certifications" hint="e.g. ISO 9001 — used as a value-prop signal.">
                <input
                  className="input-base"
                  data-testid="company-certifications-input"
                  value={state.company.details?.certifications || ""}
                  onChange={(e) => updateDetails({ certifications: e.target.value })}
                />
              </Field>
              <Field label="Export markets" hint="Comma-separated; seeds Apollo locations.">
                <input
                  className="input-base"
                  data-testid="company-export-markets-input"
                  value={state.company.details?.export_markets || ""}
                  onChange={(e) => updateDetails({ export_markets: e.target.value })}
                />
              </Field>
            </div>
            <Field
              label="Postal address"
              htmlFor="company-postal"
              hint="Required on every sent email (CAN-SPAM). Auto-send is blocked without it."
            >
              <input
                id="company-postal"
                data-testid="company-postal-input"
                className="input-base"
                placeholder="12 Industrial Way, Muscat, Oman"
                value={state.company.details?.postal_address || ""}
                onChange={(e) => updateDetails({ postal_address: e.target.value })}
              />
            </Field>
            <div className="flex items-center justify-between pt-2 border-t border-line">
              {state.company.details?.postal_address ? (
                <span className="badge-success"><CheckCircle2 size={11} /> send-ready</span>
              ) : (
                <span className="badge-warning">no postal address — draft mode only</span>
              )}
              <span className="text-xs text-zinc-500 inline-flex items-center gap-1.5">
                <Save size={12} /> Saved automatically to this browser
              </span>
            </div>
            {icpStatus ? <StatusLine tone={icpStatus.tone}>{icpStatus.text}</StatusLine> : null}
          </div>
        </Card>

        <Card eyebrow="Generated" title="Profile preview" dataTestId="company-preview-card">
          {error ? (
            <StatusLine tone="danger">Preview failed: {error}</StatusLine>
          ) : null}
          {!preview && !error ? (
            <p className="text-sm text-zinc-500">
              Click <span className="text-zinc-300 font-medium">Preview profile</span> to see the
              extracted ICP, value props, and Apollo filter suggestions.
            </p>
          ) : null}
          {preview ? <PreviewBlock data={preview} /> : null}
        </Card>
      </div>
    </>
  );
}

function PreviewBlock({ data }) {
  const provenance = data.generated_by === "llm" ? "AI-generated" : "deterministic (add ANTHROPIC_API_KEY for AI)";
  const apollo = data.suggested_apollo_filters || {};
  const apolloItems = [
    ...(apollo.person_titles || []),
    ...(apollo.organization_locations || []),
    ...(apollo.q_organization_keyword_tags || []),
  ];
  return (
    <div className="space-y-4 text-sm">
      <div className="text-[11px] uppercase tracking-overline font-semibold text-cobalt-500">
        {provenance}
      </div>
      <Section title="Summary" body={data.summary || "—"} />
      <ListSection title="Product categories" items={data.product_categories || []} />
      <ListSection title="Value propositions" items={data.value_propositions || []} />
      <ListSection title="Buyer personas (ICP titles)" items={data.buyer_personas || []} />
      <ListSection title="Target industries" items={data.target_industries || []} />
      <ListSection title="Suggested Apollo filters" items={apolloItems} />
    </div>
  );
}

function Section({ title, body }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-overline font-semibold text-zinc-500 mb-1">
        {title}
      </div>
      <p className="text-zinc-200 leading-relaxed">{body}</p>
    </div>
  );
}

function ListSection({ title, items }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-overline font-semibold text-zinc-500 mb-2">
        {title}
      </div>
      {items.length ? (
        <div className="flex flex-wrap gap-1.5">
          {items.map((it, i) => (
            <span key={i} className="badge-info">
              {it}
            </span>
          ))}
        </div>
      ) : (
        <p className="text-zinc-500 text-sm">—</p>
      )}
    </div>
  );
}
