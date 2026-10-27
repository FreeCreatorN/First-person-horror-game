"""Four unsaved inspection views for the hotel-front boundary screen."""
import sys,json,os,traceback
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'Scripts'))
import CaptureOldTownIntersectionViews as view
original_lighting=view.capture._create_temporary_lighting
def lighting():
    view.capture._state['lighting_mode']=os.environ.get('OTS_REVIEW_LIGHTING','temporary')
    original_lighting()
def main():
    report=json.loads(view.capture.BUILD_REPORT.read_text(encoding='utf-8-sig'))
    view.SPECS=report['review_camera_overrides'];view.PHASE='After'
    view.capture._create_temporary_lighting=lighting
    view.main()
if __name__=='__main__':
    try:main()
    except Exception:view.capture.fail(traceback.format_exc());raise
