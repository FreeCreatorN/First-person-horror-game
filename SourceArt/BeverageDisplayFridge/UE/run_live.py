"""Import in the current HorrorGame editor; never switch or save its level."""
from pathlib import Path
import runpy
handler=runpy.run_path(str(Path(__file__).resolve().parent/'fridge_import.py'))
handler['run'](allow_live=True)
