"""Explicit current-editor entry; does not change or save its loaded world."""
from pathlib import Path
import runpy
handler=runpy.run_path(str(Path(__file__).resolve().parent/'import_ue.py'))
handler['run'](allow_live=True)
