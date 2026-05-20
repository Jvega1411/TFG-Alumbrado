#!/usr/bin/env bash
# rpi-cx-maintenance-open.sh - Abrir ventana temporal CX Programmer Lenovo -> PLC.
#
# Ejecutar manualmente en la RPi, como root/sudo, solo durante mantenimiento OT.
# No persiste cambios tras reinicio. Cerrar siempre con rpi-cx-maintenance-close.sh.
#
# Ejemplo:
#   sudo OT_IF=eth0 LENOVO_IF=enx6083e7ac98fb \
#     bash scripts/node-config/rpi-cx-maintenance-open.sh

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
        echo "ERROR Falta $name. No se asumen interfaces en red OT."
        echo "Ejemplo: sudo OT_IF=eth0 LENOVO_IF=enx6083e7ac98fb bash $0"
        exit 1
    fi
}

require_interface() {
    local iface="$1"
    if ! ip link show dev "$iface" > /dev/null 2>&1; then
        echo "ERROR No existe la interfaz: $iface"
        exit 1
    fi
}

require_no_bridge() {
    local bridges
    bridges="$(ip -o link show type bridge || true)"
    if [[ -n "$bridges" && "${ALLOW_BRIDGE:-0}" != "1" ]]; then
        echo "ERROR Hay interfaces bridge activas. No se abre mantenimiento con bridge."
        echo "$bridges"
        echo "Si esta revisado y autorizado, repetir con ALLOW_BRIDGE=1."
        exit 1
    fi
}

check_route_uses_iface() {
    local target="$1"
    local iface="$2"
    local route
    route="$(ip route get "$target" 2>/dev/null || true)"
    if [[ -z "$route" || "$route" != *" dev $iface "* ]]; then
        echo "ERROR La ruta hacia $target no usa $iface."
        echo "Ruta actual: ${route:-sin ruta}"
        exit 1
    fi
}

add_filter_rule() {
    local args=("$@")
    if iptables -C FORWARD "${args[@]}" 2>/dev/null; then
        echo "SKIP Regla FORWARD ya existe: ${args[*]}"
    else
        iptables -I FORWARD 1 "${args[@]}"
        echo "OK   Regla FORWARD creada: ${args[*]}"
    fi
}

add_nat_rule() {
    local args=("$@")
    if iptables -t nat -C POSTROUTING "${args[@]}" 2>/dev/null; then
        echo "SKIP Regla NAT ya existe: ${args[*]}"
    else
        iptables -t nat -I POSTROUTING 1 "${args[@]}"
        echo "OK   Regla NAT creada: ${args[*]}"
    fi
}

warn_udp_listener() {
    if command -v ss > /dev/null 2>&1; then
        local listeners
        listeners="$(ss -H -lunp "sport = :$FINS_PORT" 2>/dev/null || true)"
        if [[ -n "$listeners" ]]; then
            echo "WARN Hay un proceso local escuchando UDP/$FINS_PORT en la RPi."
            echo "     Pausar adquisicion FINS antes de usar CX Programmer:"
            echo "$listeners"
        fi
    fi
}

require_root
require_var OT_IF "$OT_IF"
require_var LENOVO_IF "$LENOVO_IF"

if [[ "$OT_IF" == "$LENOVO_IF" ]]; then
    echo "ERROR OT_IF y LENOVO_IF no pueden ser la misma interfaz."
    exit 1
fi

require_interface "$OT_IF"
require_interface "$LENOVO_IF"
require_no_bridge
check_route_uses_iface "$PLC_IP" "$OT_IF"
check_route_uses_iface "$LENOVO_IP" "$LENOVO_IF"
warn_udp_listener

echo "=== Apertura mantenimiento CX Programmer ==="
echo "PLC:        $PLC_IP UDP/$FINS_PORT"
echo "Lenovo:     $LENOVO_IP"
echo "OT_IF:      $OT_IF"
echo "LENOVO_IF:  $LENOVO_IF"
echo ""

sysctl -w net.ipv4.ip_forward=1
sysctl -w net.ipv4.conf.all.send_redirects=0

add_filter_rule \
    -i "$LENOVO_IF" -o "$OT_IF" \
    -s "$LENOVO_IP" -d "$PLC_IP" \
    -p udp --dport "$FINS_PORT" \
    -m comment --comment "$COMMENT" -j ACCEPT

add_filter_rule \
    -i "$OT_IF" -o "$LENOVO_IF" \
    -s "$PLC_IP" -d "$LENOVO_IP" \
    -p udp --sport "$FINS_PORT" \
    -m conntrack --ctstate ESTABLISHED,RELATED \
    -m comment --comment "$COMMENT" -j ACCEPT

add_nat_rule \
    -o "$OT_IF" \
    -s "$LENOVO_IP" -d "$PLC_IP" \
    -p udp --dport "$FINS_PORT" \
    -m comment --comment "$COMMENT" -j MASQUERADE

echo ""
echo "=== Verificacion ==="
cat /proc/sys/net/ipv4/ip_forward
iptables -S FORWARD | grep "$COMMENT" || true
iptables -t nat -S POSTROUTING | grep "$COMMENT" || true
echo ""
echo "VENTANA ABIERTA. Cerrar al terminar con:"
echo "  sudo OT_IF=$OT_IF LENOVO_IF=$LENOVO_IF bash scripts/node-config/rpi-cx-maintenance-close.sh"
