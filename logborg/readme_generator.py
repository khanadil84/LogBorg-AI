from pathlib import Path


def discover_modules(project_root: Path) -> list[str]:
    """Discover real LogBorg Python modules from the source tree."""
    package_root = project_root / "logborg"

    return sorted(
        str(path.relative_to(project_root))
        for path in package_root.rglob("*.py")
        if path.name != "__init__.py"
    )


def generate_readme(project_root: Path) -> Path:
    """Generate README.md from the current project structure."""
    modules = discover_modules(project_root)

    lines = [
        "# LogBorg AI",
        "",
        "## The Autonomous Log Triage & Self-Healing SRE Sandbox",
        "",
        "LogBorg AI captures runtime stdout/stderr telemetry, detects known "
        "fault signatures, diagnoses supported failures, applies bounded "
        "runtime repairs, and independently verifies recovery.",
        "",
        "## Architecture",
        "",
        "```text",
        "LIVE RUNTIME",
        "     ↓",
        "INGESTION → DETECTION → DIAGNOSIS → REPAIR → VERIFICATION",
        "                                      ↓",
        "                                  RECOVERY",
        "```",
        "",
        "## Discovered Python Modules",
        "",
    ]

    lines.extend(f"- `{module}`" for module in modules)

    lines.extend(
        [
            "",
            "## Evidence",
            "",
            "- Runtime recovery evidence is written to `runtime-evidence.json`.",
            "- Remediation metadata is written to `logborg-manifest.json`.",
            "- Recovery is bounded and failed recovery triggers rollback.",
            "",
            "## Tests",
            "",
            "Run:",
            "",
            "```bash",
            "pytest -q",
            "```",
            "",
        ]
    )

    output = project_root / "README.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    output = generate_readme(root)
    print(f"README GENERATED: {output}")
