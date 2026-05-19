#!/usr/bin/env python3
"""
count_tokens.py — Estimate and track token consumption for GitHub Models API calls.

Uses tiktoken (OpenAI's official tokenizer) for accurate token counting across GPT models.

Usage:
    # Estimate tokens before API call
    python count_tokens.py \
        --system-prompt "$(cat .github/skills/security-autofix.md)" \
        --user-message "$(cat /tmp/user_msg.txt)" \
        --model "openai/gpt-4o-mini" \
        --output results/token-estimate.json

    # Compare actual vs estimated after API call
    python count_tokens.py \
        --compare \
        --estimate results/token-estimate.json \
        --actual <(echo "$RESPONSE" | jq '.usage') \
        --output results/token-usage.json
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import tiktoken
except ImportError:
    print("Error: tiktoken library not installed", file=sys.stderr)
    print("Install with: pip install tiktoken", file=sys.stderr)
    sys.exit(1)


# Model pricing per 1M tokens (May 2026)
MODEL_PRICING = {
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "openai/gpt-4o": {"input": 2.50, "output": 10.00},
    "openai/gpt-4.1": {"input": 5.00, "output": 20.00},
    "openai/o3": {"input": 10.00, "output": 40.00},
}

# Default completion token estimate (conservative)
DEFAULT_COMPLETION_ESTIMATE = 3000


def get_encoding_for_model(model: str):
    """Get the appropriate tiktoken encoding for a model."""
    # GitHub Models API uses standard OpenAI models with cl100k_base encoding
    # (gpt-4o, gpt-4o-mini, gpt-4.1 all use cl100k_base)
    # o3 also uses cl100k_base
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str, model: str = "openai/gpt-4o-mini") -> int:
    """Count tokens in a text string."""
    encoding = get_encoding_for_model(model)
    return len(encoding.encode(text))


def count_message_tokens(messages: list[dict], model: str = "openai/gpt-4o-mini") -> int:
    """
    Count tokens for a list of messages in chat completion format.
    
    Accounts for message formatting overhead:
    - Each message adds ~4 tokens (role markers, formatting)
    - Each completion adds ~3 tokens (assistant role + formatting)
    """
    encoding = get_encoding_for_model(model)
    total_tokens = 0
    
    for message in messages:
        # Add tokens for role and content
        total_tokens += 4  # Message formatting overhead
        total_tokens += len(encoding.encode(message.get("role", "")))
        total_tokens += len(encoding.encode(message.get("content", "")))
    
    total_tokens += 3  # Completion priming overhead
    return total_tokens


def format_cost(tokens: int, model: str, token_type: str = "input") -> float:
    """Calculate cost for a given number of tokens."""
    pricing = MODEL_PRICING.get(model, {"input": 0.15, "output": 0.60})
    rate = pricing.get(token_type, 0.15)
    return (tokens / 1_000_000) * rate


def estimate_tokens(system_prompt: str, user_message: str, model: str) -> dict:
    """Estimate token consumption for a chat completion request."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    
    input_tokens = count_message_tokens(messages, model)
    completion_tokens = DEFAULT_COMPLETION_ESTIMATE  # Conservative estimate
    total_tokens = input_tokens + completion_tokens
    
    input_cost = format_cost(input_tokens, model, "input")
    output_cost = format_cost(completion_tokens, model, "output")
    total_cost = input_cost + output_cost
    
    return {
        "estimated_input": input_tokens,
        "estimated_completion": completion_tokens,
        "total_estimate": total_tokens,
        "input_cost": round(input_cost, 6),
        "output_cost": round(output_cost, 6),
        "total_cost": round(total_cost, 6),
        "model": model,
    }


def compare_usage(estimate: dict, actual: dict) -> dict:
    """Compare estimated vs actual token usage."""
    estimated_input = estimate.get("estimated_input", 0)
    estimated_completion = estimate.get("estimated_completion", 0)
    
    actual_input = actual.get("prompt_tokens", 0)
    actual_completion = actual.get("completion_tokens", 0)
    actual_total = actual.get("total_tokens", 0)
    
    # Calculate variance
    input_variance = 0
    if estimated_input > 0:
        input_variance = ((actual_input - estimated_input) / estimated_input) * 100
    
    completion_variance = 0
    if estimated_completion > 0:
        completion_variance = ((actual_completion - estimated_completion) / estimated_completion) * 100
    
    # Recalculate actual costs
    model = estimate.get("model", "openai/gpt-4o-mini")
    actual_input_cost = format_cost(actual_input, model, "input")
    actual_output_cost = format_cost(actual_completion, model, "output")
    actual_total_cost = actual_input_cost + actual_output_cost
    
    return {
        "estimated": estimate,
        "actual": {
            "prompt_tokens": actual_input,
            "completion_tokens": actual_completion,
            "total_tokens": actual_total,
            "input_cost": round(actual_input_cost, 6),
            "output_cost": round(actual_output_cost, 6),
            "total_cost": round(actual_total_cost, 6),
        },
        "variance": {
            "input_percent": round(input_variance, 2),
            "completion_percent": round(completion_variance, 2),
            "input_diff": actual_input - estimated_input,
            "completion_diff": actual_completion - estimated_completion,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Count tokens for GitHub Models API calls")
    parser.add_argument("--system-prompt", help="System prompt text")
    parser.add_argument("--user-message", help="User message text")
    parser.add_argument("--model", default="openai/gpt-4o-mini", help="Model name")
    parser.add_argument("--compare", action="store_true", help="Compare mode: actual vs estimated")
    parser.add_argument("--estimate", help="Path to estimate JSON file (for compare mode)")
    parser.add_argument("--actual", help="Path to actual usage JSON file (for compare mode)")
    parser.add_argument("--output", help="Output JSON file path")
    
    args = parser.parse_args()
    
    if args.compare:
        # Compare mode
        if not args.estimate or not args.actual:
            print("Error: --compare requires --estimate and --actual", file=sys.stderr)
            sys.exit(1)
        
        with open(args.estimate, "r") as f:
            estimate = json.load(f)
        
        with open(args.actual, "r") as f:
            actual = json.load(f)
        
        result = compare_usage(estimate, actual)
    else:
        # Estimate mode
        if not args.system_prompt or not args.user_message:
            print("Error: --system-prompt and --user-message required", file=sys.stderr)
            sys.exit(1)
        
        result = estimate_tokens(args.system_prompt, args.user_message, args.model)
    
    # Output result
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Token data written to {args.output}")
    else:
        print(json.dumps(result, indent=2))
    
    # Log summary to stderr for workflow annotations
    if args.compare:
        print(f"::notice::Token usage: input={result['actual']['prompt_tokens']} "
              f"(estimated: {result['estimated']['estimated_input']}, "
              f"variance: {result['variance']['input_percent']}%), "
              f"completion={result['actual']['completion_tokens']} "
              f"(estimated: {result['estimated']['estimated_completion']}, "
              f"variance: {result['variance']['completion_percent']}%), "
              f"cost=${result['actual']['total_cost']}", file=sys.stderr)
    else:
        print(f"::notice::Estimated token usage: {result['total_estimate']} tokens "
              f"(input: {result['estimated_input']}, completion: {result['estimated_completion']}), "
              f"cost: ~${result['total_cost']}", file=sys.stderr)


if __name__ == "__main__":
    main()
