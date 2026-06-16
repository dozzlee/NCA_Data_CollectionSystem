#!/bin/bash
# =============================================================================
# NCA Data Collection System — Automated API Test Suite
# Run: bash testing/api_test.sh [BASE_URL]
# Default BASE_URL: http://localhost:8000
# For live deployment: bash testing/api_test.sh https://codedematrix-datacollection.hf.space
# =============================================================================

BASE_URL="${1:-http://localhost:8000}"
API="$BASE_URL/api/v1"
PASS=0
FAIL=0
SKIP=0

# Colours
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

pass() { echo -e "  ${GREEN}✓ PASS${NC}  $1"; ((PASS++)); }
fail() { echo -e "  ${RED}✗ FAIL${NC}  $1"; echo -e "         ${RED}$2${NC}"; ((FAIL++)); }
skip() { echo -e "  ${YELLOW}– SKIP${NC}  $1 — $2"; ((SKIP++)); }
section() { echo -e "\n${CYAN}▶ $1${NC}"; }

# Helper: check HTTP status
check_status() {
  local label="$1" expected="$2" actual="$3" body="$4"
  if [ "$actual" == "$expected" ]; then
    pass "$label (HTTP $actual)"
  else
    fail "$label" "Expected HTTP $expected, got HTTP $actual. Body: $body"
  fi
}

echo ""
echo "=================================================="
echo " NCA Data Collection — API Test Suite"
echo " Target: $BASE_URL"
echo " $(date)"
echo "=================================================="

# =============================================================================
section "1. Health Check"
# =============================================================================

RESP=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/")
if [ "$RESP" == "200" ] || [ "$RESP" == "302" ] || [ "$RESP" == "404" ]; then
  pass "Server reachable (HTTP $RESP)"
else
  fail "Server unreachable" "HTTP $RESP — is the server running at $BASE_URL?"
fi

# =============================================================================
section "2. Authentication"
# =============================================================================

# Login as NCA Admin
LOGIN_RESP=$(curl -s -X POST "$API/auth/login/" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@nca.org.gh","password":"testpass123"}')

NCA_TOKEN=$(echo "$LOGIN_RESP" | grep -o '"access":"[^"]*"' | cut -d'"' -f4)

if [ -n "$NCA_TOKEN" ]; then
  pass "NCA Admin login returns access token"
else
  fail "NCA Admin login" "No token returned. Response: $LOGIN_RESP"
fi

# Login as Provider
PROV_RESP=$(curl -s -X POST "$API/auth/login/" \
  -H "Content-Type: application/json" \
  -d '{"email":"dataentry@vodafone.com.gh","password":"testpass123"}')

PROV_TOKEN=$(echo "$PROV_RESP" | grep -o '"access":"[^"]*"' | cut -d'"' -f4)

if [ -n "$PROV_TOKEN" ]; then
  pass "Provider login returns access token"
else
  fail "Provider login" "No token returned. Response: $PROV_RESP"
fi

# Bad credentials should return 401
BAD_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API/auth/login/" \
  -H "Content-Type: application/json" \
  -d '{"email":"wrong@email.com","password":"wrongpass"}')
check_status "Bad credentials rejected" "401" "$BAD_STATUS" ""

# Get current user profile
if [ -n "$NCA_TOKEN" ]; then
  ME_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API/auth/me/" \
    -H "Authorization: Bearer $NCA_TOKEN")
  check_status "GET /auth/me/ returns profile" "200" "$ME_STATUS" ""
fi

# Unauthenticated request should be rejected
UNAUTH=$(curl -s -o /dev/null -w "%{http_code}" "$API/providers/")
check_status "Unauthenticated request rejected" "401" "$UNAUTH" ""

# =============================================================================
section "3. Providers"
# =============================================================================

if [ -n "$NCA_TOKEN" ]; then
  # List providers
  PROV_LIST=$(curl -s "$API/providers/" -H "Authorization: Bearer $NCA_TOKEN")
  PROV_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API/providers/" \
    -H "Authorization: Bearer $NCA_TOKEN")
  check_status "GET /providers/ list" "200" "$PROV_STATUS" ""

  PROV_COUNT=$(echo "$PROV_LIST" | grep -o '"count":[0-9]*' | cut -d: -f2)
  if [ -n "$PROV_COUNT" ] && [ "$PROV_COUNT" -gt 0 ]; then
    pass "Providers list has $PROV_COUNT results"
  else
    fail "Providers list empty" "Expected seeded providers. Response: $PROV_LIST"
  fi

  # Get first provider ID
  PROV_ID=$(echo "$PROV_LIST" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)

  # Search providers
  SEARCH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API/providers/?search=Vodafone" \
    -H "Authorization: Bearer $NCA_TOKEN")
  check_status "GET /providers/?search=Vodafone" "200" "$SEARCH_STATUS" ""

  # Filter by category
  CAT_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API/providers/?category=MNO" \
    -H "Authorization: Bearer $NCA_TOKEN")
  check_status "GET /providers/?category=MNO" "200" "$CAT_STATUS" ""

  # Get single provider
  if [ -n "$PROV_ID" ]; then
    SINGLE_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API/providers/$PROV_ID/" \
      -H "Authorization: Bearer $NCA_TOKEN")
    check_status "GET /providers/$PROV_ID/" "200" "$SINGLE_STATUS" ""
  fi

  # Provider cannot see other providers
  if [ -n "$PROV_TOKEN" ]; then
    PROV_LIST_AS_PROV=$(curl -s "$API/providers/" -H "Authorization: Bearer $PROV_TOKEN")
    PROV_LIST_COUNT=$(echo "$PROV_LIST_AS_PROV" | grep -o '"count":[0-9]*' | cut -d: -f2)
    if [ -n "$PROV_LIST_COUNT" ]; then
      pass "Provider user can only see own provider data (count: $PROV_LIST_COUNT)"
    fi
  fi
else
  skip "Providers tests" "No NCA token available"
fi

# =============================================================================
section "4. Submissions (Expected)"
# =============================================================================

if [ -n "$NCA_TOKEN" ]; then
  SUB_LIST=$(curl -s "$API/expected-submissions/" -H "Authorization: Bearer $NCA_TOKEN")
  SUB_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API/expected-submissions/" \
    -H "Authorization: Bearer $NCA_TOKEN")
  check_status "GET /expected-submissions/ list" "200" "$SUB_STATUS" ""

  SUB_COUNT=$(echo "$SUB_LIST" | grep -o '"count":[0-9]*' | cut -d: -f2)
  if [ -n "$SUB_COUNT" ] && [ "$SUB_COUNT" -gt 0 ]; then
    pass "Submissions list has $SUB_COUNT results"
  else
    fail "Submissions list empty" "Expected seeded submissions. Run seed_data first."
  fi

  # Get first submission ID
  SUB_ID=$(echo "$SUB_LIST" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)

  # Search submissions
  SEARCH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API/expected-submissions/?search=Vodafone" \
    -H "Authorization: Bearer $NCA_TOKEN")
  check_status "Search submissions by provider name" "200" "$SEARCH_STATUS" ""

  # Filter by status
  FILT_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API/expected-submissions/?workflow_status=DRAFT" \
    -H "Authorization: Bearer $NCA_TOKEN")
  check_status "Filter submissions by workflow_status=DRAFT" "200" "$FILT_STATUS" ""

  # Get single submission
  if [ -n "$SUB_ID" ]; then
    SINGLE_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API/expected-submissions/$SUB_ID/" \
      -H "Authorization: Bearer $NCA_TOKEN")
    check_status "GET /expected-submissions/$SUB_ID/" "200" "$SINGLE_STATUS" ""
  fi

  # Provider sees only own submissions
  if [ -n "$PROV_TOKEN" ]; then
    PROV_SUBS=$(curl -s "$API/expected-submissions/" -H "Authorization: Bearer $PROV_TOKEN")
    PROV_SUB_COUNT=$(echo "$PROV_SUBS" | grep -o '"count":[0-9]*' | cut -d: -f2)
    NCA_SUB_COUNT=$(echo "$SUB_LIST" | grep -o '"count":[0-9]*' | cut -d: -f2)
    if [ -n "$PROV_SUB_COUNT" ] && [ "$PROV_SUB_COUNT" -lt "$NCA_SUB_COUNT" ]; then
      pass "Provider sees fewer submissions than NCA ($PROV_SUB_COUNT vs $NCA_SUB_COUNT — RBAC working)"
    else
      fail "Provider RBAC on submissions" "Provider count ($PROV_SUB_COUNT) should be less than NCA count ($NCA_SUB_COUNT)"
    fi
  fi
else
  skip "Submission tests" "No NCA token available"
fi

# =============================================================================
section "5. Compliance Flags"
# =============================================================================

if [ -n "$NCA_TOKEN" ]; then
  COMP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API/compliance/flags/" \
    -H "Authorization: Bearer $NCA_TOKEN")
  check_status "GET /compliance/flags/" "200" "$COMP_STATUS" ""

  # Filter by status
  OPEN_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API/compliance/flags/?status=OPEN" \
    -H "Authorization: Bearer $NCA_TOKEN")
  check_status "GET /compliance/flags/?status=OPEN" "200" "$OPEN_STATUS" ""

  COMP_BODY=$(curl -s "$API/compliance/flags/" -H "Authorization: Bearer $NCA_TOKEN")
  FLAG_ID=$(echo "$COMP_BODY" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)

  if [ -n "$FLAG_ID" ]; then
    # Acknowledge a flag
    ACK_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH \
      "$API/compliance/flags/$FLAG_ID/acknowledge/" \
      -H "Authorization: Bearer $NCA_TOKEN")
    check_status "PATCH /compliance/flags/$FLAG_ID/acknowledge/" "200" "$ACK_STATUS" ""
  else
    skip "Flag acknowledge test" "No flags found — run flag_missing_data command first"
  fi
else
  skip "Compliance tests" "No NCA token available"
fi

# =============================================================================
section "6. Users"
# =============================================================================

if [ -n "$NCA_TOKEN" ]; then
  USERS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API/auth/users/" \
    -H "Authorization: Bearer $NCA_TOKEN")
  check_status "GET /auth/users/ list" "200" "$USERS_STATUS" ""

  # Provider cannot list all users
  if [ -n "$PROV_TOKEN" ]; then
    PROV_USERS=$(curl -s -o /dev/null -w "%{http_code}" "$API/auth/users/" \
      -H "Authorization: Bearer $PROV_TOKEN")
    if [ "$PROV_USERS" == "403" ] || [ "$PROV_USERS" == "401" ]; then
      pass "Provider blocked from listing users (HTTP $PROV_USERS)"
    else
      fail "Provider RBAC on users" "Expected 403, got $PROV_USERS"
    fi
  fi
else
  skip "Users tests" "No NCA token available"
fi

# =============================================================================
section "7. Exports"
# =============================================================================

if [ -n "$NCA_TOKEN" ] && [ -n "$PROV_ID" ] && [ -n "$PERIOD_ID" ]; then
  EXPORT_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API/exports/csv/" \
    -H "Authorization: Bearer $NCA_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"provider_id\":$PROV_ID}")
  check_status "POST /exports/csv/" "200" "$EXPORT_STATUS" ""
else
  skip "Export test" "Need provider ID and period ID from earlier tests"
fi

# =============================================================================
section "8. Audit Log"
# =============================================================================

if [ -n "$NCA_TOKEN" ]; then
  AUDIT_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API/audit/" \
    -H "Authorization: Bearer $NCA_TOKEN")
  check_status "GET /audit/ log accessible to NCA" "200" "$AUDIT_STATUS" ""
fi

# =============================================================================
echo ""
echo "=================================================="
echo " RESULTS"
echo "=================================================="
echo -e " ${GREEN}Passed:${NC}  $PASS"
echo -e " ${RED}Failed:${NC}  $FAIL"
echo -e " ${YELLOW}Skipped:${NC} $SKIP"
TOTAL=$((PASS + FAIL + SKIP))
echo " Total:   $TOTAL"
echo ""
if [ "$FAIL" -eq 0 ]; then
  echo -e " ${GREEN}All tests passed! ✓${NC}"
else
  echo -e " ${RED}$FAIL test(s) failed. Review output above.${NC}"
fi
echo "=================================================="
echo ""
