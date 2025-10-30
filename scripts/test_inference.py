#!/usr/bin/env python3
"""
Test script for Phase 9: External Inference Integration.
Tests inference intents through the Orchestrator to verify end-to-end functionality.
"""

import os
import sys
import time
import httpx
import json
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ORCH_HOST = os.getenv("UNISON_ORCH_HOST", "localhost")
ORCH_PORT = os.getenv("UNISON_ORCH_PORT", "8080")
ORCH_BASE_URL = f"http://{ORCH_HOST}:{ORCH_PORT}"

def wait_for_service(url: str, max_attempts: int = 30, delay: float = 2.0) -> bool:
    """Wait for a service to become healthy."""
    logger.info(f"Waiting for service at {url}...")
    
    for attempt in range(max_attempts):
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{url}/health")
            if response.status_code == 200:
                logger.info(f"Service at {url} is healthy!")
                return True
        except Exception as e:
            logger.debug(f"Attempt {attempt + 1}: Service not ready - {e}")
        
        if attempt < max_attempts - 1:
            time.sleep(delay)
    
    logger.error(f"Service at {url} did not become ready in time")
    return False

def test_orchestrator_ready() -> bool:
    """Test if Orchestrator and all dependencies are ready."""
    logger.info("Testing Orchestrator readiness...")
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{ORCH_BASE_URL}/ready")
        
        if response.status_code == 200:
            ready_data = response.json()
            logger.info(f"Orchestrator ready status: {ready_data}")
            
            # Check all dependencies
            deps = ready_data.get("deps", {})
            all_ok = ready_data.get("ready", False)
            
            logger.info(f"Dependencies: {deps}")
            return all_ok
        else:
            logger.error(f"Orchestrator readiness check failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error checking Orchestrator readiness: {e}")
        return False

def test_inference_intent(intent: str, prompt: str, test_name: str) -> Dict[str, Any]:
    """Test an inference intent through the Orchestrator."""
    logger.info(f"Testing {test_name}: {intent}")
    
    envelope = {
        "intent": intent,
        "source": "test-script",
        "payload": {
            "prompt": prompt,
            "max_tokens": 100,
            "temperature": 0.7
        },
        "safety_context": {
            "data_classification": "public"
        }
    }
    
    try:
        with httpx.Client(timeout=60.0) as client:  # Longer timeout for inference
            response = client.post(
                f"{ORCH_BASE_URL}/event",
                json=envelope,
                headers={"Content-Type": "application/json"}
            )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"{test_name} successful!")
            logger.info(f"Result preview: {str(result.get('inference_result', ''))[:200]}...")
            return {"success": True, "result": result}
        else:
            logger.error(f"{test_name} failed: {response.status_code} - {response.text}")
            return {"success": False, "error": response.text}
    except Exception as e:
        logger.error(f"Error testing {test_name}: {e}")
        return {"success": False, "error": str(e)}

def main():
    """Run all inference tests."""
    logger.info("Starting Phase 9 inference integration tests...")
    
    # Wait for Orchestrator
    if not wait_for_service(ORCH_BASE_URL):
        logger.error("Orchestrator not available")
        sys.exit(1)
    
    # Check readiness
    if not test_orchestrator_ready():
        logger.error("Orchestrator dependencies not ready")
        sys.exit(1)
    
    # Test cases
    test_cases = [
        {
            "intent": "summarize.doc",
            "prompt": "Summarize this text: Artificial intelligence is transforming how we work and live. Machine learning algorithms can now process vast amounts of data, recognize patterns, and make predictions with remarkable accuracy. From healthcare to finance, AI is enabling new capabilities and improving efficiency across industries.",
            "name": "Document Summarization"
        },
        {
            "intent": "analyze.code",
            "prompt": "Analyze this Python code: def fibonacci(n): if n <= 1: return n; return fibonacci(n-1) + fibonacci(n-2)",
            "name": "Code Analysis"
        },
        {
            "intent": "translate.text",
            "prompt": "Translate to French: Hello, how are you today?",
            "name": "Text Translation"
        },
        {
            "intent": "generate.idea",
            "prompt": "Generate ideas for a sustainable home garden",
            "name": "Idea Generation"
        }
    ]
    
    results = []
    for test_case in test_cases:
        result = test_inference_intent(
            test_case["intent"],
            test_case["prompt"],
            test_case["name"]
        )
        results.append({
            "name": test_case["name"],
            "intent": test_case["intent"],
            "success": result["success"]
        })
        
        # Small delay between tests
        time.sleep(2)
    
    # Summary
    logger.info("\n=== Test Summary ===")
    passed = sum(1 for r in results if r["success"])
    total = len(results)
    
    for result in results:
        status = "✓ PASS" if result["success"] else "✗ FAIL"
        logger.info(f"{status}: {result['name']} ({result['intent']})")
    
    logger.info(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        logger.info("🎉 All inference tests passed! Phase 9 integration is working.")
        return 0
    else:
        logger.error("❌ Some tests failed. Check the logs for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
