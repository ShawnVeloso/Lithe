"""
Lithe — The Brain (F-01: Core LLM Connection + F-06: Candid Persona)

This module is the primary interface to the Gemini LLM. It:
  1. Creates a Gemini client using the secure API key from config.
  2. Detects the safeword to toggle between candid and compliant personas.
  3. Sends the user's message with the appropriate system prompt.
  4. Returns the model's text response.

Architecture note (from ARCHITECTURE.md):
  The chat() function abstracts the LLM provider. Swapping to Ollama
  in a future milestone means replacing only the client initialization
  and the API call within this module.
"""

from google import genai
from google.genai import types

from src.backend.config import GEMINI_API_KEY, GEMINI_MODEL
from src.backend.prompts.system_prompt import (
    CANDID_SYSTEM_PROMPT,
    COMPLIANT_SYSTEM_PROMPT,
    detect_safeword,
)

# ---------------------------------------------------------------------------
# Gemini client (initialized once at module load)
# ---------------------------------------------------------------------------
_client = genai.Client(api_key=GEMINI_API_KEY)


def chat(user_message: str) -> str:
    """Send a message to the Gemini LLM and return its response.

    Automatically detects the safeword in the user's input to select
    the appropriate system prompt (candid vs. compliant).

    Args:
        user_message: The raw text from the user.

    Returns:
        The model's text response.

    Raises:
        google.genai.errors.APIError: If the Gemini API call fails.
    """
    # --- F-06: Safeword detection ---
    safeword_active, cleaned_message = detect_safeword(user_message)

    system_prompt = (
        COMPLIANT_SYSTEM_PROMPT if safeword_active else CANDID_SYSTEM_PROMPT
    )

    # --- F-01: Gemini API call ---
    response = _client.models.generate_content(
        model=GEMINI_MODEL,
        contents=cleaned_message,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.7,
            max_output_tokens=2048,
        ),
    )

    return response.text


# ---------------------------------------------------------------------------
# Standalone smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("Lithe — Brain Smoke Test")
    print("=" * 60)

    # Test 1: Candid mode
    test_prompt = "What is Lithe?"
    print(f"\n[CANDID MODE] Prompt: {test_prompt!r}")
    print("-" * 40)
    result = chat(test_prompt)
    print(result)

    # Test 2: Safeword mode
    test_prompt_override = "Override Lithe — Just say hello."
    print(f"\n[COMPLIANT MODE] Prompt: {test_prompt_override!r}")
    print("-" * 40)
    result_override = chat(test_prompt_override)
    print(result_override)

    print("\n" + "=" * 60)
    print("Smoke test complete.")
    print("=" * 60)
