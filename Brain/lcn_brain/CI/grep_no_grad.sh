#!/usr/bin/env bash
# CI enforcement: assert no reverse-mode autograd in lcn/
# Invariant I1 — lcn/ must not contain jax.grad, jax.vjp, jacrev, or any Heaviside.
# Run as part of the CI pipeline before merging.

set -euo pipefail

PATTERNS=(
    'jax\.grad'
    'jax\.vjp'
    'jacrev'
    'value_and_grad'
    'Heaviside\('
)

VIOLATIONS=0
for pattern in "${PATTERNS[@]}"; do
    matches=$(grep -rn "$pattern" lcn/ --include='*.py' 2>/dev/null || true)
    if [ -n "$matches" ]; then
        echo "I1 VIOLATION: $pattern found in:"
        echo "$matches"
        VIOLATIONS=$((VIOLATIONS + 1))
    fi
done

# Invariant I-RCD-2: RCDCell apply should appear exactly once, inside lax.cond(tick, ...)
RCD_SITES=$(grep -rn 'RCDCell.*apply\|rcd_step\|rcd_cell' lcn/ --include='*.py' 2>/dev/null || true)
RCD_COUNT=$(echo "$RCD_SITES" | grep -c 'rcd' || true)
echo "RCD call sites found: $RCD_COUNT"
echo "$RCD_SITES"

if [ "$VIOLATIONS" -gt 0 ]; then
    echo ""
    echo "FAIL: $VIOLATIONS I1 invariant violation(s) detected."
    echo "See §14 Invariants, §6, and §20 Pitfall 1 in the bootstrap blueprint."
    exit 1
fi

echo ""
echo "PASS: No reverse-mode autograd or Heaviside in lcn/."
exit 0
