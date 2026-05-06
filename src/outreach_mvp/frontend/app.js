let currentCampaignId = '';
let mailboxStatus = {};
let selectedLeadSource = 'csv';
let apolloLeads = [];

const $ = (id) => document.getElementById(id);

document.addEventListener('DOMContentLoaded', () => {
  document.querySelector('[data-action="profile-company"]').addEventListener('click', profileCompany);
  document.querySelector('[data-action="generate-drafts"]').addEventListener('click', generateDrafts);
  document.querySelector('[data-action="search-apollo"]').addEventListener('click', searchApolloLeads);
  document.querySelector('[data-action="refresh-mailboxes"]').addEventListener('click', loadMailboxStatus);
  document.querySelectorAll('[data-source-tab]').forEach((button) => {
    button.addEventListener('click', () => switchLeadSource(button.dataset.sourceTab));
  });
  document.querySelectorAll('[data-action="connect-mailbox"]').forEach((button) => {
    button.addEventListener('click', () => connectMailbox(button.dataset.provider));
  });
  loadMailboxStatus();
});

async function apiFetch(url, options = {}) {
  const res = await fetch(url, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || JSON.stringify(data));
  }
  return data;
}

function setStatus(message, data = null) {
  $('status').textContent = data ? `${message}\n${JSON.stringify(data, null, 2)}` : message;
}

async function loadMailboxStatus() {
  try {
    mailboxStatus = await apiFetch('/mailboxes/status');
    for (const provider of ['gmail', 'outlook']) {
      const item = mailboxStatus.providers?.[provider] || {};
      const el = $(`${provider}Status`);
      if (!el) continue;
      el.textContent = `${provider}: ${item.connected ? 'connected' : 'not connected'} · ${item.configured ? 'configured' : 'missing OAuth config'}`;
    }
  } catch (error) {
    setStatus(`Mailbox status failed: ${error.message}`);
  }
}

async function connectMailbox(provider) {
  try {
    const data = await apiFetch(`/oauth/${provider}/start`);
    window.location.href = data.auth_url;
  } catch (error) {
    setStatus(`${provider} OAuth is not ready: ${error.message}`);
  }
}

function csvToLeads(csv) {
  const lines = csv.trim().split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) return [];
  const headers = splitCsvLine(lines.shift()).map((h) => h.trim());
  return lines.map((line) => {
    const values = splitCsvLine(line);
    const row = {};
    headers.forEach((header, index) => { row[header] = (values[index] || '').trim(); });
    return row;
  });
}

function splitCsvLine(line) {
  const values = [];
  let current = '';
  let inQuotes = false;
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    const next = line[index + 1];
    if (char === '"' && inQuotes && next === '"') {
      current += '"';
      index += 1;
    } else if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === ',' && !inQuotes) {
      values.push(current);
      current = '';
    } else {
      current += char;
    }
  }
  values.push(current);
  return values;
}

function listFromInput(id) {
  return $(id).value.split(',').map((value) => value.trim()).filter(Boolean);
}

function switchLeadSource(source) {
  selectedLeadSource = source;
  $('csvLeadSource').classList.toggle('hidden', source !== 'csv');
  $('apolloLeadSource').classList.toggle('hidden', source !== 'apollo');
  document.querySelectorAll('[data-source-tab]').forEach((button) => {
    button.classList.toggle('active', button.dataset.sourceTab === source);
  });
}

function selectedLeads() {
  return selectedLeadSource === 'apollo' && apolloLeads.length ? apolloLeads : csvToLeads($('leadCsv').value);
}

function apolloSearchPayload() {
  return {
    titles: listFromInput('targetTitles'),
    locations: listFromInput('apolloLocations'),
    industries: listFromInput('targetIndustries'),
    company_domains: listFromInput('apolloCompanyDomains'),
    company_names: listFromInput('apolloCompanyNames'),
    keywords: $('apolloKeywords').value,
    max_leads: Number($('apolloMaxLeads').value || 10)
  };
}

async function searchApolloLeads() {
  try {
    setStatus('Searching Apollo leads...');
    const data = await apiFetch('/leads/apollo/search', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(apolloSearchPayload())
    });
    apolloLeads = data.leads || [];
    renderLeadPreview(apolloLeads, 'Apollo');
    setStatus(`Imported ${apolloLeads.length} Apollo lead(s). They will be used for the next draft generation.`);
  } catch (error) {
    apolloLeads = [];
    renderLeadPreview([], 'Apollo');
    setStatus(`Apollo search failed: ${error.message}. CSV fallback is still available.`);
  }
}

function renderLeadPreview(leads, sourceLabel) {
  if (!leads.length) {
    $('apolloLeadPreview').textContent = `${sourceLabel} lead preview is empty.`;
    return;
  }
  $('apolloLeadPreview').innerHTML = leads.map((lead) => `${escapeHtml(lead.first_name)} ${escapeHtml(lead.last_name)} · ${escapeHtml(lead.title)} · ${escapeHtml(lead.company_name)} · ${escapeHtml(lead.email)}`).join('<br>');
}

function payload() {
  return {
    company: {
      name: $('companyName').value,
      website: $('companyWebsite').value,
      description: $('companyDescription').value,
      details: {}
    },
    campaign: {
      name: $('campaignName').value,
      target_country: $('targetCountry').value,
      target_region: $('targetRegion').value,
      max_drafts: Number($('maxDrafts').value || 10),
      sender_name: $('senderName').value,
      sender_email: $('senderEmail').value,
      template: $('template').value,
      target_titles: listFromInput('targetTitles'),
      target_industries: listFromInput('targetIndustries')
    },
    leads: selectedLeads(),
    llm_provider: $('llmProvider').value,
    llm_model: $('llmModel').value || null,
    enrich_websites: $('enrichWebsites').checked
  };
}

async function profileCompany() {
  try {
    const data = await apiFetch('/companies/profile', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload().company)
    });
    setStatus('Company profile preview', data);
  } catch (error) {
    setStatus(`Profile preview failed: ${error.message}`);
  }
}

async function generateDrafts() {
  try {
    setStatus('Generating drafts...');
    const data = await apiFetch('/campaigns/draft', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload())
    });
    currentCampaignId = data.campaign_id;
    updateMetrics(data.drafts || [], data.skipped || {});
    setStatus(`Created ${(data.drafts || []).length} draft(s) with ${data.llm_provider}/${data.llm_model}. Skipped: ${Object.keys(data.skipped || {}).length}`);
    renderDrafts(data.drafts || []);
  } catch (error) {
    setStatus(`Draft generation failed: ${error.message}`);
  }
}

async function loadDrafts() {
  if (!currentCampaignId) return;
  const data = await apiFetch(`/campaigns/${currentCampaignId}/drafts`);
  renderDrafts(data.drafts || []);
  updateMetrics(data.drafts || []);
}

function updateMetrics(drafts, skipped = null) {
  $('metricDrafts').textContent = drafts.length;
  $('metricApproved').textContent = drafts.filter((draft) => draft.approved).length;
  if (skipped !== null) $('metricSkipped').textContent = Object.keys(skipped).length;
}

function renderDrafts(drafts) {
  const container = $('drafts');
  if (!drafts.length) {
    container.innerHTML = '<div class="status">Review Queue is empty. Generate a campaign to start reviewing drafts.</div>';
    return;
  }
  container.innerHTML = drafts.map((draft) => `
    <div class="draft" id="${escapeAttr(draft.draft_id)}">
      <div class="draft-header">
        <div>
          <h3>${escapeHtml(draft.subject)}</h3>
          <div class="meta">${escapeHtml(draft.draft_id)} · ${escapeHtml(draft.lead.first_name)} ${escapeHtml(draft.lead.last_name)} · ${escapeHtml(draft.lead.email)} · score ${escapeHtml(draft.lead_score.score)}</div>
        </div>
        <span class="badge ${escapeAttr(draft.review_status)}">${escapeHtml(draft.review_status)}</span>
      </div>
      <label for="subject-${escapeAttr(draft.draft_id)}">Subject</label>
      <input id="subject-${escapeAttr(draft.draft_id)}" value="${escapeAttr(draft.subject)}" />
      <label for="body-${escapeAttr(draft.draft_id)}">Body</label>
      <textarea id="body-${escapeAttr(draft.draft_id)}">${escapeHtml(draft.body)}</textarea>
      <div class="draft-actions">
        <button data-draft-id="${escapeAttr(draft.draft_id)}" data-action="approve-draft">Approve</button>
        <button class="secondary" data-draft-id="${escapeAttr(draft.draft_id)}" data-action="edit-draft">Save edits</button>
        <button class="secondary" data-draft-id="${escapeAttr(draft.draft_id)}" data-provider="gmail" data-action="create-mailbox-draft">Create Gmail draft</button>
        <button class="secondary" data-draft-id="${escapeAttr(draft.draft_id)}" data-provider="outlook" data-action="create-mailbox-draft">Create Outlook draft</button>
      </div>
    </div>`).join('');

  container.querySelectorAll('[data-action="approve-draft"]').forEach((button) => {
    button.addEventListener('click', () => approveDraft(button.dataset.draftId));
  });
  container.querySelectorAll('[data-action="edit-draft"]').forEach((button) => {
    button.addEventListener('click', () => editDraft(button.dataset.draftId));
  });
  container.querySelectorAll('[data-action="create-mailbox-draft"]').forEach((button) => {
    button.addEventListener('click', () => createMailboxDraft(button.dataset.draftId, button.dataset.provider));
  });
}

async function approveDraft(draftId) {
  try {
    const data = await apiFetch(`/campaigns/${currentCampaignId}/drafts/${draftId}/approve`, {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({approved_by: 'dashboard', notes: 'Approved in dashboard'})
    });
    setStatus('Draft approved', data);
    await loadDrafts();
  } catch (error) {
    setStatus(`Approval failed: ${error.message}`);
  }
}

async function editDraft(draftId) {
  try {
    const data = await apiFetch(`/campaigns/${currentCampaignId}/drafts/${draftId}/edit`, {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        subject: $(`subject-${draftId}`).value,
        body: $(`body-${draftId}`).value,
        edited_by: 'dashboard'
      })
    });
    setStatus('Draft edits saved; re-approval required', data);
    await loadDrafts();
  } catch (error) {
    setStatus(`Save edits failed: ${error.message}`);
  }
}

async function createMailboxDraft(draftId, provider) {
  try {
    const selectedDelivery = $('mailboxDelivery').value;
    const delivery = selectedDelivery === 'gmail_api' && provider !== 'gmail' ? 'local'
      : selectedDelivery === 'outlook_graph' && provider !== 'outlook' ? 'local'
      : selectedDelivery;
    const data = await apiFetch(`/campaigns/${currentCampaignId}/drafts/${draftId}/mailbox-drafts`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({provider, delivery})
    });
    setStatus(`${provider} mailbox draft created`, data);
  } catch (error) {
    setStatus(`Mailbox draft creation failed: ${error.message}`);
  }
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#039;'}[char]));
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, '&#096;');
}
