"""Read-only, mesh-only acceptance of the third old-town realism stage.

The baseline is derived from the published second-stage pointer. The caller
exports 20 original mesh records before replacing anything, then performs a
fresh native export after save. No UE process, package or evidence is written.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from itertools import product
from pathlib import Path
import argparse
import hashlib
import json
import math
import struct

from AuditOldTownRealismAppearance import collision_signature
from FinalizeOldTownRealism import native_closed_solid, native_frame_proof, native_physical_uv
from ValidateOldTownRealismSourceSolids import fbx_mesh, geometry_audit

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/"Saved/CodexOutputs/OldTownRealismRefinement_20261013"
WORK = ROOT/"Saved/CodexOutputs/OldTownSoftGoodsRefinement_20261013"
CANON = ROOT/"Saved/CodexOutputs/EnterableStreet_20261002"
MAP = ROOT/"Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap"
ART = ROOT/"SourceArt/OldTownRealismRefinement_20261013/SoftGoods"
ASSET_ROOT = "/Game/CodexGenerated/OldTown/SoftGoodsRefinement_20261013/"
GENERATED = ROOT/"Content/CodexGenerated/OldTown/SoftGoodsRefinement_20261013"
BASE_SCHEMA = "OldTownSoftGoodsBaselineV1"
AFTER_SCHEMA = "OldTownSoftGoodsAfterV1"
POSITION_BUDGET_CM = 2.e-5
ENVELOPE_BUDGET_CM = .0002
WORLD_BUDGET_CM = .000002
FRAME_BUDGET = 1.e-5
# FPackedRGBA16N uses signed16/32767 in UE5.7 PackedNormal.h. Actual native
# reprobe of all14 rigid variants measured at most one packing step on N/T,
# while raw source N/UV/T/B stay exactly original. UV/handedness gates stay.
PACKED_FRAME_STEP = 1./32767.
PACKED_FRAME_BUDGET = PACKED_FRAME_STEP + 2.**-23
MAIN = ROOT/"Content/Yastar/Maps/L_Main.umap"
PARALLEL_MAIN_AUTHORIZATION = "2026-10-14 user explicitly allowed independent Main editing"


def require(value, message):
    if not value:
        raise RuntimeError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024*1024):
            digest.update(chunk)
    return digest.hexdigest()


def reference(path):
    path = Path(path).resolve()
    return dict(file=str(path),sha256=sha(path))


def bound(row):
    require(Path(row["file"]).is_absolute() and sha(row["file"]) == row["sha256"], "Referenced file SHA differs: "+row["file"])
    return read(row["file"])


def hashes(values, label):
    require(isinstance(values,dict) and values, label+" is empty.")
    for file,digest in values.items():
        require(Path(file).is_absolute() and Path(file).is_file() and sha(file) == digest, label+" changed: "+file)


def index(actors, native=False):
    out = {}
    for actor,state in actors.items():
        for c in state if native else state["components"]:
            ident = actor+"::"+c["name"]
            require(ident not in out, "Duplicate component identity: "+ident)
            out[ident] = c
    return out


def near(first, second, tolerance):
    if isinstance(first,(list,tuple)):
        return isinstance(second,(list,tuple)) and len(first) == len(second) and all(near(a,b,tolerance) for a,b in zip(first,second))
    return isinstance(first,(int,float)) and isinstance(second,(int,float)) and math.isfinite(first) and math.isfinite(second) and abs(first-second) <= tolerance


def source_protection():
    """Retain Stage2's explicitly accepted user input, including its pickup BP."""
    source = read(SOURCE/"Baseline.json")
    protected = dict(source["protected_file_sha256"])
    pickup = source.get("preexisting_actor_reload_change")
    if pickup:
        row = pickup["source_blueprint"]
        protected[row["file"]] = row["sha256"]
    protected={file:digest for file,digest in protected.items() if Path(file).resolve()!=MAIN.resolve()}
    return protected


def create_baseline(map_copy, pointer_copy, source_mesh_records_file):
    """Return baseline data only once Stage2 has actually been published."""
    pointer = read(CANON/"CurrentEvidence.json")
    require(pointer["source_bundle_name"] == SOURCE.name and Path(pointer["source_directory"]).resolve() == SOURCE.resolve(),
            "Stage2 is not the currently published source.")
    require(sha(MAP) == sha(map_copy) == pointer["map_sha256"] and sha(pointer_copy) == sha(CANON/"CurrentEvidence.json"),
            "Frozen map/pointer differs from the published Stage2 input.")
    for path in (map_copy,pointer_copy,source_mesh_records_file):
        require(Path(path).resolve().is_relative_to((WORK/"Before").resolve()), "Frozen input escaped the Stage3 Before directory.")
    reports = {str((SOURCE/n).resolve()):h for n,h in pointer["current_report_sha256"].items()}
    previous = pointer["current_asset_sha256"]
    require(len(previous) == 1166, "The published source does not contain all1166 packages.")
    hashes(previous,"Previous1166 packages");hashes(reports,"Published Stage2 reports")
    return dict(schema=BASE_SCHEMA,source_map_sha256=pointer["map_sha256"],
        source_current_evidence=reference(pointer_copy),source_map_copy=reference(map_copy),
        source_final_review=dict(file=pointer["current_final_review"],sha256=pointer["current_final_review_sha256"]),
        source_snapshot=dict(actors=reference(SOURCE/"AfterSnapshot.json"),native=reference(SOURCE/"AppearanceSnapshot.json"),
                             lights=reference(SOURCE/"LightAudit.json")),
        source_mesh_records=reference(source_mesh_records_file),source_report_sha256=reports,
        previous_asset_sha256=previous,protected_file_sha256=source_protection(),actors=8014,scene_components=13920,
        parallel_main_edit=dict(file=str(MAIN.resolve()),source_sha256=read(pointer["current_final_review"])["current_user_main_sha256"],
            authorization=PARALLEL_MAIN_AUTHORIZATION,assistant_map_write_allowed=False))


def verify_baseline(baseline):
    require(baseline["schema"] == BASE_SCHEMA, "Wrong softgoods baseline schema.")
    pointer = bound(baseline["source_current_evidence"])
    digest = pointer["map_sha256"]
    require(pointer["source_bundle_name"] == SOURCE.name and Path(pointer["source_directory"]).resolve() == SOURCE.resolve()
            and baseline["source_map_sha256"] == digest == baseline["source_map_copy"]["sha256"],
            "Baseline is not the published Stage2 source.")
    for ref in (baseline["source_current_evidence"],baseline["source_map_copy"],baseline["source_mesh_records"]):
        require(Path(ref["file"]).resolve().is_relative_to((WORK/"Before").resolve()) and sha(ref["file"]) == ref["sha256"],
                "Frozen Stage3 input differs or escaped Before.")
    require(baseline["source_final_review"] == dict(file=pointer["current_final_review"],sha256=pointer["current_final_review_sha256"]),
            "Source review reference differs from the published pointer.")
    review = bound(baseline["source_final_review"])
    require(review["passed"] is True and review["published"] is True and review["map_sha256"] == digest,
            "Source Stage2 review is unpublished or failed.")
    require(baseline.get("parallel_main_edit")==dict(file=str(MAIN.resolve()),source_sha256=review["current_user_main_sha256"],
            authorization=PARALLEL_MAIN_AUTHORIZATION,assistant_map_write_allowed=False),
            "Parallel Main editing authorization differs; only this map may vary as user-owned input.")
    require(baseline["previous_asset_sha256"] == pointer["current_asset_sha256"] == review["current_asset_sha256"]
            and len(baseline["previous_asset_sha256"]) == 1166, "The original1166 package coverage differs.")
    require(baseline["source_report_sha256"] == {str((SOURCE/n).resolve()):h for n,h in pointer["current_report_sha256"].items()}
            and baseline["protected_file_sha256"] == source_protection(), "Source report/protected-file set differs.")
    for field in ("previous_asset_sha256","source_report_sha256","protected_file_sha256"):
        hashes(baseline[field],field)
    documents = {}
    for key,name in (("actors","AfterSnapshot.json"),("native","AppearanceSnapshot.json"),("lights","LightAudit.json")):
        ref = baseline["source_snapshot"][key]
        require(Path(ref["file"]).resolve() == (SOURCE/name).resolve(), "Wrong source snapshot: "+key)
        documents[key] = bound(ref)
    require(documents["actors"]["actors"] == documents["native"]["actors"] and len(documents["actors"]["actors"]) == baseline["actors"] == 8014
            and documents["native"]["map_sha256"] == digest
            and len(index(documents["native"]["component_records"],True)) == baseline["scene_components"] == 13920,
            "Source Actor/native coverage differs.")
    records = bound(baseline["source_mesh_records"])
    require(records["passed"] is True and records["source"] == "fresh_persisted_native_read_only"
            and records["map_sha256"] == digest and len(records["mesh_records"]) == 20
            and records["exact_scene_input_matches"] is True and records["all_light_properties_preserved"] is True
            and records["persisted_map_unchanged"] is True,
            "20 original native mesh records are missing or not read from Stage2.")
    packages = {**baseline["previous_asset_sha256"],**baseline["protected_file_sha256"]}
    for asset,record in records["mesh_records"].items():
        require(asset == record["asset"] and packages[record["file"]] == record["sha256"] == sha(record["file"])
                and sha(record["geometry_file"]) == record["geometry_sha256"], "Original native model readback differs: "+asset)
    return documents,records["mesh_records"]


def binary_face_proof(geometry, recipe, fbx_file):
    """Coordinate, winding and material-slot bijection; supports legacy aliases."""
    binary = fbx_mesh(fbx_file)
    require(binary["triangles"] == recipe["triangles"] and binary["material_indices"] == recipe["material_indices"],
            "Binary FBX topology/material indices differ from the recipe.")
    points = [tuple(v*100 for v in p) for p in binary["vertices"]]
    require(len(points) == len(recipe["vertices_cm"]) and all(near(p,q,POSITION_BUDGET_CM) for p,q in zip(points,recipe["vertices_cm"])),
            "Binary FBX coordinates differ from the source recipe.")
    f32 = lambda v:struct.unpack('<f',struct.pack('<f',v))[0]
    keys = {tuple(f32(v) for v in p) for p in points}
    cell = lambda p:tuple(math.floor(v/POSITION_BUDGET_CM) for v in p)
    buckets = defaultdict(list)
    for p in keys:buckets[cell(p)].append(p)
    actual = {tuple(p) for s in geometry["sections"] for p in s["vertices_cm"]}
    mapping, maximum = {},0.
    for p in actual:
        at = cell(p);candidates = []
        for delta in product((-1,0,1),repeat=3):
            for q in buckets.get(tuple(at[i]+delta[i] for i in range(3)),()):
                error=max(abs(p[i]-q[i]) for i in range(3))
                if error<=POSITION_BUDGET_CM:candidates.append((sum((p[i]-q[i])**2 for i in range(3)),error,q))
        candidates.sort()
        require(candidates and (len(candidates)==1 or candidates[0][0]<candidates[1][0]), "Actual vertex has no unique source coordinate.")
        mapping[p]=candidates[0][2];maximum=max(maximum,candidates[0][1])
    require(len(mapping)==len(keys)==len(set(mapping.values())), "Native/source coordinate mapping is not bijective.")
    cyclic=lambda t:min(t,t[1:]+t[:1],t[2:]+t[:2])
    source_faces=Counter((cyclic(tuple(tuple(f32(v) for v in points[i]) for i in (t[0],t[2],t[1]))),material)
        for t,material in zip(binary["triangles"],binary["material_indices"]))
    native_faces=Counter()
    for s in geometry["sections"]:
        ids=s["triangle_indices"]
        for start in range(0,len(ids),3):
            native_faces[(cyclic(tuple(mapping[tuple(s['vertices_cm'][i])] for i in ids[start:start+3])),s['material_slot_index'])]+=1
    require(source_faces==native_faces,"Actual Native/source oriented faces or slot partitions differ.")
    return dict(passed=True,triangles=sum(native_faces.values()),missing_or_unprescribed_faces=0,
        maximum_coordinate_error_cm=maximum,coordinate_tolerance_cm=POSITION_BUDGET_CM)


def source_variant_proof(variant):
    """Recompute serialized recipe, binary FBX and local-cm float32 validity."""
    recipe_file=Path(variant["geometry_recipe_file"]);fbx=Path(variant["fbx_file"])
    if not fbx.is_absolute():fbx=ART/fbx
    require(sha(recipe_file)==variant["geometry_recipe_sha256"] and sha(fbx)==variant["fbx_sha256"],
            "Source variant recipe/FBX SHA differs: "+variant["key"])
    recipe=read(recipe_file);binary=fbx_mesh(fbx)
    require(binary["triangles"]==recipe["triangles"] and binary["material_indices"]==recipe["material_indices"]
            and binary["material_roles"]==recipe["material_roles"]==variant["material_roles"],
            "Source binary topology/slot order differs: "+variant["key"])
    vertices=[tuple(v*100 for v in p) for p in binary["vertices"]]
    require(len(vertices)==len(recipe["vertices_cm"]) and all(near(p,q,POSITION_BUDGET_CM) for p,q in zip(vertices,recipe["vertices_cm"])),
            "Source binary vertex coordinates differ: "+variant["key"])
    for source_key,recipe_key in (("normals","triangle_corner_normals"),("uv","triangle_corner_uv0"),
                                  ("tangents","triangle_corner_tangents"),("bitangents","triangle_corner_bitangents")):
        require(near(binary[source_key],recipe[recipe_key],2.e-5),"Source binary/recipe corner buffer differs: "+source_key)
    scale=recipe["physical_scale"]
    require(len(scale)==3 and all(math.isfinite(v) and v>0 for v in scale),"Invalid source physical scale.")
    recipe_proof=geometry_audit(recipe["vertices_cm"],recipe["triangles"],recipe["triangle_corner_normals"],
        recipe["triangle_corner_uv0"],recipe["triangle_corner_tangents"],recipe["triangle_corner_bitangents"],scale)
    fbx_proof=geometry_audit(vertices,binary["triangles"],binary["normals"],binary["uv"],binary["tangents"],binary["bitangents"],scale)
    f32=lambda v:struct.unpack('<f',struct.pack('<f',v))[0]
    float32_proof=geometry_audit([tuple(f32(v) for v in p) for p in vertices],binary["triangles"],binary["normals"],
        binary["uv"],binary["tangents"],binary["bitangents"],scale)
    require(recipe_proof["passed"] and fbx_proof["passed"] and float32_proof["passed"],
            "Actual serialized source is not a closed valid mesh: "+variant["key"]+" / "+json.dumps({
                "recipe":recipe_proof["issue_counts"],"fbx":fbx_proof["issue_counts"],"float32":float32_proof["issue_counts"]}))
    require(sha(variant["source_recipe_file"])==variant["source_recipe_sha256"],"Original source recipe changed.")
    structural={}
    if not variant.get("source_recipe_is_native_sections"):
        old=read(variant["source_recipe_file"])
        require(old["material_roles"]==recipe["material_roles"],"Original material role order changed.")
        def face_map(data):
            result={}
            for i,(triangle,material) in enumerate(zip(data["triangles"],data["material_indices"])):
                if data["material_roles"][material] in ("Linen","LinenSeam"):continue
                positions=tuple(tuple(f32(v) for v in data["vertices_cm"][j]) for j in triangle)
                rotation=min(range(3),key=lambda k:positions[k:]+positions[:k])
                key=(material,positions[rotation:]+positions[:rotation])
                require(key not in result,"Repeated structural oriented source face.")
                result[key]={field:data[field][i][rotation:]+data[field][i][:rotation] for field in
                    ("triangle_corner_normals","triangle_corner_uv0","triangle_corner_tangents","triangle_corner_bitangents")}
            return result
        before,now=face_map(old),face_map(recipe)
        require(set(before)==set(now),"Original wood/metal structural faces or orientation changed.")
        for key,corners in before.items():
            require(all(near(values,now[key][field],1.e-5) for field,values in corners.items()),
                    "Original wood/metal corner UV/normal/tangent changed.")
        structural=dict(passed=True,faces=len(before),corners=len(before)*3,coordinate_matching="Exact local-cm float32 oriented face",
                        uv_and_frame_tolerance=1.e-5)
    return dict(passed=True,key=variant["key"],recipe=recipe_proof,binary_fbx=fbx_proof,float32_local_cm=float32_proof,
                original_structural_geometry_and_corner_buffers=structural)


def expected_selection():
    old=read(ROOT/"SourceArt/OldTownRealism_20261012/Furniture/ModelDataManifest.json")
    selected={v["key"]:"/Game/CodexGenerated/OldTown/Realism_20261012/Meshes/Furniture/"+v["mesh_name"]+"."+v["mesh_name"]
              for v in old["variants"] if v["kind"] in ("BedMattress","BedPillow","SeatBase","SeatBack")}
    require(len(selected)==18,"Original hotel softgoods selection differs.")
    folder=ROOT/"Saved/CodexOutputs/OldTownRealism_20261012/AppearanceNative/NativeMeshes"
    selected["LegacyBedMattress"]=read(folder/"SM_OTS_Blender_BedMattress_003acd56d2.json")["asset"]
    selected["LegacyBedPillow"]=read(folder/"SM_OTS_Blender_BedPillow_19772eb597.json")["asset"]
    return selected


def structural_native_proof(before, after, roles):
    """Preserve actual old hard faces and corner buffers, not recipe claims."""
    rigid={i for i,role in enumerate(roles) if role not in ("Linen","LinenSeam")}
    def collect(data):
        faces=[]
        for section in data["sections"]:
            material=section["material_slot_index"]
            if material not in rigid:continue
            ids=section["triangle_indices"]
            for start in range(0,len(ids),3):
                corners=[]
                for i in ids[start:start+3]:
                    corners.append(dict(position=tuple(section["vertices_cm"][i]),normal=section["normals"][i],
                        uv=section["uv0"][i],tangent=section["tangents"][i]["tangent_x"],
                        flip=section["tangents"][i]["flip_tangent_y"]))
                faces.append((material,corners))
        return faces
    old,new=collect(before),collect(after)
    require(len(old)==len(new),"Actual original structural triangle count changed.")
    original_points={corner["position"] for _,corners in old for corner in corners}
    buckets=defaultdict(list)
    cell=lambda p:tuple(math.floor(v/POSITION_BUDGET_CM) for v in p)
    for p in original_points:buckets[cell(p)].append(p)
    mapping={};maximum_position=0.
    for p in {corner["position"] for _,corners in new for corner in corners}:
        at=cell(p);candidates=[]
        for delta in product((-1,0,1),repeat=3):
            for q in buckets.get(tuple(at[i]+delta[i] for i in range(3)),()):
                error=max(abs(p[i]-q[i]) for i in range(3))
                if error<=POSITION_BUDGET_CM:candidates.append((sum((p[i]-q[i])**2 for i in range(3)),error,q))
        candidates.sort()
        require(candidates and (len(candidates)==1 or candidates[0][0]<candidates[1][0]),"Structural Native vertex lacks a unique original position.")
        mapping[p]=candidates[0][2];maximum_position=max(maximum_position,candidates[0][1])
    require(len(mapping)==len(original_points)==len(set(mapping.values())),"Structural Native vertex mapping is not bijective.")
    def canonical(material,corners,mapped=False):
        positions=tuple(mapping[c["position"]] if mapped else c["position"] for c in corners)
        rotation=min(range(3),key=lambda k:positions[k:]+positions[:k])
        return (material,positions[rotation:]+positions[:rotation]),corners[rotation:]+corners[:rotation]
    old_faces=defaultdict(list)
    for material,corners in old:
        key,ordered=canonical(material,corners);old_faces[key].append(ordered)
    maximum={"normal":0.,"uv":0.,"tangent":0.}
    for material,corners in new:
        key,ordered=canonical(material,corners,True)
        candidates=old_faces.get(key,[])
        found=None
        for i,original in enumerate(candidates):
            if all(c["flip"]==o["flip"] and near(c['uv'],o['uv'],FRAME_BUDGET)
                   and all(all(abs(a-b)<=PACKED_FRAME_BUDGET and abs(round(a*32767)-round(b*32767))<=1
                       and abs(a*32767-round(a*32767))<=.005 and abs(b*32767-round(b*32767))<=.005
                       for a,b in zip(c[field],o[field])) for field in ('normal','tangent'))
                   for c,o in zip(ordered,original)):
                found=i;break
        if found is None:
            details=dict(slot=material,original_oriented_face_found=bool(candidates))
            if candidates:
                first=candidates[0]
                details["maximum_corner_component_errors"]={field:max(abs(a-b) for c,o in zip(ordered,first)
                    for a,b in zip(c[field],o[field])) for field in maximum}
                details["handedness_changed"]=any(c["flip"]!=o["flip"] for c,o in zip(ordered,first))
            raise RuntimeError("Actual structural face orientation/material or corner normal/tangent/UV changed: "+json.dumps(details))
        original=candidates.pop(found)
        for c,o in zip(ordered,original):
            for field in maximum:maximum[field]=max(maximum[field],max(abs(a-b) for a,b in zip(c[field],o[field])))
    require(not any(old_faces.values()),"Actual original structural faces were removed.")
    return dict(passed=True,actual_native_structural_triangles=len(old),actual_native_structural_corners=len(old)*3,
        original_oriented_faces_and_slot_partitions_preserved=True,maximum_position_error_cm=maximum_position,
        maximum_corner_component_errors=maximum,position_tolerance_cm=POSITION_BUDGET_CM,uv_tolerance=FRAME_BUDGET,
        native_normal_tangent_maximum_signed16_steps=1,native_normal_tangent_value_budget=PACKED_FRAME_BUDGET,
        source_rigid_corner_buffers_remain_independently_bound_to_original=True,
        packing_definition='UE5.7 RenderCore/Public/PackedNormal.h FPackedRGBA16N: signed16/32767',
        measured_reimport_diagnostic=str(WORK/'NativeTangentPackingDiagnostic.json'))


def world_bounds(geometry, pose):
    x,y,z,w=pose["rotation_quaternion_xyzw"]
    require(abs(x*x+y*y+z*z+w*w-1)<1.e-6,"Invalid component rotation quaternion.")
    scale,translation=pose["scale"],pose["translation"]
    points=[]
    for section in geometry["sections"]:
        for source in section["vertices_cm"]:
            a,b,c=[source[i]*scale[i] for i in range(3)]
            tx,ty,tz=2*(y*c-z*b),2*(z*a-x*c),2*(x*b-y*a)
            points.append([a+w*tx+y*tz-z*ty+translation[0],b+w*ty+z*tx-x*tz+translation[1],c+w*tz+x*ty-y*tx+translation[2]])
    return [[min(p[i] for p in points) for i in range(3)],[max(p[i] for p in points) for i in range(3)]]


def verify_stage(baseline, manifest_reference, after):
    source,original_meshes=verify_baseline(baseline)
    manifest=bound(manifest_reference)
    digest=baseline["source_map_sha256"]
    require(Path(manifest_reference["file"]).resolve()==(ART/"ModelDataManifest.json").resolve()
            and manifest["schema"]=="OldTownRealismSoftGoodsRefinementManifestV1"
            and manifest["passed"] is True and manifest["source_map_sha256"]==digest
            and len(manifest["variants"])==20,"Softgoods manifest is incomplete or identifies another source.")
    require({v["key"]:v["source_asset"] for v in manifest["variants"]}==expected_selection(),
            "The exact18hotel and2legacy original model selection differs.")
    require(manifest["source_build_report_file"]==str(SOURCE/"BuildReport.json")
            and manifest["source_build_report_sha256"]==baseline["source_report_sha256"][str(SOURCE/"BuildReport.json")]
            and manifest["source_snapshot_file"]==baseline["source_snapshot"]["actors"]["file"]
            and manifest["source_snapshot_sha256"]==baseline["source_snapshot"]["actors"]["sha256"],
            "Authored manifest does not bind the exact published Stage2 source files.")
    require(after["schema"]==AFTER_SCHEMA and after["source"]=="fresh_persisted_map_load"
            and after["source_map_sha256"]==digest and after["manifest"]==manifest_reference
            and after["persisted_map_unchanged"] is True,"Fresh Stage3/manifest binding differs.")
    require(Path(after["map_file"]).resolve()==MAP.resolve() and sha(MAP)==after["map_sha256"]!=digest,"New map was not persisted.")
    saved=bound(after["actor_snapshot"]);native=bound(after["native_snapshot"])
    require(native["source"]=="fresh_persisted_native_read_only" and native["map_sha256"]==after["map_sha256"]
            and saved.get("source_map_sha256",saved.get("map_sha256"))==after["map_sha256"],"Fresh snapshot map/source differs.")
    require(after["light_inventory"]==source["lights"]["lights"],"A light property changed outside the mesh-only stage.")
    old_actors=source["actors"]["actors"];expected=deepcopy(old_actors);states=index(expected)
    old_native=index(source["native"]["component_records"],True);now_native=index(native["component_records"],True)
    require(set(now_native)==set(old_native),"Native component identities changed.")
    changes={};models={}
    for variant in manifest["variants"]:
        asset=ASSET_ROOT+"Meshes/"+variant["mesh_name"]+"."+variant["mesh_name"]
        require(asset not in models and variant["passed"] is True,"Duplicate/incomplete softgoods variant.")
        models[asset]=variant
        for row in variant["components"]:
            actor=row.get("actor",row.get("actor_label"));component=row.get("component",row.get("component_name","StaticMeshComponent0"))
            ident=actor+"::"+component
            require(ident not in changes and ident in states and ident in old_native,"Duplicate/unknown replacement component: "+ident)
            require(row["source_actor_state"]=={k:v for k,v in old_actors[actor].items() if k!="components"}
                    and row["source_component_state"]==states[ident],"Authored component baseline differs: "+ident)
            require(states[ident].get("visible") is True and states[ident].get("hidden_in_game") is False
                    and actor!=source["actors"]["main_home"]["actor"],"Hidden collider or MainHome was targeted: "+ident)
            require(states[ident]["mesh"]==old_native[ident]["mesh"]==variant["source_asset"],"Wrong original component mesh: "+ident)
            states[ident]["mesh"]=asset;changes[ident]=asset
    expected_source_assets=set(expected_selection().values())
    inferred={i for i,c in old_native.items() if c.get("mesh") in expected_source_assets}
    require(len(models)==20 and len(changes)==222 and set(changes)==inferred
            and manifest["components"]==[r for v in manifest["variants"] for r in v["components"]]
            and sum(len(v["components"]) for v in manifest["variants"] if not v["legacy_design"])==208
            and sum(len(v["components"]) for v in manifest["variants"] if v["legacy_design"])==14
            and set(original_meshes)=={v["source_asset"] for v in models.values()},
            "The prescribed20-model/222-component mesh-only scope differs.")
    require(set(after["mesh_records"])==set(models),"Actual new mesh record coverage differs.")
    new_assets=after["new_asset_sha256"]
    require(bool(new_assets) and all(Path(p).resolve().is_relative_to(GENERATED.resolve()) for p in new_assets)
            and set(new_assets)=={str(p.resolve()) for p in GENERATED.rglob('*') if p.is_file()},"New owned package coverage differs.")
    hashes(new_assets,"New Stage3 packages")
    require(after["current_asset_sha256"]=={**baseline["previous_asset_sha256"],**new_assets},"Current asset set omitted protected Stage2 packages.")
    geometry_by_asset={};proofs={}
    for asset,variant in models.items():
        record=after["mesh_records"][asset];original=original_meshes[variant["source_asset"]]
        require(record["asset"]==asset and new_assets[record["file"]]==record["sha256"]
                and variant["source_asset_file"]==original["file"] and variant["source_asset_sha256"]==original["sha256"]
                and record["static_material_slots"]==original["static_material_slots"]
                and record["properties"]==original["properties"]
                and collision_signature(record["collision_signature"])==collision_signature(original["collision_signature"]),
                "Actual model slots/materials/BodySetup changed: "+asset)
        require(sha(record["geometry_file"])==record["geometry_sha256"]
                and near(record["bounds_cm"],variant["local_bounds_cm"],POSITION_BUDGET_CM)
                and near(record["bounds_cm"],original["bounds_cm"],ENVELOPE_BUDGET_CM),"Model geometry/envelope differs: "+asset)
        recipe_file=Path(variant["geometry_recipe_file"]);fbx=Path(variant["fbx_file"])
        if not fbx.is_absolute():fbx=ART/fbx
        require(sha(recipe_file)==variant["geometry_recipe_sha256"] and sha(fbx)==variant["fbx_sha256"],"New source recipe/FBX changed: "+asset)
        recipe=read(recipe_file);geometry=read(record["geometry_file"]);geometry_by_asset[asset]=geometry
        require(recipe["source_asset"]==variant["source_asset"] and recipe["schema"]=="OldTownRealismRefinedSoftGoodsRecipeV1"
                and recipe["physical_scale"]==variant["physical_scale"],"Recipe source/physical scale differs: "+asset)
        require(all(near([abs(v) for v in old_native[i]["world_pose"]["scale"]],recipe["physical_scale"],1.e-8)
                    for i,a in changes.items() if a==asset),"Recipe physical scale differs from actual component scale: "+asset)
        proofs[asset]=dict(source=source_variant_proof(variant),closed=native_closed_solid(geometry),frames=native_frame_proof(geometry),
            physical_uv=native_physical_uv(geometry,recipe["physical_scale"]),binary_faces=binary_face_proof(geometry,recipe,fbx),
            original_native_structural_buffers=structural_native_proof(read(original["geometry_file"]),geometry,variant["material_roles"]))
    for ident,old in old_native.items():
        now=now_native[ident]
        if ident not in changes:
            require(now==old,"Unapproved native component changed: "+ident);continue
        asset=changes[ident];replay=deepcopy(old);replay["mesh"]=asset
        bounds=world_bounds(geometry_by_asset[asset],old["world_pose"])
        offset=old["expected_surface_translation_cm_to_preserve"]
        require(offset is not None and old["uniform_slot_surface_translation"],"Nonuniform original material WPO: "+ident)
        shifted=[[p[i]+offset[i] for i in range(3)] for p in bounds]
        require(near(now["local_render_bounds_cm"],after["mesh_records"][asset]["bounds_cm"],WORLD_BUDGET_CM)
                and near(now["world_render_bounds_before_wpo_cm"],bounds,WORLD_BUDGET_CM)
                and near(now["world_render_bounds_after_surface_translation_cm"],shifted,WORLD_BUDGET_CM),
                "Actual component envelope does not match actual model+pose+original WPO: "+ident)
        for field in ("local_render_bounds_cm","world_render_bounds_before_wpo_cm","world_render_bounds_after_surface_translation_cm"):
            replay[field]=now[field]
        require(now==replay,"Material/pose/parent/body/WPO/unapproved native field changed: "+ident)
    require(saved["actors"]==native["actors"]==expected and len(expected)==8014
            and saved["main_home"]==source["actors"]["main_home"],"OnlyMesh Actor replay or MainHome differs.")
    blueprints=source["native"]["blueprints"]
    require(len(blueprints)==18,"Source opening BP coverage differs.")
    hashes({r["file"]:r["sha256"] for r in blueprints.values()},"Opening Blueprint files")
    return dict(passed=True,source_map_sha256=digest,map_sha256=after["map_sha256"],actors=8014,scene_components=13920,
        models=20,changed_components=222,previous_packages_preserved=1166,new_packages=len(new_assets),
        materials_parent_pose_body_collision_wpo_and_lights_preserved=True,opening_blueprints_preserved=18,
        parallel_main_edit=baseline["parallel_main_edit"],assistant_main_map_write_allowed=False,
        mesh_proofs=proofs,next_required="Fresh full-world internal/all-normal scan with zero skips/exposed/duplicates, then actual capture review")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline",type=Path);parser.add_argument("manifest",type=Path);parser.add_argument("after",type=Path)
    args=parser.parse_args()
    print(json.dumps(verify_stage(read(args.baseline),reference(args.manifest),read(args.after)),ensure_ascii=False))


if __name__=="__main__":
    main()
