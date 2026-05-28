#!/usr/bin/env bash
# rpi-cx-proxyarp-open.sh - Open tested CX-One/CX Programmer path without NAT.
#
# Run manually on the RPi as root/sudo during a controlled maintenance window.
# This makes the PLC see the Lenovo as LENOVO_MAINT_IP, not as the RPi.
# Close with rpi-cx-proxyarp-close.sh before restarting normal acquisition.
#
# Example:
#   sudo OT_IF=eth0 LENOVO_IF=enx6083e7ac98fb \
#     bash scripts/node-config/rpi-cx-proxyarp-open.sh

set -Eeuo pipefail

PLC_IP="${PLC_IP:-192.168.250.1}"
OT_PREFIX="${OT_PREFIX:-192.168.250.0/24}"
LENOVO_MAINT_IP="${LENOVO_MAINT_IP:-192.168.250.221}"
LENOVO_LINK_IP="${LENOVO_LINK_IP:-10.0.0.2}"
FINS_PORT="${FINS_PORT:-9600}"
EIP_PORT="${EIP_PORT:-44818}"
OT_IF="${OT_IF:-}"
LENOVO_IF="${LENOVO_IF:-}"
COMMENT="alumbrado-cx-proxyarp"
CHAIN="ALUMBRADO_CX_PROXYARP"
STATE_FILE="${STATE_FILE:-/run/alumbrado-cx-proxyarp.state}"
ROLLBACK_ARMED=0
CHAIN_OWNED_BY_THIS_RUN=0
JUMP_LENOVO_TO_OT_ADDED=0
JUMP_OT_TO_LENOVO_ADDED=0
ROUTE_ADDED_BY_THIS_RUN=0
STATE_SAVED_BY_THIS_RUN=0

require_root() {
    if [[ "${EUID}" -ne 0 ]]; then
        echo "ERROR Run as root: sudo OT_IF=<ot_if> LENOVO_IF=<lenovo_if> bash $0"
        exit 1
    fi
}

require_var() {
    local name="$1"
    local value="$2"
    if [[ -z "$value" ]]; then
        echo "ERROR Missing $name. Interfaces are never guessed on OT."
        exit 1
    fi
}

require_interface() {
    local iface="$1"
    if ! ip link show dev "$iface" >/dev/null 2>&1; then
        echo "ERROR Interface not found: $iface"
        exit 1
    fi
}

require_no_bridge() {
    local bridges
    bridges="$(ip -o link show type bridge || true)"
    if [[ -n "$bridges" && "${ALLOW_BRIDGE:-0}" != "1" ]]; then
        echo "ERROR Bridge interface present. Refusing proxy-ARP window."
        echo "$bridges"
        exit 1
    fi
}

check_route_uses_iface() {
    local target="$1"
    local iface="$2"
    local route
    route="$(ip route get "$target" 2>/dev/null || true)"
    if [[ -z "$route" || "$route" != *" dev $iface "* ]]; then
        echo "ERROR Route to $target does not use $iface."
        echo "Current route: ${route:-no route}"
        exit 1
    fi
}

abort_on_legacy_nat_rules() {
    if iptables -S FORWARD | grep -q 'alumbrado-cx-maintenance'; then
        echo "ERROR Legacy CX NAT FORWARD rules are present. Close them first."
        exit 1
    fi
    if iptables -t nat -S POSTROUTING | grep -q 'alumbrado-cx-maintenance'; then
        echo "ERROR Legacy CX NAT POSTROUTING rules are present. Close them first."
        exit 1
    fi
}

warn_or_abort_fins_listener() {
    if command -v ss >/dev/null 2>&1; then
        local listeners
        listeners="$(ss -H -lunp 2>/dev/null | grep ":$FINS_PORT" || true)"
        if [[ -n "$listeners" && "${ALLOW_LOCAL_FINS_LISTENER:-0}" != "1" ]]; then
            echo "ERROR Local UDP/$FINS_PORT listener detected on RPi."
            echo "Stop the publisher/acquisition first, or rerun with ALLOW_LOCAL_FINS_LISTENER=1."
            echo "$listeners"
            exit 1
        fi
    fi
}

save_state_once() {
    if [[ -f "$STATE_FILE" ]]; then
        echo "ERROR State file already exists: $STATE_FILE"
        echo "Close or inspect the previous maintenance window before opening a new one."
        return 1
    fi

    {
        echo "IP_FORWARD_OLD=$(cat /proc/sys/net/ipv4/ip_forward)"
        echo "ALL_RP_FILTER_OLD=$(cat /proc/sys/net/ipv4/conf/all/rp_filter)"
        echo "OT_RP_FILTER_OLD=$(cat /proc/sys/net/ipv4/conf/$OT_IF/rp_filter)"
        echo "LENOVO_RP_FILTER_OLD=$(cat /proc/sys/net/ipv4/conf/$LENOVO_IF/rp_filter)"
        echo "OT_PROXY_ARP_OLD=$(cat /proc/sys/net/ipv4/conf/$OT_IF/proxy_arp)"
        echo "LENOVO_PROXY_ARP_OLD=$(cat /proc/sys/net/ipv4/conf/$LENOVO_IF/proxy_arp)"
    } > "$STATE_FILE"
    chmod 0600 "$STATE_FILE"
    STATE_SAVED_BY_THIS_RUN=1
    echo "OK   Saved previous sysctl state: $STATE_FILE"
}

add_forward_jump() {
    local args=("$@")
    iptables -I FORWARD 1 "${args[@]}"
    echo "OK   FORWARD jump added: ${args[*]}"
}

delete_forward_jump() {
    local args=("$@")
    while iptables -C FORWARD "${args[@]}" 2>/dev/null; do
        iptables -D FORWARD "${args[@]}"
        echo "OK   Rollback removed FORWARD jump: ${args[*]}"
    done
}

prepare_filter_chain() {
    if iptables -N "$CHAIN" 2>/dev/null; then
        CHAIN_OWNED_BY_THIS_RUN=1
        echo "OK   Created chain: $CHAIN"
    else
        local refs
        refs="$(iptables -S | grep -F " -j $CHAIN" || true)"
        if [[ -n "$refs" ]]; then
            echo "ERROR Chain $CHAIN is already referenced. Close the existing window before reopening."
            echo "$refs"
            return 1
        fi
        echo "SKIP Chain already exists; flushing: $CHAIN"
        iptables -F "$CHAIN"
        CHAIN_OWNED_BY_THIS_RUN=1
    fi
}

ensure_chain_drop() {
    if ! iptables -S "$CHAIN" >/dev/null 2>&1; then
        return
    fi
    if iptables -S "$CHAIN" | tail -n 1 | grep -q -- ' -j DROP$'; then
        echo "OK   Existing chain $CHAIN has terminal DROP."
    else
        iptables -A "$CHAIN" -m comment --comment "$COMMENT open-safety-drop" -j DROP
        echo "WARN Added safety DROP to existing referenced chain $CHAIN."
    fi
}

restore_saved_sysctl_state() {
    if [[ "$STATE_SAVED_BY_THIS_RUN" -ne 1 || ! -f "$STATE_FILE" ]]; then
        return
    fi

    # shellcheck disable=SC1090
    . "$STATE_FILE"
    sysctl -w "net.ipv4.ip_forward=${IP_FORWARD_OLD:-0}" || true
    sysctl -w "net.ipv4.conf.all.rp_filter=${ALL_RP_FILTER_OLD:-2}" || true
    sysctl -w "net.ipv4.conf.$OT_IF.rp_filter=${OT_RP_FILTER_OLD:-2}" || true
    sysctl -w "net.ipv4.conf.$LENOVO_IF.rp_filter=${LENOVO_RP_FILTER_OLD:-2}" || true
    sysctl -w "net.ipv4.conf.$OT_IF.proxy_arp=${OT_PROXY_ARP_OLD:-0}" || true
    sysctl -w "net.ipv4.conf.$LENOVO_IF.proxy_arp=${LENOVO_PROXY_ARP_OLD:-0}" || true
    rm -f "$STATE_FILE"
}

rollback_open_error() {
    local exit_code=$?
    if [[ "$ROLLBACK_ARMED" -ne 1 ]]; then
        exit "$exit_code"
    fi

    set +e
    echo "ERROR Opening failed. Rolling back partial CX proxy-ARP state."

    if [[ "$JUMP_LENOVO_TO_OT_ADDED" -eq 1 ]]; then
        delete_forward_jump -i "$LENOVO_IF" -o "$OT_IF" -s "$LENOVO_MAINT_IP" -d "$OT_PREFIX" -m comment --comment "$COMMENT" -j "$CHAIN"
    fi
    if [[ "$JUMP_OT_TO_LENOVO_ADDED" -eq 1 ]]; then
        delete_forward_jump -i "$OT_IF" -o "$LENOVO_IF" -s "$OT_PREFIX" -d "$LENOVO_MAINT_IP" -m comment --comment "$COMMENT" -j "$CHAIN"
    fi

    if [[ "$CHAIN_OWNED_BY_THIS_RUN" -eq 1 ]] && iptables -S "$CHAIN" >/dev/null 2>&1; then
        local refs
        refs="$(iptables -S | grep -F " -j $CHAIN" || true)"
        if [[ -n "$refs" ]]; then
            echo "WARN Chain $CHAIN is still referenced after rollback; keeping it restrictive."
            echo "$refs"
            ensure_chain_drop
        else
            iptables -F "$CHAIN"
            iptables -X "$CHAIN"
            echo "OK   Rollback deleted chain: $CHAIN"
        fi
    fi

    if [[ "$ROUTE_ADDED_BY_THIS_RUN" -eq 1 ]]; then
        ip route del "$LENOVO_MAINT_IP/32" dev "$LENOVO_IF" 2>/dev/null || true
    fi
    restore_saved_sysctl_state

    exit "$exit_code"
}

preflight_no_existing_window() {
    local refs
    refs="$(iptables -S | grep -F " -j $CHAIN" || true)"
    if [[ -n "$refs" ]]; then
        echo "ERROR Existing CX proxy-ARP window appears open. Close it before reopening."
        echo "$refs"
        exit 1
    fi
}

preflight_no_existing_jump() {
    local args=("$@")
    if iptables -C FORWARD "${args[@]}" 2>/dev/null; then
        echo "ERROR Expected FORWARD jump already exists before opening."
        echo "${args[*]}"
        exit 1
    fi
}

preflight_route_ownership() {
    local existing
    existing="$(ip route show "$LENOVO_MAINT_IP/32" || true)"
    if [[ -n "$existing" && "$existing" != *" dev $LENOVO_IF"* ]]; then
        echo "ERROR Existing route for $LENOVO_MAINT_IP/32 is not on $LENOVO_IF."
        echo "$existing"
        exit 1
    fi
}

add_owned_route() {
    local existing
    existing="$(ip route show "$LENOVO_MAINT_IP/32" || true)"
    if [[ "$existing" == *" dev $LENOVO_IF"* ]]; then
        echo "SKIP Route already exists: $LENOVO_MAINT_IP/32 dev $LENOVO_IF"
        return
    fi

    ip route replace "$LENOVO_MAINT_IP/32" dev "$LENOVO_IF"
    ROUTE_ADDED_BY_THIS_RUN=1
    echo "OK   Route added: $LENOVO_MAINT_IP/32 dev $LENOVO_IF"
}

add_chain_accept() {
    local args=("$@")
    iptables -A "$CHAIN" "${args[@]}" -j ACCEPT
    echo "OK   Chain ACCEPT added: ${args[*]}"
}

check_maint_ip_free_on_ot() {
    local current_route
    current_route="$(ip route get "$LENOVO_MAINT_IP" 2>/dev/null || true)"
    if [[ "$current_route" == *" dev $LENOVO_IF "* ]]; then
        echo "SKIP $LENOVO_MAINT_IP already routes to $LENOVO_IF; not probing OT occupancy."
        return
    fi

    ip neigh flush "$LENOVO_MAINT_IP" dev "$OT_IF" >/dev/null 2>&1 || true
    ping -I "$OT_IF" -c 1 -W 1 "$LENOVO_MAINT_IP" >/dev/null 2>&1 || true

    local neigh
    neigh="$(ip neigh show "$LENOVO_MAINT_IP" dev "$OT_IF" || true)"
    if echo "$neigh" | grep -Eq 'lladdr .* (REACHABLE|STALE|DELAY|PROBE|PERMANENT)'; then
        echo "ERROR $LENOVO_MAINT_IP appears occupied on $OT_IF."
        echo "$neigh"
        exit 1
    fi
    echo "OK   $LENOVO_MAINT_IP did not answer on OT side before routing."
}

require_root
require_var OT_IF "$OT_IF"
require_var LENOVO_IF "$LENOVO_IF"

if [[ "$OT_IF" == "$LENOVO_IF" ]]; then
    echo "ERROR OT_IF and LENOVO_IF cannot be the same interface."
    exit 1
fi

require_interface "$OT_IF"
require_interface "$LENOVO_IF"
require_no_bridge
check_route_uses_iface "$PLC_IP" "$OT_IF"
check_route_uses_iface "$LENOVO_LINK_IP" "$LENOVO_IF"
abort_on_legacy_nat_rules
warn_or_abort_fins_listener
check_maint_ip_free_on_ot
preflight_no_existing_window
preflight_no_existing_jump -i "$LENOVO_IF" -o "$OT_IF" -s "$LENOVO_MAINT_IP" -d "$OT_PREFIX" -m comment --comment "$COMMENT" -j "$CHAIN"
preflight_no_existing_jump -i "$OT_IF" -o "$LENOVO_IF" -s "$OT_PREFIX" -d "$LENOVO_MAINT_IP" -m comment --comment "$COMMENT" -j "$CHAIN"
preflight_route_ownership
trap rollback_open_error ERR
ROLLBACK_ARMED=1

echo "=== Opening CX proxy-ARP maintenance window ==="
echo "PLC:              $PLC_IP"
echo "OT prefix:        $OT_PREFIX"
echo "Lenovo maint IP:  $LENOVO_MAINT_IP"
echo "Lenovo link IP:   $LENOVO_LINK_IP"
echo "OT_IF:            $OT_IF"
echo "LENOVO_IF:        $LENOVO_IF"
echo "Allowed ports:    ICMP, TCP/$FINS_PORT, UDP/$FINS_PORT, TCP/$EIP_PORT"
echo "NAT:              disabled/not used"
echo ""

prepare_filter_chain
add_chain_accept -s "$LENOVO_MAINT_IP" -d "$PLC_IP" -p icmp -m comment --comment "$COMMENT allow-icmp-request"
add_chain_accept -s "$PLC_IP" -d "$LENOVO_MAINT_IP" -p icmp -m comment --comment "$COMMENT allow-icmp-response"
add_chain_accept -s "$LENOVO_MAINT_IP" -d "$PLC_IP" -p udp --dport "$FINS_PORT" -m comment --comment "$COMMENT allow-udp-fins-request"
add_chain_accept -s "$PLC_IP" -d "$LENOVO_MAINT_IP" -p udp --sport "$FINS_PORT" -m comment --comment "$COMMENT allow-udp-fins-response"
add_chain_accept -s "$LENOVO_MAINT_IP" -d "$PLC_IP" -p tcp --dport "$FINS_PORT" -m comment --comment "$COMMENT allow-tcp-fins-request"
add_chain_accept -s "$PLC_IP" -d "$LENOVO_MAINT_IP" -p tcp --sport "$FINS_PORT" -m comment --comment "$COMMENT allow-tcp-fins-response"
add_chain_accept -s "$LENOVO_MAINT_IP" -d "$PLC_IP" -p tcp --dport "$EIP_PORT" -m comment --comment "$COMMENT allow-eip-request"
add_chain_accept -s "$PLC_IP" -d "$LENOVO_MAINT_IP" -p tcp --sport "$EIP_PORT" -m comment --comment "$COMMENT allow-eip-response"
iptables -A "$CHAIN" -m comment --comment "$COMMENT drop-other-lenovo-ot-traffic" -j DROP
echo "OK   Chain terminal DROP added for other Lenovo/OT traffic"

add_forward_jump -i "$LENOVO_IF" -o "$OT_IF" -s "$LENOVO_MAINT_IP" -d "$OT_PREFIX" -m comment --comment "$COMMENT" -j "$CHAIN"
JUMP_LENOVO_TO_OT_ADDED=1
add_forward_jump -i "$OT_IF" -o "$LENOVO_IF" -s "$OT_PREFIX" -d "$LENOVO_MAINT_IP" -m comment --comment "$COMMENT" -j "$CHAIN"
JUMP_OT_TO_LENOVO_ADDED=1

save_state_once
sysctl -w net.ipv4.ip_forward=1
sysctl -w net.ipv4.conf.all.rp_filter=0
sysctl -w "net.ipv4.conf.$OT_IF.rp_filter=0"
sysctl -w "net.ipv4.conf.$LENOVO_IF.rp_filter=0"
sysctl -w "net.ipv4.conf.$OT_IF.proxy_arp=1"
sysctl -w "net.ipv4.conf.$LENOVO_IF.proxy_arp=1"

add_owned_route
ROLLBACK_ARMED=0
trap - ERR

echo ""
echo "=== Verification ==="
ip route get "$LENOVO_MAINT_IP"
cat /proc/sys/net/ipv4/ip_forward
for iface in all "$OT_IF" "$LENOVO_IF"; do
    echo "$iface proxy_arp=$(cat /proc/sys/net/ipv4/conf/$iface/proxy_arp) rp_filter=$(cat /proc/sys/net/ipv4/conf/$iface/rp_filter)"
done
iptables -S FORWARD | grep "$COMMENT" || true
iptables -S "$CHAIN"
echo ""
echo "Window open. Recommended validation:"
echo "  Lenovo: ping -S $LENOVO_MAINT_IP $PLC_IP"
echo "  RPi: sudo tcpdump -ni $OT_IF 'host $LENOVO_MAINT_IP and host $PLC_IP and (tcp port $FINS_PORT or udp port $FINS_PORT or tcp port $EIP_PORT)'"
echo ""
echo "Close with:"
echo "  sudo OT_IF=$OT_IF LENOVO_IF=$LENOVO_IF bash scripts/node-config/rpi-cx-proxyarp-close.sh"
