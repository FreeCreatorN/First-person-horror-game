"""Final window depth separation after V2 edge and toolbox refinement."""
import sys,traceback
from pathlib import Path
import unreal
sys.path.insert(0,str(Path(unreal.Paths.project_dir()).resolve()/'Scripts'))
import RefineOldTownSurfaceRepair as refinement
refinement.MARKER='RefinedDepth.json'
refinement.BACKUP='BeforeDepthRefinement'
refinement.REFINE_TOOLBOX=False
try:refinement.main()
except Exception:
    refinement.write('DepthRefinementFailure.json',dict(passed=False,traceback=traceback.format_exc()));raise
