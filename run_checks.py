"""Run development checks from the application directory."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
failed = []
checks = ["test_inference.py", "test_registration.py", "test_reports.py",
          "test_doctor_portal.py", "test_doctor_ui.py", "test_experience.py",
          "test_disclosure.py", "test_policy_pages.py", "test_visual_languages.py",
          "test_ten_reports.py"]
for name in checks:
    result = subprocess.run([sys.executable, str(root / name)], cwd=root)
    if result.returncode:
        failed.append(name)
print("Failed: " + ", ".join(failed) if failed else "All checks passed.")
sys.exit(bool(failed))
