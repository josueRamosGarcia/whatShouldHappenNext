#!/usr/bin/env bash
set -e

echo ""
echo "Desplegando ..."
echo ""

# 1. Actualizar repositorios e instalar paquetes base
apt-get update -y
apt-get install -y git python3-pip python3-venv curl ufw

# 2. Configurar Firewall básico (SSH y HTTP)
ufw allow 22/tcp
ufw allow 80/tcp
ufw --force enable

# 3. Directorio de la aplicación
APP_DIR="/opt/whatShouldHappenNext"
REPO_URL="https://github.com/josueRamosGarcia/whatShouldHappenNext.git"

if [ ! -d "$APP_DIR" ]; then
    echo "Clonando repositorio en $APP_DIR..."
    git clone "$REPO_URL" "$APP_DIR"
else
    echo "Actualizando repositorio ..."
    cd "$APP_DIR"
    git pull origin main || true
fi

cd "$APP_DIR"

# 4. Crear y configurar entorno virtual
if [ ! -d "$APP_DIR/.venv" ]; then
    echo "Creando entorno virtual..."
    python3 -m venv "$APP_DIR/.venv"
fi

echo "Instalando dependencias de Python..."
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r requirements.txt

# 5. Crear servicio Systemd para mantener Streamlit siempre activo en puerto 80
SERVICE_FILE="/etc/systemd/system/what-should-happen-next.service"

cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=What Should Happen Next - Streamlit Web App
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
EnvironmentFile=-$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/streamlit run app.py --server.port=80 --server.address=0.0.0.0 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 6. Recargar systemd e iniciar servicio
systemctl daemon-reload
systemctl enable what-should-happen-next.service
systemctl restart what-should-happen-next.service

echo "=========================================================="
echo "¡Despliegue completado con éxito!"
PUBLIC_IP=$(curl -s https://api.ipify.org || hostname -I | awk '{print $1}')
echo "Aplicación en vivo: http://${PUBLIC_IP}"
echo "=========================================================="
