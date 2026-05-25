#!/usr/bin/env bash
# rpi-enable-publisher.sh — Activar publisher FINS→MQTT contra PLC real
# Ejecutar en RPi SOLO cuando eth0 este conectado fisicamente a la red OT.
# Prerequisito: .env en ~/dev/alumbrado-gateway con PLC_IP, FINS_SOURCE_NODE, FINS_DEST_NODE.

set -euo pipefail
REPO="/home/master/dev/alumbrado-gateway"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="alumbrado-publisher-dev.service"
SERVICE_SRC="$SCRIPT_DIR/$SERVICE_NAME"
SERVICE_DST="/etc/systemd/system/$SERVICE_NAME"

find_temp_ssh_rule() {
    sudo ufw status numbered |
        awk '/\[ *[0-9]+\]/ && /22\/tcp/ && /ALLOW IN/ && /192\.168\.250\.200/ { print }'
}

delete_temp_ssh_rule() {
    mapfile -t matches < <(find_temp_ssh_rule)
    case "${#matches[@]}" in
        0)
            echo "SKIP  Regla SSH temporal no encontrada (ya eliminada)."
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
            echo "OK  Regla temporal eliminada."
            ;;
        *)
            echo "ERROR Hay varias reglas UFW candidatas para 192.168.250.200:22/tcp."
            printf '  %s\n' "${matches[@]}"
            echo "Abortando para no borrar una regla incorrecta."
            exit 1
            ;;
    esac
}

echo "=== [1/5] Eliminando regla SSH temporal eth0 (192.168.250.200) ==="
delete_temp_ssh_rule

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
python -m acquisition.publisher --max-cycles 1

echo ""
echo "=== [5/5] Revisando resultado ==="
echo ">>> Si el payload anterior tiene al menos un bloque con status=ok,"
echo "    confirmar para habilitar el servicio (Enter) o Ctrl+C para abortar."
read -r

echo ""
echo "=== Instalando unidad systemd versionada: $SERVICE_NAME ==="
if [[ ! -f "$SERVICE_SRC" ]]; then
    echo "ERROR No existe $SERVICE_SRC. No se habilita systemd sin unidad versionada."
    exit 1
fi
sudo cp "$SERVICE_SRC" "$SERVICE_DST"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start  "$SERVICE_NAME"
sleep 3
sudo systemctl status "$SERVICE_NAME" --no-pager -l
echo ""
echo "Para seguir logs en vivo:"
echo "  sudo journalctl -u $SERVICE_NAME -f"
