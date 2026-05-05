from __future__ import annotations


def dashboard_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Lead Email Automation</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #08090a;
      --panel: #0f1011;
      --surface: rgba(255,255,255,0.035);
      --surface-2: rgba(255,255,255,0.055);
      --border: rgba(255,255,255,0.08);
      --text: #f7f8f8;
      --muted: #8a8f98;
      --soft: #d0d6e0;
      --accent: #5e6ad2;
      --accent-hover: #828fff;
      --ok: #10b981;
      --warn: #f59e0b;
      --danger: #ef4444;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: radial-gradient(circle at top left, rgba(94,106,210,0.14), transparent 34rem), var(--bg);
      color: var(--text);
      font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
      font-feature-settings: "cv01", "ss03";
    }
    header {
      position: sticky;
      top: 0;
      z-index: 2;
      background: rgba(8,9,10,0.86);
      backdrop-filter: blur(16px);
      border-bottom: 1px solid rgba(255,255,255,0.05);
      padding: 18px 28px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .brand { font-weight: 590; letter-spacing: -0.24px; }
    .pill { border: 1px solid var(--border); color: var(--soft); border-radius: 999px; padding: 6px 10px; font-size: 12px; }
    main { max-width: 1280px; margin: 0 auto; padding: 28px; }
    .hero { margin: 26px 0 30px; }
    h1 { font-size: clamp(36px, 6vw, 64px); line-height: 1; letter-spacing: -1.4px; margin: 0 0 12px; font-weight: 510; }
    h2 { font-size: 18px; margin: 0 0 14px; font-weight: 590; letter-spacing: -0.2px; }
    p { color: var(--muted); line-height: 1.6; }
    .grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 18px; }
    .card { grid-column: span 6; background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 18px; box-shadow: rgba(0,0,0,0.2) 0 0 0 1px; }
    .card.full { grid-column: 1 / -1; }
    label { display: block; color: var(--soft); font-size: 12px; font-weight: 510; margin: 12px 0 6px; }
    input, textarea, select {
      width: 100%;
      background: rgba(255,255,255,0.025);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 12px;
      font: inherit;
      outline: none;
    }
    textarea { min-height: 96px; resize: vertical; }
    input:focus, textarea:focus { border-color: rgba(130,143,255,0.7); box-shadow: 0 0 0 3px rgba(94,106,210,0.18); }
    button {
      background: var(--accent);
      color: white;
      border: 0;
      border-radius: 8px;
      padding: 10px 14px;
      font-weight: 590;
      cursor: pointer;
      margin-top: 12px;
    }
    button.secondary { background: rgba(255,255,255,0.05); color: var(--soft); border: 1px solid var(--border); }
    button:hover { background: var(--accent-hover); }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .status { font-family: 'JetBrains Mono', ui-monospace, monospace; white-space: pre-wrap; font-size: 12px; color: var(--soft); background: #050607; border: 1px solid var(--border); border-radius: 10px; padding: 12px; min-height: 52px; }
    .draft { border: 1px solid var(--border); border-radius: 12px; padding: 14px; background: rgba(255,255,255,0.025); margin-bottom: 12px; }
    .draft h3 { margin: 0 0 8px; font-size: 15px; }
    .meta { color: var(--muted); font-size: 12px; margin-bottom: 10px; }
    .badge { display: inline-block; border-radius: 999px; padding: 3px 8px; background: rgba(94,106,210,0.18); color: #cfd3ff; margin-left: 8px; }
    @media (max-width: 860px) { .card { grid-column: 1 / -1; } .row { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <header>
    <div class="brand">Lead Email Automation</div>
    <div class="pill">Draft-first MVP</div>
  </header>
  <main>
    <!-- API route examples used by this dashboard: /campaigns/draft, /campaigns/{campaign_id}/drafts/draft-1/approve, /campaigns/{campaign_id}/drafts/draft-1/edit -->
    <section class="hero">
      <h1>Create, review, and approve personalized outreach drafts.</h1>
      <p>Enter a company profile, campaign targeting, and lead CSV. The backend generates safe drafts, then you edit or approve them before any email integration is added.</p>
    </section>

    <section class="grid">
      <div class="card">
        <h2>Company Profile</h2>
        <label>Company name</label>
        <input id="companyName" value="Acme Rubber Works" />
        <label>Website</label>
        <input id="companyWebsite" value="https://acme.example" />
        <label>Description</label>
        <textarea id="companyDescription">Rubber products manufacturer for OEMs, industrial distributors, and construction suppliers.</textarea>
        <button class="secondary" onclick="profileCompany()">Preview Profile</button>
      </div>

      <div class="card">
        <h2>Campaign Builder</h2>
        <div class="row">
          <div><label>Campaign name</label><input id="campaignName" value="UAE distributor outreach" /></div>
          <div><label>Target country</label><input id="targetCountry" value="United Arab Emirates" /></div>
        </div>
        <div class="row">
          <div><label>Target region</label><input id="targetRegion" value="UAE" /></div>
          <div><label>Max drafts</label><input id="maxDrafts" type="number" value="10" /></div>
        </div>
        <div class="row">
          <div><label>Sender name</label><input id="senderName" value="Maya" /></div>
          <div><label>Sender email</label><input id="senderEmail" value="maya@acme.example" /></div>
        </div>
        <div class="row">
          <div>
            <label>LLM provider</label>
            <select id="llmProvider">
              <option value="deterministic">Deterministic fallback</option>
              <option value="codex">Codex</option>
              <option value="gemini">Gemini</option>
            </select>
          </div>
          <div><label>LLM model</label><input id="llmModel" placeholder="optional, e.g. gemini-3.1-pro-preview" /></div>
        </div>
        <label><input id="enrichWebsites" type="checkbox" style="width:auto; margin-right:8px;" />Enrich lead websites with Scrapling/static fetch</label>
      </div>

      <div class="card full">
        <h2>Email Template</h2>
        <textarea id="template">Hi {{first_name}}, I noticed {{company_name}} works in {{lead_context}}. We manufacture {{value_prop}}. Would it make sense to send a short catalogue? Best, {{sender_name}}</textarea>
      </div>

      <div class="card full">
        <h2>Lead CSV</h2>
        <p>Paste CSV with columns: first_name,last_name,email,title,company_name,country,industry,website,context</p>
        <textarea id="leadCsv" style="min-height: 140px;">first_name,last_name,email,title,company_name,country,industry,website,context
Ahmed,Khan,ahmed@example.ae,Procurement Manager,Gulf Industrial Supplies,United Arab Emirates,Industrial,https://gulf.example,industrial maintenance supplies in Dubai
Sara,Noor,sara@example.ae,Sourcing Manager,BuildRight UAE,UAE,Construction,https://buildright.example,construction materials procurement
Bob,Smith,bob@example.com,Marketing Manager,US Retail Co,United States,Retail,https://retail.example,consumer retail</textarea>
        <button onclick="generateDrafts()">Generate Drafts</button>
      </div>

      <div class="card full">
        <h2>Draft Review</h2>
        <div id="status" class="status">Ready.</div>
        <div id="drafts" style="margin-top: 14px;"></div>
      </div>
    </section>
  </main>

  <script>
    let currentCampaignId = '';

    function csvToLeads(csv) {
      const lines = csv.trim().split(/\r?\n/).filter(Boolean);
      const headers = lines.shift().split(',').map(h => h.trim());
      return lines.map(line => {
        const values = line.split(',');
        const row = {};
        headers.forEach((header, index) => row[header] = (values[index] || '').trim());
        return row;
      });
    }

    function payload() {
      return {
        company: {
          name: document.getElementById('companyName').value,
          website: document.getElementById('companyWebsite').value,
          description: document.getElementById('companyDescription').value,
          details: {}
        },
        campaign: {
          name: document.getElementById('campaignName').value,
          target_country: document.getElementById('targetCountry').value,
          target_region: document.getElementById('targetRegion').value,
          max_drafts: Number(document.getElementById('maxDrafts').value || 10),
          sender_name: document.getElementById('senderName').value,
          sender_email: document.getElementById('senderEmail').value,
          template: document.getElementById('template').value,
          target_titles: ['Procurement Manager', 'Sourcing Manager', 'Operations Manager'],
          target_industries: ['Industrial', 'Construction', 'Manufacturing']
        },
        leads: csvToLeads(document.getElementById('leadCsv').value),
        llm_provider: document.getElementById('llmProvider').value,
        llm_model: document.getElementById('llmModel').value || null,
        enrich_websites: document.getElementById('enrichWebsites').checked
      };
    }

    async function profileCompany() {
      const res = await fetch('/companies/profile', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload().company) });
      document.getElementById('status').textContent = JSON.stringify(await res.json(), null, 2);
    }

    async function generateDrafts() {
      const res = await fetch('/campaigns/draft', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload()) });
      const data = await res.json();
      currentCampaignId = data.campaign_id;
      document.getElementById('status').textContent = `Created ${data.drafts.length} draft(s) with ${data.llm_provider}/${data.llm_model}. Skipped: ${JSON.stringify(data.skipped)}`;
      renderDrafts(data.drafts);
    }

    async function loadDrafts() {
      if (!currentCampaignId) return;
      const res = await fetch(`/campaigns/${currentCampaignId}/drafts`);
      const data = await res.json();
      renderDrafts(data.drafts);
    }

    function renderDrafts(drafts) {
      document.getElementById('drafts').innerHTML = drafts.map(d => `
        <div class="draft" id="${d.draft_id}">
          <h3>${d.subject}<span class="badge">${d.review_status}</span></h3>
          <div class="meta">${d.draft_id} · ${d.lead.first_name} ${d.lead.last_name} · ${d.lead.email} · score ${d.lead_score.score}</div>
          <label>Subject</label>
          <input id="subject-${d.draft_id}" value="${escapeHtml(d.subject)}" />
          <label>Body</label>
          <textarea id="body-${d.draft_id}">${escapeHtml(d.body)}</textarea>
          <button onclick="approveDraft('${d.draft_id}')">Approve</button>
          <button class="secondary" onclick="editDraft('${d.draft_id}')">Save edits</button>
        </div>`).join('');
    }

    async function approveDraft(draftId) {
      const res = await fetch(`/campaigns/${currentCampaignId}/drafts/${draftId}/approve`, {
        method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({approved_by: 'dashboard', notes: 'Approved in dashboard'})
      });
      document.getElementById('status').textContent = JSON.stringify(await res.json(), null, 2);
      await loadDrafts();
    }

    async function editDraft(draftId) {
      const res = await fetch(`/campaigns/${currentCampaignId}/drafts/${draftId}/edit`, {
        method: 'PATCH', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({subject: document.getElementById(`subject-${draftId}`).value, body: document.getElementById(`body-${draftId}`).value, edited_by: 'dashboard'})
      });
      document.getElementById('status').textContent = JSON.stringify(await res.json(), null, 2);
      await loadDrafts();
    }

    function escapeHtml(value) {
      return String(value || '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));
    }
  </script>
</body>
</html>"""
