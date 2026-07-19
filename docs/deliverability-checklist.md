# Deliverability checklist (read before the first real campaign)

Cold email lives or dies on sender reputation. Work through this once per sending domain.

## 1. Domain & mailbox

- [ ] Send from a real, warmed mailbox on your own domain — never a fresh throwaway domain with day-one volume.
- [ ] The mailbox has a human name, photo, and signature; it has sent/received normal email for at least 2–4 weeks.

## 2. DNS records (check with `GET /api/deliverability/<your-domain>` — all three must be green)

- [ ] **SPF** TXT on the root: Gmail → `v=spf1 include:_spf.google.com ~all` · Microsoft 365 → `v=spf1 include:spf.protection.outlook.com -all`
- [ ] **DKIM** enabled in the provider admin console (Google Workspace: Apps → Gmail → Authenticate email; M365: Defender portal → Email authentication).
- [ ] **DMARC** TXT at `_dmarc.<domain>`: start with `v=DMARC1; p=none; rua=mailto:you@<domain>`, tighten to `p=quarantine` after 2 clean weeks.

## 3. Volume rules (the app enforces the cap; you own the ramp)

- [ ] Start ≤ 20/day per mailbox (`DAILY_SEND_CAP=20`), add ~10/week, hard ceiling 50/day.
- [ ] No bursts: spread sends across the working day.
- [ ] Watch replies and bounces daily for the first two weeks; a bounce rate over ~3% means stop and clean the list.

## 4. Content rules (mostly enforced by the drafting prompts)

- [ ] Plain text, 60–120 words, no tracking pixels, no link shorteners, at most one link.
- [ ] Truthful sender identity + postal address + working one-click unsubscribe in every mail (the footer builder adds these when `APP_BASE_URL`, `UNSUBSCRIBE_SECRET`, and `company.details.postal_address` are set — auto-send refuses to run without them).

## 5. Legal quick-reference

- B2B cold email is lawful in most jurisdictions IF identity is truthful, opt-out works and is honored immediately (ours is instant and permanent), and volumes are sane.
- EU/UK recipients: stricter (PECR / GDPR legitimate interest). Keep EU sending in draft mode (human presses Send) and only email role-relevant business addresses.
- Never buy scraped personal-address lists. Apollo business contacts and your own CSVs only.
