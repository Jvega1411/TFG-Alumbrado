#!/usr/bin/env bash
# rpi-ufw-cleanup.sh — Eliminar regla SSH temporal (laptop OT) y verificar UFW final
# Ejecutar en RPi via: bash ~/dev/alumbrado-gateway/scripts/node-config/rpi-ufw-cleanup.sh
# Prerequisito: acceso SSH ya funcional via Lenovo (ssh master@10.0.0.1)

set -euo pipefail

find_temp_ssh_rule() {
    sudo ufw status numbered |
        awk '/\[ *[0-9]+\]/ && /22\/tcp/ && /ALLOW IN/ && /192\.168\.250\.200/ { print }'
}

delete_temp_ssh_rule() {
    mapfile -t matches < <(find_temp_ssh_rule)
    case "${#matches[@]}" in
        0)
            echo "SKIP  Regla no encontrada (ya eliminada previamente)."
            ;;
        1)
            local line="${matches[0]}"
            local number
            number="$(printf '%s\n' "$line" | sed -E 's/^\[ *([0-9]+)\].*/\1/')"
            if [[ -z "$number" || "$number" == "$line" ]]; then
                echo "ERROR No se pudo extraer el indice UFW de la regla encontrada:"
                echo "  $line"
                exit 1
            fi
            echo "Regla encontrada:"
            echo "  $line"
            sudo ufw --force delete "$number"
            echo "OK  Regla eliminada."
            ;;
        *)
            echo "ERROR Hay varias reglas UFW candidatas para 192.168.250.200:22/tcp."
            printf '  %s\n' "${matches[@]}"
            echo "Abortando para no borrar una regla incorrecta."
            exit 1
            ;;
    esac
}

echo "=== UFW actual ==="
sudo ufw status numbered

echo ""
echo "=== Eliminando regla SSH temporal eth0 (192.168.250.200) ==="
delete_temp_ssh_rule

echo ""
echo "=== UFW final ==="
sudo ufw status numbered

echo ""
echo "Reglas esperadas:"
echo "  [1] 22/tcp on wlan0           ALLOW IN Anywhere  (SSH emergencia hotspot)"
echo "  [2] 10.0.0.2 1883/tcp         ALLOW OUT enx6083e7ac98fb  (MQTT hacia Lenovo)"
echo "  [3] 22/tcp on enx6083e7ac98fb ALLOW IN 10.0.0.2  (SSH mantenimiento Lenovo)"
echo "  [4] Anywhere on enx6083e7ac98fb DENY IN Anywhere (bloqueo general IT inbound)"
