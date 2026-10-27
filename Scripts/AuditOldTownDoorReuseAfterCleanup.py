"""Independent full map readback after exact owned-unused package isolation."""
import sys
from pathlib import Path
import unreal
sys.path.insert(0,str(Path(unreal.Paths.project_dir()).resolve()/'Scripts'))
from ApplyOldTownDoorReuse import audit
audit(after_cleanup=True)
