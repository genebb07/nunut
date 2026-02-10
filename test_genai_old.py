try:
    print("Testing 'import google.generativeai as genai'...")
    import google.generativeai as genai
    print("Success!")
    if hasattr(genai, 'configure'):
        print("This is the OLD SDK (google-generativeai)")
    if hasattr(genai, 'Client'):
        print("This is the NEW SDK (google-genai)")
except ImportError as e:
    print(f"Import failed: {e}")
except Exception as e:
    print(f"Other error: {e}")
