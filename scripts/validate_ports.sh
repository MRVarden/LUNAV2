#!/bin/bash
# ============================================
# Luna Consciousness - Port Validation Script
# ============================================
# Exécuter après rebuild pour valider tous les ports
# Usage: ./scripts/validate_ports.sh
# ============================================

echo "=============================================="
echo "🔍 Luna Consciousness - Port Validation"
echo "=============================================="
echo ""

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Compteurs
PASSED=0
FAILED=0

check_port() {
    local port=$1
    local name=$2
    local endpoint=$3

    echo -n "Testing $name (port $port)... "

    response=$(curl -sf -o /dev/null -w "%{http_code}" "http://127.0.0.1:${port}${endpoint}" --max-time 5 2>/dev/null || echo "000")

    if [ "$response" != "000" ]; then
        echo -e "${GREEN}✅ OK${NC} (HTTP $response)"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}❌ FAILED${NC} (connection refused)"
        ((FAILED++))
        return 1
    fi
}

check_websocket() {
    local port=$1
    echo -n "Testing WebSocket (port $port)... "

    # Test de connexion TCP
    if timeout 2 bash -c "echo > /dev/tcp/127.0.0.1/$port" 2>/dev/null; then
        echo -e "${GREEN}✅ OK${NC} (port open)"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}❌ FAILED${NC} (port closed)"
        ((FAILED++))
        return 1
    fi
}

check_container() {
    echo "📦 Checking container status..."
    echo "-------------------------------------------"

    if docker ps | grep -q luna-consciousness; then
        status=$(docker ps --filter "name=luna-consciousness" --format "{{.Status}}")
        echo -e "Container: ${GREEN}Running${NC} ($status)"
        return 0
    else
        echo -e "Container: ${RED}NOT RUNNING${NC}"
        return 1
    fi
}

check_logs() {
    echo ""
    echo "📋 Checking critical logs..."
    echo "-------------------------------------------"

    # Vérifier que Uvicorn écoute sur 0.0.0.0
    if docker logs luna-consciousness 2>&1 | grep -q "Uvicorn running on http://0.0.0.0:8000"; then
        echo -e "${GREEN}✅${NC} MCP Server bound to 0.0.0.0:8000"
    elif docker logs luna-consciousness 2>&1 | grep -q "Uvicorn running on http://127.0.0.1:8000"; then
        echo -e "${RED}❌${NC} MCP Server bound to 127.0.0.1:8000 (PROBLÈME!)"
        ((FAILED++))
    else
        echo -e "${YELLOW}⚠️${NC}  MCP Server binding - check logs manually"
    fi

    # Vérifier les erreurs
    error_count=$(docker logs luna-consciousness 2>&1 | grep -c "ERROR\|Error\|error" || echo "0")
    if [ "$error_count" -gt 0 ]; then
        echo -e "${YELLOW}⚠️${NC}  Found $error_count error(s) in logs"
    else
        echo -e "${GREEN}✅${NC} No errors in logs"
    fi
}

# ============================================
# PRE-CHECKS
# ============================================

echo "🔌 Pre-flight checks..."
echo "-------------------------------------------"

if ! check_container; then
    echo ""
    echo -e "${RED}Container not running! Start with: docker compose up -d${NC}"
    exit 1
fi

echo ""

# ============================================
# PORT TESTS
# ============================================

echo "🔌 Testing all Luna ports..."
echo "-------------------------------------------"

# Port 9100 - Prometheus (test en premier car c'est le healthcheck)
check_port 9100 "Prometheus" "/metrics"

# Port 8080 - API REST
check_port 8080 "API REST" "/health"

# Port 8000 - MCP Server direct
check_port 8000 "MCP Server (8000)" "/sse"

# Port 3000 - MCP SSE (alias vers 8000)
check_port 3000 "MCP SSE alias (3000)" "/sse"

# Port 9000 - WebSocket
check_websocket 9000

# Vérifier les logs
check_logs

# ============================================
# RÉSUMÉ
# ============================================
echo ""
echo "=============================================="
echo "📊 VALIDATION SUMMARY"
echo "=============================================="
echo -e "Passed: ${GREEN}${PASSED}${NC}"
echo -e "Failed: ${RED}${FAILED}${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL PORTS VALIDATED SUCCESSFULLY!${NC}"
    echo ""
    echo "Services disponibles:"
    echo "  - MCP SSE:    http://127.0.0.1:3000/sse"
    echo "  - MCP Direct: http://127.0.0.1:8000/sse"
    echo "  - API REST:   http://127.0.0.1:8080/docs"
    echo "  - WebSocket:  ws://127.0.0.1:9000"
    echo "  - Prometheus: http://127.0.0.1:9100/metrics"
    echo ""
    echo "Claude Desktop config:"
    echo '  "luna": {'
    echo '    "url": "http://127.0.0.1:8000/sse"'
    echo '  }'
    exit 0
else
    echo -e "${RED}⚠️  SOME PORTS FAILED VALIDATION${NC}"
    echo ""
    echo "Debug commands:"
    echo "  docker logs luna-consciousness 2>&1 | tail -100"
    echo "  docker exec luna-consciousness netstat -tlnp"
    echo "  docker exec luna-consciousness curl -v http://localhost:8000/sse"
    exit 1
fi
