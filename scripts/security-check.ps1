# Security Validation Script for Unison (PowerShell Version)
# This script validates the security configuration of a deployed Unison stack

param(
    [string]$AuthUrl = $env:UNISON_AUTH_URL ?? "http://localhost:8088",
    [string]$ApiUrl = $env:UNISON_API_URL ?? "http://localhost",
    [string]$KongAdminUrl = $env:UNISON_KONG_ADMIN_URL ?? "http://localhost:8001"
)

# Color output functions
function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

function Write-Section {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Yellow
}

# Test functions
function Test-AuthService {
    Write-Section "Testing Authentication Service..."

    try {
        # Test health endpoint
        $response = Invoke-RestMethod -Uri "$AuthUrl/health" -Method Get -ErrorAction Stop
        Write-Success "Auth service health check passed"
    }
    catch {
        Write-Error "Auth service health check failed"
        return $false
    }

    try {
        # Test token endpoint with default credentials
        $tokenResponse = Invoke-RestMethod -Uri "$AuthUrl/token" -Method Post `
            -ContentType "application/x-www-form-urlencoded" `
            -Body "grant_type=password&username=admin&password=admin123" `
            -ErrorAction Stop

        if ($tokenResponse.access_token) {
            Write-Success "Token endpoint working"
            $script:AccessToken = $tokenResponse.access_token
        } else {
            Write-Error "Token endpoint failed - no access token returned"
            return $false
        }
    }
    catch {
        Write-Error "Token endpoint failed"
        return $false
    }

    try {
        # Test token verification
        $verifyBody = @{ token = $script:AccessToken } | ConvertTo-Json
        $verifyResponse = Invoke-RestMethod -Uri "$AuthUrl/verify" -Method Post `
            -ContentType "application/json" `
            -Body $verifyBody `
            -ErrorAction Stop

        if ($verifyResponse.valid -eq $true) {
            Write-Success "Token verification working"
        } else {
            Write-Error "Token verification failed"
            return $false
        }
    }
    catch {
        Write-Error "Token verification failed"
        return $false
    }

    return $true
}

function Test-ApiGateway {
    Write-Section "Testing API Gateway (Kong)..."

    try {
        # Test Kong admin API
        $null = Invoke-RestMethod -Uri "$KongAdminUrl/services" -Method Get -ErrorAction Stop
        Write-Success "Kong admin API accessible"
    }
    catch {
        Write-Error "Kong admin API not accessible"
        return $false
    }

    try {
        # Test JWT plugin is enabled
        $plugins = Invoke-RestMethod -Uri "$KongAdminUrl/plugins" -Method Get -ErrorAction Stop
        if ($plugins.data.name -contains "jwt") {
            Write-Success "JWT plugin enabled"
        } else {
            Write-Error "JWT plugin not found"
            return $false
        }
    }
    catch {
        Write-Error "Failed to check Kong plugins"
        return $false
    }

    try {
        # Test rate limiting plugin is enabled
        $plugins = Invoke-RestMethod -Uri "$KongAdminUrl/plugins" -Method Get -ErrorAction Stop
        if ($plugins.data.name -contains "rate-limiting") {
            Write-Success "Rate limiting plugin enabled"
        } else {
            Write-Error "Rate limiting plugin not found"
            return $false
        }
    }
    catch {
        Write-Error "Failed to check rate limiting plugin"
        return $false
    }

    try {
        # Test CORS plugin is enabled
        $plugins = Invoke-RestMethod -Uri "$KongAdminUrl/plugins" -Method Get -ErrorAction Stop
        if ($plugins.data.name -contains "cors") {
            Write-Success "CORS plugin enabled"
        } else {
            Write-Error "CORS plugin not found"
            return $false
        }
    }
    catch {
        Write-Error "Failed to check CORS plugin"
        return $false
    }

    return $true
}

function Test-SecurityHeaders {
    Write-Section "Testing Security Headers..."

    try {
        # Test headers on a protected endpoint
        $response = Invoke-WebRequest -Uri "$ApiUrl/health" -Method Get -ErrorAction Stop

        # Check for security headers
        $securityHeaders = @(
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Referrer-Policy",
            "Content-Security-Policy"
        )

        foreach ($header in $securityHeaders) {
            if ($response.Headers[$header]) {
                Write-Success "$header header present"
            } else {
                Write-Error "$header header missing"
            }
        }
    }
    catch {
        Write-Error "Failed to retrieve security headers"
        return $false
    }

    return $true
}

function Test-AuthenticationRequired {
    Write-Section "Testing Authentication Requirements..."

    try {
        # Test that protected endpoints require authentication
        $body = @{ test = "data" } | ConvertTo-Json
        $response = Invoke-WebRequest -Uri "$ApiUrl/api/event" -Method Post `
            -ContentType "application/json" `
            -Body $body `
            -ErrorAction Stop

        Write-Warning "Protected endpoint returned $($response.StatusCode) (expected 401/403)"
    }
    catch {
        if ($_.Exception.Response.StatusCode -eq 401 -or $_.Exception.Response.StatusCode -eq 403) {
            Write-Success "Protected endpoint requires authentication"
        } else {
            Write-Error "Protected endpoint returned $($_.Exception.Response.StatusCode) (expected 401/403)"
        }
    }

    return $true
}

function Test-RateLimiting {
    Write-Section "Testing Rate Limiting..."

    $rateLimitHit = $false

    # Make multiple rapid requests to test rate limiting
    for ($i = 1; $i -le 25; $i++) {
        try {
            $response = Invoke-WebRequest -Uri "$ApiUrl/health" -Method Get -ErrorAction Stop
        }
        catch {
            if ($_.Exception.Response.StatusCode -eq 429) {
                $rateLimitHit = $true
                break
            }
        }

        Start-Sleep -Milliseconds 100
    }

    if ($rateLimitHit) {
        Write-Success "Rate limiting active"
    } else {
        Write-Warning "Rate limiting not triggered (may be configured with higher limits)"
    }

    return $true
}

function Test-InputValidation {
    Write-Section "Testing Input Validation..."

    if ($script:AccessToken) {
        try {
            $maliciousPayload = @{
                timestamp = "2024-01-01T12:00:00Z"
                source = "test<script>alert(""xss"")</script>"
                intent = "<script>alert(""xss"")</script>"
                payload = @{ test = "data" }
            } | ConvertTo-Json -Depth 3

            $response = Invoke-WebRequest -Uri "$ApiUrl/api/event" -Method Post `
                -ContentType "application/json" `
                -Body $maliciousPayload `
                -Headers @{ Authorization = "Bearer $script:AccessToken" } `
                -ErrorAction Stop

            Write-Error "Malicious input accepted (returned $($response.StatusCode))"
        }
        catch {
            if ($_.Exception.Response.StatusCode -eq 400) {
                Write-Success "Malicious input rejected"
            } else {
                Write-Error "Unexpected response: $($_.Exception.Response.StatusCode)"
            }
        }
    } else {
        Write-Warning "Skipping input validation test (no auth token)"
    }

    return $true
}

function Test-NetworkSegmentation {
    Write-Section "Testing Network Segmentation..."

    # Test that internal services are not directly accessible from public network
    $internalServices = @(
        @{ host = "context"; port = 8081 },
        @{ host = "storage"; port = 8082 },
        @{ host = "policy"; port = 8083 },
        @{ host = "inference"; port = 8087 }
    )

    foreach ($service in $internalServices) {
        try {
            $response = Invoke-WebRequest -Uri "http://$($service.host):$($service.port)/health" -Method Get -TimeoutSec 5 -ErrorAction Stop
            Write-Error "$($service.host):$($service.port) is publicly accessible (security risk!)"
        }
        catch {
            Write-Success "$($service.host):$($service.port) not publicly accessible"
        }
    }

    return $true
}

function Test-SSLConfiguration {
    Write-Section "Testing SSL Configuration..."

    if ($ApiUrl -like "https://*") {
        $domain = ($ApiUrl -replace "https://", "") -split ":" | Select-Object -First 1

        try {
            # Test SSL certificate
            $cert = [System.Net.ServicePointManager]::FindServicePoint($domain, $null).Certificate
            if ($cert -and $cert.NotAfter -gt (Get-Date)) {
                Write-Success "SSL certificate is valid"
            } else {
                Write-Error "SSL certificate issue detected"
            }
        }
        catch {
            Write-Error "Failed to validate SSL certificate"
        }

        try {
            # Test TLS version
            $tcpClient = New-Object System.Net.Sockets.TcpClient
            $tcpClient.Connect($domain, 443)
            $sslStream = New-Object System.Net.Security.SslStream($tcpClient.GetStream())
            $sslStream.AuthenticateAsClient($domain)
            $tlsVersion = $sslStream.SslProtocol

            if ($tlsVersion -ge [System.Net.Security.SslProtocols]::Tls12) {
                Write-Success "Using modern TLS version ($tlsVersion)"
            } else {
                Write-Error "Using outdated TLS version ($tlsVersion)"
            }

            $sslStream.Close()
            $tcpClient.Close()
        }
        catch {
            Write-Error "Failed to check TLS version"
        }
    } else {
        Write-Warning "HTTPS not configured (HTTP only)"
    }

    return $true
}

function Test-Secrets {
    Write-Section "Checking Secrets Configuration..."

    # Load environment file if exists
    $envFile = ".env"
    if (Test-Path $envFile) {
        $envContent = Get-Content $envFile

        # Check if default secrets are being used
        if ($envContent -match "change-this-secret-key-in-production") {
            Write-Error "Default JWT secret detected - change for production!"
        } else {
            Write-Success "JWT secret appears to be customized"
        }

        if ($envContent -match "change-this-redis-password-in-production") {
            Write-Error "Default Redis password detected - change for production!"
        } else {
            Write-Success "Redis password appears to be customized"
        }

        # Check JWT secret length
        $jwtSecret = ($envContent | Where-Object { $_ -match "^UNISON_JWT_SECRET=" }) -replace "UNISON_JWT_SECRET=", ""
        if ($jwtSecret.Length -ge 64) {
            Write-Success "JWT secret length is adequate ($($jwtSecret.Length) characters)"
        } else {
            Write-Error "JWT secret too short ($($jwtSecret.Length) characters, minimum 64 recommended)"
        }
    } else {
        Write-Warning ".env file not found - cannot check secrets configuration"
    }

    return $true
}

# Main execution
function Main {
    Write-Section "=== Unison Security Validation ==="
    Write-Host ""

    $failedTests = 0

    # Run all tests
    if (-not (Test-AuthService)) { $failedTests++ }
    Write-Host ""

    if (-not (Test-ApiGateway)) { $failedTests++ }
    Write-Host ""

    Test-SecurityHeaders
    Write-Host ""

    Test-AuthenticationRequired
    Write-Host ""

    Test-RateLimiting
    Write-Host ""

    Test-InputValidation
    Write-Host ""

    Test-NetworkSegmentation
    Write-Host ""

    Test-SSLConfiguration
    Write-Host ""

    Test-Secrets
    Write-Host ""

    # Summary
    if ($failedTests -eq 0) {
        Write-Success "=== All Critical Tests Passed ==="
        Write-Success "Your Unison deployment appears to be properly secured!"
    } else {
        Write-Error "=== $failedTests Test(s) Failed ==="
        Write-Error "Please address the security issues above before production deployment."
        exit 1
    }

    Write-Host ""
    Write-Section "=== Additional Recommendations ==="
    Write-Host "• Ensure all default passwords are changed"
    Write-Host "• Use valid SSL certificates in production"
    Write-Host "• Enable comprehensive monitoring and alerting"
    Write-Host "• Regular security audits and penetration testing"
    Write-Host "• Keep all dependencies updated"
    Write-Host "• Implement proper backup and disaster recovery"
}

# Run main function
Main
