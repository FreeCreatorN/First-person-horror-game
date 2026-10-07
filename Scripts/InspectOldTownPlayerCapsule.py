"""Read the on-disk project's character capsule without changing assets."""
import json
from pathlib import Path
import unreal

blueprint = unreal.load_asset("/Game/Yastar/Blueprints/BP_Character")
assert blueprint is not None
character = unreal.get_default_object(blueprint.generated_class())
capsule = character.get_component_by_class(unreal.CapsuleComponent)
movement = character.get_component_by_class(unreal.CharacterMovementComponent)
assert capsule is not None and movement is not None
report = {"blueprint": blueprint.get_path_name(),
          "radius_cm": capsule.get_unscaled_capsule_radius(),
          "half_height_cm": capsule.get_unscaled_capsule_half_height(),
          "max_step_height_cm": movement.get_editor_property("max_step_height")}
output = Path(unreal.Paths.project_dir()).resolve() / "Saved/CodexOutputs/EnterableStreet_20261002/PlayerCapsule.json"
output.write_text(json.dumps(report, indent=2), encoding="utf-8")
unreal.log("OTS_PLAYER_CAPSULE " + json.dumps(report))
