# Hostinger VPS + Traefik deployment for LeadEmailAutomation

Target public URL:

- https://lead.hermes-agent-2bhv.srv1390211.hstgr.cloud

This keeps Hermes on its existing root URL:

- https://hermes-agent-2bhv.srv1390211.hstgr.cloud/

## What this deploys

A separate containerized FastAPI app for LeadEmailAutomation, reverse-proxied by Traefik on a dedicated subdomain.

## Assumptions

- The VPS already has Traefik running.
- A Docker network named `traefik` exists and is used by Traefik.
- Wildcard DNS for `*.hermes-agent-2bhv.srv1390211.hstgr.cloud` already resolves to the VPS.
- Hermes remains on the root hostname and should not be replaced.

## Deployment file

Use:

- `deploy/lead-email-compose.yml`

It routes:

- `Host(lead.hermes-agent-2bhv.srv1390211.hstgr.cloud)`

to the FastAPI app on internal container port `8000`.

## Before starting

From the VPS, verify the Traefik Docker network exists:

```bash
docker network ls | grep traefik
```

If the network name differs, update this label and network section in the compose file:

```yaml
- traefik.docker.network=traefik

networks:
  traefik:
    external: true
```

## Start the app

From the repo root on the VPS:

```bash
cd /path/to/email-outreach-mvp
mkdir -p campaign_runs
docker compose -f deploy/lead-email-compose.yml up -d --build
```

## Verify container health

```bash
docker compose -f deploy/lead-email-compose.yml ps
docker compose -f deploy/lead-email-compose.yml logs -f
```

You should see Uvicorn start on port 8000.

## Verify Traefik routing

Check that the router labels are present:

```bash
docker inspect lead-email-app --format '{{json .Config.Labels}}'
```

Expected key labels:

```text
traefik.enable=true
traefik.http.routers.lead-email.rule=Host(`lead.hermes-agent-2bhv.srv1390211.hstgr.cloud`)
traefik.http.routers.lead-email.entrypoints=websecure
traefik.http.routers.lead-email.tls=true
traefik.http.services.lead-email.loadbalancer.server.port=8000
```

## Verify the app directly from inside the container

```bash
docker exec -it lead-email-app sh -lc 'python - <<"PY"
import urllib.request
print(urllib.request.urlopen("http://127.0.0.1:8000/health").read().decode())
PY'
```

Expected:

```json
{"status":"ok"}
```

## Verify the public URL

```bash
curl -I https://lead.hermes-agent-2bhv.srv1390211.hstgr.cloud/health
```

Expected: `HTTP/2 200`

Then open in a browser:

- https://lead.hermes-agent-2bhv.srv1390211.hstgr.cloud/

## OAuth notes

For Gmail/Outlook connect flows to work correctly on the public app, set:

```text
APP_BASE_URL=https://lead.hermes-agent-2bhv.srv1390211.hstgr.cloud
GOOGLE_OAUTH_REDIRECT_URI=https://lead.hermes-agent-2bhv.srv1390211.hstgr.cloud/oauth/gmail/callback
MICROSOFT_OAUTH_REDIRECT_URI=https://lead.hermes-agent-2bhv.srv1390211.hstgr.cloud/oauth/outlook/callback
```

Also provide the matching client IDs/secrets for each provider if live draft creation is needed.

## Troubleshooting

1. DNS resolves but page does not load
- Traefik router/service labels are missing or incorrect.
- Container is not attached to the same Docker network as Traefik.
- Traefik `entrypoints` or `certresolver` names differ from this example.

2. TLS/certificate errors
- Traefik may use a different resolver name than `letsencrypt`.
- Update:

```yaml
- traefik.http.routers.lead-email.tls.certresolver=letsencrypt
```

to the resolver actually used on the VPS.

3. Container starts but Traefik cannot reach it
- Confirm the app listens on `0.0.0.0:8000`.
- Confirm the service label port is `8000`.
- Confirm container and Traefik share the same Docker network.

4. Hermes root URL breaks
- Root URL should remain owned by Hermes.
- This app should only be on:
  - `lead.hermes-agent-2bhv.srv1390211.hstgr.cloud`

## Recommended next steps after deployment

1. Verify public frontend access.
2. Verify campaign history and draft generation from the public URL.
3. Configure OAuth callback URLs against the new subdomain.
4. Then build reply/bounce/unsubscribe sync.
