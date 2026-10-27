import sys
from pathlib import Path
import unreal
sys.path.insert(0,str(Path(unreal.Paths.project_dir()).resolve()/'Scripts'))
from ApplyOldTownDoorReuse import audit
audit()
