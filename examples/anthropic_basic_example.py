"""
Basic example demonstrating Olakai SDK auto-instrumentation with Anthropic.

This script shows:
1. How to configure the SDK
2. How to instrument Anthropic
3. Basic usage with context
4. Streaming support

Usage:
    export OLAKAI_API_KEY=your-olakai-key
    export ANTHROPIC_API_KEY=your-anthropic-key
    python examples/anthropic_basic_example.py
"""

import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from olakaisdk import (
    olakai_config,
    instrument_anthropic,
    olakai_context,
    is_anthropic_instrumented,
)


async def main():
    """Run basic Anthropic examples."""

    print("=" * 60)
    print("Olakai SDK - Anthropic Basic Example")
    print("=" * 60)
    print()

    # Get API keys from environment
    olakai_api_key = os.getenv("OLAKAI_API_KEY")
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

    if not olakai_api_key:
        print("Error: OLAKAI_API_KEY environment variable not set")
        print("   Set it with: export OLAKAI_API_KEY=your-key")
        return

    if not anthropic_api_key:
        print(
            "Error: ANTHROPIC_API_KEY environment variable not set"
        )
        print(
            "   Set it with: export ANTHROPIC_API_KEY=your-key"
        )
        return

    # Step 1: Configure Olakai
    print("Step 1: Configuring Olakai SDK...")
    olakai_config(olakai_api_key, debug=True)
    print("SDK configured")
    print()

    # Step 2: Instrument Anthropic
    print("Step 2: Instrumenting Anthropic...")
    instrument_anthropic()

    if is_anthropic_instrumented():
        print("Anthropic instrumented successfully")
    else:
        print("Failed to instrument Anthropic")
        return
    print()

    # Create Anthropic client
    try:
        import anthropic
    except ImportError:
        print("Error: Anthropic SDK not installed")
        print("   Install it with: pip install anthropic")
        return

    client = anthropic.Anthropic(api_key=anthropic_api_key)

    # Example 1: Basic call without context
    print("-" * 60)
    print("Example 1: Basic call (automatic tracking)")
    print("-" * 60)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Say hello!"}],
    )

    print(f"Response: {response.content[0].text}")
    if response.usage:
        total = (
            response.usage.input_tokens
            + response.usage.output_tokens
        )
        print(f"Tokens used: {total}")
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
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": "What is Python?"}
            ],
        )

    print(f"Response: {response.content[0].text[:200]}...")
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
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": "Explain what AI is in one sentence.",
                }
            ],
        )

    print(f"Response: {response.content[0].text}")
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
        stream = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": "Count from 1 to 5",
                }
            ],
            stream=True,
        )

        print("Streaming response: ", end="", flush=True)
        for event in stream:
            if (
                hasattr(event, "type")
                and event.type == "content_block_delta"
            ):
                if hasattr(event.delta, "text"):
                    print(event.delta.text, end="", flush=True)

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
