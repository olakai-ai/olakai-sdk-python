"""
Basic example demonstrating Olakai SDK auto-instrumentation with Google GenAI.

This script shows:
1. How to configure the SDK
2. How to instrument Google Generative AI
3. Basic usage with context
4. Streaming support

Usage:
    export OLAKAI_API_KEY=your-olakai-key
    export GOOGLE_API_KEY=your-google-key
    python examples/google_basic_example.py
"""

import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from olakaisdk import (
    olakai_config,
    instrument_google,
    olakai_context,
    is_google_instrumented,
)


async def main():
    """Run basic Google GenAI examples."""

    print("=" * 60)
    print("Olakai SDK - Google Generative AI Basic Example")
    print("=" * 60)
    print()

    # Get API keys from environment
    olakai_api_key = os.getenv("OLAKAI_API_KEY")
    google_api_key = os.getenv("GOOGLE_API_KEY")

    if not olakai_api_key:
        print("Error: OLAKAI_API_KEY environment variable not set")
        print("   Set it with: export OLAKAI_API_KEY=your-key")
        return

    if not google_api_key:
        print("Error: GOOGLE_API_KEY environment variable not set")
        print("   Set it with: export GOOGLE_API_KEY=your-key")
        return

    # Step 1: Configure Olakai
    print("Step 1: Configuring Olakai SDK...")
    olakai_config(olakai_api_key, debug=True)
    print("SDK configured")
    print()

    # Step 2: Instrument Google GenAI
    print("Step 2: Instrumenting Google Generative AI...")
    instrument_google()

    if is_google_instrumented():
        print("Google GenAI instrumented successfully")
    else:
        print("Failed to instrument Google GenAI")
        return
    print()

    # Configure Google GenAI
    try:
        import google.generativeai as genai
    except ImportError:
        print("Error: Google Generative AI SDK not installed")
        print(
            "   Install it with: pip install google-generativeai"
        )
        return

    genai.configure(api_key=google_api_key)

    # Create a model
    model = genai.GenerativeModel("gemini-2.5-flash")

    # Example 1: Basic call without context
    print("-" * 60)
    print("Example 1: Basic call (automatic tracking)")
    print("-" * 60)

    response = model.generate_content("Say hello!")

    print(f"Response: {response.text}")
    if response.usage_metadata:
        print(
            f"Tokens used: {response.usage_metadata.total_token_count}"
        )
    print()

    # Example 2: Call with user context
    print("-" * 60)
    print("Example 2: Call with user context")
    print("-" * 60)

    with olakai_context(
        userEmail="demo@example.com",
        task="Demo",
        subTask="basic-chat",
    ):
        response = model.generate_content("What is Python?")

    print(f"Response: {response.text[:200]}...")
    print()

    # Example 3: Call with custom data
    print("-" * 60)
    print("Example 3: Call with custom data")
    print("-" * 60)

    with olakai_context(
        userEmail="demo@example.com",
        task="Demo",
        subTask="metadata-example",
        customData={
            "environment": "demo",
            "example_type": "documentation",
            "language": "en",
            "user_id": 12345,
            "session_number": 1,
        },
    ):
        response = model.generate_content(
            "Explain what AI is in one sentence."
        )

    print(f"Response: {response.text}")
    print()

    # Example 4: Streaming
    print("-" * 60)
    print(
        "Example 4: Streaming (telemetry sent after stream completes)"
    )
    print("-" * 60)

    with olakai_context(
        userEmail="demo@example.com",
        task="Demo",
        subTask="streaming-example",
    ):
        response = model.generate_content(
            "Count from 1 to 5", stream=True
        )

        print("Streaming response: ", end="", flush=True)
        for chunk in response:
            if chunk.text:
                print(chunk.text, end="", flush=True)

        print()
        print("Stream complete - telemetry sent!")
    print()

    # Summary
    print("=" * 60)
    print("All examples completed successfully!")
    print("=" * 60)
    print()
    print("Check your Olakai dashboard at https://app.olakai.ai")
    print("   to see the tracked data!")
    print()
    print("What was tracked:")
    print("  - Token usage (input/output)")
    print("  - Model names")
    print("  - Latency")
    print("  - User context and metadata")
    print("  - Custom data")
    print()


if __name__ == "__main__":
    asyncio.run(main())
