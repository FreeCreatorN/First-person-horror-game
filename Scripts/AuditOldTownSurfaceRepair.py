"""Reload saved repairs and verify physical hotel, every approved visual edit."""
import json,sys,traceback
from pathlib import Path
import unreal
ROOT=Path(unreal.Paths.project_dir()).resolve();sys.path.insert(0,str(ROOT/'Scripts'))
import AuditOldTownHotelV4 as architecture
import InspectOldTownSurfaceInput as geometry
WORK=ROOT/'Saved/CodexOutputs/SurfaceSeparation_20261009'
architecture.WORK=WORK
try:
    architecture.main()
    geometry.STAGE='After';geometry.main()
    unreal.log('SURFACE_SAVED_AUDIT_PASS')
except Exception:
    (WORK/'SavedAuditFailure.json').write_text(traceback.format_exc(),encoding='utf-8');raise
