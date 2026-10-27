"""Verify the current camera with its separate shutter button."""
import runpy,shutil
from pathlib import Path
root=Path(__file__).resolve().parent
try:
    runpy.run_path(str(root/'ShutterSplit'/'verify_update.py'),run_name='__main__')
finally:
    report=root/'ShutterSplit'/'final_verification.json'
    if report.is_file():shutil.copyfile(report,root/'final_verification.json')
