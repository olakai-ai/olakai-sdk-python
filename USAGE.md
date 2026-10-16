# Olakai SDK - Usage Guide

Comprehensive guide with real-world examples for the Olakai Python SDK v1.0.0.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Basic Usage](#basic-usage)
- [Manual Event Reporting](#manual-event-reporting)
- [Real-World Examples](#real-world-examples)
  - [Customer Support Chatbot](#customer-support-chatbot)
  - [Content Generation Service](#content-generation-service)
  - [RAG (Retrieval-Augmented Generation)](#rag-retrieval-augmented-generation)
  - [Multi-User Applications](#multi-user-applications)
  - [Streaming Responses](#streaming-responses)
  - [Async Applications](#async-applications)
- [Advanced Patterns](#advanced-patterns)
- [Flask/FastAPI Integration](#flaskfastapi-integration)
- [Production Best Practices](#production-best-practices)
- [Troubleshooting](#troubleshooting)

---

## Getting Started

### Installation

```bash
pip install olakai-sdk openai
```

### Environment Setup

Store your API keys securely:

```bash
# .env file
OLAKAI_API_KEY=your-olakai-key-here
OPENAI_API_KEY=your-openai-key-here
```

Load them in your code:

```python
import os
from dotenv import load_dotenv

load_dotenv()

olakai_api_key = os.getenv("OLAKAI_API_KEY")
openai_api_key = os.getenv("OPENAI_API_KEY")
```

---

## Basic Usage

### Minimal Setup

```python
import os
from olakaisdk import olakai_config, instrument_openai
from openai import OpenAI

# 1. Configure Olakai
olakai_config(os.getenv("OLAKAI_API_KEY"))

# 2. Instrument OpenAI
instrument_openai()

# 3. Use OpenAI as usual
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)

print(response.choices[0].message.content)
```

That's it! All metrics are automatically tracked.

---

## Manual Event Reporting

While auto-instrumentation handles most use cases, you can use `olakai_event()` to manually report events when you need more control or when working with non-instrumented LLM providers.

### Basic Manual Reporting

```python
import os
from olakaisdk import olakai_config, olakai_event, OlakaiEventParams

# Configure Olakai
olakai_config(os.getenv("OLAKAI_API_KEY"))

# Send a manual event report
olakai_event(OlakaiEventParams(
    prompt="What is the capital of France?",
    response="The capital of France is Paris.",
    userEmail="user@example.com",
    task="Geography Q&A"
))
```

### With Custom Metadata

```python
from olakaisdk import olakai_event, OlakaiEventParams

# Report with full metadata
olakai_event(OlakaiEventParams(
    prompt="Generate a product description for wireless headphones",
    response="Experience crystal-clear sound with our premium wireless headphones...",
    userEmail="marketing@company.com",
    task="Content Generation",
    subTask="product-description",
    customData={
        "product_category": "electronics",
        "target_audience": "consumers",
        "word_count": 150,
        "model": "gpt-4",
        "temperature": 0.7
    },
    tokens=200,
    requestTime=1500  # milliseconds
))
```

### Tracking Non-OpenAI Providers

Use `olakai_event()` to track LLM calls from providers that aren't auto-instrumented:

```python
import anthropic
import time
from olakaisdk import olakai_config, olakai_event, OlakaiEventParams

olakai_config(os.getenv("OLAKAI_API_KEY"))

def call_claude_with_tracking(prompt: str, user_email: str):
    """Call Claude API with manual tracking."""

    client = anthropic.Anthropic()

    start_time = time.time()

    # Make the API call
    response = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    duration_ms = int((time.time() - start_time) * 1000)
    response_text = response.content[0].text

    # Report the event manually
    olakai_event(OlakaiEventParams(
        prompt=prompt,
        response=response_text,
        userEmail=user_email,
        task="Claude Chat",
        customData={
            "provider": "anthropic",
            "model": "claude-3-opus-20240229",
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens
        },
        tokens=response.usage.input_tokens + response.usage.output_tokens,
        requestTime=duration_ms
    ))

    return response_text

# Example usage
result = call_claude_with_tracking(
    prompt="Explain quantum computing in simple terms",
    user_email="researcher@university.edu"
)
print(result)
```

### Batch Processing with Manual Events

```python
from olakaisdk import olakai_event, OlakaiEventParams
import asyncio

async def process_batch_with_tracking(items: list, user_email: str):
    """Process a batch of items and report each as an event."""

    results = []

    for i, item in enumerate(items):
        # Your processing logic here
        prompt = item["prompt"]
        response = await your_llm_call(prompt)

        # Report each item
        olakai_event(OlakaiEventParams(
            prompt=prompt,
            response=response,
            userEmail=user_email,
            task="Batch Processing",
            customData={
                "batch_index": i,
                "batch_size": len(items),
                "item_id": item.get("id")
            }
        ))

        results.append(response)

    return results
```

### Combining Auto-Instrumentation and Manual Events

You can use both approaches in the same application:

```python
from olakaisdk import (
    olakai_config,
    instrument_openai,
    olakai_context,
    olakai_event,
    OlakaiEventParams
)
from openai import OpenAI

olakai_config(os.getenv("OLAKAI_API_KEY"))
instrument_openai()  # Auto-track OpenAI calls

client = OpenAI()

# Auto-instrumented OpenAI call
with olakai_context(userEmail="user@example.com", task="Chat"):
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello!"}]
    )
    # ^ This is automatically tracked

# Manual event for custom processing
olakai_event(OlakaiEventParams(
    prompt="Custom pipeline input",
    response="Custom pipeline output",
    userEmail="user@example.com",
    task="Custom Processing",
    customData={"pipeline": "custom-v2"}
))
```

---

## Real-World Examples

### Customer Support Chatbot

Track support interactions with user metadata:

```python
import os
from olakaisdk import olakai_config, instrument_openai, olakai_context
from openai import OpenAI

# Setup
olakai_config(os.getenv("OLAKAI_API_KEY"))
instrument_openai()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def handle_support_request(user_email, user_question, conversation_history):
    """
    Handle a customer support request.

    Tracks:
    - User email
    - Task category (Customer Support)
    - Subtask (based on question type)
    - Custom data (user tier, language, conversation length)
    """

    # Detect question type
    question_type = classify_question(user_question)

    # Build conversation
    messages = conversation_history + [
        {"role": "user", "content": user_question}
    ]

    # Add metadata context
    with olakai_context(
        userEmail=user_email,
        task="Customer Support",
        subTask=question_type,
        customData={
            "user_tier": get_user_tier(user_email),
            "language": "en",
            "channel": "web-chat",
            "conversation_length": len(conversation_history) / 2  # num exchanges
        }
    ):
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7
        )

    return response.choices[0].message.content

def classify_question(question):
    """Simple question classifier."""
    question_lower = question.lower()
    if any(word in question_lower for word in ["password", "login", "reset"]):
        return "authentication"
    elif any(word in question_lower for word in ["billing", "payment", "charge"]):
        return "billing"
    elif any(word in question_lower for word in ["bug", "error", "not working"]):
        return "technical-issue"
    else:
        return "general-inquiry"

def get_user_tier(email):
    """Get user subscription tier."""
    # Your logic here
    return "premium"  # or "basic", "enterprise"

# Example usage
conversation = [
    {"role": "system", "content": "You are a helpful customer support agent."}
]

answer = handle_support_request(
    user_email="customer@example.com",
    session_id="support-123",
    user_question="How do I reset my password?",
    conversation_history=conversation
)

print(answer)
```

### Content Generation Service

Track content generation with metadata about the content type:

```python
from olakaisdk import olakai_config, instrument_openai, olakai_context
from openai import OpenAI
import os

olakai_config(os.getenv("OLAKAI_API_KEY"))
instrument_openai()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_blog_post(topic, target_audience, word_count, user_id):
    """
    Generate a blog post.

    Tracks:
    - Content type and length
    - Target audience
    - User ID
    - Generation parameters
    """

    prompt = f"""Write a {word_count}-word blog post about {topic}
    for {target_audience} audience. Make it engaging and informative."""

    with olakai_context(
        userEmail=f"user-{user_id}@example.com",
        task="Content Generation",
        subTask="blog-post",
        customData={
            "content_type": "blog",
            "topic_category": categorize_topic(topic),
            "target_audience": target_audience,
            "environment": os.getenv("ENV", "production"),
            "target_word_count": word_count,
            "user_id": user_id
        }
    ):
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a professional content writer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8
        )

    return response.choices[0].message.content

def generate_social_media_post(platform, topic, tone, user_id):
    """Generate social media content."""

    char_limits = {
        "twitter": 280,
        "linkedin": 3000,
        "instagram": 2200
    }

    prompt = f"""Create a {platform} post about {topic}.
    Tone: {tone}. Max {char_limits.get(platform, 500)} characters."""

    with olakai_context(
        userEmail=f"user-{user_id}@example.com",
        task="Content Generation",
        subTask=f"social-{platform}",
        customData={
            "platform": platform,
            "tone": tone,
            "content_type": "social-media"
        }
    ):
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # Faster for short content
            messages=[
                {"role": "system", "content": f"You are a {platform} content expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.9
        )

    return response.choices[0].message.content

def categorize_topic(topic):
    """Categorize topic for tracking."""
    # Your categorization logic
    return "technology"  # or "business", "lifestyle", etc.

# Example usage
blog = generate_blog_post(
    topic="AI in Healthcare",
    target_audience="healthcare professionals",
    word_count=1000,
    user_id=12345
)

tweet = generate_social_media_post(
    platform="twitter",
    topic="New AI features",
    tone="excited",
    user_id=12345
)

print("Blog:", blog[:200] + "...")
print("Tweet:", tweet)
```

### RAG (Retrieval-Augmented Generation)

Track RAG pipeline with context about retrieved documents:

```python
from olakaisdk import olakai_config, instrument_openai, olakai_context
from openai import OpenAI
import os

olakai_config(os.getenv("OLAKAI_API_KEY"))
instrument_openai()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def answer_with_rag(question, user_email, knowledge_base="docs"):
    """
    Answer question using RAG pattern.

    Tracks:
    - Number of documents retrieved
    - Knowledge base used
    - Retrieval quality metrics
    """

    # Step 1: Retrieve relevant documents
    documents = retrieve_documents(question, knowledge_base, top_k=3)

    # Step 2: Build context from documents
    context = "\n\n".join([doc["content"] for doc in documents])

    # Step 3: Generate answer with context
    prompt = f"""Based on the following context, answer the question.

Context:
{context}

Question: {question}

Answer:"""

    with olakai_context(
        userEmail=user_email,
        task="RAG Query",
        subTask=f"kb-{knowledge_base}",
        customData={
            "knowledge_base": knowledge_base,
            "query_type": "rag",
            "docs_retrieved": len(documents),
            "avg_doc_relevance": calculate_avg_relevance(documents),
            "context_length": len(context)
        }
    ):
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that answers based on provided context."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3  # Lower temperature for factual answers
        )

    return {
        "answer": response.choices[0].message.content,
        "sources": [doc["source"] for doc in documents]
    }

def retrieve_documents(query, knowledge_base, top_k=3):
    """
    Retrieve relevant documents (mock implementation).

    In production, this would use a vector database like:
    - Pinecone
    - Weaviate
    - Chroma
    - Qdrant
    """
    # Mock implementation
    return [
        {
            "content": "Document content about AI safety...",
            "source": "ai-safety-guide.pdf",
            "relevance": 0.92
        },
        {
            "content": "Another relevant document...",
            "source": "best-practices.md",
            "relevance": 0.87
        },
        {
            "content": "Third document...",
            "source": "faq.txt",
            "relevance": 0.81
        }
    ][:top_k]

def calculate_avg_relevance(documents):
    """Calculate average relevance score."""
    if not documents:
        return 0.0
    return sum(doc.get("relevance", 0) for doc in documents) / len(documents)

# Example usage
result = answer_with_rag(
    question="What are the best practices for AI safety?",
    user_email="researcher@university.edu",
    knowledge_base="ai-research"
)

print("Answer:", result["answer"])
print("Sources:", result["sources"])
```

### Multi-User Applications

Handle multiple users with different contexts:

```python
from olakaisdk import olakai_config, instrument_openai, olakai_context
from openai import OpenAI
import os
from typing import List, Dict

olakai_config(os.getenv("OLAKAI_API_KEY"))
instrument_openai()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class UserSession:
    """Manage user sessions with automatic tracking."""

    def __init__(self, user_id: str, user_email: str, user_tier: str):
        self.user_id = user_id
        self.user_email = user_email
        self.user_tier = user_tier
        self.conversation_history: List[Dict] = []

    def chat(self, message: str, task: str = "General Chat"):
        """Send a message and get response."""

        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": message
        })

        # Create context for this user
        with olakai_context(
            userEmail=self.user_email,
            task=task,
            customData={
                "user_tier": self.user_tier,
                "user_id": self.user_id,
                "conversation_length": len(self.conversation_history)
            }
        ):
            response = client.chat.completions.create(
                model=self.get_model_for_tier(),
                messages=self.conversation_history,
                temperature=0.7
            )

        # Add assistant response to history
        assistant_message = response.choices[0].message.content
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_message
        })

        return assistant_message

    def get_model_for_tier(self):
        """Select model based on user tier."""
        tier_models = {
            "free": "gpt-3.5-turbo",
            "pro": "gpt-4",
            "enterprise": "gpt-4"
        }
        return tier_models.get(self.user_tier, "gpt-3.5-turbo")

# Example: Handle multiple concurrent users
users = {
    "user_1": UserSession("1", "alice@example.com", "pro"),
    "user_2": UserSession("2", "bob@example.com", "free"),
    "user_3": UserSession("3", "charlie@company.com", "enterprise")
}

# Each user interaction is tracked separately
response_1 = users["user_1"].chat("What's the weather like?", task="Small Talk")
response_2 = users["user_2"].chat("Help me write code", task="Code Assistance")
response_3 = users["user_3"].chat("Analyze this data", task="Data Analysis")

print(f"User 1: {response_1}")
print(f"User 2: {response_2}")
print(f"User 3: {response_3}")
```

### Streaming Responses

Monitor streaming API calls:

```python
from olakaisdk import olakai_config, instrument_openai, olakai_context
from openai import OpenAI
import os

olakai_config(os.getenv("OLAKAI_API_KEY"))
instrument_openai()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def stream_story(topic, user_email):
    """
    Generate and stream a story.

    Streaming is automatically handled - telemetry sent after stream completes.
    """

    with olakai_context(
        userEmail=user_email,
        task="Content Generation",
        subTask="story-streaming"
    ):
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "user", "content": f"Tell me a short story about {topic}"}
            ],
            stream=True  # Enable streaming
        )

        # Iterate through stream
        full_story = ""
        for chunk in response:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                print(content, end="", flush=True)
                full_story += content

        print("\n")  # New line after streaming completes

        # Telemetry is automatically sent here after stream completes
        return full_story

# Example usage
story = stream_story("a brave knight", "user@example.com")
```

### Async Applications

Works seamlessly with async code:

```python
import asyncio
import os
from olakaisdk import olakai_config, instrument_openai, olakai_context
from openai import AsyncOpenAI

olakai_config(os.getenv("OLAKAI_API_KEY"))
instrument_openai()

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def process_request(user_email: str, request: str):
    """Process a single async request."""

    with olakai_context(
        userEmail=user_email,
        task="Async Processing"
    ):
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": request}]
        )

    return response.choices[0].message.content

async def process_batch(requests: list):
    """Process multiple requests concurrently."""

    tasks = [
        process_request(req["email"], req["message"])
        for req in requests
    ]

    # Run all requests concurrently
    results = await asyncio.gather(*tasks)

    return results

# Example usage
async def main():
    requests = [
        {"email": "user1@example.com", "message": "What is AI?"},
        {"email": "user2@example.com", "message": "Explain quantum computing"},
        {"email": "user3@example.com", "message": "How does blockchain work?"}
    ]

    results = await process_batch(requests)

    for i, result in enumerate(results):
        print(f"Response {i+1}: {result[:100]}...")

# Run async main
asyncio.run(main())
```

---

## Advanced Patterns

### Conditional Tracking

Track only specific types of requests:

```python
from olakaisdk import olakai_context

def should_track(user_tier: str, request_type: str) -> bool:
    """Decide whether to track this request."""
    # Only track premium users or important requests
    return user_tier in ["premium", "enterprise"] or request_type == "critical"

def handle_request(user_email, user_tier, request, request_type):
    """Handle request with conditional tracking."""

    if should_track(user_tier, request_type):
        with olakai_context(
            userEmail=user_email,
            task="Critical Request",
            customData={"tier": user_tier, "type": request_type}
        ):
            return client.chat.completions.create(...)
    else:
        # No tracking for basic requests
        return client.chat.completions.create(...)
```

### Error Handling with Tracking

Track errors and retries:

```python
from olakaisdk import olakai_context
import time

def robust_llm_call(prompt, user_email, max_retries=3):
    """Make LLM call with retry logic and error tracking."""

    for attempt in range(max_retries):
        try:
            with olakai_context(
                userEmail=user_email,
                task="Robust Call",
                customData={
                    "attempt": attempt + 1,
                    "retry_count": attempt
                }
            ):
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}]
                )

                return response.choices[0].message.content

        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")

            if attempt < max_retries - 1:
                # Exponential backoff
                time.sleep(2 ** attempt)
            else:
                # Final attempt failed, re-raise
                raise
```

### A/B Testing

Track different prompt strategies:

```python
from olakaisdk import olakai_context
import random

def ab_test_prompts(question, user_email):
    """Test two different prompt strategies."""

    # Randomly assign variant
    variant = "A" if random.random() < 0.5 else "B"

    if variant == "A":
        # Strategy A: Direct question
        prompt = question
    else:
        # Strategy B: Step-by-step prompting
        prompt = f"Let's think step by step. {question}"

    with olakai_context(
        userEmail=user_email,
        task="A/B Test",
        customData={
            "variant": variant,
            "prompt_strategy": "direct" if variant == "A" else "step-by-step"
        }
    ):
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )

    return {
        "answer": response.choices[0].message.content,
        "variant": variant
    }
```

---

## Flask/FastAPI Integration

### Flask Example

```python
from flask import Flask, request, jsonify
from olakaisdk import olakai_config, instrument_openai, olakai_context
from openai import OpenAI
import os

app = Flask(__name__)

# Initialize at app startup
olakai_config(os.getenv("OLAKAI_API_KEY"))
instrument_openai()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.route("/chat", methods=["POST"])
def chat():
    """Handle chat requests."""

    data = request.json
    user_email = data.get("user_email")
    message = data.get("message")

    # Add context for this request
    with olakai_context(
        userEmail=user_email,
        task="Web Chat",
        customData={
            "endpoint": "/chat",
            "method": "POST"
        }
    ):
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": message}]
        )

    return jsonify({
        "response": response.choices[0].message.content
    })

if __name__ == "__main__":
    app.run(debug=True)
```

### FastAPI Example

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from olakaisdk import olakai_config, instrument_openai, olakai_context
from openai import AsyncOpenAI
import os

app = FastAPI()

# Initialize at startup
olakai_config(os.getenv("OLAKAI_API_KEY"))
instrument_openai()

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class ChatRequest(BaseModel):
    user_email: str
    message: str

class ChatResponse(BaseModel):
    response: str

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Handle async chat requests."""

    with olakai_context(
        userEmail=request.user_email,
        task="API Chat",
        customData={
            "endpoint": "/chat",
            "framework": "fastapi"
        }
    ):
        try:
            response = await client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": request.message}]
            )

            return ChatResponse(
                response=response.choices[0].message.content
            )

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
async def startup_event():
    print("Olakai monitoring enabled")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## Production Best Practices

### 1. Environment-Based Configuration

```python
import os

def get_olakai_config():
    """Get configuration based on environment.

    Tip: in many deployments you can skip this entirely and just set
    the `OLAKAI_HOST` env var per-environment — the SDK will pick it up
    automatically from `olakai_config(api_key)`.
    """
    env = os.getenv("ENVIRONMENT", "development")

    if env == "production":
        return {
            "api_key": os.getenv("OLAKAI_API_KEY"),
            "host": "app.olakai.ai",
            "debug": False
        }
    elif env == "staging":
        return {
            "api_key": os.getenv("OLAKAI_STAGING_KEY"),
            "host": "staging.olakai.ai",
            "debug": True
        }
    else:  # development
        return {
            "api_key": os.getenv("OLAKAI_DEV_KEY", "dev-key"),
            "host": "dev.olakai.ai",
            "debug": True
        }

# Use configuration
config = get_olakai_config()
olakai_config(**config)
```

### 2. Graceful Degradation

```python
from olakaisdk import olakai_config, instrument_openai, is_initialized
import logging

logger = logging.getLogger(__name__)

def setup_monitoring():
    """Setup monitoring with graceful fallback."""
    try:
        api_key = os.getenv("OLAKAI_API_KEY")

        if not api_key:
            logger.warning("Olakai API key not found, monitoring disabled")
            return False

        olakai_config(api_key)
        instrument_openai()

        logger.info("Olakai monitoring enabled")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize Olakai: {e}")
        return False

# Use in production
monitoring_enabled = setup_monitoring()
```

### 3. Performance Monitoring

```python
import time
from olakaisdk import olakai_context

def timed_llm_call(prompt, user_email):
    """Track LLM call with custom latency metrics."""

    start_time = time.time()

    try:
        with olakai_context(
            userEmail=user_email,
            task="Performance Test"
        ):
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}]
            )

        latency = time.time() - start_time

        # Log performance
        if latency > 5.0:
            logger.warning(f"Slow LLM call: {latency:.2f}s")

        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"LLM call failed after {time.time() - start_time:.2f}s: {e}")
        raise
```

---

## Troubleshooting

### Debug Mode

Enable debug logging to see what's happening:

```python
from olakaisdk import olakai_config
import logging

# Enable Olakai debug mode
olakai_config("api-key", debug=True)

# Also enable Python logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Instrumentation Status

```python
from olakaisdk import is_instrumented, is_initialized

print(f"SDK Initialized: {is_initialized()}")
print(f"OpenAI Instrumented: {is_instrumented()}")
```

### Common Issues

**Issue: No data appearing in dashboard**

```python
# Checklist:
# 1. Verify configuration
from olakaisdk import get_config
config = get_config()
print(f"API Key: {config.api_key[:10]}...")
print(f"Endpoint: {config.endpoint}")

# 2. Check instrumentation
from olakaisdk import is_instrumented
print(f"Instrumented: {is_instrumented()}")

# 3. Enable debug mode
olakai_config("key", debug=True)

# 4. Make a test call
response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "test"}]
)
# You should see debug output
```

---

## Next Steps

- Read the [README.md](./README.md) for API reference
- Check [examples/](./examples/) for more sample code
- Visit [Olakai Dashboard](https://app.olakai.ai) to view your metrics

**Need help?** Contact [support@olakai.ai](mailto:support@olakai.ai)
