$ErrorActionPreference='Stop'
$v2Root='D:\UE\Project\HorrorGame'
$v2Work=Join-Path $v2Root 'Saved\CodexOutputs\OldTownVersion2_20261016'
$v2Python='C:\Users\aa131\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $v2Python -X utf8 (Join-Path $v2Root 'Scripts\PrepareOldTownVersion2Geometry.py')
if ($LASTEXITCODE -ne 0) { throw 'Current V2 geometry invariance failed.' }
$v2Geo=Join-Path $v2Work 'GeometryCurrentV2.json'
& $v2Python -X utf8 (Join-Path $v2Root 'Scripts\OldTownCoplanarScan.py') $v2Geo (Join-Path $v2Work 'CoplanarScan.json') --include-internal --recognize-cubes > (Join-Path $v2Work 'FullScan.log') 2>&1
if ($LASTEXITCODE -ne 0) { throw 'V2 full surface scan failed.' }
Write-Output 'V2_RAW_SCAN_EXIT=0'
& $v2Python -X utf8 (Join-Path $v2Root 'Scripts\ClassifyOldTownInternalSurfaceOcclusion.py') $v2Geo (Join-Path $v2Work 'CoplanarScan.json') (Join-Path $v2Work 'InternalOcclusionScan.json') > (Join-Path $v2Work 'FullScanClassifier.log') 2>&1
if ($LASTEXITCODE -ne 0) { throw 'V2 occlusion classification failed.' }
$v2Created=Get-Content -LiteralPath (Join-Path $v2Work 'Created.json') -Raw | ConvertFrom-Json
& $v2Python -X utf8 (Join-Path $v2Root 'Scripts\SummarizeOldTownSurfaceScan.py') $v2Geo (Join-Path $v2Work 'CoplanarScan.json') (Join-Path $v2Work 'InternalOcclusionScan.json') $v2Created.version2_map_file (Join-Path $v2Work 'SurfaceScanSummary.json') --export-summary (Join-Path $v2Work 'AfterSummary.json') > (Join-Path $v2Work 'FullScanSummary.log') 2>&1
if ($LASTEXITCODE -ne 0) { throw 'V2 saved-scan summary failed.' }
Write-Output 'V2_COMPLETE_SCAN_EXIT=0'
