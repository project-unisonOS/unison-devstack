# Security-Hardened Deployment Guide

## Overview

This guide covers deploying the Unison platform with comprehensive security hardening including authentication, network segmentation, API gateway, and enhanced input validation.

## Prerequisites

- Docker and Docker Compose installed
- OpenSSL for generating certificates (or use provided test certificates)
- Strong secrets for production deployment

## Quick Start

### 1. Generate Security Secrets

Create a `.env` file with strong secrets:

```bash
# Generate a strong JWT secret (256+ bits)
openssl rand -hex 32

# Generate Redis password
openssl rand -base64 32

# Generate service secrets
openssl rand -base64 32  # for orchestrator
openssl rand -base64 32  # for inference
openssl rand -base64 32  # for policy
```

Create `.env` file:
```env
# JWT Configuration
UNISON_JWT_SECRET=your-generated-256-bit-secret-here

# Redis Configuration
REDIS_PASSWORD=your-redis-password-here

# Service Authentication Secrets
UNISON_ORCHESTRATOR_SERVICE_SECRET=your-orchestrator-secret
UNISON_INFERENCE_SERVICE_SECRET=your-inference-secret
UNISON_POLICY_SERVICE_SECRET=your-policy-secret

# HTTPS Configuration
UNISON_FORCE_HTTPS=true

# CORS Configuration
UNISON_CORS_ORIGINS=https://your-domain.com,https://app.your-domain.com

# Allowed Hosts
UNISON_ALLOWED_HOSTS=your-domain.com,app.your-domain.com,localhost
```

### 2. SSL/TLS Certificates

For production, use proper SSL certificates. For testing, generate self-signed certificates:

```bash
mkdir -p ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssl/kong.key \
  -out ssl/kong.crt \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
```

### 3. Deploy with Security Configuration

```bash
# Deploy the security-hardened stack
docker-compose -f docker-compose.security.yml up -d

# Check service status
docker-compose -f docker-compose.security.yml ps

# View logs
docker-compose -f docker-compose.security.yml logs -f
```

## Architecture Overview

### Network Segmentation

The security-hardened deployment uses multiple isolated networks:

- **Public Network** (172.20.0.0/24): Only API gateway and load balancer
- **Internal Network** (172.21.0.0/24): Service-to-service communication
- **Data Network** (172.22.0.0/24): Storage and database services
- **Auth Network** (172.23.0.0/24): Authentication and Redis
- **Inference Network** (172.24.0.0/24): AI/ML services

### API Gateway (Kong)

Kong serves as the single entry point, providing:
- JWT authentication
- Rate limiting
- CORS handling
- Request/response transformation
- Security headers

### Authentication Flow

1. Client obtains JWT token from `/auth/token`
2. Token is included in `Authorization: Bearer <token>` header
3. Kong validates JWT signature and expiration
4. Service validates token with auth service
5. User roles and permissions are enforced

## Service Configuration

### Authentication Service

The auth service provides:
- User authentication with bcrypt password hashing
- Service-to-service authentication
- Token blacklisting with Redis
- Role-based access control

Default users (change passwords in production):
- admin / admin123
- operator / operator123
- developer / dev123
- user / user123

### Security Headers

All responses include security headers:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy: default-src 'self'...`
- `Strict-Transport-Security` (when HTTPS enabled)

### Rate Limiting

- Global: 20 requests/minute for anonymous
- Authenticated: 100 requests/minute per IP
- Inference: 50 requests/minute per user
- Storage: 200 requests/minute per user
- Services: Custom limits per service type

## Monitoring and Logging

### Security Events

All security events are logged with structured JSON:
- Authentication attempts (success/failure)
- Authorization failures
- Policy denials
- Rate limit violations
- Input validation failures

### Health Checks

All services expose `/health` endpoints:
- Basic service health
- Dependency health checks
- Redis connectivity (auth service)
- Policy service availability

### Metrics

Prometheus-compatible metrics at `/metrics`:
- Request counts by endpoint
- Authentication success/failure rates
- Token issuance counts
- Rate limit violations

## Production Hardening Checklist

### Secrets Management

- [ ] Use strong, randomly generated secrets
- [ ] Store secrets in secure vault (not in git)
- [ ] Rotate secrets regularly
- [ ] Use different secrets per environment

### Network Security

- [ ] Deploy behind proper firewall
- [ ] Use VPN or private networks for admin access
- [ ] Disable unused ports and services
- [ ] Implement proper DNS security

### SSL/TLS

- [ ] Use valid SSL certificates from trusted CA
- [ ] Enable HTTPS only (disable HTTP)
- [ ] Implement certificate rotation
- [ ] Use TLS 1.2+ only

### Authentication

- [ ] Change default passwords
- [ ] Implement password policies
- [ ] Enable multi-factor authentication
- [ ] Set appropriate token lifetimes

### Authorization

- [ ] Review and tighten role permissions
- [ ] Implement principle of least privilege
- [ ] Regular audit of user access
- [ ] Disable unused accounts

### Monitoring

- [ ] Enable comprehensive logging
- [ ] Set up log aggregation and analysis
- [ ] Configure security alerts
- [ ] Monitor for anomalous behavior

### Backup and Recovery

- [ ] Regular database backups
- [ ] Test restore procedures
- [ ] Document disaster recovery plan
- [ ] Store backups securely

## API Usage Examples

### Authentication

```bash
# Get access token
curl -X POST https://your-domain.com/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password&username=admin&password=admin123"

# Use token for authenticated requests
curl -X POST https://your-domain.com/api/event \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2024-01-01T12:00:00Z",
    "source": "test-client",
    "intent": "echo",
    "payload": {"message": "Hello World"}
  }'
```

### Service Authentication

```bash
# Service-to-service authentication
curl -X POST http://auth:8088/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&username=service-orchestrator&password=orchestrator-secret"
```

## Troubleshooting

### Common Issues

**Authentication Failures**
```bash
# Check auth service logs
docker-compose logs auth

# Verify JWT secret matches
grep UNISON_JWT_SECRET .env

# Test token validation
curl -X POST http://localhost:8088/verify \
  -H "Content-Type: application/json" \
  -d '{"token": "your-token-here"}'
```

**Network Connectivity**
```bash
# Check network configuration
docker network ls
docker network inspect unison-devstack_internal

# Test service connectivity
docker-compose exec orchestrator curl http://auth:8088/health
```

**Rate Limiting**
```bash
# Check Kong configuration
curl -X GET http://localhost:8001/services

# View rate limiting plugins
curl -X GET http://localhost:8001/plugins
```

### Security Debug Mode

For debugging, you can temporarily enable verbose logging:

```env
# Add to .env for debugging
LOG_LEVEL=DEBUG
UNISON_DEBUG_AUTH=true
```

**Important**: Remove debug settings in production!

## Migration from Standard Deployment

To migrate from the standard docker-compose.yml:

1. **Backup existing data**
   ```bash
   docker-compose exec storage tar -czf /backup/data.tar.gz /data
   ```

2. **Update configuration**
   - Copy docker-compose.security.yml to docker-compose.yml
   - Add security secrets to .env
   - Generate SSL certificates

3. **Deploy new services**
   ```bash
   docker-compose down
   docker-compose -f docker-compose.security.yml up -d
   ```

4. **Verify functionality**
   - Test authentication
   - Verify all services are healthy
   - Check API connectivity through Kong

## Compliance Considerations

This security implementation addresses common compliance requirements:

- **Authentication**: Strong passwords, JWT tokens, MFA support
- **Authorization**: Role-based access control, least privilege
- **Audit Logging**: Comprehensive security event logging
- **Data Protection**: Input validation, sanitization, encryption in transit
- **Network Security**: Segmentation, firewalls, secure protocols

## Support

For security issues or questions:
- Review the security documentation
- Check service logs for detailed error information
- Test with the provided examples
- Ensure all secrets and certificates are properly configured
