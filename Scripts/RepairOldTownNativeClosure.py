"""Recover the exact 22 diagnosed FBX face losses; never save/edit the map.

Run in an isolated editor helper after reviewing this script. New FBX caches
use a separate namespace. Existing PBR masters/textures are only loaded.
"""
from __future__ import annotations
from collections import Counter
from copy import deepcopy
import json, math, shutil, sys, traceback
from pathlib import Path
import unreal

ROOT = Path(unreal.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts'))
import OldTownRealismMaterials as pbr
import OldTownRealismImport as importer
import InspectOldTownRealismInput as native
from AuditOldTownRealismAppearance import collision_signature, finite_vector
from FinalizeOldTownRealism import native_closed_solid, native_physical_uv

WORK = ROOT / 'Saved/CodexOutputs/OldTownRealism_20261012'
BEFORE = WORK / 'BeforeNativeClosure'
MAP = ROOT / 'Content/Yastar/Maps/Scenes/L_OldTownSchoolStreet.umap'
EXPECTED_MAP_SHA = '82b8b44a08c223ca654807f85b633e0cf7e912372f82e84a3cdd8d816e873f5e'
SOURCE = ROOT / 'SourceArt/OldTownRealism_20261012'
CATEGORIES = ('Furniture', 'Architecture', 'Sanitary', 'Street')
FROZEN_REPORTS = ('RealismApply.json', 'Applied.json', 'ExpectedSnapshot.json',
    'ArchitecturePlan.json', 'FollowupSurfaceRepairs.json', 'AdditionalSurfaceRepairs.json',
    'MaterialRoleRepairs.json', 'RealismInput.json', 'RealismStreetInput.json',
    'SourceSolidsRepair.json', 'SourceSolidsIndependentAudit.json')
BACKUP_REPORTS = ('BuildReport.json', 'MaterialBuild.json', 'AppearanceAudit.json',
    'NativeClosedSolidDiagnostic.json', 'NativeSourceFaceLossDiagnosis.json') + FROZEN_REPORTS + tuple(
    c + 'AssetBuild.json' for c in CATEGORIES)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def normalized(hashes):
    return {str(Path(p).resolve()): h for p, h in hashes.items()}


def exact_edge_proof(geometry):
    edges = Counter()
    for section in geometry['sections']:
        vertices, indices = section['vertices_cm'], section['triangle_indices']
        for start in range(0, len(indices), 3):
            keys = [tuple(float(v) for v in vertices[i]) for i in indices[start:start + 3]]
            assert len(set(keys)) == 3
            for a, b in ((0, 1), (1, 2), (2, 0)):
                edges[tuple(sorted((keys[a], keys[b])))] += 1
    return dict(exact_odd_edges=sum(v % 2 for v in edges.values()), exact_edge_count=len(edges))


def normal_facing_sign(geometry):
    for section in geometry['sections']:
        points, ids, normals = section['vertices_cm'], section['triangle_indices'][:3], section['normals']
        if not ids: continue
        a, b, c = [points[i] for i in ids]
        ab, ac = [b[k]-a[k] for k in range(3)], [c[k]-a[k] for k in range(3)]
        cross = [ab[1]*ac[2]-ab[2]*ac[1], ab[2]*ac[0]-ab[0]*ac[2], ab[0]*ac[1]-ab[1]*ac[0]]
        dot = sum(cross[k]*normals[ids[0]][k] for k in range(3))
        assert math.isfinite(dot) and dot != 0
        return 1 if dot > 0 else -1
    raise AssertionError('No native face establishes its saved winding/normal convention.')


def frame_proof(geometry, expected_normal_sign):
    assert expected_normal_sign in (-1, 1)
    triangles = negative = invalid = uv_zero = 0
    for section in geometry['sections']:
        points, indices, normals, tangents, uv = (section[k] for k in
            ('vertices_cm', 'triangle_indices', 'normals', 'tangents', 'uv0'))
        assert len(points) == len(normals) == len(tangents) == len(uv)
        invalid += sum(not finite_vector(n, True) for n in normals)
        invalid += sum(not finite_vector(t['tangent_x'], True) for t in tangents)
        for start in range(0, len(indices), 3):
            ids = indices[start:start + 3]
            a, b, c = [points[i] for i in ids]
            ab, ac = [b[k] - a[k] for k in range(3)], [c[k] - a[k] for k in range(3)]
            cross = [ab[1]*ac[2]-ab[2]*ac[1], ab[2]*ac[0]-ab[0]*ac[2], ab[0]*ac[1]-ab[1]*ac[0]]
            for i in ids:
                negative += expected_normal_sign*sum(cross[k]*normals[i][k] for k in range(3)) <= 0
            ua, ub, uc = [uv[i] for i in ids]
            area = (ub[0]-ua[0])*(uc[1]-ua[1])-(ub[1]-ua[1])*(uc[0]-ua[0])
            uv_zero += not math.isfinite(area) or abs(area) < 1.e-12
            triangles += 1
    assert invalid == negative == uv_zero == 0, (invalid, negative, uv_zero)
    return dict(passed=True, triangles=triangles, nonfinite_or_zero_frames=invalid,
                nonpositive_corner_normals=negative, degenerate_uv0_triangles=uv_zero,
                expected_corner_normal_sign=expected_normal_sign, original_native_normal_orientation_preserved=True)


def native_record(mesh, directory):
    native.WORK = directory
    native.MESH_CACHE.clear()
    record = native.mesh_record(mesh)
    record = {k: v for k, v in record.items() if not k.startswith('_')}
    geometry = read(record['geometry_file'])
    return record, geometry


def main():
    assert not (WORK/'ModelClosureImportRepairs.json').exists(), 'Do not reapply a successful stage.'
    assert not BEFORE.exists(), 'A previous attempt exists; preserve it before starting a new attempt.'
    build = read(WORK/'BuildReport.json')
    map_sha = pbr.sha(MAP)
    assert map_sha == build['map_sha256'] == EXPECTED_MAP_SHA
    old_assets = normalized(build['new_asset_sha256'])
    assert len(old_assets) == 905 and all(pbr.sha(p) == h for p, h in old_assets.items())
    diagnostic_path = WORK/'NativeClosedSolidDiagnostic.json'
    diagnostic = read(diagnostic_path)
    assert diagnostic['map_sha256'] == map_sha and diagnostic['count'] == 143
    diagnosed = {r['asset']: r for r in diagnostic['rows'] if r['exact_odd_edges']}
    assert len(diagnosed) == diagnostic['failed_count'] == 22
    assert all(r['exact_odd_edges'] == r['rounded_odd_edges'] > 0 and
               r['rounded_collapsed_faces'] == 0 for r in diagnosed.values())
    independent = read(WORK/'SourceSolidsIndependentAudit.json')
    assert independent['passed'] and independent['audited_variant_count'] == 143
    face_loss_path = WORK/'NativeSourceFaceLossDiagnosis.json'
    face_loss = read(face_loss_path)
    assert face_loss['passed'] and face_loss['map_sha256'] == map_sha
    assert face_loss['source_model_count'] == 22 and face_loss['total_missing_source_faces'] == 880
    assert all(pbr.sha(p) == h for p, h in face_loss['input_sha256'].items())
    assets_by_category = {c: read(WORK/(c+'AssetBuild.json')) for c in CATEGORIES}
    variants = {}
    source_hashes = {}
    for category in CATEGORIES:
        base = SOURCE/category
        manifest = base/'ModelDataManifest.json'
        source_hashes[str(manifest.resolve())] = pbr.sha(manifest)
        for entry in read(manifest)['variants']:
            path = pbr.ASSET+'/Meshes/'+category+'/'+entry['mesh_name']
            asset = path+'.'+entry['mesh_name']
            if asset not in diagnosed:
                continue
            fbx = Path(entry.get('fbx_file', entry.get('file', '')))
            if not fbx.is_absolute(): fbx = base/fbx
            recipe_path = Path(entry['geometry_recipe_file'])
            if not recipe_path.is_absolute(): recipe_path = base/recipe_path
            recipe = read(recipe_path)
            assert pbr.sha(fbx) == entry.get('source_file_sha256', entry.get('fbx_sha256'))
            assert pbr.sha(recipe_path) == entry['geometry_recipe_sha256']
            assert len(recipe['triangles']) == entry['triangles'] > diagnosed[asset]['triangles']
            source_hashes.update({str(fbx.resolve()): pbr.sha(fbx), str(recipe_path.resolve()): pbr.sha(recipe_path)})
            variants[asset] = (category, base, deepcopy(entry), recipe)
    assert set(variants) == set(diagnosed)
    original_inputs = read(WORK/'RealismInput.json')
    street_inputs = read(WORK/'RealismStreetInput.json')
    protected = {}
    for doc in (original_inputs, street_inputs):
        for name in ('source_asset_file_sha256', 'original_400_shared_asset_sha256', 'protected_map_sha256'):
            protected.update(normalized(doc.get(name, {})))
    assert all(pbr.sha(p) == h for p, h in protected.items())
    frozen = {str((WORK/n).resolve()): pbr.sha(WORK/n) for n in FROZEN_REPORTS}
    BEFORE.mkdir()
    shutil.copy2(MAP, BEFORE/MAP.name)
    for name in BACKUP_REPORTS:
        shutil.copy2(WORK/name, BEFORE/name)
    write(BEFORE/'SourceAssetSHA256.json', old_assets)
    original_native_mesh_backups = {}
    for path, digest in face_loss['input_sha256'].items():
        source_file = Path(path).resolve()
        if source_file.parent.name == 'NativeMeshes':
            destination = BEFORE/'NativeMeshes'/source_file.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, destination)
            assert pbr.sha(destination) == digest
            original_native_mesh_backups[str(source_file)] = dict(backup_file=str(destination.resolve()), sha256=digest)
    assert len(original_native_mesh_backups) == 22
    backup_files = {}
    target_files = {}
    for asset in sorted(variants):
        old_row = next(r for r in assets_by_category[variants[asset][0]]['assets'] if r['asset'] == asset)
        target_file = Path(old_row['file']).resolve()
        backup_file = BEFORE/'Packages'/target_file.relative_to(ROOT)
        backup_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target_file, backup_file)
        assert pbr.sha(backup_file) == old_assets[str(target_file)]
        backup_files[asset] = str(backup_file.resolve())
        target_files[asset] = str(target_file)
    # Seed existing masters directly. Calling initialize()/master() without
    # this cache would rebuild already accepted textures/material graphs.
    material = read(WORK/'MaterialBuild.json')
    for row in material['assets']:
        if row.get('kind') == 'master':
            obj = unreal.EditorAssetLibrary.load_asset(row['asset'])
            assert obj
            pbr._cache[(row['role'], row['projection'])] = obj
    native.MATERIAL_CACHE.clear()
    native.SOURCE_FILES.clear()
    native.LIMITATIONS.clear()
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world, 'Interchange.FeatureFlags.Import.Enable 0')
    axes = read(WORK/'AxisVerification.json')
    result_rows = []
    cache_files = set()
    for asset, (category, base, entry, recipe) in sorted(variants.items()):
        mesh = unreal.EditorAssetLibrary.load_asset(asset)
        old_record, old_geometry = native_record(mesh, BEFORE/'Native')
        assert old_record['triangle_count'] == diagnosed[asset]['triangles']
        assert old_record['geometry_sha256'] == diagnosed[asset]['geometry_sha256']
        old_edge = exact_edge_proof(old_geometry)
        assert old_edge['exact_odd_edges'] == diagnosed[asset]['exact_odd_edges']
        original_normal_sign = normal_facing_sign(old_geometry)
        assert original_normal_sign == -1, 'The diagnosed UE clockwise normal convention changed.'
        frame_proof(old_geometry, original_normal_sign)
        write(BEFORE/'Native'/('Record_'+entry['mesh_name']+'.json'), old_record)
        suffix = 'NativeClosureNoMerge_'+entry.get('source_file_sha256', entry.get('fbx_sha256'))[:12]
        cache_path = pbr.ASSET+'/Meshes/ImportData/'+entry['mesh_name']+'_Import_'+suffix
        assert not unreal.EditorAssetLibrary.does_asset_exist(cache_path), 'Fresh cache required: '+cache_path
        entry.update(native_no_degenerate_merge=True, native_source_model_read=True, native_uv_chart_separation=False,
                     native_import_cache_suffix=suffix, native_physical_scale=recipe['physical_scale'])
        out, new_row = importer.build_variant(entry, base, axes, category)
        new_record, new_geometry = native_record(out, WORK/'NativeClosureAfter')
        assert new_record['triangle_count'] == len(recipe['triangles']), (asset, new_record['triangle_count'], len(recipe['triangles']))
        closed = native_closed_solid(new_geometry)
        exact = exact_edge_proof(new_geometry)
        assert exact['exact_odd_edges'] == 0
        # Preserve source UVs on the first import. If legacy wedge merging
        # corrupts an island, apply the already verified wardrobe workaround.
        try:
            uv = native_physical_uv(new_geometry, recipe['physical_scale'])
        except RuntimeError:
            entry['native_uv_chart_separation'] = True
            out, new_row = importer.build_variant(entry, base, axes, category)
            new_record, new_geometry = native_record(out, WORK/'NativeClosureAfter')
            assert new_record['triangle_count'] == len(recipe['triangles'])
            closed = native_closed_solid(new_geometry)
            exact = exact_edge_proof(new_geometry)
            assert exact['exact_odd_edges'] == 0
            uv = native_physical_uv(new_geometry, recipe['physical_scale'])
        frames = frame_proof(new_geometry, original_normal_sign)
        assert new_record['static_material_slots'] == old_record['static_material_slots'], asset
        assert collision_signature(new_record['collision_signature']) == collision_signature(old_record['collision_signature']), asset
        maximum_bounds_change = max(abs(a-b) for aa, bb in zip(new_record['bounds_cm'], old_record['bounds_cm']) for a, b in zip(aa, bb))
        assert maximum_bounds_change < .03
        old_row = next(r for r in assets_by_category[category]['assets'] if r['asset'] == asset)
        assert new_row['material_roles'] == old_row['material_roles']
        mutable_fields = {'sha256', 'triangles', 'actual_local_bounds_cm'}
        assert set(new_row) == set(old_row) and all(new_row[k] == v for k, v in old_row.items()
                                                   if k not in mutable_fields), asset
        assets_by_category[category]['assets'] = [new_row if r['asset'] == asset else r for r in assets_by_category[category]['assets']]
        imported_cache = unreal.EditorAssetLibrary.load_asset(cache_path)
        cache_file = str(pbr.file(imported_cache).resolve())
        cache_files.add(cache_file)
        result_rows.append(dict(asset=asset, category=category, key=entry['key'],
            source_fbx_file=str(Path(new_row['fbx_source']).resolve()), source_fbx_sha256=new_row['fbx_sha256'],
            source_recipe_file=entry['geometry_recipe_file'], source_recipe_sha256=entry['geometry_recipe_sha256'],
            source_triangles=len(recipe['triangles']), before_target_file=target_files[asset],
            before_target_file_sha256=old_assets[target_files[asset]], before_target_backup_file=backup_files[asset],
            before_target_backup_sha256=pbr.sha(backup_files[asset]), new_target_file=target_files[asset],
            new_target_sha256=new_row['sha256'], old_native_triangles=old_record['triangle_count'],
            new_native_triangles=new_record['triangle_count'], recovered_triangles=new_record['triangle_count']-old_record['triangle_count'],
            before_native=old_record, after_native=new_record, old_edge_proof=old_edge,
            native_closed_solid=closed, native_exact_edge_proof=exact, physical_uv=uv, frames=frames,
            physical_scale=recipe['physical_scale'], maximum_bounds_change_cm=maximum_bounds_change,
            material_slots_preserved=True, bodysetup_signature_preserved=True,
            native_source_model_read=True, native_no_degenerate_merge=True,
            fbx_remove_degenerates=False, lod_remove_degenerates=False, copy_remove_degenerates=False,
            uv_chart_separation=entry['native_uv_chart_separation'], import_cache_asset=imported_cache.get_path_name(),
            import_cache_file=cache_file, import_cache_sha256=pbr.sha(cache_file)))
        unreal.log('NATIVE_CLOSURE_RECOVERED '+asset+' '+str(result_rows[-1]['recovered_triangles']))
    assert len(result_rows) == 22 and sum(r['recovered_triangles'] for r in result_rows) == 880
    assert not pbr.report()['assets'], 'Existing PBR masters/textures must not be rebuilt.'
    assert all(pbr.sha(p) == h for p, h in frozen.items())
    assert all(pbr.sha(p) == h for p, h in protected.items())
    assert all(pbr.sha(p) == h for p, h in source_hashes.items())
    assert pbr.sha(MAP) == map_sha
    generated = ROOT/'Content/CodexGenerated/OldTown/Realism_20261012'
    after_assets = dict(old_assets)
    after_assets.update({str(p.resolve()): pbr.sha(p) for p in generated.rglob('*.uasset')})
    changed = {p for p in old_assets if after_assets[p] != old_assets[p]}
    added = set(after_assets)-set(old_assets)
    assert changed == set(target_files.values()) and added == cache_files and len(added) == 22
    assert all(pbr.sha(p) == h for p, h in old_assets.items() if p not in changed)
    material_before_assets = deepcopy(material['assets'])
    material['final_compile_logs'].append(str(WORK/'NativeClosureImport.stdout.log'))
    assert material['assets'] == material_before_assets
    report = dict(schema='OldTownRealismModelClosureImportRepairsV1', passed=True,
        source_map_sha256=map_sha, map_sha256=map_sha, source_asset_sha256=old_assets,
        after_asset_sha256=after_assets, changed_target_count=22, added_import_cache_count=22,
        recovered_source_triangle_count=880, components_or_actors_changed=0,
        map_unchanged=True, source_materials_textures_and_collision_preserved=True,
        source_fbx_and_recipe_sha256=source_hashes, protected_source_file_sha256=protected,
        frozen_report_sha256=frozen, diagnostic_file=str(diagnostic_path.resolve()),
        diagnostic_sha256=pbr.sha(diagnostic_path), face_loss_diagnosis_file=str(face_loss_path.resolve()),
        face_loss_diagnosis_sha256=pbr.sha(face_loss_path), original_native_mesh_backups=original_native_mesh_backups,
        before_directory=str(BEFORE.resolve()), rows=result_rows)
    build['new_asset_sha256'] = after_assets
    build['model_closure_import_repairs'] = report
    for category in CATEGORIES:
        write(WORK/(category+'AssetBuild.json'), assets_by_category[category])
    write(WORK/'MaterialBuild.json', material)
    write(WORK/'ModelClosureImportRepairs.json', report)
    write(WORK/'BuildReport.json', build)
    assert pbr.sha(MAP) == map_sha
    unreal.log('NATIVE_MODEL_CLOSURE_IMPORT_REPAIR_PASS '+map_sha)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        write(WORK/'ModelClosureImportFailure.json', dict(passed=False, map_sha256=pbr.sha(MAP),
            map_unchanged=pbr.sha(MAP)==EXPECTED_MAP_SHA, traceback=traceback.format_exc()))
        raise
