#!/usr/bin/env bash
# rpi-enable-publisher.sh — Activar publisher FINS→MQTT contra PLC real
# Ejecutar en RPi SOLO cuando eth0 este conectado fisicamente a la red OT.
# Prerequisito: .env en ~/dev/alumbrado-gateway con PLC_IP, FINS_SOURCE_NODE, FINS_DEST_NODE.

set -euo pipefail
REPO="/home/master/dev/alumbrado-gateway"

echo "=== [1/5] Eliminando regla SSH temporal eth0 (192.168.250.200) ==="
if sudo ufw status numbered | grep -q "192.168.250.200"; then
    # La regla temporal siempre fue la [1]
    sudo ufw delete 1
    echo "OK  Regla temporal eliminada."
else
    echo "SKIP  Regla SSH temporal no encontrada (ya eliminada)."
fi

echo ""
echo "=== [2/5] UFW actual ==="
sudo ufw status numbered

echo ""
echo "=== [3/5] Verificando conectividad OT (ping PLC) ==="
if ping -c 3 -W 2 192.168.250.1 > /dev/null 2>&1; then
    echo "OK  PLC 192.168.250.1 responde."
else
    echo "ERROR  El PLC no responde. Verificar que eth0 esta en la red OT antes de continuar."
    exit 1
fi

echo ""
echo "=== [4/5] Prueba manual max_cycles=1 ==="
cd "$REPO"
. .venv/bin/activate
python - <<'PY'
from acquisition.publisher import run_publisher
run_publisher(max_cycles=1)
PY

echo ""
echo "=== [5/5] Revisando resultado ==="
echo ">>> Si el payload anterior tiene al menos un bloque con status=ok,"
echo "    confirmar para habilitar el servicio (Enter) o Ctrl+C para abortar."
read -r

echo ""
sudo systemctl enable alumbrado-publisher-dev.service
sudo systemctl start  alumbrado-publisher-dev.service
sleep 3
sudo systemctl status alumbrado-publisher-dev.service --no-pager -l
echo ""
echo "Para seguir logs en vivo:"
echo "  sudo journalctl -u alumbrado-publisher-dev.service -f"
