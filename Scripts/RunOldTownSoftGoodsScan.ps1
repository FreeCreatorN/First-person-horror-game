$ErrorActionPreference='Stop'
$scanProject='D:\UE\Project\HorrorGame'
$scanWork=Join-Path $scanProject 'Saved\CodexOutputs\OldTownSoftGoodsRefinement_20261013'
$scanPython='C:\Users\aa131\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$scanGeometry=Join-Path $scanWork 'GeometryAfter.json'
$scanRaw=Join-Path $scanWork 'CoplanarScan.json'
$scanClassified=Join-Path $scanWork 'InternalOcclusionScan.json'
& $scanPython -X utf8 (Join-Path $scanProject 'Scripts\OldTownCoplanarScan.py') $scanGeometry $scanRaw --include-internal --recognize-cubes > (Join-Path $scanWork 'FullScan.log') 2>&1
if ($LASTEXITCODE -ne 0) { throw 'Raw complete scan failed.' }
Write-Output 'RAW_SCAN_EXIT=0'
& $scanPython -X utf8 (Join-Path $scanProject 'Scripts\ClassifyOldTownInternalSurfaceOcclusion.py') $scanGeometry $scanRaw $scanClassified > (Join-Path $scanWork 'FullScanClassifier.log') 2>&1
if ($LASTEXITCODE -ne 0) { throw 'Closed-surface classifier failed.' }
Write-Output 'CLASSIFIER_EXIT=0'
& $scanPython -X utf8 (Join-Path $scanProject 'Scripts\SummarizeOldTownSurfaceScan.py') $scanGeometry $scanRaw $scanClassified (Join-Path $scanProject 'Content\Yastar\Maps\Scenes\L_OldTownSchoolStreet.umap') (Join-Path $scanWork 'SurfaceScanSummary.json') --export-summary (Join-Path $scanWork 'AfterSummary.json') > (Join-Path $scanWork 'FullScanSummary.log') 2>&1
if ($LASTEXITCODE -ne 0) { throw 'Saved scan summary failed.' }
Write-Output 'SCAN_SUMMARY_EXIT=0'
