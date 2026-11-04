#!/usr/bin/env python3
"""Quick test to verify LLM summary generation works."""

import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(__file__))

from src.llm import gateway
from src.agents.tool_agent import _extract_final_text_from_message

async def test_llm_summary():
    """Test LLM summary generation directly."""

    print("=" * 80)
    print("TESTING LLM-BASED SUMMARY GENERATION")
    print("=" * 80)

    # Sample conversation
    transcript = """
USER: I want to build a financial dashboard
ASSISTANT: Great! What are the key features you need?
USER: Real-time stock updates and portfolio tracking
ASSISTANT: I recommend React with D3 for charts and WebSocket for real-time data
USER: Perfect! What about authentication?
ASSISTANT: JWT tokens in httpOnly cookies is the standard approach
    """.strip()

    prompt = f"""Summarize the following conversation in 2-4 lines.
Focus on: what was discussed, key decisions made, and any agreements or next steps.
Keep it concise and actionable.

Conversation:
{transcript}

Summary:"""

    print(f"\n[1] Testing gateway.create_message()...")
    print(f"    Model: {gateway.model_for('default')}")

    try:
        msg = gateway.create_message(
            model=gateway.model_for("default"),
            max_tokens=200,
            temperature=0.3,
            system="You are a concise conversation summarizer.",
            messages=[{"role": "user", "content": prompt}],
        )
        print(f"    [OK] Gateway call succeeded")

        print(f"\n[2] Extracting summary text...")
        summary = _extract_final_text_from_message(msg).strip()
        print(f"    [OK] Text extracted")

        if summary:
            print(f"\n[3] GENERATED SUMMARY:")
            print(f"    {summary}")
            print(f"\n[SUCCESS] LLM summary generation is working correctly!")
        else:
            print(f"    [ERROR] Summary is empty!")

    except Exception as e:
        print(f"    [ERROR] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_llm_summary())
