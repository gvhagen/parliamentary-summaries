import socket
import requests
import time
import os

def lookup_deepseek_ip():
    """Find DeepSeek's IP address"""
    try:
        # DNS lookup for api.deepseek.com
        ip_address = socket.gethostbyname('api.deepseek.com')
        print(f"✅ DeepSeek IP address: {ip_address}")
        return ip_address
    except Exception as e:
        print(f"❌ DNS lookup failed: {e}")
        return None

def test_dns_vs_ip():
    """Test response times for DNS vs IP"""
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        print("❌ DEEPSEEK_API_KEY not set")
        return
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Host": "api.deepseek.com"  # Important: preserve the Host header for IP requests
    }
    
    simple_payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 10
    }
    
    # Test with DNS
    print("Testing with DNS (api.deepseek.com)...")
    dns_times = []
    for i in range(3):
        try:
            start = time.time()
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=headers,
                json=simple_payload,
                timeout=30
            )
            end = time.time()
            
            if response.status_code == 200:
                dns_times.append(end - start)
                print(f"  Test {i+1}: {end - start:.2f}s ✅")
            else:
                print(f"  Test {i+1}: Failed with status {response.status_code}")
        except Exception as e:
            print(f"  Test {i+1}: Failed - {e}")
        
        time.sleep(1)
    
    # Get IP and test with IP
    ip = lookup_deepseek_ip()
    if ip:
        print(f"\nTesting with IP ({ip})...")
        ip_times = []
        for i in range(3):
            try:
                start = time.time()
                response = requests.post(
                    f"https://{ip}/v1/chat/completions",
                    headers=headers,
                    json=simple_payload,
                    timeout=30,
                    verify=False  # Skip SSL verification for IP requests
                )
                end = time.time()
                
                if response.status_code == 200:
                    ip_times.append(end - start)
                    print(f"  Test {i+1}: {end - start:.2f}s ✅")
                else:
                    print(f"  Test {i+1}: Failed with status {response.status_code}")
            except Exception as e:
                print(f"  Test {i+1}: Failed - {e}")
            
            time.sleep(1)
        
        # Compare results
        if dns_times and ip_times:
            avg_dns = sum(dns_times) / len(dns_times)
            avg_ip = sum(ip_times) / len(ip_times)
            
            print(f"\n📊 Results:")
            print(f"DNS average: {avg_dns:.2f}s")
            print(f"IP average: {avg_ip:.2f}s")
            
            if avg_ip < avg_dns:
                print(f"🚀 IP is {avg_dns/avg_ip:.1f}x faster!")
                print(f"Recommendation: Use IP {ip}")
                return ip
            else:
                print(f"📡 DNS is {avg_ip/avg_dns:.1f}x faster!")
                print(f"Recommendation: Stick with DNS")
                return None
    
    return None

def test_multiple_ips():
    """Sometimes there are multiple IPs, test them all"""
    try:
        import subprocess
        
        # Use nslookup to get all IPs
        result = subprocess.run(['nslookup', 'api.deepseek.com'], 
                              capture_output=True, text=True)
        
        print("Full DNS lookup result:")
        print(result.stdout)
        
        # Extract IPs from nslookup output
        lines = result.stdout.split('\n')
        ips = []
        for line in lines:
            if 'Address:' in line and '::' not in line:  # IPv4 only
                ip = line.split('Address:')[-1].strip()
                if ip and ip != '127.0.0.53':  # Skip localhost
                    ips.append(ip)
        
        print(f"\nFound IPs: {ips}")
        return ips
        
    except Exception as e:
        print(f"nslookup failed: {e}")
        return []

if __name__ == "__main__":
    print("=== DeepSeek DNS vs IP Test ===\n")
    
    # Get all possible IPs
    all_ips = test_multiple_ips()
    
    # Test DNS vs IP performance
    best_ip = test_dns_vs_ip()
    
    if best_ip:
        print(f"\n🎯 Best option: Use IP {best_ip}")
        print(f"Update your code to use: https://{best_ip}/v1/chat/completions")
        print(f"Don't forget to add Host header: 'Host': 'api.deepseek.com'")
    else:
        print(f"\n💭 Recommendation: Stick with DNS for now")
    
    print(f"\nAlternative solutions:")
    print(f"1. Use the fastest IP found above")
    print(f"2. Add connection pooling/keep-alive")
    print(f"3. Reduce chunk size even more (15k characters)")
    print(f"4. Add delay between requests")
