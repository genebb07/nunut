import urllib.request
import sys

def test_url(url):
    print(f"Testing {url}...")
    try:
        response = urllib.request.urlopen(url)
        print(f"SUCCESS: {response.getcode()}")
    except urllib.error.HTTPError as e:
        print(f"HTTP ERROR: {e.code}")
        # Print first 500 chars of body
        print(e.read()[:500].decode('utf-8'))
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_url('http://localhost:8002/dashboard/')
    test_url('http://localhost:8002/planes/')
