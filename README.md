# Food Service — Backend

API REST do **Food Service** (SaaS multi-tenant para Food Service).

**Stack:** Python 3.12, Django 5, DRF, PostgreSQL, Redis, Celery.

Documentação completa em `../vendas_frontend/docs/`.

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

# 6. Servidor
python manage.py runserver
```

Health check: [http://localhost:8000/api/v1/health/](http://localhost:8000/api/v1/health/)

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

**Sprint 0 — Fundação** (`docs/09-roadmap.md`)

- [x] Django + DRF configurado
- [x] Settings por ambiente
- [x] Docker Compose (PostgreSQL, Redis)
- [x] `core/` — BaseModel, TenantAwareModel, TenantMiddleware
- [x] `GET /api/v1/health/`
- [x] pytest + ruff + CI

Próximo: **Sprint 1 — Tenant e Empresa**
