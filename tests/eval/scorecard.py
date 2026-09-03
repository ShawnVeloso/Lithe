"""Shared scorecard state and rendering.

This lives outside conftest.py deliberately. pytest loads conftest as a plugin,
so a test module importing `tests.eval.conftest` can end up with a second
module object holding a different RESULTS list — results append to one list
while the terminal hook reads the other, and the scorecard silently prints
nothing. A plain module is imported once and shared by both.
"""

RESULTS = []


def render(write):
    """Print the capability scorecard. `write` takes one line of text."""
    if not RESULTS:
        return

    write("")
    write("=" * 72)
    write("LITHE CAPABILITY SCORECARD")
    write("=" * 72)

    categories = {}
    for r in RESULTS:
        categories.setdefault(r["category"], []).append(r)

    scored = [r for r in RESULTS if not r["known_gap"]]
    gaps = [r for r in RESULTS if r["known_gap"]]

    for category in sorted(categories):
        rows = categories[category]
        counted = [r for r in rows if not r["known_gap"]]
        passed = sum(1 for r in counted if r["verdict"] == "pass")
        flaky = [r for r in counted if r["verdict"] == "flaky"]
        label = f"{passed}/{len(counted)}" if counted else "-"
        suffix = f"  ({len(flaky)} flaky)" if flaky else ""
        write(f"  {category:<22} {label}{suffix}")
        for r in rows:
            if r["known_gap"] or r["verdict"] == "pass":
                continue
            write(f"      {r['verdict']:<6} {r['id']}: {r['detail']}")

    if scored:
        score = sum(1 for r in scored if r["verdict"] == "pass") / len(scored)
        write("")
        write(f"  CAPABILITY SCORE: {score:.0%}  ({len(scored)} scored cases)")

    if gaps:
        write("")
        write("  Known gaps (excluded from the score):")
        for r in gaps:
            mark = "now passing" if r["verdict"] == "pass" else "still failing"
            write(f"      {r['id']:<28} {mark}")

    write("")
    write("  The absolute number means little. Compare it across branches.")
    write("=" * 72)
