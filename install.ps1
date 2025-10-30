# Unison Installer Script for Windows PowerShell
# Sets up Unison with Docker Compose

param(
    [string]$InstallDir = "$env:USERPROFILE\unison",
    [string]$Version = "latest",
    [switch]$WithOllama,
    [switch]$SingleMachine,
    [switch]$Help
)

# Color output functions
function Write-Info($message) {
    Write-Host "[INFO] $message" -ForegroundColor Blue
}

function Write-Success($message) {
    Write-Host "[SUCCESS] $message" -ForegroundColor Green
}

function Write-Warning($message) {
    Write-Host "[WARNING] $message" -ForegroundColor Yellow
}

function Write-Error($message) {
    Write-Host "[ERROR] $message" -ForegroundColor Red
}

# Help text
function Show-Help {
    @"
Unison Installer Script

USAGE:
    .\install.ps1 [OPTIONS]

OPTIONS:
    -InstallDir DIR        Installation directory (default: $env:USERPROFILE\unison)
    -Version VERSION       Version to install (default: latest)
    -WithOllama            Include Ollama for local LLM inference
    -SingleMachine         Configure for single-machine deployment
    -Help                  Show this help message

EXAMPLES:
    .\install.ps1                                    # Basic installation
    .\install.ps1 -InstallDir "C:\unison" -WithOllama # Install to C:\unison with Ollama
    .\install.ps1 -Version "v1.0.0" -SingleMachine   # Install specific version for single machine

"@
}

# Check prerequisites
function Test-Prerequisites {
    Write-Info "Checking prerequisites..."
    
    # Check if Docker is installed
    try {
        $null = Get-Command docker -ErrorAction Stop
        Write-Success "Docker is installed"
    }
    catch {
        Write-Error "Docker is not installed. Please install Docker Desktop for Windows."
        Write-Info "Visit: https://docs.docker.com/desktop/windows/install/"
        exit 1
    }
    
    # Check if Docker Compose is installed
    try {
        $null = Get-Command docker-compose -ErrorAction Stop
        Write-Success "Docker Compose is installed"
    }
    catch {
        Write-Error "Docker Compose is not installed. Please install Docker Compose."
        Write-Info "Visit: https://docs.docker.com/compose/install/"
        exit 1
    }
    
    # Check if Docker daemon is running
    try {
        $null = docker info 2>$null
        Write-Success "Docker daemon is running"
    }
    catch {
        Write-Error "Docker daemon is not running. Please start Docker Desktop."
        exit 1
    }
    
    Write-Success "Prerequisites check passed"
}

# Create installation directory
function New-InstallDirectory {
    Write-Info "Creating installation directory: $InstallDir"
    
    if (Test-Path $InstallDir) {
        Write-Warning "Directory already exists. Updating existing installation."
    }
    else {
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    }
    
    Set-Location $InstallDir
}

# Download docker-compose.yml
function Get-ComposeFile {
    Write-Info "Downloading Docker Compose configuration..."
    
    $composeContent = @"
version: '3.8'

services:
  orchestrator:
    image: ghcr.io/project-unisonos/unison-orchestrator:latest
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      UNISON_CONTEXT_HOST: "context"
      UNISON_CONTEXT_PORT: "8081"
      UNISON_STORAGE_HOST: "storage"
      UNISON_STORAGE_PORT: "8082"
      UNISON_POLICY_HOST: "policy"
      UNISON_POLICY_PORT: "8083"
      UNISON_INFERENCE_HOST: "inference"
      UNISON_INFERENCE_PORT: "8087"
    depends_on:
      - context
      - storage
      - policy
      - inference

  inference:
    image: ghcr.io/project-unisonos/unison-inference:latest
    restart: unless-stopped
    ports:
      - "8087:8087"
    environment:
      UNISON_INFERENCE_PROVIDER: "ollama"
      UNISON_INFERENCE_MODEL: "llama3.2"
      OLLAMA_BASE_URL: "http://ollama:11434"
    depends_on:
      - ollama

  context:
    image: ghcr.io/project-unisonos/unison-context:latest
    restart: unless-stopped
    ports:
      - "8081:8081"

  storage:
    image: ghcr.io/project-unisonos/unison-storage:latest
    restart: unless-stopped
    ports:
      - "8082:8082"
    volumes:
      - unison_data:/data

  policy:
    image: ghcr.io/project-unisonos/unison-policy:latest
    restart: unless-stopped
    ports:
      - "8083:8083"

  io-core:
    image: ghcr.io/project-unisonos/unison-io-core:latest
    restart: unless-stopped
    ports:
      - "8085:8085"
    environment:
      UNISON_ORCH_HOST: "orchestrator"
      UNISON_ORCH_PORT: "8080"

  io-speech:
    image: ghcr.io/project-unisonos/unison-io-speech:latest
    restart: unless-stopped
    ports:
      - "8084:8084"

  io-vision:
    image: ghcr.io/project-unisonos/unison-io-vision:latest
    restart: unless-stopped
    ports:
      - "8086:8086"

volumes:
  unison_data:
"@
    
    # Add Ollama service if requested
    if ($WithOllama) {
        $composeContent += @"

  ollama:
    image: ollama/ollama:latest
    restart: unless-stopped
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    pull_policy: always

volumes:
  unison_data:
  ollama_data:
"@
    }
    
    $composeContent | Out-File -FilePath "docker-compose.yml" -Encoding UTF8
    Write-Success "Docker Compose configuration downloaded"
}

# Create environment file
function New-EnvironmentFile {
    Write-Info "Creating environment configuration..."
    
    $envContent = @"
# Unison Configuration
# Generated by installer on $(Get-Date)

# Installation directory
UNISON_HOME=$InstallDir

# Version
UNISON_VERSION=$Version

# Ollama configuration
INCLUDE_OLLAMA=$(if ($WithOllama) { "true" } else { "false" })

# Single machine mode
SINGLE_MACHINE=$(if ($SingleMachine) { "true" } else { "false" })

# Optional: External API keys (uncomment to use)
# OPENAI_API_KEY=your-openai-api-key
# AZURE_OPENAI_ENDPOINT=your-azure-endpoint
# AZURE_OPENAI_API_KEY=your-azure-api-key
"@
    
    $envContent | Out-File -FilePath ".env" -Encoding UTF8
    Write-Success "Environment configuration created"
}

# Pull Docker images
function Get-DockerImages {
    Write-Info "Pulling Docker images..."
    
    if ($Version -eq "latest") {
        docker-compose pull
    }
    else {
        # Pull specific versions
        (Get-Content "docker-compose.yml") -replace ":latest", ":$Version" | Set-Content "docker-compose.yml"
        docker-compose pull
        (Get-Content "docker-compose.yml") -replace ":$Version", ":latest" | Set-Content "docker-compose.yml"
    }
    
    Write-Success "Docker images pulled"
}

# Start services
function Start-Services {
    Write-Info "Starting Unison services..."
    
    if ($WithOllama) {
        docker-compose --profile tools up -d
    }
    else {
        docker-compose up -d
    }
    
    Write-Success "Unison services started"
}

# Wait for services to be ready
function Wait-ForServices {
    Write-Info "Waiting for services to be ready..."
    
    # Wait for orchestrator
    $timeout = 60
    $ready = $false
    
    while ($timeout -gt 0 -and -not $ready) {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8080/health" -TimeoutSec 2 -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                $ready = $true
                Write-Success "Orchestrator is ready"
                break
            }
        }
        catch {
            # Service not ready yet
        }
        
        Start-Sleep -Seconds 2
        $timeout -= 2
    }
    
    if ($timeout -le 0) {
        Write-Warning "Orchestrator did not become ready within timeout"
    }
    
    # Check readiness
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8080/ready" -TimeoutSec 5 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-Success "All services are ready"
        }
    }
    catch {
        Write-Warning "Some services may still be starting"
    }
}

# Setup Ollama model if included
function Set-OllamaModel {
    if ($WithOllama) {
        Write-Info "Setting up Ollama model..."
        
        # Wait for Ollama to be ready
        $timeout = 60
        $ready = $false
        
        while ($timeout -gt 0 -and -not $ready) {
            try {
                $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 2 -ErrorAction Stop
                if ($response.StatusCode -eq 200) {
                    $ready = $true
                    break
                }
            }
            catch {
                # Ollama not ready yet
            }
            
            Start-Sleep -Seconds 2
            $timeout -= 2
        }
        
        if ($timeout -gt 0) {
            # Pull llama3.2 model
            docker exec ollama ollama pull llama3.2
            Write-Success "Ollama model setup complete"
        }
        else {
            Write-Warning "Ollama did not become ready within timeout"
            Write-Info "You can pull the model later with: docker exec ollama ollama pull llama3.2"
        }
    }
}

# Create CLI script
function New-CLIScript {
    Write-Info "Creating Unison CLI script..."
    
    $cliContent = @"
# Unison CLI Wrapper for PowerShell

param(
    [Parameter(Position=0)]
    [ValidateSet("start", "stop", "restart", "status", "logs", "update", "clean", "help")]
    [string]$Command = "help",
    
    [Parameter(Position=1)]
    [string]$Service = ""
)

`$UNISON_HOME = `$env:UNISON_HOME, "`$env:USERPROFILE\unison"
if (Test-Path Env:UNISON_HOME) {
    `$UNISON_HOME = `$env:UNISON_HOME
}

`$COMPOSE_FILE = "`$UNISON_HOME\docker-compose.yml"

function Show-Help {
    @"
Unison CLI - Management tool for Unison services

USAGE:
    unison.ps1 [COMMAND] [SERVICE]

COMMANDS:
    start           Start all services
    stop            Stop all services
    restart         Restart all services
    status          Show service status
    logs            Show service logs
    update          Update to latest version
    clean           Remove all containers and volumes
    help            Show this help message

EXAMPLES:
    .\unison.ps1 start                    # Start all services
    .\unison.ps1 logs orchestrator        # Show orchestrator logs
    .\unison.ps1 status                   # Check service health

"@
}

function Show-Status {
    Write-Host "Unison Service Status" -ForegroundColor Green
    Write-Host "========================"
    
    Set-Location `$UNISON_HOME
    docker-compose ps
    
    Write-Host ""
    Write-Host "Health Checks" -ForegroundColor Green
    Write-Host "==============="
    
    # Check main services
    `$services = @(
        @{Name="orchestrator"; Port=8080},
        @{Name="context"; Port=8081},
        @{Name="storage"; Port=8082},
        @{Name="policy"; Port=8083},
        @{Name="inference"; Port=8087},
        @{Name="io-core"; Port=8085},
        @{Name="io-speech"; Port=8084},
        @{Name="io-vision"; Port=8086}
    )
    
    foreach (`$service in `$services) {
        try {
            `$response = Invoke-WebRequest -Uri "http://localhost:`$(`$service.Port)/health" -TimeoutSec 2 -ErrorAction Stop
            if (`$response.StatusCode -eq 200) {
                Write-Host "`$(`$service.Name): ✓ Healthy" -ForegroundColor Green
            }
        }
        catch {
            Write-Host "`$(`$service.Name): ✗ Unhealthy" -ForegroundColor Red
        }
    }
    
    # Check Ollama if enabled
    try {
        `$response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 2 -ErrorAction Stop
        if (`$response.StatusCode -eq 200) {
            Write-Host "ollama: ✓ Healthy" -ForegroundColor Green
        }
    }
    catch {
        # Ollama not enabled or not ready
    }
}

# Main command handler
switch (`$Command) {
    "start" {
        Write-Host "Starting Unison services..." -ForegroundColor Green
        Set-Location `$UNISON_HOME
        docker-compose up -d
        Write-Host "Services started. Run '.\unison.ps1 status' to check health."
    }
    "stop" {
        Write-Host "Stopping Unison services..." -ForegroundColor Yellow
        Set-Location `$UNISON_HOME
        docker-compose down
        Write-Host "Services stopped."
    }
    "restart" {
        Write-Host "Restarting Unison services..." -ForegroundColor Yellow
        Set-Location `$UNISON_HOME
        docker-compose restart
        Write-Host "Services restarted."
    }
    "status" {
        Show-Status
    }
    "logs" {
        Set-Location `$UNISON_HOME
        if (`$Service) {
            docker-compose logs -f `$Service
        }
        else {
            docker-compose logs -f
        }
    }
    "update" {
        Write-Host "Updating Unison..." -ForegroundColor Green
        Set-Location `$UNISON_HOME
        docker-compose pull
        docker-compose up -d
        Write-Host "Update complete."
    }
    "clean" {
        Write-Host "This will remove all containers and volumes. Are you sure? (y/N)" -ForegroundColor Red
        `$response = Read-Host
        if (`$response -eq 'y' -or `$response -eq 'Y') {
            Set-Location `$UNISON_HOME
            docker-compose down -v
            docker system prune -f
            Write-Host "Cleanup complete."
        }
    }
    "help" {
        Show-Help
    }
}
"@
    
    $cliContent | Out-File -FilePath "unison.ps1" -Encoding UTF8
    
    Write-Success "Unison CLI created at $InstallDir\unison.ps1"
}

# Print completion message
function Show-Completion {
    $completionMessage = @"

🎉 Unison installation complete!

Quick Start:
    cd $InstallDir
    .\unison.ps1 status    # Check service status
    .\unison.ps1 logs      # View logs

Service URLs:
    Orchestrator:  http://localhost:8080
    Context:       http://localhost:8081
    Storage:       http://localhost:8082
    Policy:        http://localhost:8083
    Inference:     http://localhost:8087
    IO Core:       http://localhost:8085
    IO Speech:     http://localhost:8084
    IO Vision:     http://localhost:8086

"@
    
    if ($WithOllama) {
        $completionMessage += @"

Ollama:
    API:     http://localhost:11434
    Model:   llama3.2 (pulled automatically)

"@
    }
    
    $completionMessage += @"

Next Steps:
    1. Test the installation: Invoke-WebRequest -Uri "http://localhost:8080/health"
    2. View documentation: https://github.com/project-unisonos/unison
    3. Join the community: https://github.com/project-unisonos/unison/discussions

Note: Use the 'unison.ps1' script to manage your Unison installation.

"@
    
    Write-Host $completionMessage -ForegroundColor Green
}

# Main installation flow
function Main {
    Write-Host "Unison Installer for Windows" -ForegroundColor Blue
    Write-Host "============================="
    Write-Host ""
    
    if ($Help) {
        Show-Help
        return
    }
    
    Test-Prerequisites
    New-InstallDirectory
    Get-ComposeFile
    New-EnvironmentFile
    Get-DockerImages
    Start-Services
    Wait-ForServices
    Set-OllamaModel
    New-CLIScript
    Show-Completion
}

# Run main function
Main
