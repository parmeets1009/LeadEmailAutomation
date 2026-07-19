import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

// v2 adds company.details, campaign delivery_mode/score_threshold/stages — bump
// the key so a shallow merge of old persisted state can't leave those undefined.
const STORAGE_KEY = "lea-app-state-v2";

const defaultState = {
  company: {
    name: "Acme Rubber Works",
    website: "https://acme.example",
    description:
      "Rubber products manufacturer for OEMs, industrial distributors, and construction suppliers.",
    details: {
      postal_address: "",
      certifications: "",
      export_markets: "",
    },
  },
  campaign: {
    name: "UAE distributor outreach",
    target_country: "United Arab Emirates",
    target_region: "UAE",
    max_drafts: 10,
    score_threshold: 50,
    delivery_mode: "draft",
    sender_name: "Maya",
    sender_email: "maya@acme.example",
    target_titles: "Procurement Manager, Sourcing Manager, Operations Manager",
    target_industries: "Industrial, Construction, Manufacturing",
  },
  template:
    "Hi {{first_name}}, I noticed {{company_name}} works in {{lead_context}}. We manufacture {{value_prop}}. Would it make sense to send a short catalogue? Best, {{sender_name}}",
  stages: [],
  llm: {
    provider: "deterministic",
    model: "",
    enrich_websites: false,
  },
  leadCsv: `first_name,last_name,email,title,company_name,country,industry,website,context
Ahmed,Khan,ahmed@example.ae,Procurement Manager,Gulf Industrial Supplies,United Arab Emirates,Industrial,https://gulf.example,industrial maintenance supplies in Dubai
Sara,Noor,sara@example.ae,Sourcing Manager,BuildRight UAE,UAE,Construction,https://buildright.example,construction materials procurement
Bob,Smith,bob@example.com,Marketing Manager,US Retail Co,United States,Retail,https://retail.example,consumer retail`,
  apolloLeads: [],
  leadSource: "csv",
  apolloQuery: {
    locations: "United Arab Emirates",
    company_domains: "",
    company_names: "",
    keywords: "",
    max_leads: 10,
  },
  currentCampaignId: "",
};

const AppStateContext = createContext(null);

export function AppStateProvider({ children }) {
  const [state, setState] = useState(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) return { ...defaultState, ...JSON.parse(raw) };
    } catch (_) {}
    return defaultState;
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (_) {}
  }, [state]);

  const update = useCallback(
    (patch) =>
      setState((prev) =>
        typeof patch === "function" ? patch(prev) : { ...prev, ...patch }
      ),
    []
  );

  const updateSection = useCallback(
    (section, patch) =>
      setState((prev) => ({
        ...prev,
        [section]: { ...prev[section], ...patch },
      })),
    []
  );

  const reset = useCallback(() => setState(defaultState), []);

  const value = useMemo(
    () => ({ state, update, updateSection, reset }),
    [state, update, updateSection, reset]
  );

  return (
    <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>
  );
}

export function useAppState() {
  const ctx = useContext(AppStateContext);
  if (!ctx) throw new Error("useAppState must be used within AppStateProvider");
  return ctx;
}

export function listFromString(str) {
  return String(str || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export function csvToLeads(csv) {
  const lines = (csv || "").trim().split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) return [];
  const headers = splitCsvLine(lines.shift()).map((h) => h.trim());
  return lines.map((line) => {
    const values = splitCsvLine(line);
    const row = {};
    headers.forEach((h, i) => {
      row[h] = (values[i] || "").trim();
    });
    return row;
  });
}

function splitCsvLine(line) {
  const out = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    const n = line[i + 1];
    if (c === '"' && inQuotes && n === '"') {
      cur += '"';
      i += 1;
    } else if (c === '"') {
      inQuotes = !inQuotes;
    } else if (c === "," && !inQuotes) {
      out.push(cur);
      cur = "";
    } else {
      cur += c;
    }
  }
  out.push(cur);
  return out;
}

export function buildDraftPayload(state) {
  const leads =
    state.leadSource === "apollo" && state.apolloLeads.length
      ? state.apolloLeads
      : csvToLeads(state.leadCsv);
  const stages = (state.stages || [])
    .filter((s) => (s.template || "").trim())
    .map((s) => ({ offset_days: Number(s.offset_days || 3), template: s.template }));
  return {
    company: {
      name: state.company.name,
      website: state.company.website,
      description: state.company.description,
      details: cleanDetails(state.company.details),
    },
    campaign: {
      ...state.campaign,
      max_drafts: Number(state.campaign.max_drafts || 10),
      score_threshold: Number(state.campaign.score_threshold ?? 50),
      delivery_mode: state.campaign.delivery_mode || "draft",
      target_titles: listFromString(state.campaign.target_titles),
      target_industries: listFromString(state.campaign.target_industries),
      template: state.template,
      stages,
    },
    leads,
    llm_provider: state.llm.provider,
    llm_model: state.llm.model || null,
    enrich_websites: !!state.llm.enrich_websites,
  };
}

function cleanDetails(details) {
  const out = {};
  for (const [key, value] of Object.entries(details || {})) {
    if (String(value || "").trim()) out[key] = value;
  }
  return out;
}
