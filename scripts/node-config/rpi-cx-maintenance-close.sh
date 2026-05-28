#!/usr/bin/env bash
# rpi-cx-maintenance-close.sh - Close LEGACY CX Programmer NAT diagnostic path.
#
# Ejecutar manualmente en la RPi, como root/sudo.
# Elimina solo reglas marcadas como alumbrado-cx-maintenance y desactiva forwarding.

set -euo pipefail

PLC_IP="${PLC_IP:-192.168.250.1}"
LENOVO_IP="${LENOVO_IP:-10.0.0.2}"
FINS_PORT="${FINS_PORT:-9600}"
OT_IF="${OT_IF:-}"
LENOVO_IF="${LENOVO_IF:-}"
COMMENT="alumbrado-cx-maintenance"

require_root() {
    if [[ "${EUID}" -ne 0 ]]; then
        echo "ERROR Ejecutar como root: sudo OT_IF=<ot_if> LENOVO_IF=<lenovo_if> bash $0"
        exit 1
    fi
}

require_var() {
    local name="$1"
    local value="$2"
    if [[ -z "$value" ]]; then
        echo "ERROR Falta $name. Usar los mismos valores que en la apertura."
        exit 1
    fi
}

delete_filter_rule() {
    local args=("$@")
    if iptables -C FORWARD "${args[@]}" 2>/dev/null; then
        iptables -D FORWARD "${args[@]}"
        echo "OK   Regla FORWARD eliminada: ${args[*]}"
    else
        echo "SKIP Regla FORWARD no existe: ${args[*]}"
    fi
}

delete_nat_rule() {
    local args=("$@")
    if iptables -t nat -C POSTROUTING "${args[@]}" 2>/dev/null; then
        iptables -t nat -D POSTROUTING "${args[@]}"
        echo "OK   Regla NAT eliminada: ${args[*]}"
    else
        echo "SKIP Regla NAT no existe: ${args[*]}"
    fi
}

require_root
require_var OT_IF "$OT_IF"
require_var LENOVO_IF "$LENOVO_IF"

echo "=== Cierre mantenimiento CX Programmer ==="

delete_filter_rule \
    -i "$LENOVO_IF" -o "$OT_IF" \
    -s "$LENOVO_IP" -d "$PLC_IP" \
    -p udp --dport "$FINS_PORT" \
    -m comment --comment "$COMMENT" -j ACCEPT

delete_filter_rule \
    -i "$OT_IF" -o "$LENOVO_IF" \
    -s "$PLC_IP" -d "$LENOVO_IP" \
    -p udp --sport "$FINS_PORT" \
    -m conntrack --ctstate ESTABLISHED,RELATED \
    -m comment --comment "$COMMENT" -j ACCEPT

delete_nat_rule \
    -o "$OT_IF" \
    -s "$LENOVO_IP" -d "$PLC_IP" \
    -p udp --dport "$FINS_PORT" \
    -m comment --comment "$COMMENT" -j MASQUERADE

sysctl -w net.ipv4.ip_forward=0

echo ""
echo "=== Verificacion ==="
cat /proc/sys/net/ipv4/ip_forward
if iptables -S FORWARD | grep "$COMMENT"; then
    echo "WARN Quedan reglas FORWARD de mantenimiento."
else
    echo "OK   Sin reglas FORWARD de mantenimiento."
fi
if iptables -t nat -S POSTROUTING | grep "$COMMENT"; then
    echo "WARN Quedan reglas NAT de mantenimiento."
else
    echo "OK   Sin reglas NAT de mantenimiento."
fi
