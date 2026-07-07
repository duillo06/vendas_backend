# Food Service — Backend

API REST do **Food Service** (SaaS multi-tenant para Food Service).

**Stack:** Python 3.12, Django 5, DRF, PostgreSQL, Redis, Celery.

Documentação e skills em `../vendas_frontend/docs/` e `../vendas_frontend/.cursor/skills/`.

## Portas locais (projeto secundário)

Este projeto usa portas **alternativas** para não conflitar com o projeto principal (Django `8000`, Vite `5173`):

| Serviço | Porta |
|---------|-------|
| API Django | **8001** |
| Storefront (Vite) | **5174** |
| Backoffice (Vite) | **5175** |

Detalhes: [`../vendas_frontend/docs/00-portas-locais.md`](../vendas_frontend/docs/00-portas-locais.md)

## Pré-requisitos

- Python 3.12+
- Docker e Docker Compose
- [Opcional] `venv`

## Setup rápido

```bash
# 1. Ambiente virtual
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. Dependências
pip install -r requirements/development.txt

# 3. Variáveis de ambiente
cp .env.example .env

# 4. Infraestrutura (PostgreSQL + Redis)
docker compose -f docker-compose.dev.yml up -d

# 5. Migrations
export DJANGO_ENV=development
python manage.py migrate

# 6. Seed do tenant demo
python manage.py seed_dev

# 7. Servidor (porta 8001 — não use 8000 se o projeto principal estiver rodando)
python manage.py runserver 8001
```

Health check: [http://localhost:8001/api/v1/health/](http://localhost:8001/api/v1/health/)

## Deploy (produção)

```bash
cp .env.production.example .env.production
# edite secrets
docker compose -f deploy/docker-compose.prod.yml up -d --build
```

Guia completo: [`deploy/DEPLOY.md`](deploy/DEPLOY.md)

## Testes e lint

```bash
DJANGO_ENV=test pytest
ruff check .
```

## Estrutura

```
config/          # Settings, URLs, WSGI
core/            # BaseModel, tenant, health, pagination
apps/            # Módulos de domínio (Sprint 1+)
requirements/    # base, development, production
tests/           # pytest
```

## Sprint atual

**Sprint 10 — Deploy MVP** (`../vendas_frontend/docs/09-roadmap.md`)

- [x] `Dockerfile` + Gunicorn
- [x] `deploy/docker-compose.prod.yml` (PostgreSQL, Redis, API, Celery, Nginx)
- [x] Celery app + task de e-mail de confirmação de pedido
- [x] `python manage.py onboard_tenant` — onboarding cliente real
- [x] Settings produção (segurança, CORS, SMTP, Sentry opcional)
- [x] `.env.production.example` + `deploy/DEPLOY.md`
- [x] CI Docker + deploy staging (GitHub Actions)

Próximo: **Sprint 11** — Clientes e conta (V1).
