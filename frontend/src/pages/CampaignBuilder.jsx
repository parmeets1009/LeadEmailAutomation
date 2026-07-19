import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, FileEdit, Plus, Trash2, Send, FileText } from "lucide-react";
import { PageHeader, Card, Field } from "../components/UI.jsx";
import { useAppState } from "../state/AppState.jsx";
import { api } from "../lib/api.js";

const PROVIDER_LABELS = {
  claude: "Claude (recommended)",
  deterministic: "Deterministic (no key needed)",
  codex: "Codex (needs OpenAI key + model)",
  gemini: "Gemini (needs Google key + model)",
};

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
  const stages = state.stages || [];
  const setC = (patch) => updateSection("campaign", patch);
  const setLLM = (patch) => updateSection("llm", patch);

  function addStage() {
    update({ stages: [...stages, { offset_days: 3, template: "" }] });
  }
  function updateStage(i, patch) {
    update({ stages: stages.map((s, idx) => (idx === i ? { ...s, ...patch } : s)) });
  }
  function removeStage(i) {
    update({ stages: stages.filter((_, idx) => idx !== i) });
  }

  return (
    <>
      <PageHeader
        eyebrow="Step 2"
        title="Campaign builder"
        description="Configure the campaign target, sender identity, delivery mode, the LLM provider, and the templates the agent will personalize."
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
              <input className="input-base" value={c.name} onChange={(e) => setC({ name: e.target.value })} data-testid="campaign-name-input" />
            </Field>
            <Field label="Max drafts" hint="1–50">
              <input type="number" min="1" max="50" className="input-base" value={c.max_drafts} onChange={(e) => setC({ max_drafts: e.target.value })} data-testid="campaign-max-drafts-input" />
            </Field>
            <Field label="Target country">
              <input className="input-base" value={c.target_country} onChange={(e) => setC({ target_country: e.target.value })} data-testid="campaign-country-input" />
            </Field>
            <Field label="Target region">
              <input className="input-base" value={c.target_region} onChange={(e) => setC({ target_region: e.target.value })} data-testid="campaign-region-input" />
            </Field>
            <Field label="Sender name">
              <input className="input-base" value={c.sender_name} onChange={(e) => setC({ sender_name: e.target.value })} data-testid="campaign-sender-name-input" />
            </Field>
            <Field label="Sender email">
              <input className="input-base" value={c.sender_email} onChange={(e) => setC({ sender_email: e.target.value })} data-testid="campaign-sender-email-input" />
            </Field>
            <Field label="Target titles" hint="Comma-separated">
              <input className="input-base" value={c.target_titles} onChange={(e) => setC({ target_titles: e.target.value })} data-testid="campaign-titles-input" />
            </Field>
            <Field label="Target industries" hint="Comma-separated">
              <input className="input-base" value={c.target_industries} onChange={(e) => setC({ target_industries: e.target.value })} data-testid="campaign-industries-input" />
            </Field>
            <Field label="Score threshold" hint="Skip leads scoring below this (0–100).">
              <input type="number" min="0" max="100" className="input-base" value={c.score_threshold} onChange={(e) => setC({ score_threshold: e.target.value })} data-testid="campaign-threshold-input" />
            </Field>
            <Field label="Delivery mode">
              <select className="input-base" value={c.delivery_mode} onChange={(e) => setC({ delivery_mode: e.target.value })} data-testid="campaign-delivery-select">
                <option value="draft">Draft only (you press send)</option>
                <option value="auto_send">Auto-send (capped, compliance-gated)</option>
              </select>
            </Field>
          </div>
          {c.delivery_mode === "auto_send" ? (
            <div className="mt-4 rounded-md border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-400 leading-relaxed">
              Auto-send emails leave the desk after approval, one at a time, under the daily cap.
              It requires a postal address (Company Profile) and a working unsubscribe link.
              Every send is still individually gated on approval.
            </div>
          ) : null}
        </Card>

        <Card eyebrow="Generation" title="LLM provider" dataTestId="campaign-llm-card">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Provider">
              <select className="input-base" value={llm.provider} onChange={(e) => setLLM({ provider: e.target.value })} data-testid="campaign-llm-provider-select">
                {(providers?.available_providers || ["deterministic", "claude", "codex", "gemini"]).map((p) => (
                  <option key={p} value={p}>
                    {PROVIDER_LABELS[p] || p}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Model" hint={providers?.default_models?.[llm.provider] ? `default: ${providers.default_models[llm.provider]}` : "optional"}>
              <input className="input-base" placeholder="optional" value={llm.model} onChange={(e) => setLLM({ model: e.target.value })} data-testid="campaign-llm-model-input" />
            </Field>
            <Field label="Website enrichment" hint="Fetch each lead's site for a specific, checkable hook before drafting.">
              <label className="flex items-center gap-2 cursor-pointer text-sm text-zinc-300">
                <input type="checkbox" checked={!!llm.enrich_websites} onChange={(e) => setLLM({ enrich_websites: e.target.checked })} className="accent-cobalt-600" data-testid="campaign-enrich-checkbox" />
                Enrich lead websites
              </label>
            </Field>
            <div className="rounded-md border border-cobalt-600/30 bg-cobalt-600/5 p-3 text-xs text-zinc-600 leading-relaxed self-end">
              {providers?.default_provider === "claude"
                ? "Claude is active on this server — drafts are AI-written."
                : "No AI key on this server yet; the deterministic provider fills the template. Drafts are labelled honestly in the review queue."}
            </div>
          </div>
        </Card>

        <Card
          eyebrow="Step 3"
          title="Email template"
          dataTestId="campaign-template-card"
          className="lg:col-span-2"
          action={
            <span className="text-xs text-zinc-500 inline-flex items-center gap-1.5">
              <FileEdit size={12} /> Use {"{{first_name}}"}, {"{{company_name}}"}, {"{{lead_context}}"}, {"{{value_prop}}"}, {"{{sender_name}}"}.
            </span>
          }
        >
          <textarea className="input-base min-h-[160px] font-mono text-[13px] leading-relaxed" value={state.template} onChange={(e) => update({ template: e.target.value })} data-testid="campaign-template-input" />
        </Card>

        <Card
          eyebrow="Step 4 · optional"
          title="Follow-up sequence"
          dataTestId="campaign-stages-card"
          className="lg:col-span-2"
          action={
            <button onClick={addStage} className="btn-secondary" disabled={stages.length >= 3} data-testid="campaign-add-stage">
              <Plus size={14} /> Add follow-up
            </button>
          }
        >
          <p className="text-sm text-zinc-500 mb-4">
            Each follow-up is generated for sent, unanswered leads after its offset elapses, and lands in
            the review queue <span className="text-zinc-300 font-medium">unapproved</span>. Replies and
            unsubscribes stop the sequence automatically. Max 3 follow-ups.
          </p>
          {stages.length === 0 ? (
            <div className="text-center py-6 border border-dashed border-line rounded-md">
              <Send size={22} className="mx-auto text-zinc-600 mb-2" />
              <p className="text-sm text-zinc-500">No follow-ups. Stage 0 is the email template above.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {stages.map((s, i) => (
                <div key={i} className="panel p-4" data-testid={`campaign-stage-${i}`}>
                  <div className="flex items-center justify-between mb-3">
                    <span className="badge-info"><FileText size={11} /> Follow-up {i + 1}</span>
                    <div className="flex items-center gap-3">
                      <label className="text-xs text-zinc-500 flex items-center gap-2">
                        Send after
                        <input type="number" min="1" max="60" className="input-base !w-20 !py-1" value={s.offset_days} onChange={(e) => updateStage(i, { offset_days: e.target.value })} data-testid={`campaign-stage-offset-${i}`} />
                        days
                      </label>
                      <button onClick={() => removeStage(i)} className="btn-ghost text-red-400" data-testid={`campaign-stage-remove-${i}`}>
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                  <textarea className="input-base min-h-[100px] font-mono text-[12px] leading-relaxed" placeholder="Hi {{first_name}}, just floating my earlier note about {{value_prop}}. {{sender_name}}" value={s.template} onChange={(e) => updateStage(i, { template: e.target.value })} data-testid={`campaign-stage-template-${i}`} />
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
