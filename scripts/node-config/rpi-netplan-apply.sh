#!/usr/bin/env bash
# rpi-netplan-apply.sh — Aplicar netplan estatico para eth0 (red OT / PLC)
# Ejecutar en RPi via: bash ~/dev/alumbrado-gateway/scripts/node-config/rpi-netplan-apply.sh
#
# Si quieres una IP distinta a 192.168.250.220, edita NETPLAN_IP antes de ejecutar.
# La IP del PLC (192.168.250.1) debe estar en la misma /24.

set -euo pipefail

NETPLAN_IP="${NETPLAN_IP:-192.168.250.220}"
NETPLAN_FILE="/etc/netplan/50-ot-eth0.yaml"
REPO_YAML="$(dirname "$0")/rpi-netplan-ot-static.yaml"

echo "=== eth0 actual ==="
ip -br addr show eth0

echo ""

# Verificar si ya existe un fichero netplan gestionando eth0
if grep -rl "eth0" /etc/netplan/ 2>/dev/null | grep -v "$NETPLAN_FILE"; then
    echo "AVISO: Existe otro fichero netplan con eth0:"
    grep -rl "eth0" /etc/netplan/ | grep -v "$NETPLAN_FILE"
    echo "Revisalo antes de continuar para evitar conflictos."
    echo "Pulsa Enter para continuar o Ctrl+C para abortar."
    read -r
fi

echo "=== Escribiendo $NETPLAN_FILE con IP $NETPLAN_IP/24 ==="
sudo tee "$NETPLAN_FILE" > /dev/null <<EOF
network:
  version: 2
  renderer: networkd
  ethernets:
    eth0:
      dhcp4: false
      addresses:
        - ${NETPLAN_IP}/24
      routes: []
      nameservers:
        addresses: []
EOF

sudo chmod 600 "$NETPLAN_FILE"
echo "OK  Fichero escrito y permisos 600 aplicados."

echo ""
echo "=== Generando y aplicando netplan ==="
sudo netplan generate
sudo netplan apply

sleep 2
echo ""
echo "=== Verificacion post-apply ==="
ip -br addr show eth0
ping -c 2 192.168.250.1 && echo "OK  PLC 192.168.250.1 responde." || echo "WARN  PLC no responde (normal si aun no esta conectado eth0 al switch OT)."
