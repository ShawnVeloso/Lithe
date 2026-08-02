import os
import sys
import traceback
from dotenv import load_dotenv

print("--- Dependency Check ---")
try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
    print("SUCCESS: Imported `google.genai` SDK.")
    has_genai = True
except ImportError as e:
    print(f"ERROR: Could not import `google.genai` ({e}).")
    has_genai = False

def main():
    print("\n--- Environment & Connection Verification ---")
    
    # Load from .env file to ensure the script operates independently
    env_loaded = load_dotenv()
    print(f"Loaded .env file: {env_loaded}")
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY environment variable is missing!")
        return
    else:
        # Masked output to confirm the key is loaded without printing it completely
        print(f"SUCCESS: GEMINI_API_KEY is loaded. (Starts with: {api_key[:4]}..., Length: {len(api_key)})")
    
    model_name = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
    print(f"Using Model Target: {model_name}")

    if not has_genai:
        print("\n[!] FATAL: Cannot proceed with API call without the SDK.")
        return

    print("\n--- Testing API Connection ---")
    try:
        # Client initialization
        print("Initializing genai.Client...")
        client = genai.Client(api_key=api_key)
        
        # Basic configuration
        config = types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=1024,
        )
        
        # Sending a small, minimal prompt
        print(f"Sending request to {model_name}...")
        response = client.models.generate_content(
            model=model_name,
            contents="Say 'Hello, World!' and tell me your model version.",
            config=config,
        )
        
        print("\n--- Response Received ---")
        print(response.text)
        print("--- Connection Successful ---")

    except Exception as e:
        print("\n!!! ERROR CAUGHT !!!")
        print(f"Exception Type: {type(e).__name__}")
        print(f"Exception Message: {str(e)}")
        
        # Try to pull out the HTTP status code if present (google.genai uses httpx underneath)
        if hasattr(e, 'code'):
            print(f"HTTP Status Code: {e.code}")
        elif hasattr(e, 'response') and hasattr(e.response, 'status_code'):
            print(f"HTTP Status Code: {e.response.status_code}")
            
        print("\n--- Full Traceback ---")
        traceback.print_exc(file=sys.stdout)
        
if __name__ == "__main__":
    main()
