import { useState } from "react";
import { Eye, Save } from "lucide-react";
import { PageHeader, Card, Field, StatusLine } from "../components/UI.jsx";
import { useAppState } from "../state/AppState.jsx";
import { api, extractError } from "../lib/api.js";

export default function CompanyProfile() {
  const { state, updateSection } = useAppState();
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const update = (patch) => updateSection("company", patch);

  async function previewProfile() {
    setLoading(true);
    setError("");
    setPreview(null);
    try {
      const res = await api.post("/companies/profile", { ...state.company, details: {} });
      setPreview(res.data);
    } catch (e) {
      setError(extractError(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Step 1"
        title="Company profile"
        description="Describe your business so the AI can extract your ICP, value props, and Apollo-style filter suggestions for downstream targeting."
        actions={
          <button
            onClick={previewProfile}
            className="btn-primary"
            disabled={loading}
            data-testid="company-preview-button"
          >
            <Eye size={16} /> {loading ? "Generating…" : "Preview profile"}
          </button>
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
                className="input-base min-h-[160px] font-mono text-[13px]"
                value={state.company.description}
                onChange={(e) => update({ description: e.target.value })}
              />
            </Field>
            <div className="flex items-center justify-end pt-2 border-t border-line">
              <span className="text-xs text-zinc-500 inline-flex items-center gap-1.5">
                <Save size={12} /> Saved automatically to this browser
              </span>
            </div>
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
  return (
    <div className="space-y-4 text-sm">
      <Section title="Industry" body={data.industry || "—"} />
      <Section title="Value proposition" body={data.value_proposition || "—"} />
      <ListSection title="ICP titles" items={data.icp_titles || []} />
      <ListSection title="ICP industries" items={data.icp_industries || []} />
      <ListSection title="Apollo filters" items={data.apollo_filter_suggestions || []} />
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
