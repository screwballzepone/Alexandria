"""
Config drift guard ÔÇö runs on app startup, validates OpenCode configuration.
Returns a list of warning strings (empty = all clear).
"""

import jsonfrom pathlib import Pathdef check_config(project_root: str) -> list[str]:
    """
    Validates .opencode/opencode.json and agent files.
    Returns list of human-readable warning strings.
    """
    warnings = []
    opencode_dir = Path(project_root) / ".opencode"

    # 1. Check opencode.json exists and is valid JSON
    config_path = opencode_dir / "opencode.json"
    if not config_path.exists():
        warnings.append("ÔÜá .opencode/opencode.json not found")
        return warnings

    try:
        with open(config_path) as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        warnings.append(f"ÔÜá opencode.json is invalid JSON: {e}")
        return warnings

    # 2. Check default_agent exists as a file
    default_agent = cfg.get("default_agent", "build")
    agent_file = opencode_dir / "agent" / f"{default_agent}.md"
    if not agent_file.exists():
        warnings.append(
            f"ÔÜá default_agent '{default_agent}' has no agent file at"
            f" .opencode/agent/{default_agent}.md"
        )

    # 3. Check all .opencode/agent/*.md files exist
    agent_dir = opencode_dir / "agent"
    if agent_dir.exists():
        for md_file in agent_dir.glob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                # Basic frontmatter check
                if not content.startswith("---"):
                    warnings.append(
                        f"ÔÜá Agent file {md_file.name} missing frontmatter (should start with ---)"
                    )
            except Exception:
                warnings.append(f"ÔÜá Could not read agent file {md_file.name}")

    # 4. Check instructions files exist
    for instr_path in cfg.get("instructions", []):
        full_path = Path(project_root) / instr_path
        if not full_path.exists():
            warnings.append(f"ÔÜá instructions file not found: {instr_path}")

    # 5. Check protocols directory exists (new in this session)
    protocols_dir = opencode_dir / "protocols"
    if not protocols_dir.exists():
        warnings.append("ÔÜá .opencode/protocols/ missing ÔÇö mission autonomy features unavailable")

    return warnings
