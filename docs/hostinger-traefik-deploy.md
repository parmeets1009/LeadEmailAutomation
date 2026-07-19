# Hostinger VPS + Traefik deployment

Target public URL: `https://lead.hermes-agent-2bhv.srv1390211.hstgr.cloud`

The container runs the **bridge** (`backend/server.py`, port **8001**): React dashboard at `/`, API under `/api`, everything behind Traefik Basic Auth EXCEPT the public unsubscribe routes (`/api/u/...`).

> Field note (2026-07-19): Traefik answers on this VPS but even the root hermes
> host currently 404s — verify what is actually running before assuming the
> environment below.

## 1. Pre-flight (on the VPS)

```bash
docker ps | grep -i traefik                 # traefik must be running
docker network ls | grep traefik            # note the REAL network name
docker inspect <traefik-container> | grep -i certresolver   # note the resolver name
```

If the network or resolver differ from `traefik` / `letsencrypt`, edit the labels in `deploy/lead-email-compose.yml`.

## 2. Install

```bash
git clone https://github.com/parmeets1009/LeadEmailAutomation.git /opt/lead-email
cd /opt/lead-email
cp /dev/null .env && nano .env    # fill in per the compose file header:
# LEAD_BASIC_AUTH='admin:$apr1$...'   (htpasswd -nb admin 'pass'; keep single quotes)
# UNSUBSCRIBE_SECRET=<long random>    (the app refuses to start without it)
# APP_BASE_URL=https://lead.hermes-agent-2bhv.srv1390211.hstgr.cloud/api
# ANTHROPIC_API_KEY=sk-ant-...  DAILY_SEND_CAP=20  (+OAuth/Apollo when ready)
mkdir -p campaign_runs
docker compose --env-file .env -f deploy/lead-email-compose.yml up -d
```

`--env-file` is required: label interpolation (`${LEAD_BASIC_AUTH}`) reads it; the service `env_file:` alone does not feed labels.

## 3. Verify inside-out

```bash
docker compose -f deploy/lead-email-compose.yml logs -f     # expect uvicorn on 0.0.0.0:8001
docker exec lead-email-app sh -lc 'python -c "import urllib.request;print(urllib.request.urlopen(\"http://127.0.0.1:8001/api/health\").read().decode())"'
# expect {"status":"ok"}
curl -I https://lead.hermes-agent-2bhv.srv1390211.hstgr.cloud/api/health   # 401 (Basic Auth working)
curl -I -u admin:PASS https://lead.hermes-agent-2bhv.srv1390211.hstgr.cloud/api/health  # 200
curl -vI https://lead.hermes-agent-2bhv.srv1390211.hstgr.cloud 2>&1 | grep -i issuer    # Let's Encrypt, not TRAEFIK DEFAULT
```

Browser: URL → Basic Auth prompt → React dashboard. Run the smoke flow (playbook §0.4) against `https://…/api`.

## 4. Post-deploy

1. Set the OAuth redirect URIs in the Google/Microsoft consoles to `https://…/api/oauth/{gmail,outlook}/callback`, connect mailboxes from the dashboard.
2. Check `GET /api/deliverability/<your-sending-domain>` is fully green before any real campaign (see docs/deliverability-checklist.md).
3. Nightly backup of `campaign_runs/` (it IS the database):
   `0 3 * * * tar czf /root/backups/campaign_runs-$(date +\%F).tgz -C /opt/lead-email campaign_runs`

## Troubleshooting

- **404 from Traefik**: labels/network mismatch — recheck step 1 names.
- **TRAEFIK DEFAULT CERT**: resolver name wrong, or DNS not pointing here.
- **App exits at boot with "UNSUBSCRIBE_SECRET must be set"**: intended — set it in `.env`.
- **401 on unsubscribe links**: the `/api/u/` router labels are missing/edited — recipients must reach them without credentials.
