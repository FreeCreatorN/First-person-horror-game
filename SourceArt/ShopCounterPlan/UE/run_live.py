"""Open from the HorrorGame editor's Output Log Python console."""

from pathlib import Path
import runpy


entry = Path(__file__).resolve().parent / 'import_ue.py'
handler = runpy.run_path(str(entry))
handler['run'](allow_live=True)
