#!/usr/bin/env bash
# rpi-ufw-cleanup.sh — Eliminar regla SSH temporal (laptop OT) y verificar UFW final
# Ejecutar en RPi via: bash ~/dev/alumbrado-gateway/scripts/node-config/rpi-ufw-cleanup.sh
# Prerequisito: acceso SSH ya funcional via Lenovo (ssh master@10.0.0.1)

set -euo pipefail

echo "=== UFW actual ==="
sudo ufw status numbered

echo ""
echo "=== Eliminando regla SSH temporal eth0 (192.168.250.200) ==="
if sudo ufw status numbered | grep -q "192.168.250.200"; then
    sudo ufw delete 1
    echo "OK  Regla eliminada."
else
    echo "SKIP  Regla no encontrada (ya eliminada previamente)."
fi

echo ""
echo "=== UFW final ==="
sudo ufw status numbered

echo ""
echo "Reglas esperadas:"
echo "  [1] 22/tcp on wlan0           ALLOW IN Anywhere  (SSH emergencia hotspot)"
echo "  [2] 10.0.0.2 1883/tcp         ALLOW OUT enx6083e7ac98fb  (MQTT hacia Lenovo)"
echo "  [3] 22/tcp on enx6083e7ac98fb ALLOW IN 10.0.0.2  (SSH mantenimiento Lenovo)"
echo "  [4] Anywhere on enx6083e7ac98fb DENY IN Anywhere (bloqueo general IT inbound)"
