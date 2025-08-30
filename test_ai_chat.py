"""
Test script for AI Chat functionality
"""
import requests
import json
import sys

# Configuration
BASE_URL = "http://localhost:5000"  # Adjust port as needed
TEST_USER_ID = "your_test_user_id"  # Replace with actual user ID from MongoDB
JWT_TOKEN = "your_jwt_token"  # Replace with actual JWT token

def test_api_key_update():
    """Test updating API key"""
    headers = {
        "Authorization": f"Bearer {JWT_TOKEN}",
        "Content-Type": "application/json"
    }
    
    data = {
        "api_key": "sk-test-openai-key-here"  # Replace with actual OpenAI API key
    }
    
    response = requests.put(
        f"{BASE_URL}/api/users/{TEST_USER_ID}/api-key",
        headers=headers,
        json=data
    )
    
    print(f"API Key Update Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print("-" * 50)

def test_ai_chat():
    """Test the AI chat endpoint"""
    
    headers = {
        "Authorization": f"Bearer {JWT_TOKEN}",
        "Content-Type": "application/json"
    }
    
    data = {
        "message": "Hello, how are you?",
        "room_id": f"ai_chat_{TEST_USER_ID}",
        "user_id": TEST_USER_ID
    }
    
    response = requests.post(
        f"{BASE_URL}/api/chat/ai/send",
        headers=headers,
        json=data
    )
    
    print(f"AI Chat Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print("-" * 50)

def test_chat_history():
    """Test the chat history endpoint"""
    
    headers = {
        "Authorization": f"Bearer {JWT_TOKEN}",
        "Content-Type": "application/json"
    }
    
    room_id = f"ai_chat_{TEST_USER_ID}"
    response = requests.get(
        f"{BASE_URL}/api/chat/ai/history/{room_id}",
        headers=headers
    )
    
    print(f"Chat History Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print("-" * 50)

def test_get_api_key():
    """Test getting API key"""
    headers = {
        "Authorization": f"Bearer {JWT_TOKEN}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(
        f"{BASE_URL}/api/users/{TEST_USER_ID}/api-key",
        headers=headers
    )
    
    print(f"Get API Key Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print("-" * 50)

def main():
    """Run all tests"""
    print("Starting AI Chat Backend Tests")
    print("=" * 50)
    
    if TEST_USER_ID == "your_test_user_id" or JWT_TOKEN == "your_jwt_token":
        print("ERROR: Please update TEST_USER_ID and JWT_TOKEN in the script")
        sys.exit(1)
    
    print("1. Testing API Key Update...")
    test_api_key_update()
    
    print("2. Testing Get API Key...")
    test_get_api_key()
    
    print("3. Testing AI Chat...")
    test_ai_chat()
    
    print("4. Testing Chat History...")
    test_chat_history()
    
    print("All tests completed!")

if __name__ == "__main__":
    main()
