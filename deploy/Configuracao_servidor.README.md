# Deploy Food Service — Hostinger VPS (receita prática)

Guia do que fizemos para subir o projeto no **KVM 2** (Ubuntu 24.04) com domínio **`pediu.cloud`**, Docker e deploy via GitHub Actions.

Guia mais longo / arquitetura: [`DEPLOY.md`](./DEPLOY.md).

**Repos:** `duillo06/vendas_backend` + `duillo06/vendas_frontend`  
**VPS:** `/opt/foodservice/`  
**IP de referência:** `2.25.119.30` (troque se mudar de servidor)

---

## Visão geral

```
Seu PC --SSH chave--> VPS Hostinger
                         │
                         ├── /opt/foodservice/vendas_backend
                         ├── /opt/foodservice/vendas_frontend
                         └── Docker: Caddy + Nginx + API + Celery + Postgres + Redis

git push origin main  -->  GitHub Actions  --SSH-->  remote-deploy.sh na VPS
```

| Componente | Função |
|------------|--------|
| **Caddy** | HTTPS (Let's Encrypt) + roteia `api` / `admin` / `demo` |
| **Nginx** | Serve storefront + backoffice e proxy `/api` |
| **API (Gunicorn)** | Django |
| **Celery** | Filas (e-mail, WhatsApp, etc.) |
| **Postgres / Redis** | Banco e cache/filas |

---

## 0. No seu PC — acesso SSH ao VPS

Gera chave (uma vez), se ainda não tiver:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_hostinger -N ""
```

Cadastra a **pública** (`*.pub`) no painel Hostinger na criação do VPS (ou depois em SSH keys).  
Define senha root no painel (obrigatório na Hostinger) e guarda.

Conectar:

```bash
ssh -i ~/.ssh/id_ed25519_hostinger root@SEU_IP
```

Primeira vez: digite `yes` no fingerprint do host.

---

## 1. Bootstrap da VPS (uma vez)

No servidor (já no SSH):

```bash
# Instala Docker, Compose, git, UFW (22/80/443) e cria /opt/foodservice
# Se o repo ainda não estiver na VPS, copie o script do PC:
```

Do **seu PC**:

```bash
scp -i ~/.ssh/id_ed25519_hostinger \
  ~/projetos/vendas_backend/deploy/scripts/vps-bootstrap.sh \
  root@SEU_IP:/tmp/vps-bootstrap.sh

ssh -i ~/.ssh/id_ed25519_hostinger root@SEU_IP 'bash /tmp/vps-bootstrap.sh'
```

**O que faz:** atualiza pacotes, instala Docker, libera SSH/HTTP/HTTPS no firewall, cria `/opt/foodservice`.

Swap recomendado (4–8 GB de RAM):

```bash
# No VPS — evita OOM no build Docker
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

---

## 2. Chaves Git no servidor (Deploy keys)

O GitHub **não deixa** a mesma Deploy key em dois repos. Por isso são **duas** chaves.

No VPS:

```bash
# Backend
ssh-keygen -t ed25519 -C "vps-foodservice-backend" -f ~/.ssh/foodservice_deploy -N ""

# Frontend
ssh-keygen -t ed25519 -C "vps-foodservice-frontend" -f ~/.ssh/foodservice_deploy_frontend -N ""

# Chave para o GitHub Actions entrar na VPS
ssh-keygen -t ed25519 -C "github-actions-foodservice" -f ~/.ssh/github_actions_vps -N ""
cat ~/.ssh/github_actions_vps.pub >> ~/.ssh/authorized_keys

# SSH config — cada Host usa uma chave
cat > ~/.ssh/config <<'EOF'
Host github.com-vendas-backend
  HostName github.com
  User git
  IdentityFile ~/.ssh/foodservice_deploy
  IdentitiesOnly yes

Host github.com-vendas-frontend
  HostName github.com
  User git
  IdentityFile ~/.ssh/foodservice_deploy_frontend
  IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config ~/.ssh/foodservice_deploy ~/.ssh/foodservice_deploy_frontend ~/.ssh/github_actions_vps

ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts
```

Mostrar públicas para colar no GitHub:

```bash
echo "=== BACKEND ===" && cat ~/.ssh/foodservice_deploy.pub
echo "=== FRONTEND ===" && cat ~/.ssh/foodservice_deploy_frontend.pub
```

No GitHub (por repo):

1. `vendas_backend` → **Settings → Deploy keys → Add** → cola chave backend → **write desmarcado**
2. `vendas_frontend` → mesma coisa com a chave frontend

---

## 3. Clonar os repos na VPS

```bash
cd /opt/foodservice

git clone git@github.com-vendas-backend:duillo06/vendas_backend.git vendas_backend
git clone git@github.com-vendas-frontend:duillo06/vendas_frontend.git vendas_frontend
```

**O que faz:** baixa o código usando as Deploy keys (Hosts do `~/.ssh/config`).

---

## 4. Variáveis de produção

```bash
cd /opt/foodservice/vendas_backend
cp .env.production.example .env.production
nano .env.production
```

Ajuste no mínimo:

| Variável | Exemplo |
|----------|---------|
| `BASE_DOMAIN` | `pediu.cloud` |
| `SECRET_KEY` | string longa aleatória |
| `POSTGRES_PASSWORD` | senha forte |
| `ALLOWED_HOSTS` | `.pediu.cloud,api.pediu.cloud,admin.pediu.cloud,demo.pediu.cloud` |
| `CORS_ALLOWED_ORIGINS` / `CSRF_TRUSTED_ORIGINS` | URLs `https://…` do domínio |
| `STOREFRONT_BASE_DOMAIN` | mesmo que `BASE_DOMAIN` |

Gerar secrets rápido:

```bash
openssl rand -hex 32   # SECRET_KEY
openssl rand -hex 24   # POSTGRES_PASSWORD
```

**Não commitar** `.env.production`.

---

## 5. DNS (Hostinger → Domínios)

| Tipo | Nome | Conteúdo |
|------|------|----------|
| A | `api` | IP da VPS |
| A | `admin` | IP da VPS |
| A | `demo` | IP da VPS |
| A | `@` | IP da VPS (opcional; raiz do domínio) |

Conferir do PC:

```bash
dig +short api.pediu.cloud A
dig +short admin.pediu.cloud A
dig +short demo.pediu.cloud A
```

Sem DNS certo o Caddy **não** emite certificado HTTPS.

---

## 6. Secrets do GitHub Actions (deploy automático)

Nos **dois** repos → **Settings → Environments → `production`**:

| Secret | Valor |
|--------|--------|
| `PRODUCTION_HOST` | IP da VPS |
| `PRODUCTION_USER` | `root` |
| `PRODUCTION_SSH_KEY` | chave **privada** do Actions |

Pegar a privada **do seu PC** (não precisa estar logado no VPS antes):

```bash
ssh -i ~/.ssh/id_ed25519_hostinger root@SEU_IP 'cat ~/.ssh/github_actions_vps'
```

Copiar do `BEGIN` até o `END` e colar no secret.

**O que faz:** em todo `push` em `main`, o Actions SSH na VPS e roda `remote-deploy.sh`.

Workflows:

- backend: `.github/workflows/deploy-production.yml`
- frontend: `.github/workflows/deploy-production.yml`

---

## 7. Primeiro deploy (manual)

No VPS:

```bash
cd /opt/foodservice/vendas_backend
bash deploy/scripts/remote-deploy.sh
```

**O que faz:**

1. `git pull` backend + frontend (`main`)
2. Gera Nginx + Caddy a partir do `BASE_DOMAIN`
3. `docker compose up -d --build`
4. Roda migrations

Acompanhar:

```bash
docker compose -f deploy/docker-compose.prod.yml ps
docker compose -f deploy/docker-compose.prod.yml logs -f --tail=80 api
curl -sS -o /dev/null -w "%{http_code}\n" https://api.pediu.cloud/api/v1/health/
```

URLs:

| App | URL |
|-----|-----|
| API health | https://api.pediu.cloud/api/v1/health/ |
| Backoffice | https://admin.pediu.cloud |
| Storefront demo | https://demo.pediu.cloud |

---

## 8. Deploy no dia a dia

No PC, depois de commit:

```bash
git push origin main
```

O Actions faz o resto (se os secrets estiverem certos).

Redeploy manual na VPS (sem passar pelo Actions):

```bash
cd /opt/foodservice/vendas_backend
bash deploy/scripts/remote-deploy.sh
```

---

## 9. Tenant demo / onboarding

Sempre com `--env-file .env.production` (senão: `POSTGRES_PASSWORD obrigatório`):

```bash
cd /opt/foodservice/vendas_backend
COMPOSE="docker compose -f deploy/docker-compose.prod.yml --env-file .env.production"

$COMPOSE exec api python manage.py onboard_tenant \
  --trade-name "Loja Demo" \
  --subdomain demo \
  --email contato@demo.local \
  --phone "(00) 00000-0000" \
  --owner-email admin@demo.local \
  --owner-password "troque-esta-senha"
```

Seed demo (opcional — smoke test, não cliente real):

```bash
$COMPOSE exec api python manage.py seed_locations
$COMPOSE exec api python manage.py seed_demo_pizzaria
# $COMPOSE exec api python manage.py seed_demo_pizzaria --skip-images
```

Tenant novo: criar registro DNS `A` + bloco no `deploy/caddy/Caddyfile.template` + rodar o deploy de novo.

---

## 10. Comandos úteis

```bash
cd /opt/foodservice/vendas_backend
COMPOSE="docker compose -f deploy/docker-compose.prod.yml --env-file .env.production"

# status dos containers
$COMPOSE ps

# logs
$COMPOSE logs -f --tail=100 api
$COMPOSE logs -f --tail=50 caddy

# parar / subir
$COMPOSE down
$COMPOSE up -d

# backup Postgres
$COMPOSE exec -T db \
  pg_dump -U foodservice foodservice > backup-$(date +%F).sql
```

> `remote-deploy.sh` já inclui `--env-file`. Em `exec` / `ps` / `logs` manuais, passe o flag.

---

## Checklist rápido (servidor novo)

1. [ ] Ubuntu + SSH com chave
2. [ ] `vps-bootstrap.sh` + swap
3. [ ] 2 Deploy keys + `~/.ssh/config` + chave Actions no `authorized_keys`
4. [ ] Clone em `/opt/foodservice/`
5. [ ] `.env.production` preenchido
6. [ ] DNS `api` / `admin` / `demo` → IP
7. [ ] Secrets `PRODUCTION_*` nos dois repos
8. [ ] `bash deploy/scripts/remote-deploy.sh`
9. [ ] Health + admin + demo no navegador

---

## Observações

- **Segurança básica do bootstrap:** Docker + UFW (22/80/443). Ainda não inclui fail2ban, desligar senha root, etc.
- **Build do frontend** roda dentro do Docker (Nginx image); erro de TypeScript quebra o deploy inteiro.
- Confs geradas (`deploy/nginx/default.conf`, `deploy/caddy/Caddyfile`) não devem travar o `git pull` — o script/Actions descartam antes do pull.
- Evolution API **não** entra neste Compose; configurar depois (URL/key no env) se for WhatsApp hospedado.
