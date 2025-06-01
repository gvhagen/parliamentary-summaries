import requests
import json
import os
import locale
import sys

def check_system_encoding():
    """Check system encoding configuration"""
    print("=== System Encoding Diagnostics ===")
    print(f"Python version: {sys.version}")
    print(f"Default encoding: {sys.getdefaultencoding()}")
    print(f"File system encoding: {sys.getfilesystemencoding()}")
    
    try:
        print(f"Locale: {locale.getlocale()}")
        print(f"Preferred encoding: {locale.getpreferredencoding()}")
    except:
        print("Could not get locale info")

def test_deepseek_with_utf8():
    """Test DeepSeek with explicit UTF-8 handling"""
    
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        print("❌ DEEPSEEK_API_KEY not set")
        return False
    
    # Force UTF-8 environment
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    # Test with completely clean ASCII text
    test_message = "Hello DeepSeek! Please respond with JSON containing a summary field."
    
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": test_message}],
        "max_tokens": 200,
        "temperature": 0.1
    }
    
    try:
        print("Testing with explicit UTF-8 encoding...")
        
        # Method 1: Use data parameter with explicit encoding
        payload_json = json.dumps(payload, ensure_ascii=True)
        
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            data=payload_json.encode('utf-8'),
            timeout=30
        )
        
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            print(f"✅ UTF-8 method worked! Response: {content}")
            return True
        else:
            print(f"❌ HTTP Error {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"❌ UTF-8 method failed: {e}")
    
    try:
        print("Testing with session and explicit encoding...")
        
        # Method 2: Use session with custom adapter
        session = requests.Session()
        session.headers.update(headers)
        
        # Ensure clean JSON
        clean_payload = {
            "model": "deepseek-chat", 
            "messages": [{"role": "user", "content": "Test message"}],
            "max_tokens": 100
        }
        
        response = session.post(
            "https://api.deepseek.com/v1/chat/completions",
            json=clean_payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Session method worked!")
            return True
        else:
            print(f"❌ Session method failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Session method failed: {e}")
    
    return False

def test_simple_requests():
    """Test if the issue is with requests library itself"""
    
    try:
        print("Testing basic HTTPS request...")
        response = requests.get("https://httpbin.org/json", timeout=10)
        if response.status_code == 200:
            print("✅ Basic HTTPS works")
        else:
            print(f"❌ Basic HTTPS failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Basic HTTPS error: {e}")
    
    try:
        print("Testing JSON POST...")
        test_data = {"test": "simple ascii only"}
        response = requests.post(
            "https://httpbin.org/post", 
            json=test_data,
            timeout=10
        )
        if response.status_code == 200:
            print("✅ JSON POST works")
        else:
            print(f"❌ JSON POST failed: {response.status_code}")
    except Exception as e:
        print(f"❌ JSON POST error: {e}")

def fix_environment():
    """Try to fix encoding environment"""
    print("Attempting to fix encoding environment...")
    
    # Set environment variables
    os.environ['LC_ALL'] = 'en_US.UTF-8'
    os.environ['LANG'] = 'en_US.UTF-8'
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    
    # Try to set locale
    try:
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
        print("✅ Set locale to en_US.UTF-8")
    except:
        try:
            locale.setlocale(locale.LC_ALL, 'C.UTF-8')
            print("✅ Set locale to C.UTF-8")
        except:
            print("❌ Could not set UTF-8 locale")

if __name__ == "__main__":
    print("=== DeepSeek Encoding Fix Diagnostics ===\n")
    
    # Check system
    check_system_encoding()
    print()
    
    # Test basic requests
    test_simple_requests()
    print()
    
    # Try to fix environment
    fix_environment()
    print()
    
    # Test DeepSeek with fixes
    success = test_deepseek_with_utf8()
    
    if success:
        print("\n🎉 DeepSeek is working with encoding fixes!")
        print("We can now implement the parliamentary summarizer with these fixes.")
    else:
        print("\n🤔 DeepSeek still has issues. Let's try alternative solutions:")
        print("1. Use a different Python environment")
        print("2. Use OpenAI API instead (similar pricing)")
        print("3. Stick with Claude for now")
        print("4. Use a different machine/environment")
