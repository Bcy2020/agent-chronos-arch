"""
Test script for Phase 1: Basic infrastructure.
Tests config, models, and API client.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from api_client import APIClient
from models import Node, InputParam, OutputParam, Boundary, ChildContract


def test_config():
    print("Testing Config...")
    config = Config.from_env()
    print(f"  base_url: {config.base_url}")
    print(f"  model: {config.model}")
    print(f"  max_depth: {config.max_depth}")
    print(f"  temperature: {config.temperature}")
    print(f"  api_key set: {config.api_key is not None}")
    assert config.base_url == "https://api.deepseek.com"
    print("  Config test passed!\n")


def test_models():
    print("Testing Models...")
    
    node = Node(
        node_id="test_node",
        name="TestFunction",
        depth=0,
        purpose="A test function for validation",
        inputs=[InputParam(name="x", type="int", description="Input value")],
        outputs=[OutputParam(name="result", type="int", description="Output value")],
        boundary=Boundary(in_scope=["calculate"], out_of_scope=["IO operations"])
    )
    
    print(f"  Node name: {node.name}")
    print(f"  Node purpose: {node.purpose}")
    print(f"  Interface signature: {node.get_interface_signature()}")
    
    json_str = node.to_json()
    print(f"  JSON serialization works: {len(json_str) > 0}")
    
    restored = Node.from_json(json_str)
    assert restored.name == node.name
    assert restored.purpose == node.purpose
    print("  Models test passed!\n")


def test_api_client():
    print("Testing API Client...")
    
    config = Config.from_env()
    
    if not config.api_key:
        print("  WARNING: DEEPSEEK_API_KEY not set, skipping API test")
        return
    
    client = APIClient(config)
    
    print("  Testing connection...")
    if client.test_connection():
        print("  API connection successful!")
        
        print("  Testing simple chat...")
        response = client.chat([
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'hello world' in exactly those words."}
        ], max_tokens=20)
        print(f"  Response: {response}")
        print("  API Client test passed!\n")
    else:
        print("  API connection failed. Check your API key.")


def main():
    print("=" * 50)
    print("Phase 1 Tests: Basic Infrastructure")
    print("=" * 50 + "\n")
    
    test_config()
    test_models()
    test_api_client()
    
    print("=" * 50)
    print("All Phase 1 tests completed!")
    print("=" * 50)


if __name__ == "__main__":
    main()
