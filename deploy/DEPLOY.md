# Deploy — VPS Hostinger + GitHub Actions

Guia para subir o Food Service em produção (Docker) com **deploy automático via Git** (`push` em `main`).

## Arquitetura

```
Internet
   │
   ▼
┌──────────────────────────────────────────┐
│  Caddy (:80/:443)  — TLS Let's Encrypt   │
│  api.* / admin.* / {tenant}.*            │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  Nginx (interno) — SPA storefront/admin  │
│  + proxy /api → Gunicorn                 │
└──────────────────┬───────────────────────┘
                   │
     ┌─────────────┼─────────────┐
     ▼             ▼             ▼
  Gunicorn      Postgres       Redis
  + Celery
```

## Pré-requisitos

- VPS Hostinger (Ubuntu 22.04/24.04) com acesso SSH
- Docker 24+ (instalado pelo bootstrap)
- Domínio com DNS apontando para o IP da VPS:
  - `A` → `api`, `admin`, `demo` (e cada tenant novo)
  - Opcional depois: wildcard `*.seudominio.com` (precisa DNS-01)
- Repos GitHub: `vendas_backend` e `vendas_frontend` (privados ou públicos)

## 1. Bootstrap da VPS (uma vez)

No servidor (SSH como root):

```bash
# cole o script ou copie do repo depois do clone
curl -fsSL https://get.docker.com | sh   # se ainda não tiver Docker
mkdir -p /opt/foodservice && cd /opt/foodservice

git clone git@github.com:SEU_USER/vendas_backend.git vendas_backend
git clone git@github.com:SEU_USER/vendas_frontend.git vendas_frontend

# OU bootstrap completo (firewall + docker):
# bash vendas_backend/deploy/scripts/vps-bootstrap.sh
```

Deploy key (recomendado): crie uma chave SSH só para o servidor e adicione como **Deploy key** (read) nos dois repos GitHub.

```bash
ssh-keygen -t ed25519 -C "vps-foodservice" -f ~/.ssh/foodservice_deploy -N ""
# publique ~/.ssh/foodservice_deploy.pub em cada repo → Settings → Deploy keys
```

`~/.ssh/config` no servidor:

```
Host github.com
  IdentityFile ~/.ssh/foodservice_deploy
  IdentitiesOnly yes
```

## 2. Variáveis de produção

```bash
cd /opt/foodservice/vendas_backend
cp .env.production.example .env.production
nano .env.production
```

Campos críticos:

| Variável | O quê |
|----------|--------|
| `BASE_DOMAIN` | domínio raiz (ex.: `meusite.com.br`) |
| `SECRET_KEY` | string longa aleatória |
| `POSTGRES_PASSWORD` | senha forte |
| `ALLOWED_HOSTS` | `.dominio`, `api.`, `admin.`, `demo.` |
| `CORS_ALLOWED_ORIGINS` | URLs `https://…` |
| `VITE_API_BASE_URL` | `https://api.DOMINIO/api/v1` |
| `STOREFRONT_BASE_DOMAIN` | mesmo que `BASE_DOMAIN` |

Troque `foodservice.app` pelo **seu domínio** em todos os campos.

## 3. DNS na Hostinger

No painel DNS do domínio:

| Tipo | Nome | Valor |
|------|------|--------|
| A | `api` | IP da VPS |
| A | `admin` | IP da VPS |
| A | `demo` | IP da VPS |
| A | `@` (opcional) | IP da VPS |

Cada tenant novo (ex.: `pizzaria-joao`) precisa de um registro `A` **e** um bloco no `deploy/caddy/Caddyfile.template`.

## 4. Primeiro deploy (manual)

```bash
cd /opt/foodservice/vendas_backend
bash deploy/scripts/remote-deploy.sh
```

Isso:

1. `git pull` backend + frontend (`main`)
2. Gera Nginx + Caddy com o `BASE_DOMAIN`
3. `docker compose up -d --build`
4. Roda migrations

Confira:

```bash
docker compose -f deploy/docker-compose.prod.yml ps
curl -I https://api.SEU_DOMINIO/api/v1/health/
```

## 5. Deploy automático via Git

### Secrets no GitHub

Nos **dois** repositórios → Settings → Environments → **production**:

| Secret | Valor |
|--------|--------|
| `PRODUCTION_HOST` | IP da VPS |
| `PRODUCTION_USER` | `root` (ou user com Docker) |
| `PRODUCTION_SSH_KEY` | chave **privada** que entra na VPS |

Na VPS, a chave pública correspondente deve estar em `~/.ssh/authorized_keys`.

### Workflows

| Repo | Arquivo | Trigger |
|------|---------|---------|
| backend | `.github/workflows/deploy-production.yml` | push `main` |
| frontend | `.github/workflows/deploy-production.yml` | push `main` |

Fluxo: `git push origin main` → Action SSH → `/opt/foodservice/vendas_backend/deploy/scripts/remote-deploy.sh`.

Também dá para rodar manualmente: Actions → Deploy Production → Run workflow.

### Staging (opcional)

`deploy-staging.yml` no backend ainda aponta para branch `develop` e environment `staging` (`STAGING_*`).

## 6. Onboarding do cliente

```bash
cd /opt/foodservice/vendas_backend
docker compose -f deploy/docker-compose.prod.yml exec api python manage.py onboard_tenant \
  --trade-name "Pizzaria do João" \
  --subdomain pizzaria-joao \
  --email contato@pizzariajoao.com \
  --phone "(11) 99999-0000" \
  --owner-email joao@pizzariajoao.com \
  --owner-password "senha-inicial-segura"
```

Depois:

1. DNS `A` → `pizzaria-joao.SEU_DOMINIO`
2. Descomente/adicione o bloco no `deploy/caddy/Caddyfile.template`
3. Rode de novo o `remote-deploy.sh` (ou push em `main`)

## 7. Comandos úteis na VPS

```bash
cd /opt/foodservice/vendas_backend

# status
docker compose -f deploy/docker-compose.prod.yml ps

# logs
docker compose -f deploy/docker-compose.prod.yml logs -f --tail=100 api
docker compose -f deploy/docker-compose.prod.yml logs -f --tail=50 caddy

# redeploy manual
bash deploy/scripts/remote-deploy.sh

# backup Postgres
docker compose -f deploy/docker-compose.prod.yml exec -T db \
  pg_dump -U foodservice foodservice > backup-$(date +%F).sql
```

## 8. Monitoramento e e-mail

No `.env.production`:

```env
SENTRY_DSN=https://...@sentry.io/...
SENTRY_ENVIRONMENT=production
# SMTP (SendGrid, Amazon SES, etc.)
```

## 9. Checklist go-live

Ver [`../../vendas_frontend/docs/14-checklist-e2e-go-live.md`](../../vendas_frontend/docs/14-checklist-e2e-go-live.md).

## URLs

| App | URL |
|-----|-----|
| Storefront tenant | `https://{subdomain}.SEU_DOMINIO` |
| Backoffice | `https://admin.SEU_DOMINIO` |
| API | `https://api.SEU_DOMINIO/api/v1` |

## Estrutura dos arquivos de deploy

```text
vendas_backend/deploy/
├── docker-compose.prod.yml
├── scripts/
│   ├── vps-bootstrap.sh      # 1ª vez na VPS
│   ├── remote-deploy.sh      # pull + build + up
│   └── entrypoint.sh         # migrate + collectstatic na API
├── nginx/
│   ├── default.conf.template
│   └── default.conf          # gerado
├── caddy/
│   ├── Caddyfile.template
│   └── Caddyfile             # gerado
└── DEPLOY.md                 # este arquivo

vendas_frontend/deploy/
├── Dockerfile                # build storefront + admin
└── README.md
```

## Desenvolvimento local (referência)

Portas alternativas: API `8001`, storefront `5174`, backoffice `5175` — ver `docs/00-portas-locais.md`.
