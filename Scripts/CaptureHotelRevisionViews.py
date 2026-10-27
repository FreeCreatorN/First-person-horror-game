"""Unsaved review cameras for current hotel revision, no user editor control."""
import sys,json,traceback
from pathlib import Path
import unreal
R=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(R/'Scripts'))
import CaptureOldTownIntersectionViews as view

def main():
    report=json.loads(view.capture.BUILD_REPORT.read_text(encoding='utf-8-sig'))
    view.SPECS=report['review_camera_overrides'];view.PHASE='After';view.main()
if __name__=='__main__':
    try:main()
    except Exception:view.capture.fail(traceback.format_exc());raise
