#!/usr/bin/env bash
# rpi-cx-proxyarp-close.sh - Close tested CX-One/CX Programmer proxy-ARP path.
#
# Removes only rules tagged alumbrado-cx-proxyarp, removes the Lenovo host route,
# and restores saved sysctl state when available.

set -euo pipefail

PLC_IP="${PLC_IP:-192.168.250.1}"
OT_PREFIX="${OT_PREFIX:-192.168.250.0/24}"
LENOVO_MAINT_IP="${LENOVO_MAINT_IP:-192.168.250.221}"
FINS_PORT="${FINS_PORT:-9600}"
EIP_PORT="${EIP_PORT:-44818}"
OT_IF="${OT_IF:-}"
LENOVO_IF="${LENOVO_IF:-}"
COMMENT="alumbrado-cx-proxyarp"
CHAIN="ALUMBRADO_CX_PROXYARP"
STATE_FILE="${STATE_FILE:-/run/alumbrado-cx-proxyarp.state}"
CHAIN_DELETE_FAILED=0

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
        echo "ERROR Missing $name. Use the same interfaces as open."
        exit 1
    fi
}

delete_all_filter_rules() {
    local args=("$@")
    local removed=0
    while iptables -C FORWARD "${args[@]}" 2>/dev/null; do
        iptables -D FORWARD "${args[@]}"
        removed=$((removed + 1))
    done
    if [[ "$removed" -eq 0 ]]; then
        echo "SKIP FORWARD rule absent: ${args[*]}"
    else
        echo "OK   Removed $removed FORWARD rule(s): ${args[*]}"
    fi
}

delete_filter_chain() {
    if ! iptables -S "$CHAIN" >/dev/null 2>&1; then
        echo "SKIP Chain absent: $CHAIN"
        return
    fi

    local refs
    refs="$(iptables -S | grep -F " -j $CHAIN" || true)"
    if [[ -n "$refs" ]]; then
        echo "ERROR Chain $CHAIN still has references; refusing to flush it."
        echo "$refs"
        ensure_chain_drop
        CHAIN_DELETE_FAILED=1
        return
    fi

    iptables -F "$CHAIN"
    if iptables -X "$CHAIN" 2>/dev/null; then
        echo "OK   Deleted chain: $CHAIN"
    else
        echo "WARN Could not delete chain $CHAIN; check remaining references."
        ensure_chain_drop
        CHAIN_DELETE_FAILED=1
    fi
}

ensure_chain_drop() {
    if ! iptables -S "$CHAIN" >/dev/null 2>&1; then
        return
    fi
    if iptables -S "$CHAIN" | tail -n 1 | grep -q -- ' -j DROP$'; then
        echo "OK   Chain $CHAIN still has terminal DROP."
    else
        iptables -A "$CHAIN" -m comment --comment "$COMMENT close-safety-drop" -j DROP
        echo "WARN Added safety DROP to referenced chain $CHAIN."
    fi
}

restore_sysctl_state() {
    if [[ -f "$STATE_FILE" ]]; then
        # shellcheck disable=SC1090
        . "$STATE_FILE"
        sysctl -w "net.ipv4.ip_forward=${IP_FORWARD_OLD:-0}"
        sysctl -w "net.ipv4.conf.all.rp_filter=${ALL_RP_FILTER_OLD:-2}"
        sysctl -w "net.ipv4.conf.$OT_IF.rp_filter=${OT_RP_FILTER_OLD:-2}"
        sysctl -w "net.ipv4.conf.$LENOVO_IF.rp_filter=${LENOVO_RP_FILTER_OLD:-2}"
        sysctl -w "net.ipv4.conf.$OT_IF.proxy_arp=${OT_PROXY_ARP_OLD:-0}"
        sysctl -w "net.ipv4.conf.$LENOVO_IF.proxy_arp=${LENOVO_PROXY_ARP_OLD:-0}"
        rm -f "$STATE_FILE"
        echo "OK   Restored sysctl state from $STATE_FILE"
    else
        echo "WARN No state file found; restoring project defaults."
        sysctl -w net.ipv4.ip_forward=0
        sysctl -w net.ipv4.conf.all.rp_filter=2
        sysctl -w "net.ipv4.conf.$OT_IF.rp_filter=2"
        sysctl -w "net.ipv4.conf.$LENOVO_IF.rp_filter=2"
        sysctl -w "net.ipv4.conf.$OT_IF.proxy_arp=0"
        sysctl -w "net.ipv4.conf.$LENOVO_IF.proxy_arp=0"
    fi
}

require_root
require_var OT_IF "$OT_IF"
require_var LENOVO_IF "$LENOVO_IF"

echo "=== Closing CX proxy-ARP maintenance window ==="

delete_all_filter_rules -i "$LENOVO_IF" -o "$OT_IF" -s "$LENOVO_MAINT_IP" -d "$OT_PREFIX" -m comment --comment "$COMMENT" -j "$CHAIN"
delete_all_filter_rules -i "$OT_IF" -o "$LENOVO_IF" -s "$OT_PREFIX" -d "$LENOVO_MAINT_IP" -m comment --comment "$COMMENT" -j "$CHAIN"

delete_all_filter_rules -i "$LENOVO_IF" -o "$OT_IF" -s "$LENOVO_MAINT_IP" -d "$PLC_IP" -p icmp -m comment --comment "$COMMENT" -j ACCEPT
delete_all_filter_rules -i "$OT_IF" -o "$LENOVO_IF" -s "$PLC_IP" -d "$LENOVO_MAINT_IP" -p icmp -m comment --comment "$COMMENT" -j ACCEPT
delete_all_filter_rules -i "$LENOVO_IF" -o "$OT_IF" -s "$LENOVO_MAINT_IP" -d "$PLC_IP" -p udp --dport "$FINS_PORT" -m comment --comment "$COMMENT" -j ACCEPT
delete_all_filter_rules -i "$OT_IF" -o "$LENOVO_IF" -s "$PLC_IP" -d "$LENOVO_MAINT_IP" -p udp --sport "$FINS_PORT" -m comment --comment "$COMMENT" -j ACCEPT
delete_all_filter_rules -i "$LENOVO_IF" -o "$OT_IF" -s "$LENOVO_MAINT_IP" -d "$PLC_IP" -p tcp --dport "$FINS_PORT" -m comment --comment "$COMMENT" -j ACCEPT
delete_all_filter_rules -i "$OT_IF" -o "$LENOVO_IF" -s "$PLC_IP" -d "$LENOVO_MAINT_IP" -p tcp --sport "$FINS_PORT" -m comment --comment "$COMMENT" -j ACCEPT
delete_all_filter_rules -i "$LENOVO_IF" -o "$OT_IF" -s "$LENOVO_MAINT_IP" -d "$PLC_IP" -p tcp --dport "$EIP_PORT" -m comment --comment "$COMMENT" -j ACCEPT
delete_all_filter_rules -i "$OT_IF" -o "$LENOVO_IF" -s "$PLC_IP" -d "$LENOVO_MAINT_IP" -p tcp --sport "$EIP_PORT" -m comment --comment "$COMMENT" -j ACCEPT
delete_filter_chain

if ip route show "$LENOVO_MAINT_IP/32" | grep -q " dev $LENOVO_IF"; then
    ip route del "$LENOVO_MAINT_IP/32" dev "$LENOVO_IF"
    echo "OK   Removed route: $LENOVO_MAINT_IP/32 dev $LENOVO_IF"
else
    echo "SKIP Route absent or not on $LENOVO_IF: $LENOVO_MAINT_IP/32"
fi

restore_sysctl_state

echo ""
echo "=== Verification ==="
if iptables -S FORWARD | grep "$COMMENT"; then
    echo "WARN Proxy-ARP FORWARD rules remain."
else
    echo "OK   No proxy-ARP FORWARD rules remain."
fi
if iptables -S "$CHAIN" >/dev/null 2>&1; then
    echo "WARN Proxy-ARP chain still exists: $CHAIN"
else
    echo "OK   Proxy-ARP chain absent."
fi
ip route show "$LENOVO_MAINT_IP/32" || true
cat /proc/sys/net/ipv4/ip_forward
for iface in all "$OT_IF" "$LENOVO_IF"; do
    echo "$iface proxy_arp=$(cat /proc/sys/net/ipv4/conf/$iface/proxy_arp) rp_filter=$(cat /proc/sys/net/ipv4/conf/$iface/rp_filter)"
done

if [[ "$CHAIN_DELETE_FAILED" -ne 0 ]]; then
    echo "ERROR Close left chain $CHAIN in place because references remain. Chain was kept restrictive."
    exit 1
fi
