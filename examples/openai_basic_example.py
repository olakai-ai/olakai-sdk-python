"""
Basic example demonstrating Olakai SDK v0.5.0 auto-instrumentation.

This script shows:
1. How to configure the SDK
2. How to instrument OpenAI
3. Basic usage with context
4. Streaming support

Usage:
    export OLAKAI_API_KEY=your-olakai-key
    export OPENAI_API_KEY=your-openai-key
    python examples/basic_example.py
"""

import os
import sys
import asyncio

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from olakaisdk import olakai_config, instrument_openai, olakai_context, is_openai_instrumented

async def main():
    """Run basic examples."""

    print("=" * 60)
    print("Olakai SDK v0.5.0 - Basic Example")
    print("=" * 60)
    print()

    # Get API keys from environment
    olakai_api_key = os.getenv("OLAKAI_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not olakai_api_key:
        print("❌ Error: OLAKAI_API_KEY environment variable not set")
        print("   Set it with: export OLAKAI_API_KEY=your-key")
        return

    if not openai_api_key:
        print("❌ Error: OPENAI_API_KEY environment variable not set")
        print("   Set it with: export OPENAI_API_KEY=your-key")
        return

    # Step 1: Configure Olakai
    print("Step 1: Configuring Olakai SDK...")
    olakai_config(olakai_api_key, debug=True)
    print("✅ SDK configured")
    print()

    # Step 2: Instrument OpenAI
    print("Step 2: Instrumenting OpenAI...")
    instrument_openai()

    if is_openai_instrumented():
        print("✅ OpenAI instrumented successfully")
    else:
        print("❌ Failed to instrument OpenAI")
        return
    print()

    # Import OpenAI after instrumentation
    try:
        from openai import OpenAI
    except ImportError:
        print("❌ Error: OpenAI SDK not installed")
        print("   Install it with: pip install openai")
        return

    # Create OpenAI client
    client = OpenAI(api_key=openai_api_key)

    # Example 1: Basic call without context
    print("-" * 60)
    print("Example 1: Basic call (automatic tracking)")
    print("-" * 60)

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Say hello!"}],
        max_tokens=50
    )

    print(f"Response: {response.choices[0].message.content}")
    print(f"Tokens used: {response.usage.total_tokens if response.usage != None else None}")
    print()

    # Example 2: Call with user context
    print("-" * 60)
    print("Example 2: Call with user context")
    print("-" * 60)

    with olakai_context(
        userEmail="demo@example.com",
        task="Demo",
        subTask="basic-chat"
    ):
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "What is Python?"}],
            max_tokens=100
        )

    print(f"Response: {response.choices[0].message.content[:200]}..." if response.choices[0].message.content != None else None)
    print(f"Tokens used: {response.usage.total_tokens if response.usage != None else None}")
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
            "session_number": 1
        }
    ):
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Explain what AI is in one sentence."}
            ],
            max_tokens=100
        )

    print(f"Response: {response.choices[0].message.content}")
    print(f"Tokens used: {response.usage.total_tokens if response.usage != None else None}")
    print()

    # Example 4: Streaming
    print("-" * 60)
    print("Example 4: Streaming (telemetry sent after stream completes)")
    print("-" * 60)

    with olakai_context(
        userEmail="demo@example.com",
        task="Demo",
        subTask="streaming-example"
    ):
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Count from 1 to 5"}],
            max_tokens=50,
            stream=True
        )

        print("Streaming response: ", end="", flush=True)
        for chunk in response:
            if chunk.choices[0].delta.content:
                print(chunk.choices[0].delta.content, end="", flush=True)

        print()  # New line after streaming
        print("Stream complete - telemetry sent!")
    print()

    # Summary
    print("=" * 60)
    print("✅ All examples completed successfully!")
    print("=" * 60)
    print()
    print("📊 Check your Olakai dashboard at https://app.olakai.ai")
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
