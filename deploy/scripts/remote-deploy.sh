#!/usr/bin/env bash
# Deploy na VPS — puxa Git, rebuilda Docker, migrate.
# Uso no servidor:
#   cd /opt/foodservice/vendas_backend && bash deploy/scripts/remote-deploy.sh
# Vars opcionais:
#   DEPLOY_BRANCH=main
#   SKIP_FRONTEND=1   — não rebuilda nginx/SPA
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FRONTEND_ROOT="$(cd "$ROOT/../vendas_frontend" 2>/dev/null && pwd || true)"
BRANCH="${DEPLOY_BRANCH:-main}"
COMPOSE=(docker compose -f "$ROOT/deploy/docker-compose.prod.yml" --env-file "$ROOT/.env.production")

cd "$ROOT"

if [[ ! -f "$ROOT/.env.production" ]]; then
  echo "ERRO: falta $ROOT/.env.production — copie de .env.production.example e preencha."
  exit 1
fi

# shellcheck disable=SC1091
set -a
# shellcheck source=/dev/null
source "$ROOT/.env.production"
set +a

BASE_DOMAIN="${BASE_DOMAIN:-foodservice.app}"
echo "==> Domínio base: $BASE_DOMAIN"

echo "==> Git pull backend ($BRANCH)"
# confs geradas na VPS não podem bloquear o pull
git checkout -- deploy/nginx/default.conf deploy/caddy/Caddyfile 2>/dev/null || true
git fetch origin
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

if [[ -z "${SKIP_FRONTEND:-}" ]]; then
  if [[ -n "$FRONTEND_ROOT" && -d "$FRONTEND_ROOT/.git" ]]; then
    echo "==> Git pull frontend ($BRANCH)"
    git -C "$FRONTEND_ROOT" fetch origin
    git -C "$FRONTEND_ROOT" checkout "$BRANCH"
    git -C "$FRONTEND_ROOT" pull --ff-only origin "$BRANCH"
  else
    echo "AVISO: vendas_frontend não encontrado em $ROOT/../vendas_frontend — nginx pode falhar no build."
  fi
fi

# Nginx com o domínio real (template → conf)
# ponto vira \. no regex; no sed o \ precisa ser dobrado na substituição
BASE_DOMAIN_ESCAPED="${BASE_DOMAIN//./\\.}"
BASE_DOMAIN_ESCAPED_SED="${BASE_DOMAIN_ESCAPED//\\/\\\\}"
TEMPLATE="$ROOT/deploy/nginx/default.conf.template"
CONF="$ROOT/deploy/nginx/default.conf"
if [[ -f "$TEMPLATE" ]]; then
  echo "==> Gerando nginx default.conf para *.$BASE_DOMAIN"
  sed -e "s/__BASE_DOMAIN_ESCAPED__/${BASE_DOMAIN_ESCAPED_SED}/g" \
      -e "s/__BASE_DOMAIN__/${BASE_DOMAIN}/g" \
      "$TEMPLATE" > "$CONF"
fi

# Caddyfile com o mesmo domínio
CADDY_TPL="$ROOT/deploy/caddy/Caddyfile.template"
CADDY_OUT="$ROOT/deploy/caddy/Caddyfile"
if [[ -f "$CADDY_TPL" ]]; then
  echo "==> Gerando Caddyfile"
  sed "s/__BASE_DOMAIN__/${BASE_DOMAIN}/g" "$CADDY_TPL" > "$CADDY_OUT"
fi

export VITE_API_BASE_URL="${VITE_API_BASE_URL:-https://api.${BASE_DOMAIN}/api/v1}"
export VITE_DEFAULT_TENANT_SUBDOMAIN="${VITE_DEFAULT_TENANT_SUBDOMAIN:-demo}"
export BASE_DOMAIN

echo "==> Docker compose up --build"
"${COMPOSE[@]}" up -d --build --remove-orphans

echo "==> Migrate (garantia — entrypoint também migra)"
"${COMPOSE[@]}" exec -T api python manage.py migrate --noinput

echo "==> Catálogo de estados e cidades"
"${COMPOSE[@]}" exec -T api python manage.py seed_locations --if-empty

echo "==> Health"
sleep 2
curl -fsS "http://127.0.0.1:80/api/v1/health/" >/dev/null 2>&1 \
  || "${COMPOSE[@]}" exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/')" \
  || echo "AVISO: health check falhou — confira: docker compose -f deploy/docker-compose.prod.yml logs --tail=80"

echo "==> Deploy ok ($(date -Iseconds))"
