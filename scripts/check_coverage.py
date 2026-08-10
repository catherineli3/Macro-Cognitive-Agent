"""RC-3: Run test suite with coverage and generate report."""
import subprocess
import json
import os
import sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Run pytest with coverage
result = subprocess.run(
    [
        sys.executable, "-m", "pytest",
        "tests/integration/test_beta_e2e.py",
        "tests/integration/test_e2e_mvp.py",
        "tests/integration/test_rc1_reliability.py",
        "tests/test_smoke.py",
        "tests/signal/",
        "tests/hypothesis/",
        "tests/critic/",
        "tests/memory/",
        "tests/domain/",
        "tests/executor/",
        "tests/planning/",
        "tests/schemas/",
        "tests/normalizer/",
        "tests/shared/",
        "tests/validation/",
        "tests/report/",
        "tests/analyzer/",
        "tests/api/",
        "--cov=src",
        "--cov-report=json",
        "-q",
    ],
    capture_output=True,
    text=True,
    timeout=120,
)

# Parse coverage
if os.path.exists("coverage.json"):
    with open("coverage.json") as f:
        cov = json.load(f)

    totals = cov.get("totals", {})
    pct = totals.get("percent_covered", 0)
    num_statements = totals.get("num_statements", 0)
    covered = totals.get("covered_lines", 0)

    print(f"Coverage: {pct:.1f}% ({covered}/{num_statements} lines)")

    # Find files with < 80% coverage
    low_cov = []
    for file_path, file_data in cov.get("files", {}).items():
        fpct = file_data.get("summary", {}).get("percent_covered", 100)
        if fpct < 80:
            low_cov.append((file_path, fpct))

    if low_cov:
        print(f"\nFiles below 80% coverage ({len(low_cov)}):")
        for path, p in sorted(low_cov, key=lambda x: x[1]):
            print(f"  {p:.1f}%  {path}")
    else:
        print("\nAll files >= 80% coverage!")

print(f"\n{result.stdout.strip()}")
if result.stderr.strip():
    print(result.stderr.strip()[-500:])
