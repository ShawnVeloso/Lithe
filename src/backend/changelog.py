import os
import re

def generate_changelog():
    """Generates CHANGELOG.md from docs/agent-logs/INDEX.md log entries."""
    # Paths are relative to the project root (where server runs)
    index_path = os.path.join("docs", "agent-logs", "INDEX.md")
    changelog_path = "CHANGELOG.md"

    if not os.path.exists(index_path):
        print(f"[Changelog] {index_path} not found. Skipping.")
        return

    try:
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Find the Log Entries table
        table_match = re.search(r"## Log Entries\n+(.*?)(?=\n## |\Z)", content, re.DOTALL)
        if not table_match:
            print("[Changelog] Log Entries table not found in INDEX.md.")
            return

        table_text = table_match.group(1).strip()
        lines = table_text.split("\n")
        
        # Parse table rows (skip header and separator)
        entries = []
        for line in lines[2:]:
            if line.startswith("|"):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 4:
                    date = parts[1]
                    action = parts[3]
                    entries.append((date, action))

        # Group by date
        grouped = {}
        for date, action in entries:
            if date not in grouped:
                grouped[date] = []
            grouped[date].append(action)

        # Generate CHANGELOG.md content
        changelog_lines = ["# Changelog\n", "Auto-generated from `docs/agent-logs/INDEX.md`.\n"]
        
        # Sort dates descending
        for date in sorted(grouped.keys(), reverse=True):
            changelog_lines.append(f"## {date}")
            for action in grouped[date]:
                changelog_lines.append(f"- {action}")
            changelog_lines.append("")

        with open(changelog_path, "w", encoding="utf-8") as f:
            f.write("\n".join(changelog_lines))
            
        print("[Changelog] Successfully generated CHANGELOG.md")
    except Exception as e:
        print(f"[Changelog] Error generating changelog: {e}")

if __name__ == "__main__":
    generate_changelog()
