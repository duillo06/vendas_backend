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
python manage.py seed_locations  # estados e cidades oficiais do IBGE

# 6. Seed do tenant demo (mínimo)
python manage.py seed_dev

# 6b. Seed pizzaria (recomendado pra começar) — pizzas + bebidas + fotos
python manage.py seed_demo_pizzaria
# sem baixar fotos: python manage.py seed_demo_pizzaria --skip-images

# 7. Servidor (porta 8001 — não use 8000 se o projeto principal estiver rodando)
python manage.py runserver 8001
```

Health check: [http://localhost:8001/api/v1/health/](http://localhost:8001/api/v1/health/)

## Comandos do dia a dia

Tudo a partir de `vendas_backend`, com o venv ativo (ou use `.venv/bin/python`).

### Docker (Postgres 5433 + Redis 6380)

```bash
# subir infra
docker compose -f docker-compose.dev.yml up -d

# status / logs
docker compose -f docker-compose.dev.yml ps
docker compose -f docker-compose.dev.yml logs -f db

# parar (mantém dados)
docker compose -f docker-compose.dev.yml stop

# parar e remover containers (mantém volume)
docker compose -f docker-compose.dev.yml down

# ZERAR O BANCO de verdade (apaga o volume pgdata)
docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up -d
export DJANGO_ENV=development
python manage.py migrate
python manage.py seed_demo_pizzaria
```

### Banco e seeds

```bash
export DJANGO_ENV=development

# migrations
python manage.py migrate

# catálogo oficial usado nos selects de estado e cidade
python manage.py seed_locations

# limpar só os dados (mantém tabelas)
python manage.py flush --no-input

# seed mínimo (tenant + cardápio curto)
python manage.py seed_dev

# seed pizzaria (recomendado) — pizzas + bebidas + fotos + tamanhos/bordas
python manage.py seed_demo_pizzaria
python manage.py seed_demo_pizzaria --skip-images
python manage.py seed_demo_pizzaria --subdomain demo

# seed rico genérico (várias categorias + fotos + campanhas)
python manage.py seed_demo_rich
python manage.py seed_demo_rich --skip-images
```

**Login demo:** `admin@demo.com` / `demo1234`

### API

```bash
export DJANGO_ENV=development
python manage.py runserver 8001
```

### Reset completo (receita rápida)

```bash
docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up -d
export DJANGO_ENV=development
python manage.py migrate
python manage.py seed_demo_pizzaria
python manage.py runserver 8001
```

## Deploy (produção / VPS Hostinger)

Guia completo (Docker + Caddy TLS + deploy automático via Git):

→ [`deploy/DEPLOY.md`](deploy/DEPLOY.md)

```bash
# Na VPS, depois do bootstrap e do .env.production:
cd /opt/foodservice/vendas_backend
bash deploy/scripts/remote-deploy.sh
```

Push em `main` (backend ou frontend) dispara o deploy via GitHub Actions → SSH na VPS.

## Deploy (produção) — atalho compose

```bash
cp .env.production.example .env.production
# edite secrets + BASE_DOMAIN
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

## Comando para startar o ngrok 
~/.local/bin/ngrok http 5174
