#!/usr/bin/env python3
"""
Setup script for Ollama models.
Pulls the default model (llama3.2) for local inference.
"""

import os
import sys
import time
import httpx
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost")
OLLAMA_PORT = os.getenv("OLLAMA_PORT", "11434")
OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

def wait_for_ollama(max_attempts=30, delay=2):
    """Wait for Ollama service to be ready."""
    logger.info(f"Waiting for Ollama at {OLLAMA_BASE_URL}...")

    for attempt in range(max_attempts):
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                logger.info("Ollama is ready!")
                return True
        except Exception as e:
            logger.debug(f"Attempt {attempt + 1}: Ollama not ready - {e}")

        if attempt < max_attempts - 1:
            time.sleep(delay)

    logger.error("Ollama did not become ready in time")
    return False

def pull_model(model_name):
    """Pull a model from Ollama."""
    logger.info(f"Pulling model: {model_name}")

    try:
        with httpx.Client(timeout=300.0) as client:  # 5 minute timeout for large models
            response = client.post(f"{OLLAMA_BASE_URL}/api/pull", json={"name": model_name})

        if response.status_code == 200:
            logger.info(f"Successfully pulled model: {model_name}")
            return True
        else:
            logger.error(f"Failed to pull model {model_name}: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error pulling model {model_name}: {e}")
        return False

def list_models():
    """List available models."""
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{OLLAMA_BASE_URL}/api/tags")

        if response.status_code == 200:
            models = response.json().get("models", [])
            logger.info(f"Available models: {[m['name'] for m in models]}")
            return models
        else:
            logger.error(f"Failed to list models: {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        return []

def main():
    """Main setup function."""
    logger.info("Starting Ollama setup...")

    # Wait for Ollama to be ready
    if not wait_for_ollama():
        sys.exit(1)

    # Check if model already exists
    models = list_models()
    model_names = [m['name'] for m in models]

    if DEFAULT_MODEL in model_names:
        logger.info(f"Model {DEFAULT_MODEL} already exists")
        return

    # Pull the default model
    if not pull_model(DEFAULT_MODEL):
        logger.error("Failed to pull required model")
        sys.exit(1)

    # Verify model was pulled
    models = list_models()
    if DEFAULT_MODEL in [m['name'] for m in models]:
        logger.info("Setup completed successfully!")
    else:
        logger.error("Model not found after pull")
        sys.exit(1)

if __name__ == "__main__":
    main()
