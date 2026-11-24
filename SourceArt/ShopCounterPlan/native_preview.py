"""Capture the saved MCP-authored .blend through CLI-Anything's preview workflow.

The installed harness only reconstructs primitive JSON scenes. This isolated
adapter replaces its script generator in this process, leaving the installed
package and source .blend unchanged. All geometry, materials, cameras and lights
come from the native file, whose SHA256 participates in the preview cache key.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import uuid


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("blend", type=Path)
    parser.add_argument("--blender", type=Path, default=Path(r"D:\SteamLibrary\steamapps\common\Blender\blender.exe"))
    parser.add_argument("--camera", help="Existing camera name; defaults to saved active camera")
    parser.add_argument("--frame", type=int, default=1)
    parser.add_argument("--width", type=int, default=1560)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    source = args.blend.resolve(strict=True)
    executable = args.blender.resolve(strict=True)
    source_sha = digest(source)
    os.environ["PATH"] = str(executable.parent) + os.pathsep + os.environ.get("PATH", "")
    # Keep metadata and CLI backend render scripts in the writable asset area.
    # These variables are inherited by every background Blender subprocess.
    temporary_root = (Path(__file__).resolve().parent / ".preview_tmp").resolve()
    temporary_root.mkdir(parents=True, exist_ok=True)
    assert temporary_root.parent == Path(__file__).resolve().parent
    os.environ["TEMP"] = str(temporary_root)
    os.environ["TMP"] = str(temporary_root)
    tempfile.tempdir = str(temporary_root)

    # Read actual file metadata in an isolated background process, never the live
    # Blender window. The metadata is not used to reconstruct any geometry.
    # Python's mkdtemp creates owner-only Windows ACLs which are inaccessible
    # to this managed process. Ordinary workspace directories inherit access.
    temporary = temporary_root / ("native_blend_metadata_" + uuid.uuid4().hex)
    temporary.mkdir()
    metadata_path = temporary / "native.json"
    script_path = temporary / "inspect.py"
    script = f'''import bpy, json
from pathlib import Path
bpy.ops.wm.open_mainfile(filepath={str(source)!r})
s=bpy.context.scene
assert s.camera, 'The native source needs an active preview camera.'
data={{'name':s.name,'objects':[{{'name':o.name,'type':o.type}} for o in s.objects],
      'materials':[{{'name':m.name}} for m in bpy.data.materials],
      'cameras':[{{'name':o.name,'is_active':o==s.camera}} for o in s.objects if o.type=='CAMERA'],
      'lights':[{{'name':o.name}} for o in s.objects if o.type=='LIGHT'],
      'fps':s.render.fps,'frame_start':s.frame_start,'frame_end':s.frame_end}}
Path({str(metadata_path)!r}).write_text(json.dumps(data,ensure_ascii=True),encoding='utf-8')
'''
    script_path.write_text(script, encoding="utf-8")
    result = subprocess.run([str(executable), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(script_path)],
                            capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    if result.returncode != 0 or not metadata_path.is_file():
        raise RuntimeError(f"Native source inspection failed: {result.stdout[-1600:]}\n{result.stderr[-1600:]}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    camera_name = args.camera or next(c["name"] for c in metadata["cameras"] if c["is_active"])
    assert camera_name in {c["name"] for c in metadata["cameras"]}, f"No source camera: {camera_name}"
    assert metadata["lights"], "The source needs its own preview lights; no synthetic rig will be injected."
    assert digest(source) == source_sha, "Source changed during metadata read."

    from cli_anything.blender.core import render as render_mod
    from cli_anything.blender.core.scene import create_scene
    from cli_anything.blender.blender_cli import cli
    from cli_anything.blender.utils import blender_backend

    project = create_scene(metadata["name"], resolution_x=args.width*2, resolution_y=args.height*2,
                           frame_start=metadata["frame_start"], frame_end=metadata["frame_end"], fps=metadata["fps"])
    for key in ("objects", "materials", "cameras", "lights"):
        project[key] = metadata[key]
    project["scene"]["frame_current"] = args.frame
    project["native_blend"] = {"path": str(source), "sha256": source_sha, "camera": camera_name,
                               "adapter": "source-file-loader/v1"}
    project_path = source.with_name(source.stem + f".frame{args.frame}.native-preview.blend-cli.json")
    project_path.write_text(json.dumps(project, indent=2, ensure_ascii=True), encoding="utf-8")

    def native_script(data, output_path, frame=None, animation=False):
        assert not animation, "Still preview only"
        native = data["native_blend"]
        settings = data["render"]
        engine = {"EEVEE": "BLENDER_EEVEE", "WORKBENCH": "BLENDER_WORKBENCH", "CYCLES": "CYCLES"}[settings["engine"]]
        code = f'''import bpy, hashlib
from pathlib import Path
source=Path({native['path']!r})
assert hashlib.sha256(source.read_bytes()).hexdigest()=={native['sha256']!r}, 'Native source changed.'
bpy.ops.wm.open_mainfile(filepath=str(source))
scene=bpy.context.scene
scene.camera=bpy.data.objects[{native['camera']!r}]
scene.frame_set({int(frame or 1)})
scene.render.engine={engine!r}
scene.render.resolution_x={settings['resolution_x']}
scene.render.resolution_y={settings['resolution_y']}
scene.render.resolution_percentage={settings['resolution_percentage']}
scene.render.image_settings.file_format='PNG'
scene.render.film_transparent=False
scene.render.filepath={str(Path(output_path).resolve())!r}
if scene.render.engine=='BLENDER_EEVEE':
    if hasattr(scene.eevee,'use_raytracing'):
        scene.eevee.use_raytracing=True
if scene.render.engine=='BLENDER_WORKBENCH':
    scene.display.shading.light='STUDIO'
    scene.display.shading.color_type='MATERIAL'
    scene.display.shading.show_shadows=True
    scene.display.shading.show_cavity=True
    scene.display.shading.cavity_type='BOTH'
bpy.ops.render.render(write_still=True)
assert hashlib.sha256(source.read_bytes()).hexdigest()=={native['sha256']!r}, 'Native source was modified.'
'''
        # The harness writes its temporary render script with the platform default
        # encoding. Escaping non-ASCII names keeps this portable on Windows.
        return code.encode("ascii", "backslashreplace").decode("ascii")

    render_mod.generate_bpy_script = native_script
    def workspace_render(script_content, output_path, timeout=300):
        # Use the harness's real backend with an ordinary inherited-access file,
        # rather than NamedTemporaryFile's owner-only temporary ACL.
        path = temporary_root / ("blender_render_" + uuid.uuid4().hex + ".py")
        path.write_text(script_content, encoding="utf-8")
        result = blender_backend.render_script(str(path), timeout=timeout)
        if result["returncode"] != 0:
            raise RuntimeError(f"Blender preview failed: {result['stderr'][-1600:]}")
        output = Path(output_path)
        if not output.is_file():
            raise RuntimeError(f"Missing native preview output: {output}\n{result['stdout'][-1600:]}\n{result['stderr'][-1600:]}")
        return {"output": str(output.resolve()), "format": output.suffix.lstrip("."),
                "method": "blender-headless-native-source", "blender_version": blender_backend.get_version(),
                "file_size": output.stat().st_size}
    blender_backend.render_scene_headless = workspace_render
    cli_args = ["--json", "--dry-run", "--project", str(project_path), "preview", "capture", "--recipe", "quick"]
    if args.force:
        cli_args.append("--force")
    cli.main(args=cli_args, prog_name="cli-anything-blender")


if __name__ == "__main__":
    main()
