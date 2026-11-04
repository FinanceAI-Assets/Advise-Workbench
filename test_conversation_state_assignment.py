#!/usr/bin/env python3
"""Test to verify ConversationState assignment works correctly."""

import json
from src.memory.short_term.conversation_state import ConversationState

# Create a state object
state = ConversationState(
    schema_version=2,
    state="exploring",
    slots={"client": {"name": "Test"}},
    deliverable={},
    last_router={},
    pending_questions=[],
    surfaced_wiki_refs=[],
    history_summary="",
    conversation_summary=""  # Initially empty
)

print("=" * 80)
print("TEST: ConversationState Assignment and Serialization")
print("=" * 80)
print()

# Test 1: Initial state
print("1. Initial state:")
print(f"   conversation_summary = '{state.conversation_summary}'")
print(f"   Type: {type(state.conversation_summary)}")
print()

# Test 2: Assignment
test_summary = "Discovered: client, outcome | Status: exploring"
state.conversation_summary = test_summary
print("2. After assignment:")
print(f"   conversation_summary = '{state.conversation_summary}'")
print(f"   Equals test value: {state.conversation_summary == test_summary}")
print()

# Test 3: to_json()
json_str = state.to_json()
print("3. After to_json():")
print(f"   JSON string length: {len(json_str)}")
parsed = json.loads(json_str)
print(f"   conversation_summary in JSON: '{parsed.get('conversation_summary')}'")
print(f"   Value in JSON equals assignment: {parsed.get('conversation_summary') == test_summary}")
print()

# Test 4: Check if field exists
print("4. Field presence:")
print(f"   'conversation_summary' in JSON: {'conversation_summary' in parsed}")
print(f"   Value is empty string: {parsed.get('conversation_summary') == ''}")
print(f"   Value is None: {parsed.get('conversation_summary') is None}")
print()

# Test 5: to_dict()
dict_repr = state.to_dict()
print("5. to_dict():")
print(f"   'conversation_summary' in dict: {'conversation_summary' in dict_repr}")
print(f"   Value: '{dict_repr.get('conversation_summary')}'")
print()

# Final result
if parsed.get('conversation_summary') == test_summary:
    print("✅ TEST PASSED: ConversationState serialization works correctly")
else:
    print("❌ TEST FAILED: ConversationState not serializing correctly")
    print(f"   Expected: '{test_summary}'")
    print(f"   Got: '{parsed.get('conversation_summary')}'")
