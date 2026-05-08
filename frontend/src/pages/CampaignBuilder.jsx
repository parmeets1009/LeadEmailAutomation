import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, FileEdit } from "lucide-react";
import { PageHeader, Card, Field } from "../components/UI.jsx";
import { useAppState } from "../state/AppState.jsx";
import { api } from "../lib/api.js";

export default function CampaignBuilder() {
  const { state, updateSection, update } = useAppState();
  const [providers, setProviders] = useState(null);

  useEffect(() => {
    api
      .get("/llm/providers")
      .then((r) => setProviders(r.data))
      .catch(() => {});
  }, []);

  const c = state.campaign;
  const llm = state.llm;
  const setC = (patch) => updateSection("campaign", patch);
  const setLLM = (patch) => updateSection("llm", patch);

  return (
    <>
      <PageHeader
        eyebrow="Step 2"
        title="Campaign builder"
        description="Configure the campaign target, sender identity, the LLM provider, and the email template the agent will personalize."
        actions={
          <Link to="/leads" className="btn-primary" data-testid="campaign-go-leads">
            Continue to leads <ArrowRight size={14} />
          </Link>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card eyebrow="Targeting" title="Campaign settings" dataTestId="campaign-settings-card">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Campaign name">
              <input
                className="input-base"
                value={c.name}
                onChange={(e) => setC({ name: e.target.value })}
                data-testid="campaign-name-input"
              />
            </Field>
            <Field label="Max drafts">
              <input
                type="number"
                min="1"
                max="50"
                className="input-base"
                value={c.max_drafts}
                onChange={(e) => setC({ max_drafts: e.target.value })}
                data-testid="campaign-max-drafts-input"
              />
            </Field>
            <Field label="Target country">
              <input
                className="input-base"
                value={c.target_country}
                onChange={(e) => setC({ target_country: e.target.value })}
                data-testid="campaign-country-input"
              />
            </Field>
            <Field label="Target region">
              <input
                className="input-base"
                value={c.target_region}
                onChange={(e) => setC({ target_region: e.target.value })}
                data-testid="campaign-region-input"
              />
            </Field>
            <Field label="Sender name">
              <input
                className="input-base"
                value={c.sender_name}
                onChange={(e) => setC({ sender_name: e.target.value })}
                data-testid="campaign-sender-name-input"
              />
            </Field>
            <Field label="Sender email">
              <input
                className="input-base"
                value={c.sender_email}
                onChange={(e) => setC({ sender_email: e.target.value })}
                data-testid="campaign-sender-email-input"
              />
            </Field>
            <Field label="Target titles" hint="Comma-separated">
              <input
                className="input-base"
                value={c.target_titles}
                onChange={(e) => setC({ target_titles: e.target.value })}
                data-testid="campaign-titles-input"
              />
            </Field>
            <Field label="Target industries" hint="Comma-separated">
              <input
                className="input-base"
                value={c.target_industries}
                onChange={(e) => setC({ target_industries: e.target.value })}
                data-testid="campaign-industries-input"
              />
            </Field>
          </div>
        </Card>

        <Card eyebrow="Generation" title="LLM provider" dataTestId="campaign-llm-card">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Provider">
              <select
                className="input-base"
                value={llm.provider}
                onChange={(e) => setLLM({ provider: e.target.value })}
                data-testid="campaign-llm-provider-select"
              >
                {(providers?.available_providers || ["deterministic", "codex", "gemini"]).map(
                  (p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  )
                )}
              </select>
            </Field>
            <Field
              label="Model"
              hint={
                providers?.default_models?.[llm.provider]
                  ? `default: ${providers.default_models[llm.provider]}`
                  : "optional"
              }
            >
              <input
                className="input-base"
                placeholder="optional"
                value={llm.model}
                onChange={(e) => setLLM({ model: e.target.value })}
                data-testid="campaign-llm-model-input"
              />
            </Field>
            <Field label="Website enrichment" hint="Use Scrapling or static fetch to enrich lead websites before scoring.">
              <label className="flex items-center gap-2 cursor-pointer text-sm text-zinc-300">
                <input
                  type="checkbox"
                  checked={!!llm.enrich_websites}
                  onChange={(e) => setLLM({ enrich_websites: e.target.checked })}
                  className="accent-cobalt-600"
                  data-testid="campaign-enrich-checkbox"
                />
                Enrich lead websites
              </label>
            </Field>
            <div className="rounded-md border border-cobalt-600/30 bg-cobalt-600/5 p-3 text-xs text-zinc-300 leading-relaxed self-end">
              The deterministic provider works without any API keys and produces the
              same draft every time — great for safe MVP runs.
            </div>
          </div>
        </Card>

        <Card eyebrow="Step 3" title="Email template" dataTestId="campaign-template-card" className="lg:col-span-2"
          action={
            <span className="text-xs text-zinc-500 inline-flex items-center gap-1.5">
              <FileEdit size={12} /> Use {"{{first_name}}"}, {"{{company_name}}"}, {"{{lead_context}}"}, {"{{value_prop}}"}, {"{{sender_name}}"}.
            </span>
          }
        >
          <textarea
            className="input-base min-h-[180px] font-mono text-[13px] leading-relaxed"
            value={state.template}
            onChange={(e) => update({ template: e.target.value })}
            data-testid="campaign-template-input"
          />
        </Card>
      </div>
    </>
  );
}
