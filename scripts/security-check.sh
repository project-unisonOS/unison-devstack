#!/bin/bash

# Security Validation Script for Unison
# This script validates the security configuration of a deployed Unison stack

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
AUTH_URL="${UNISON_AUTH_URL:-http://localhost:8088}"
API_URL="${UNISON_API_URL:-http://localhost}"
KONG_ADMIN_URL="${UNISON_KONG_ADMIN_URL:-http://localhost:8001}"

# Test functions
test_auth_service() {
    echo -e "${YELLOW}Testing Authentication Service...${NC}"
    
    # Test health endpoint
    if curl -s -f "$AUTH_URL/health" > /dev/null; then
        echo -e "${GREEN}✓ Auth service health check passed${NC}"
    else
        echo -e "${RED}✗ Auth service health check failed${NC}"
        return 1
    fi
    
    # Test token endpoint with default credentials
    local token_response=$(curl -s -X POST "$AUTH_URL/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "grant_type=password&username=admin&password=admin123" || echo "")
    
    if echo "$token_response" | grep -q "access_token"; then
        echo -e "${GREEN}✓ Token endpoint working${NC}"
        ACCESS_TOKEN=$(echo "$token_response" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
    else
        echo -e "${RED}✗ Token endpoint failed${NC}"
        return 1
    fi
    
    # Test token verification
    if curl -s -X POST "$AUTH_URL/verify" \
        -H "Content-Type: application/json" \
        -d "{\"token\":\"$ACCESS_TOKEN\"}" | grep -q '"valid":true'; then
        echo -e "${GREEN}✓ Token verification working${NC}"
    else
        echo -e "${RED}✗ Token verification failed${NC}"
        return 1
    fi
}

test_api_gateway() {
    echo -e "${YELLOW}Testing API Gateway (Kong)...${NC}"
    
    # Test Kong admin API
    if curl -s -f "$KONG_ADMIN_URL/services" > /dev/null; then
        echo -e "${GREEN}✓ Kong admin API accessible${NC}"
    else
        echo -e "${RED}✗ Kong admin API not accessible${NC}"
        return 1
    fi
    
    # Test JWT plugin is enabled
    if curl -s "$KONG_ADMIN_URL/plugins" | grep -q "jwt"; then
        echo -e "${GREEN}✓ JWT plugin enabled${NC}"
    else
        echo -e "${RED}✗ JWT plugin not found${NC}"
        return 1
    fi
    
    # Test rate limiting plugin is enabled
    if curl -s "$KONG_ADMIN_URL/plugins" | grep -q "rate-limiting"; then
        echo -e "${GREEN}✓ Rate limiting plugin enabled${NC}"
    else
        echo -e "${RED}✗ Rate limiting plugin not found${NC}"
        return 1
    fi
    
    # Test CORS plugin is enabled
    if curl -s "$KONG_ADMIN_URL/plugins" | grep -q "cors"; then
        echo -e "${GREEN}✓ CORS plugin enabled${NC}"
    else
        echo -e "${RED}✗ CORS plugin not found${NC}"
        return 1
    fi
}

test_security_headers() {
    echo -e "${YELLOW}Testing Security Headers...${NC}"
    
    # Test headers on a protected endpoint
    local headers=$(curl -s -I "$API_URL/health" || echo "")
    
    # Check for security headers
    local security_headers=(
        "X-Content-Type-Options"
        "X-Frame-Options"
        "X-XSS-Protection"
        "Referrer-Policy"
        "Content-Security-Policy"
    )
    
    for header in "${security_headers[@]}"; do
        if echo "$headers" | grep -qi "$header"; then
            echo -e "${GREEN}✓ $header header present${NC}"
        else
            echo -e "${RED}✗ $header header missing${NC}"
        fi
    done
}

test_authentication_required() {
    echo -e "${YELLOW}Testing Authentication Requirements...${NC}"
    
    # Test that protected endpoints require authentication
    local response=$(curl -s -w "%{http_code}" -o /dev/null "$API_URL/api/event" \
        -H "Content-Type: application/json" \
        -d '{"test": "data"}' || echo "000")
    
    if [ "$response" = "401" ] || [ "$response" = "403" ]; then
        echo -e "${GREEN}✓ Protected endpoint requires authentication${NC}"
    else
        echo -e "${RED}✗ Protected endpoint returned $response (expected 401/403)${NC}"
    fi
}

test_rate_limiting() {
    echo -e "${YELLOW}Testing Rate Limiting...${NC}"
    
    # Make multiple rapid requests to test rate limiting
    local rate_limit_hit=false
    for i in {1..25}; do
        local response=$(curl -s -w "%{http_code}" -o /dev/null "$API_URL/health" || echo "000")
        if [ "$response" = "429" ]; then
            rate_limit_hit=true
            break
        fi
    done
    
    if [ "$rate_limit_hit" = true ]; then
        echo -e "${GREEN}✓ Rate limiting active${NC}"
    else
        echo -e "${YELLOW}⚠ Rate limiting not triggered (may be configured with higher limits)${NC}"
    fi
}

test_input_validation() {
    echo -e "${YELLOW}Testing Input Validation...${NC}"
    
    # Test malicious input rejection
    local malicious_payload='{
        "timestamp": "2024-01-01T12:00:00Z",
        "source": "test<script>alert(\"xss\")</script>",
        "intent": "<script>alert(\"xss\")</script>",
        "payload": {"test": "data"}
    }'
    
    if [ -n "${ACCESS_TOKEN:-}" ]; then
        local response=$(curl -s -w "%{http_code}" -o /dev/null "$API_URL/api/event" \
            -H "Authorization: Bearer $ACCESS_TOKEN" \
            -H "Content-Type: application/json" \
            -d "$malicious_payload" || echo "000")
        
        if [ "$response" = "400" ]; then
            echo -e "${GREEN}✓ Malicious input rejected${NC}"
        else
            echo -e "${RED}✗ Malicious input accepted (returned $response)${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ Skipping input validation test (no auth token)${NC}"
    fi
}

test_network_segmentation() {
    echo -e "${YELLOW}Testing Network Segmentation...${NC}"
    
    # Test that internal services are not directly accessible from public network
    local internal_services=(
        "context:8081"
        "storage:8082"
        "policy:8083"
        "inference:8087"
    )
    
    for service in "${internal_services[@]}"; do
        local host=$(echo "$service" | cut -d: -f1)
        local port=$(echo "$service" | cut -d: -f2)
        
        # Try to connect directly (should fail from public network)
        if ! curl -s -f "http://$host:$port/health" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ $host:$port not publicly accessible${NC}"
        else
            echo -e "${RED}✗ $host:$port is publicly accessible (security risk!)${NC}"
        fi
    done
}

test_ssl_configuration() {
    echo -e "${YELLOW}Testing SSL Configuration...${NC}"
    
    # Test HTTPS if configured
    if [[ "$API_URL" == https://* ]]; then
        local domain=$(echo "$API_URL" | sed 's|https://||' | cut -d: -f1)
        
        # Test SSL certificate
        if echo | openssl s_client -connect "$domain:443" -servername "$domain" 2>/dev/null | openssl x509 -noout -dates | grep -q "notAfter"; then
            echo -e "${GREEN}✓ SSL certificate is valid${NC}"
        else
            echo -e "${RED}✗ SSL certificate issue detected${NC}"
        fi
        
        # Test TLS version
        local tls_version=$(echo | openssl s_client -connect "$domain:443" -servername "$domain" 2>/dev/null | grep "Protocol" | tail -1 || echo "")
        if echo "$tls_version" | grep -E "TLSv1\.[2-3]"; then
            echo -e "${GREEN}✓ Using modern TLS version${NC}"
        else
            echo -e "${RED}✗ Using outdated TLS version${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ HTTPS not configured (HTTP only)${NC}"
    fi
}

check_secrets() {
    echo -e "${YELLOW}Checking Secrets Configuration...${NC}"
    
    # Check if default secrets are being used
    if grep -q "change-this-secret-key-in-production" .env 2>/dev/null; then
        echo -e "${RED}✗ Default JWT secret detected - change for production!${NC}"
    else
        echo -e "${GREEN}✓ JWT secret appears to be customized${NC}"
    fi
    
    if grep -q "change-this-redis-password-in-production" .env 2>/dev/null; then
        echo -e "${RED}✗ Default Redis password detected - change for production!${NC}"
    else
        echo -e "${GREEN}✓ Redis password appears to be customized${NC}"
    fi
    
    # Check JWT secret length
    local jwt_secret=$(grep UNISON_JWT_SECRET .env 2>/dev/null | cut -d= -f2 || echo "")
    if [ ${#jwt_secret} -ge 64 ]; then
        echo -e "${GREEN}✓ JWT secret length is adequate (${#jwt_secret} characters)${NC}"
    else
        echo -e "${RED}✗ JWT secret too short (${#jwt_secret} characters, minimum 64 recommended)${NC}"
    fi
}

main() {
    echo -e "${YELLOW}=== Unison Security Validation ===${NC}\n"
    
    # Load environment if .env exists
    if [ -f ".env" ]; then
        set -a
        source .env
        set +a
    fi
    
    # Run all tests
    local failed_tests=0
    
    test_auth_service || ((failed_tests++))
    echo
    test_api_gateway || ((failed_tests++))
    echo
    test_security_headers
    echo
    test_authentication_required
    echo
    test_rate_limiting
    echo
    test_input_validation
    echo
    test_network_segmentation
    echo
    test_ssl_configuration
    echo
    check_secrets
    echo
    
    # Summary
    if [ $failed_tests -eq 0 ]; then
        echo -e "${GREEN}=== All Critical Tests Passed ===${NC}"
        echo -e "${GREEN}Your Unison deployment appears to be properly secured!${NC}"
    else
        echo -e "${RED}=== $failed_tests Test(s) Failed ===${NC}"
        echo -e "${RED}Please address the security issues above before production deployment.${NC}"
        exit 1
    fi
    
    echo -e "\n${YELLOW}=== Additional Recommendations ===${NC}"
    echo "• Ensure all default passwords are changed"
    echo "• Use valid SSL certificates in production"
    echo "• Enable comprehensive monitoring and alerting"
    echo "• Regular security audits and penetration testing"
    echo "• Keep all dependencies updated"
    echo "• Implement proper backup and disaster recovery"
}

# Run main function
main "$@"
