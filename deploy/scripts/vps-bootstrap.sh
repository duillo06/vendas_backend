#!/usr/bin/env bash
# Bootstrap inicial da VPS (Hostinger ou qualquer Ubuntu/Debian).
# Rode UMA VEZ no servidor, como root ou com sudo:
#   curl -fsSL … | bash   OU   bash deploy/scripts/vps-bootstrap.sh
set -euo pipefail

echo "==> Atualizando pacotes"
apt-get update -y
apt-get install -y ca-certificates curl git ufw

echo "==> Docker"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
fi

# Compose plugin costuma vir com get.docker.com; garante o comando
docker compose version >/dev/null

echo "==> Usuário deploy (opcional — se existir \$SUDO_USER, adiciona ao grupo docker)"
if [[ -n "${SUDO_USER:-}" ]]; then
  usermod -aG docker "$SUDO_USER" || true
fi

echo "==> Firewall básico (SSH + HTTP/HTTPS)"
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable || true

echo "==> Pasta do projeto"
mkdir -p /opt/foodservice
chown "${SUDO_USER:-root}:${SUDO_USER:-root}" /opt/foodservice

echo
echo "Pronto. Próximos passos no servidor:"
echo "  cd /opt/foodservice"
echo "  git clone <url-vendas_backend> vendas_backend"
echo "  git clone <url-vendas_frontend> vendas_frontend"
echo "  cd vendas_backend"
echo "  cp .env.production.example .env.production   # edite secrets + BASE_DOMAIN"
echo "  bash deploy/scripts/remote-deploy.sh"
echo
echo "Depois configure secrets no GitHub (environment production):"
echo "  PRODUCTION_HOST, PRODUCTION_USER, PRODUCTION_SSH_KEY"
