# Olakai SDK Examples

This directory contains example scripts demonstrating how to use the Olakai SDK v0.5.0.

## Prerequisites

1. Install the SDK:
```bash
pip install olakai-sdk openai
```

2. Set environment variables:
```bash
export OLAKAI_API_KEY=your-olakai-api-key
export OPENAI_API_KEY=your-openai-api-key
```

## Examples

### openai_basic_example.py

Demonstrates core SDK functionality:
- SDK configuration
- OpenAI instrumentation
- Basic tracking
- Context usage
- Streaming support

**Run it:**
```bash
python examples/openai_basic_example.py
```

### openai_advanced_example.py

Shows real-world use cases:
- Customer support chatbot
- Content generation with metadata
- Error handling and retries
- Nested contexts for multi-step workflows

**Run it:**
```bash
python examples/openai_advanced_example.py
```

## What Gets Tracked

All examples automatically track:
- ✅ Token usage (input/output)
- ✅ Model names
- ✅ Request latency
- ✅ Prompts and responses
- ✅ User context and metadata
- ✅ Custom dimensions and metrics

## View Your Data

After running the examples, visit your [Olakai Dashboard](https://app.olakai.ai) to see the tracked data!

## Need Help?

- Read [USAGE.md](../USAGE.md) for detailed documentation
- Check [README.md](../README.md) for API reference
- Contact [support@olakai.ai](mailto:support@olakai.ai)
