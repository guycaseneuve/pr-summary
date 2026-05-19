#!/usr/bin/env python3
"""
cost_analysis.py — Generate comprehensive cost comparison tables for security scanning.

Generates 4 cost comparison tables:
1. Security scan tiers (Free vs GHAS vs self-hosted)
2. AI model pricing (gpt-4o-mini, gpt-4o, gpt-4.1, o3)
3. Scan frequency impact (per-PR, daily, weekly, main branch push)
4. Repository size impact (small, medium, large, enterprise)

Usage:
    python cost_analysis.py --output results/cost-analysis.md
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# Model pricing per 1M tokens (May 2026)
MODEL_PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "context": "128K", "max_completion": "16K"},
    "gpt-4o": {"input": 2.50, "output": 10.00, "context": "128K", "max_completion": "16K"},
    "gpt-4.1": {"input": 5.00, "output": 20.00, "context": "256K", "max_completion": "32K"},
    "o3": {"input": 10.00, "output": 40.00, "context": "200K", "max_completion": "100K"},
}

# Typical token counts per scan (based on current workflow measurements)
TYPICAL_SCAN = {
    "input_tokens": 6250,
    "output_tokens": 3000,
}


def calculate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """Calculate cost for a given token count and model."""
    pricing = MODEL_PRICING.get(model, {"input": 0.15, "output": 0.60})
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost


def load_current_usage(usage_file: Path) -> dict:
    """Load actual token usage from current workflow run."""
    if not usage_file.exists():
        return None
    
    try:
        data = json.loads(usage_file.read_text())
        return {
            "input_tokens": data["actual"]["prompt_tokens"],
            "output_tokens": data["actual"]["completion_tokens"],
            "data_source": "actual_current_run",
            "model": data["estimated"].get("model", "unknown"),
        }
    except (json.JSONDecodeError, KeyError) as e:
        print(f"::warning::Failed to load token usage: {e}", file=sys.stderr)
        return None


def generate_table_1() -> str:
    """Generate Table 1: Security Scan Tiers Comparison."""
    return """### Table 1: Security Scan Tiers Comparison

| Tier | CodeQL | Dependabot | Secret Scanning | Monthly Cost | Notes |
|------|--------|------------|-----------------|--------------|-------|
| **Free (Public)** | ✅ Unlimited | ✅ Basic alerts | ✅ Public repos only | **$0** | Public repositories only |
| **GHAS (Private)** | ✅ Unlimited | ✅ Advanced alerts + Auto-triage | ✅ Advanced + Custom patterns | **~$49/active committer** | Enterprise plan required; billed per active committer |
| **Self-hosted** | ⚠️ Manual setup | ⚠️ Manual setup | ⚠️ Manual setup | Infrastructure cost | Requires maintenance overhead, custom tooling |

**Notes:**
- GitHub Advanced Security (GHAS) pricing based on May 2026 public pricing
- Free tier includes CodeQL, Dependabot, and secret scanning for public repositories
- GHAS required for private repositories with advanced security features
- Self-hosted scanners incur infrastructure costs (compute, storage, maintenance)
"""


def generate_table_2() -> str:
    """Generate Table 2: AI Model Pricing."""
    table = """### Table 2: AI Model Pricing (GitHub Models API, per 1M tokens)

| Model | Input $/1M | Output $/1M | Context Window | Max Completion | Best For |
|-------|-----------|-------------|----------------|----------------|----------|
"""
    
    for model, pricing in MODEL_PRICING.items():
        input_price = f"${pricing['input']:.2f}"
        output_price = f"${pricing['output']:.2f}"
        context = pricing['context']
        max_comp = pricing['max_completion']
        
        if model == "gpt-4o-mini":
            best_for = "Default (cost-effective, fast)"
        elif model == "gpt-4o":
            best_for = "Higher quality analysis"
        elif model == "gpt-4.1":
            best_for = "Large context requirements"
        else:  # o3
            best_for = "Complex reasoning, multi-step"
        
        table += f"| **{model}** | {input_price} | {output_price} | {context} | {max_comp} | {best_for} |\n"
    
    table += """
**Notes:**
- Pricing as of May 2026 (GitHub Models API)
- Input tokens = prompt + system message + context
- Output tokens = AI-generated response
- Context window = maximum total tokens (input + output)
"""
    return table


def generate_table_3(usage_data: dict = None) -> str:
    """Generate Table 3: Scan Frequency Impact."""
    frequencies = [
        {"name": "Per PR (20/mo)", "scans": 20, "description": "Scan every pull request"},
        {"name": "Per push (100/mo)", "scans": 100, "description": "Scan every commit"},
        {"name": "Daily", "scans": 30, "description": "Once per day"},
        {"name": "Weekly", "scans": 4, "description": "Once per week"},
        {"name": "**Current (main push)**", "scans": 10, "description": "**~10 pushes to main/month**"},
    ]
    
    # Use actual data if available, else defaults
    if usage_data:
        input_tokens = usage_data["input_tokens"]
        output_tokens = usage_data["output_tokens"]
        data_source = usage_data.get("data_source", "actual")
        model_used = usage_data.get("model", "unknown")
    else:
        input_tokens = TYPICAL_SCAN["input_tokens"]
        output_tokens = TYPICAL_SCAN["output_tokens"]
        data_source = "estimated"
        model_used = None
    
    table = f"""### Table 3: Scan Frequency Impact

*Assumes {input_tokens:,} input tokens + {output_tokens:,} output tokens per security scan*

| Frequency | Scans/Month | Input Tokens | Output Tokens | Cost (gpt-4o-mini) | Cost (gpt-4o) |
|-----------|-------------|--------------|---------------|--------------------|---------------|
"""
    
    for freq in frequencies:
        scans = freq["scans"]
        total_input = input_tokens * scans
        total_output = output_tokens * scans
        cost_mini = calculate_cost(total_input, total_output, "gpt-4o-mini")
        cost_4o = calculate_cost(total_input, total_output, "gpt-4o")
        
        table += f"| {freq['name']} | {scans} | {total_input:,} | {total_output:,} | ${cost_mini:.2f} | ${cost_4o:.2f} |\n"
    
    # Add data source footer
    if data_source == "actual_current_run":
        variance_input = ((input_tokens - TYPICAL_SCAN["input_tokens"]) / TYPICAL_SCAN["input_tokens"] * 100)
        variance_output = ((output_tokens - TYPICAL_SCAN["output_tokens"]) / TYPICAL_SCAN["output_tokens"] * 100)
        table += f"""
**Data Source:** Actual usage from current workflow run
- Model: {model_used}
- Actual: {input_tokens:,} input / {output_tokens:,} output tokens
- Estimated: {TYPICAL_SCAN["input_tokens"]:,} input / {TYPICAL_SCAN["output_tokens"]:,} output tokens
- Variance: {variance_input:+.1f}% input, {variance_output:+.1f}% output

**Notes:**
- Current workflow triggers on main branch push (~10x/month typical for active repos)
- Per-PR scanning can be expensive for high-traffic repositories
- Weekly scans balance cost with security coverage
"""
    else:
        table += """
**Data Source:** Estimated typical usage (hardcoded defaults)

**Notes:**
- Current workflow triggers on main branch push (~10x/month typical for active repos)
- Per-PR scanning can be expensive for high-traffic repositories
- Weekly scans balance cost with security coverage
- Token counts based on typical scan patterns
"""
    return table


def generate_table_4(usage_data: dict = None) -> str:
    """Generate Table 4: Repository Size Impact."""
    # If we have actual data, adjust Medium tier to match current repo
    if usage_data and usage_data.get("data_source") == "actual_current_run":
        repo_sizes = [
            {"name": "Small", "files": "<10", "findings": "5-10", "input": 3000, "output": 1500},
            {"name": "Medium (current repo)", "files": "10-50", "findings": "10-50", 
             "input": usage_data["input_tokens"], "output": usage_data["output_tokens"]},
            {"name": "Large", "files": "50-200", "findings": "50-100", "input": 10000, "output": 3000},
            {"name": "Enterprise", "files": "200+", "findings": "100+", "input": 10000, "output": 3000},
        ]
    else:
        repo_sizes = [
            {"name": "Small", "files": "<10", "findings": "5-10", "input": 3000, "output": 1500},
            {"name": "Medium", "files": "10-50", "findings": "10-50", "input": 6250, "output": 3000},
            {"name": "Large", "files": "50-200", "findings": "50-100", "input": 10000, "output": 3000},
            {"name": "Enterprise", "files": "200+", "findings": "100+", "input": 10000, "output": 3000},
        ]
    
    table = """### Table 4: Repository Size Impact

*Based on typical security scan findings and truncation limits*

| Repo Size | Files | Typical Findings | Input Tokens | Output Tokens | Cost/Scan (gpt-4o-mini) |
|-----------|-------|------------------|--------------|---------------|-------------------------|
"""
    
    for size in repo_sizes:
        cost = calculate_cost(size["input"], size["output"], "gpt-4o-mini")
        table += f"| {size['name']} | {size['files']} | {size['findings']} | {size['input']:,} | {size['output']:,} | ${cost:.4f} |\n"
    
    table += """
**Notes:**
- Findings JSON truncated to 10,000 chars to prevent unbounded costs
- Large and enterprise repos hit truncation limit (similar token usage)
- Output tokens relatively stable regardless of input size (report format is consistent)
- Actual costs vary based on code complexity and vulnerability density
"""
    return table


def generate_cost_analysis(usage_data: dict = None) -> str:
    """Generate complete cost analysis markdown."""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    # Add data source indicator in header
    data_indicator = ""
    if usage_data and usage_data.get("data_source") == "actual_current_run":
        data_indicator = " (Using Actual Token Data)"
    
    markdown = f"""# Security Scanning Cost Analysis{data_indicator}

**Generated:** {timestamp}

This report compares costs across security scanning tiers, AI models, scan frequencies, and repository sizes to help optimize the security automation workflow.

---

{generate_table_1()}

---

{generate_table_2()}

---

{generate_table_3(usage_data)}

---

{generate_table_4(usage_data)}

---

## Cost Optimization Recommendations

1. **Use gpt-4o-mini for routine scans** — Provides good quality at 1/17th the cost of gpt-4o
2. **Trigger on main branch only** — Reduces token waste on abandoned feature branches (~50% cost reduction)
3. **Weekly scheduled scans** — Balance between cost ($0.02/month) and security coverage
4. **Truncate findings to 10KB** — Prevents runaway costs on large repositories (already implemented)
5. **Cache system prompts** — Skills and prompts are static (~2KB saved per call if supported by API)

## Current Workflow Configuration

- **Trigger:** Main branch push (~10x/month)
- **Model:** gpt-4o-mini (default, configurable via workflow_dispatch)
- **Truncation:** 10,000 chars for findings JSON
- **Estimated monthly cost:** ~$0.03 (gpt-4o-mini) or ~$0.46 (gpt-4o)

## Break-even Analysis

To justify GHAS cost ($49/committer/month), you would need to prevent:
- **1 critical vulnerability** reaching production (avg remediation cost: $500-5,000)
- **OR 1 hour of developer time** saved per month (at $50-100/hr)

The AI-powered auto-fix workflow adds minimal cost (~$0.03-0.50/month) while significantly improving remediation speed.
"""
    return markdown


def main():
    parser = argparse.ArgumentParser(description="Generate security scanning cost analysis")
    parser.add_argument("--output", required=True, help="Output markdown file path")
    parser.add_argument("--usage-file", help="Path to token-usage.json from current workflow run")
    
    args = parser.parse_args()
    
    # Load actual token usage if provided
    usage_data = None
    if args.usage_file:
        usage_data = load_current_usage(Path(args.usage_file))
        if usage_data:
            print(f"::notice::Using actual token data: {usage_data['input_tokens']} input, {usage_data['output_tokens']} output")
        else:
            print("::warning::Failed to load token usage file, using estimated defaults")
    
    # Generate cost analysis
    markdown = generate_cost_analysis(usage_data)
    
    # Write to file
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown)
    
    print(f"Cost analysis written to {args.output}")
    print(f"::notice::Cost analysis generated with 4 comparison tables")


if __name__ == "__main__":
    main()
