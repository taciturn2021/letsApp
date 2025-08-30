#!/usr/bin/env python3
"""
Enhanced Test script for AI Chat History functionality
"""
import requests
import json
import time
import sys

# Configuration
BASE_URL = "http://localhost:5001"
TEST_EMAIL = "barood@gmail.com"  # Update with actual test user email
TEST_PASSWORD = "your_password"  # Update with actual password

def login_user():
    """Login and get JWT token"""
    login_data = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    
    try:
        response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token"), data.get("user", {}).get("_id")
        else:
            print(f"Login failed: {response.status_code} - {response.text}")
            return None, None
    except Exception as e:
        print(f"Login error: {str(e)}")
        return None, None

def send_ai_message(token, user_id, message):
    """Send a message to AI chat"""
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "message": message,
        "room_id": f"ai_chat_{user_id}",
        "user_id": user_id
    }
    
    response = requests.post(f"{BASE_URL}/api/chat/ai/send", json=data, headers=headers)
    return response

def get_ai_chat_history(token, user_id, page=1, limit=50):
    """Get AI chat history"""
    headers = {"Authorization": f"Bearer {token}"}
    params = {"page": page, "limit": limit}
    
    response = requests.get(f"{BASE_URL}/api/chat/ai/history/{user_id}", 
                          headers=headers, params=params)
    return response

def clear_ai_chat_history(token, user_id):
    """Clear AI chat history"""
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.delete(f"{BASE_URL}/api/chat/ai/history/{user_id}", headers=headers)
    return response

def update_api_key(token, user_id, api_key):
    """Update user's API key"""
    headers = {"Authorization": f"Bearer {token}"}
    data = {"api_key": api_key}
    
    response = requests.put(f"{BASE_URL}/api/users/{user_id}/api-key", json=data, headers=headers)
    return response

def test_ai_chat_history():
    """Test the AI chat history functionality"""
    print("🤖 Testing AI Chat History Backend...")
    print("=" * 60)
    
    # Login
    print("1. 🔐 Logging in...")
    token, user_id = login_user()
    if not token or not user_id:
        print("❌ Failed to login")
        return
    print(f"✅ Login successful - User ID: {user_id}")
    
    # Update API key if needed (replace with your actual Gemini API key)
    print("\n2. 🔑 Checking API key...")
    api_key = "YOUR_GEMINI_API_KEY_HERE"  # Replace with actual key
    if api_key != "YOUR_GEMINI_API_KEY_HERE":
        update_response = update_api_key(token, user_id, api_key)
        if update_response.status_code == 200:
            print("✅ API key updated successfully")
        else:
            print(f"⚠️ API key update: {update_response.status_code} - {update_response.text}")
    else:
        print("⚠️ Please update the API key in the script")
    
    # Clear existing history
    print("\n3. 🧹 Clearing existing chat history...")
    clear_response = clear_ai_chat_history(token, user_id)
    if clear_response.status_code == 200:
        data = clear_response.json()
        print(f"✅ Chat history cleared ({data.get('deleted_count', 0)} messages)")
    else:
        print(f"⚠️ Clear history: {clear_response.status_code} - {clear_response.text}")
    
    # Send test messages
    test_messages = [
        "Hello! What's your name?",
        "Can you help me with Python programming?",
        "What are some good books to read about AI?",
        "Tell me a short joke!"
    ]
    
    print(f"\n4. 💬 Sending {len(test_messages)} test messages...")
    successful_messages = 0
    for i, message in enumerate(test_messages, 1):
        print(f"   📤 Sending message {i}: {message}")
        response = send_ai_message(token, user_id, message)
        
        if response.status_code == 200:
            print(f"   ✅ Message {i} sent successfully")
            successful_messages += 1
            time.sleep(2)  # Delay between messages to avoid rate limits
        else:
            print(f"   ❌ Message {i} failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"      Error: {error_data.get('error', 'Unknown error')}")
            except:
                print(f"      Raw error: {response.text}")
    
    print(f"   📊 Sent {successful_messages}/{len(test_messages)} messages successfully")
    
    # Test getting chat history
    print("\n5. 📜 Testing chat history retrieval...")
    history_response = get_ai_chat_history(token, user_id)
    
    if history_response.status_code == 200:
        history_data = history_response.json()
        if history_data.get("success"):
            messages = history_data.get("messages", [])
            pagination = history_data.get("pagination", {})
            
            print(f"✅ Retrieved {len(messages)} messages")
            print(f"   📊 Total messages: {pagination.get('total', 0)}")
            print(f"   📄 Page: {pagination.get('page', 1)}")
            print(f"   ➡️  Has more: {pagination.get('has_more', False)}")
            
            # Display messages
            print("\n   💬 Recent messages:")
            for i, msg in enumerate(messages[-6:], 1):  # Show last 6 messages
                sender = "👤 User" if msg["message_type"] == "user" else "🤖 AI"
                content = msg['content'][:60] + "..." if len(msg['content']) > 60 else msg['content']
                print(f"     {i}. {sender}: {content}")
        else:
            print(f"❌ History retrieval failed: {history_data.get('error')}")
    else:
        print(f"❌ History request failed: {history_response.status_code} - {history_response.text}")
    
    # Test pagination
    print("\n6. 📄 Testing pagination...")
    paginated_response = get_ai_chat_history(token, user_id, page=1, limit=3)
    
    if paginated_response.status_code == 200:
        paginated_data = paginated_response.json()
        if paginated_data.get("success"):
            messages = paginated_data.get("messages", [])
            pagination = paginated_data.get("pagination", {})
            print(f"✅ Pagination test: Retrieved {len(messages)} messages (limit=3)")
            print(f"   Total: {pagination.get('total')}, Has more: {pagination.get('has_more')}")
        else:
            print(f"❌ Pagination test failed: {paginated_data.get('error')}")
    else:
        print(f"❌ Pagination request failed: {paginated_response.status_code}")
    
    print("\n" + "=" * 60)
    print("🎉 AI Chat History test completed!")

def quick_test():
    """Quick test for basic functionality"""
    print("⚡ Quick AI Chat Test...")
    
    token, user_id = login_user()
    if not token:
        print("❌ Login failed")
        return
    
    # Send one message
    response = send_ai_message(token, user_id, "Hello, this is a test message!")
    if response.status_code == 200:
        print("✅ Message sent successfully")
    else:
        print(f"❌ Message failed: {response.status_code}")
    
    # Get history
    history = get_ai_chat_history(token, user_id)
    if history.status_code == 200:
        data = history.json()
        count = len(data.get("messages", []))
        print(f"✅ History retrieved: {count} messages")
    else:
        print(f"❌ History failed: {history.status_code}")

def main():
    """Main function"""
    if len(sys.argv) > 1:
        if sys.argv[1] == "quick":
            quick_test()
        elif sys.argv[1] == "full":
            test_ai_chat_history()
        else:
            print("Usage: python test_ai_chat.py [quick|full]")
    else:
        test_ai_chat_history()

if __name__ == "__main__":
    main()
