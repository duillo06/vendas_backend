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

**Sprint 3 — Catálogo (Backend)** (`../vendas_frontend/docs/09-roadmap.md`)

- [x] App `catalog`: Category, Product, ProductImage, OptionGroup, Option, ProductOptionGroup
- [x] ProductService, OptionGroupService, PriceCalculator, CatalogSelector
- [x] API pública: categories, products, product detail
- [x] API admin: products, categories, option-groups + upload de imagens
- [x] Cache Redis + invalidação
- [x] Seed de cardápio demo (`python manage.py seed_dev`)
- [x] Testes PriceCalculator + API catálogo

Próximo: **Sprint 4 — Frontend Base e Design System**
