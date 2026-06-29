#!/usr/bin/env bash

set -euo pipefail

readonly NODE_MAJOR=20
readonly POSTGRES_VERSION=16
readonly APP_ROOT="/var/www/oge-math"
readonly ENV_DIR="/etc/oge-math"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root."
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get upgrade -y

apt-get install -y \
  ca-certificates \
  curl \
  git \
  gnupg \
  lsb-release \
  software-properties-common

if [[ ! -f /etc/apt/keyrings/nodesource.gpg ]]; then
  install -d -m 0755 /etc/apt/keyrings
  curl -fsSL "https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key" \
    | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
fi

cat >/etc/apt/sources.list.d/nodesource.list <<EOF
deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main
EOF

apt-get update

apt-get install -y \
  python3 \
  python3-dev \
  python3-pip \
  python3-venv \
  python3.12 \
  python3.12-dev \
  python3.12-venv \
  nodejs \
  nginx \
  certbot \
  python3-certbot-nginx \
  postgresql \
  postgresql-contrib \
  "postgresql-${POSTGRES_VERSION}"

systemctl enable --now postgresql
systemctl enable --now nginx

install -d -m 0755 "${APP_ROOT}"
install -d -m 0755 "${APP_ROOT}/frontend"
install -d -m 0755 "${APP_ROOT}/backend"
install -d -m 0750 "${ENV_DIR}"

python3.12 --version
node --version
psql --version
nginx -v
certbot --version

echo "Initial server bootstrap completed."
