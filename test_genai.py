from google import genai
import os
import django
from django.conf import settings

# Setup django environment if needed, but we can just test the import
try:
    print("Testing 'from google import genai'...")
    from google import genai
    print("Success!")
    
    # Check if it has 'configure' (old) or 'Client' (new)
    if hasattr(genai, 'configure'):
        print("This is the OLD SDK (google-generativeai)")
    if hasattr(genai, 'Client'):
        print("This is the NEW SDK (google-genai)")
except ImportError as e:
    print(f"Import failed: {e}")
except Exception as e:
    print(f"Other error: {e}")
