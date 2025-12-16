#!/bin/bash
# Unison Installer Script
# Sets up Unison with Docker Compose

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
INSTALL_DIR="$HOME/unison"
VERSION="latest"
INCLUDE_OLLAMA=false
SINGLE_MACHINE=false

# Help text
help_text() {
    cat << EOF
Unison Installer Script

USAGE:
    $0 [OPTIONS]

OPTIONS:
    -d, --dir DIR           Installation directory (default: $HOME/unison)
    -v, --version VERSION   Version to install (default: latest)
    -o, --with-ollama       Include Ollama for local LLM inference
    -s, --single-machine    Configure for single-machine deployment
    -h, --help              Show this help message

EXAMPLES:
    $0                                      # Basic installation
    $0 -d /opt/unison -o                    # Install to /opt/unison with Ollama
    $0 --version v1.0.0 --single-machine   # Install specific version for single machine

EOF
}

# Print functions
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--dir)
            INSTALL_DIR="$2"
            shift 2
            ;;
        -v|--version)
            VERSION="$2"
            shift 2
            ;;
        -o|--with-ollama)
            INCLUDE_OLLAMA=true
            shift
            ;;
        -s|--single-machine)
            SINGLE_MACHINE=true
            shift
            ;;
        -h|--help)
            help_text
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            help_text
            exit 1
            ;;
    esac
done

# Check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."

    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        print_info "Visit: https://docs.docker.com/get-docker/"
        exit 1
    fi

    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        print_info "Visit: https://docs.docker.com/compose/install/"
        exit 1
    fi

    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running. Please start Docker."
        exit 1
    fi

    print_success "Prerequisites check passed"
}

# Create installation directory
create_install_dir() {
    print_info "Creating installation directory: $INSTALL_DIR"

    if [ -d "$INSTALL_DIR" ]; then
        print_warning "Directory already exists. Updating existing installation."
    else
        mkdir -p "$INSTALL_DIR"
    fi

    cd "$INSTALL_DIR"
}

# Download docker-compose.yml
download_compose_file() {
    print_info "Downloading Docker Compose configuration..."

    # Base compose file
    cat > docker-compose.yml << 'EOF'
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
      UNISON_INFERENCE_MODEL: "qwen2.5"
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
EOF

    # Add Ollama service if requested
    if [ "$INCLUDE_OLLAMA" = true ]; then
        cat >> docker-compose.yml << 'EOF'

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
EOF
    fi

    print_success "Docker Compose configuration downloaded"
}

# Create environment file
create_env_file() {
    print_info "Creating environment configuration..."

    cat > .env << EOF
# Unison Configuration
# Generated by installer on $(date)

# Installation directory
UNISON_HOME=$INSTALL_DIR

# Version
UNISON_VERSION=$VERSION

# Ollama configuration
INCLUDE_OLLAMA=$INCLUDE_OLLAMA

# Single machine mode
SINGLE_MACHINE=$SINGLE_MACHINE

# Optional: External API keys (uncomment to use)
# OPENAI_API_KEY=your-openai-api-key
# AZURE_OPENAI_ENDPOINT=your-azure-endpoint
# AZURE_OPENAI_API_KEY=your-azure-api-key
EOF

    print_success "Environment configuration created"
}

# Pull Docker images
pull_images() {
    print_info "Pulling Docker images..."

    if [ "$VERSION" = "latest" ]; then
        docker-compose pull
    else
        # Pull specific versions
        sed -i.bak "s/:latest/:$VERSION/g" docker-compose.yml
        docker-compose pull
        mv docker-compose.yml.bak docker-compose.yml
    fi

    print_success "Docker images pulled"
}

# Start services
start_services() {
    print_info "Starting Unison services..."

    if [ "$INCLUDE_OLLAMA" = true ]; then
        docker-compose --profile tools up -d
    else
        docker-compose up -d
    fi

    print_success "Unison services started"
}

# Wait for services to be ready
wait_for_services() {
    print_info "Waiting for services to be ready..."

    # Wait for orchestrator
    timeout=60
    while [ $timeout -gt 0 ]; do
        if curl -s http://localhost:8080/health > /dev/null 2>&1; then
            print_success "Orchestrator is ready"
            break
        fi
        sleep 2
        timeout=$((timeout - 2))
    done

    if [ $timeout -le 0 ]; then
        print_warning "Orchestrator did not become ready within timeout"
    fi

    # Check readiness
    if curl -s http://localhost:8080/ready > /dev/null 2>&1; then
        print_success "All services are ready"
    else
        print_warning "Some services may still be starting"
    fi
}

# Setup Ollama model if included
setup_ollama() {
    if [ "$INCLUDE_OLLAMA" = true ]; then
        print_info "Setting up Ollama model..."

        # Wait for Ollama to be ready
        timeout=60
        while [ $timeout -gt 0 ]; do
            if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
                break
            fi
            sleep 2
            timeout=$((timeout - 2))
        done

        if [ $timeout -gt 0 ]; then
            # Pull qwen2.5 model
            docker exec ollama ollama pull qwen2.5
            print_success "Ollama model setup complete"
        else
            print_warning "Ollama did not become ready within timeout"
            print_info "You can pull the model later with: docker exec ollama ollama pull qwen2.5"
        fi
    fi
}

# Create CLI script
create_cli_script() {
    print_info "Creating Unison CLI script..."

    cat > unison << 'EOF'
#!/bin/bash
# Unison CLI Wrapper

UNISON_HOME="${UNISON_HOME:-$HOME/unison}"
COMPOSE_FILE="$UNISON_HOME/docker-compose.yml"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Help function
help() {
    cat << EOF
Unison CLI - Management tool for Unison services

USAGE:
    unison [COMMAND]

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
    unison start                    # Start all services
    unison logs orchestrator        # Show orchestrator logs
    unison status                   # Check service health

EOF
}

# Status command
status() {
    echo -e "${GREEN}Unison Service Status${NC}"
    echo "========================"

    cd "$UNISON_HOME"
    docker-compose ps

    echo ""
    echo -e "${GREEN}Health Checks${NC}"
    echo "==============="

    # Check main services
    services=("orchestrator:8080" "context:8081" "storage:8082" "policy:8083" "inference:8087" "io-core:8085" "io-speech:8084" "io-vision:8086")

    for service in "${services[@]}"; do
        name=$(echo $service | cut -d: -f1)
        port=$(echo $service | cut -d: -f2)

        if curl -s "http://localhost:$port/health" > /dev/null 2>&1; then
            echo -e "$name: ${GREEN}✓ Healthy${NC}"
        else
            echo -e "$name: ${RED}✗ Unhealthy${NC}"
        fi
    done

    # Check Ollama if enabled
    if curl -s "http://localhost:11434/api/tags" > /dev/null 2>&1; then
        echo -e "ollama: ${GREEN}✓ Healthy${NC}"
    fi
}

# Logs command
logs() {
    cd "$UNISON_HOME"
    if [ -n "$1" ]; then
        docker-compose logs -f "$1"
    else
        docker-compose logs -f
    fi
}

# Main command handler
case "${1:-help}" in
    start)
        echo -e "${GREEN}Starting Unison services...${NC}"
        cd "$UNISON_HOME"
        docker-compose up -d
        echo "Services started. Run 'unison status' to check health."
        ;;
    stop)
        echo -e "${YELLOW}Stopping Unison services...${NC}"
        cd "$UNISON_HOME"
        docker-compose down
        echo "Services stopped."
        ;;
    restart)
        echo -e "${YELLOW}Restarting Unison services...${NC}"
        cd "$UNISON_HOME"
        docker-compose restart
        echo "Services restarted."
        ;;
    status)
        status
        ;;
    logs)
        logs "$2"
        ;;
    update)
        echo -e "${GREEN}Updating Unison...${NC}"
        cd "$UNISON_HOME"
        docker-compose pull
        docker-compose up -d
        echo "Update complete."
        ;;
    clean)
        echo -e "${RED}This will remove all containers and volumes. Are you sure? (y/N)${NC}"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            cd "$UNISON_HOME"
            docker-compose down -v
            docker system prune -f
            echo "Cleanup complete."
        fi
        ;;
    help)
        help
        ;;
    *)
        echo "Unknown command: $1"
        help
        exit 1
        ;;
esac
EOF

    chmod +x unison

    # Add to PATH if not already there
    if ! echo "$PATH" | grep -q "$INSTALL_DIR"; then
        echo "export PATH=\"\$PATH:$INSTALL_DIR\"" >> ~/.bashrc
        export PATH="$PATH:$INSTALL_DIR"
    fi

    print_success "Unison CLI created at $INSTALL_DIR/unison"
}

# Print completion message
print_completion() {
    cat << EOF

${GREEN}🎉 Unison installation complete!${NC}

${BLUE}Quick Start:${NC}
    cd $INSTALL_DIR
    ./unison status    # Check service status
    ./unison logs      # View logs

${BLUE}Service URLs:${NC}
    Orchestrator:  http://localhost:8080
    Context:       http://localhost:8081
    Storage:       http://localhost:8082
    Policy:        http://localhost:8083
    Inference:     http://localhost:8087
    IO Core:       http://localhost:8085
    IO Speech:     http://localhost:8084
    IO Vision:     http://localhost:8086

EOF

    if [ "$INCLUDE_OLLAMA" = true ]; then
        echo -e "${BLUE}Ollama:${NC}"
        echo "    API:     http://localhost:11434"
        echo "    Model:   qwen2.5 (pulled automatically)"
        echo ""
    fi

    cat << EOF
${BLUE}Next Steps:${NC}
    1. Test the installation: curl http://localhost:8080/health
    2. View documentation: https://github.com/project-unisonos/unison
    3. Join the community: https://github.com/project-unisonos/unison/discussions

${YELLOW}Note:${NC} The 'unison' command has been added to your PATH.
        You may need to restart your shell or run: source ~/.bashrc

EOF
}

# Main installation flow
main() {
    echo -e "${BLUE}Unison Installer${NC}"
    echo "=================="
    echo ""

    check_prerequisites
    create_install_dir
    download_compose_file
    create_env_file
    pull_images
    start_services
    wait_for_services
    setup_ollama
    create_cli_script
    print_completion
}

# Run main function
main
