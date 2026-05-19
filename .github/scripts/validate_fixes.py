#!/usr/bin/env python3
"""
validate_fixes.py — Validate AI-suggested fixes against Dependabot recommendations.

Ensures that AI model suggestions match Dependabot's exact version recommendations
for dependency vulnerabilities (grounded data validation).

Usage:
    python validate_fixes.py \
        --findings results/aggregated-findings.json \
        --dependabot results/dependabot.json \
        --output results/validation-report.md

Exit codes:
    0 = All dependency fixes match Dependabot (validation passed)
    1 = One or more mismatches found (validation failed)
"""

import argparse
import json
import re
import sys
from pathlib import Path
from collections import defaultdict


def extract_package_name(message: str) -> str:
    """Extract package name from Dependabot finding message."""
    # Format: "package-name: Summary text"
    match = re.match(r"^(\S+):", message)
    if match:
        return match.group(1)
    return ""


def extract_suggested_version(suggestion: str) -> str:
    """Extract version from AI suggestion text."""
    # Format: "Upgrade package-name to >= 1.2.3"
    # or "Upgrade package-name to version 1.2.3"
    match = re.search(r"(?:>=|to version|to)\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?)", suggestion)
    if match:
        return match.group(1)
    return ""


def parse_aggregated_findings(findings_path: Path) -> dict:
    """Parse aggregated findings and extract dependency-related findings."""
    with open(findings_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    dependency_findings = []
    codeql_findings = defaultdict(int)
    
    for finding in data.get("findings", []):
        if finding.get("scanner") == "dependabot":
            package = extract_package_name(finding.get("message", ""))
            suggested_version = extract_suggested_version(finding.get("suggestion", ""))
            
            dependency_findings.append({
                "package": package,
                "rule": finding.get("rule", ""),
                "severity": finding.get("severity", ""),
                "message": finding.get("message", ""),
                "suggestion": finding.get("suggestion", ""),
                "suggested_version": suggested_version,
                "file": finding.get("file", ""),
            })
        elif finding.get("scanner") == "codeql":
            rule = finding.get("rule", "unknown")
            severity = finding.get("severity", "medium")
            codeql_findings[f"{severity}:{rule}"] += 1
    
    return {
        "dependency_findings": dependency_findings,
        "codeql_findings": codeql_findings,
    }


def parse_dependabot_data(dependabot_path: Path) -> dict:
    """Parse Dependabot JSON and extract recommended versions."""
    with open(dependabot_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Handle both array and object with alerts key
    alerts = data if isinstance(data, list) else data.get("alerts", [])
    
    recommendations = {}
    
    for alert in alerts:
        # Extract package info
        dep = alert.get("dependency", {})
        package_info = dep.get("package", {})
        package_name = package_info.get("name", "")
        
        if not package_name:
            continue
        
        # Extract recommended version
        first_patched = (
            alert.get("security_vulnerability", {})
            .get("first_patched_version", {})
            .get("identifier", "")
        )
        
        # Extract severity
        severity = (
            alert.get("security_vulnerability", {}).get("severity", "")
            or alert.get("security_advisory", {}).get("severity", "medium")
        ).lower()
        
        # Extract CVE
        cve_id = ""
        identifiers = alert.get("security_advisory", {}).get("identifiers", [])
        for ident in identifiers:
            if ident.get("type") == "CVE":
                cve_id = ident.get("value", "")
                break
        
        recommendations[package_name] = {
            "recommended_version": first_patched,
            "severity": severity,
            "cve": cve_id,
        }
    
    return recommendations


def validate_fixes(aggregated: dict, dependabot_recommendations: dict) -> dict:
    """Validate that AI suggestions match Dependabot recommendations."""
    matched = []
    mismatched = []
    
    for finding in aggregated["dependency_findings"]:
        package = finding["package"]
        ai_version = finding["suggested_version"]
        
        if package not in dependabot_recommendations:
            # No Dependabot recommendation found (possibly filtered or different source)
            continue
        
        recommended = dependabot_recommendations[package]
        dependabot_version = recommended["recommended_version"]
        
        if ai_version == dependabot_version:
            matched.append({
                "package": package,
                "severity": finding["severity"],
                "ai_suggests": ai_version,
                "dependabot_recommends": dependabot_version,
                "cve": recommended.get("cve", ""),
            })
        else:
            mismatched.append({
                "package": package,
                "severity": finding["severity"],
                "ai_suggests": ai_version,
                "dependabot_recommends": dependabot_version,
                "cve": recommended.get("cve", ""),
            })
    
    return {
        "matched": matched,
        "mismatched": mismatched,
        "codeql_findings": aggregated["codeql_findings"],
    }


def generate_report(validation: dict) -> str:
    """Generate markdown validation report."""
    matched = validation["matched"]
    mismatched = validation["mismatched"]
    codeql = validation["codeql_findings"]
    
    passed = len(mismatched) == 0
    status_emoji = "✅" if passed else "❌"
    status_text = "PASSED" if passed else "FAILED"
    
    report = f"""## Fix Validation Report

**Validation Status**: {status_emoji} {status_text}

"""
    
    # Matched fixes
    if matched:
        report += """### ✅ Validated Fixes (AI model matches Dependabot exactly)

| Package | Severity | AI Suggests | Dependabot Recommends | CVE | Status |
|---------|----------|-------------|----------------------|-----|--------|
"""
        for fix in matched:
            cve = fix.get("cve", "N/A")
            report += f"| {fix['package']} | {fix['severity']} | {fix['ai_suggests']} | {fix['dependabot_recommends']} | {cve} | ✅ MATCH |\n"
        report += "\n"
    
    # Mismatched fixes
    if mismatched:
        report += """### ❌ Mismatched Fixes (AI suggestion differs from Dependabot — REVIEW REQUIRED)

| Package | Severity | AI Suggests | Dependabot Recommends | CVE | Action |
|---------|----------|-------------|----------------------|-----|--------|
"""
        for fix in mismatched:
            cve = fix.get("cve", "N/A")
            report += f"| {fix['package']} | {fix['severity']} | {fix['ai_suggests']} | {fix['dependabot_recommends']} | {cve} | ⚠️ **USE DEPENDABOT VERSION** |\n"
        report += "\n"
    
    # CodeQL findings
    if codeql:
        report += """### ℹ️ CodeQL Findings (no version validation needed)

| Rule | Severity | Count |
|------|----------|-------|
"""
        for key, count in sorted(codeql.items(), key=lambda x: x[1], reverse=True):
            severity, rule = key.split(":", 1)
            report += f"| `{rule}` | {severity} | {count} |\n"
        report += "\n"
    
    # Summary
    total_deps = len(matched) + len(mismatched)
    report += f"""---

**Grounded Data Verification**: {len(matched)} of {total_deps} dependency fixes match Dependabot recommendations.

"""
    
    if not passed:
        report += """⚠️ **AUTO-FIX PR CREATION BLOCKED**

Manual review required due to mismatched version recommendations. The AI model suggested different versions than Dependabot for one or more packages.

**Required action:** Review the mismatched fixes above and determine the correct version to use. Typically, Dependabot's recommendation should be trusted as it's based on security advisory data.
"""
    else:
        report += "✅ **VALIDATION PASSED** — Auto-fix PR can proceed safely.\n"
    
    return report


def main():
    parser = argparse.ArgumentParser(description="Validate AI fixes against Dependabot")
    parser.add_argument("--findings", required=True, help="Path to aggregated-findings.json")
    parser.add_argument("--dependabot", required=True, help="Path to dependabot.json")
    parser.add_argument("--output", required=True, help="Output markdown report path")
    
    args = parser.parse_args()
    
    # Parse inputs
    findings_path = Path(args.findings)
    dependabot_path = Path(args.dependabot)
    
    if not findings_path.exists():
        print(f"Error: Findings file not found: {args.findings}", file=sys.stderr)
        sys.exit(1)
    
    if not dependabot_path.exists():
        print(f"Error: Dependabot file not found: {args.dependabot}", file=sys.stderr)
        sys.exit(1)
    
    aggregated = parse_aggregated_findings(findings_path)
    dependabot_recommendations = parse_dependabot_data(dependabot_path)
    
    # Validate
    validation = validate_fixes(aggregated, dependabot_recommendations)
    
    # Generate report
    report = generate_report(validation)
    
    # Write report
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report)
    
    # Output summary
    matched_count = len(validation["matched"])
    mismatched_count = len(validation["mismatched"])
    total_count = matched_count + mismatched_count
    
    print(f"Validation report written to {args.output}")
    print(f"Matched: {matched_count}/{total_count}, Mismatched: {mismatched_count}/{total_count}")
    
    if mismatched_count > 0:
        print(f"::error::Validation failed: {mismatched_count} AI suggestions differ from Dependabot", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"::notice::Validation passed: All AI suggestions match Dependabot recommendations")
        sys.exit(0)


if __name__ == "__main__":
    main()
