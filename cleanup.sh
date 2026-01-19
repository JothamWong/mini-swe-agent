#!/bin/bash
# Cleanup script for TrEnvX sandbox resources made by Claude Opus 4.5
# Run with: ./cleanup.sh or sudo ./cleanup.sh (for network cleanup)

set -e

echo "=== TrEnvX Cleanup Script ==="

# 1. Kill all unshare processes (these hold the sandboxes)
echo "[1/6] Killing stale unshare processes..."
pkill -u "$(whoami)" -f 'unshare.*bind_mount' 2>/dev/null && echo "  Killed unshare processes" || echo "  No unshare processes found"

# 2. Kill all Firecracker processes
echo "[2/6] Killing Firecracker processes..."
pkill -u "$(whoami)" firecracker 2>/dev/null && echo "  Killed Firecracker processes" || echo "  No Firecracker processes found"

# 3. Remove VMM sockets
echo "[3/6] Removing VMM sockets..."
rm -f /tmp/vmm-*.socket 2>/dev/null && echo "  Removed VMM sockets" || echo "  No VMM sockets found"

# 4. Clean up veth-ci-* devices (the actual sandbox veth pairs)
echo "[4/6] Cleaning up veth-ci-* devices..."
for i in $(seq 1 20); do
    sudo ip link delete "veth-ci-$i" 2>/dev/null && echo "  Deleted veth-ci-$i"
done
echo "  Done cleaning veth-ci-* devices"

# 5. Clean up sandbox network namespaces
echo "[5/6] Cleaning up network namespaces..."
for ns in $(ip netns list 2>/dev/null | grep -E '^sandbox-net' | awk '{print $1}'); do
    sudo ip netns delete "$ns" 2>/dev/null && echo "  Deleted namespace: $ns" || echo "  Failed to delete: $ns"
done

# 6. Clean up any other orphaned veth devices with sandbox pattern
echo "[6/6] Cleaning up other sandbox veth devices..."
for veth in $(ip link show 2>/dev/null | grep -oE 'veth-sandbox-[^:@]+' | sort -u); do
    sudo ip link delete "$veth" 2>/dev/null && echo "  Deleted veth: $veth" || echo "  Failed to delete: $veth"
done

echo ""
echo "=== Cleanup Complete ==="
echo ""
echo "Remaining resources:"
echo "  Firecracker processes: $(pgrep -u "$(whoami)" firecracker 2>/dev/null | wc -l)"
echo "  Unshare processes: $(pgrep -u "$(whoami)" -f 'unshare.*bind_mount' 2>/dev/null | wc -l)"
echo "  VMM sockets: $(ls /tmp/vmm-*.socket 2>/dev/null | wc -l || echo 0)"
echo "  Sandbox namespaces: $(ip netns list 2>/dev/null | grep -c '^sandbox-net' || echo 0)"
echo "  veth-ci devices: $(ip link show 2>/dev/null | grep -c 'veth-ci-' || echo 0)"
