# Deploy MVP — Sprint 10

Guia para colocar o Food Service em produção (VPS/cloud) com Docker.

## Arquitetura

```
                    ┌─────────────────────────────────────┐
                    │           Nginx (porta 80/443)       │
                    │  admin.* → backoffice SPA            │
                    │  api.*   → Django API                │
                    │  {tenant}.* → storefront + /api/     │
                    └──────────────┬──────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
         Gunicorn              PostgreSQL            Redis
         (api)                 (db)                  (cache + Celery)
              │
              ▼
         Celery worker (e-mails de confirmação)
```

## Pré-requisitos no servidor

- Docker 24+ e Docker Compose v2
- Domínio `foodservice.app` com DNS:
  - `A` → IP do servidor para `api`, `admin`
  - `A` ou `CNAME` wildcard `*.foodservice.app` → IP do servidor
- TLS: recomendado **Caddy** ou **Certbot** na frente do Nginx (ou Traefik)

## Estrutura de repositórios no servidor

```bash
~/foodservice/
├── vendas_backend/
└── vendas_frontend/    # sibling — necessário para build do Nginx
```

## 1. Configurar variáveis

```bash
cd ~/foodservice/vendas_backend
cp .env.production.example .env.production
# Edite SECRET_KEY, POSTGRES_PASSWORD, e-mail SMTP, etc.
```

## 2. Subir stack

```bash
cd ~/foodservice/vendas_backend
docker compose -f deploy/docker-compose.prod.yml up -d --build
```

Serviços: `db`, `redis`, `api`, `celery`, `nginx`.

## 3. Onboarding do cliente real

```bash
docker compose -f deploy/docker-compose.prod.yml exec api python manage.py onboard_tenant \
  --trade-name "Pizzaria do João" \
  --subdomain pizzaria-joao \
  --email contato@pizzariajoao.com \
  --phone "(11) 99999-0000" \
  --owner-email joao@pizzariajoao.com \
  --owner-password "senha-inicial-segura"
```

Opcional (staging): adicione `--seed-catalog` para cardápio demo.

Depois cadastre o cardápio real pelo backoffice em `https://admin.foodservice.app`.

## 4. TLS (Let's Encrypt)

Exemplo com Certbot + Nginx (ajuste paths):

```bash
sudo certbot certonly --nginx -d foodservice.app -d '*.foodservice.app' -d api.foodservice.app -d admin.foodservice.app
```

Wildcard exige validação DNS (`dns-01`). Para MVP sem wildcard, emita certificados por subdomínio.

## 5. CI/CD

| Workflow | Repo | Trigger |
|----------|------|---------|
| `ci.yml` | ambos | PR + push `main` — lint, testes, build |
| `docker.yml` | ambos | build das imagens Docker |
| `deploy-staging.yml` | backend | push `develop` — deploy SSH |

Secrets necessários no GitHub (environment `staging`):

- `STAGING_HOST`
- `STAGING_USER`
- `STAGING_SSH_KEY`

## 6. Monitoramento

Configure no `.env.production`:

```env
SENTRY_DSN=https://...@sentry.io/...
SENTRY_ENVIRONMENT=production
```

## 7. Backup PostgreSQL

```bash
docker compose -f deploy/docker-compose.prod.yml exec db \
  pg_dump -U foodservice foodservice > backup-$(date +%F).sql
```

Agende via cron diário.

## 8. Checklist E2E manual

Ver [`../../vendas_frontend/docs/14-checklist-e2e-go-live.md`](../../vendas_frontend/docs/14-checklist-e2e-go-live.md).

## URLs de produção

| App | URL |
|-----|-----|
| Storefront tenant | `https://{subdomain}.foodservice.app` |
| Backoffice | `https://admin.foodservice.app` |
| API | `https://api.foodservice.app/api/v1` |

## Desenvolvimento local (referência)

Portas alternativas: API `8001`, storefront `5174`, backoffice `5175` — ver `docs/00-portas-locais.md`.
