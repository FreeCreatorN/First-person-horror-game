$ErrorActionPreference = 'Stop'
$notebookTaskRoot = 'D:\UE\Project\HorrorGame\SourceArt\Notebook\UE'
$notebookTaskProject = 'D:\UE\Project\HorrorGame'
$notebookTaskScript = Join-Path $notebookTaskRoot 'import_ue.py'
$notebookTaskReport = Join-Path $notebookTaskRoot 'ue_import_report.json'
$notebookTaskCompletion = Join-Path $notebookTaskRoot 'ue_import_completion.json'
$notebookTaskTarget = Join-Path $notebookTaskProject 'Content\Yastars\Mesh\Notebook'
$notebookTaskEditor = 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'
if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) {
    throw 'Preserve the running UE editor. This import requires the editor to be saved and closed.'
}
if ((Test-Path -LiteralPath $notebookTaskTarget) -and @(Get-ChildItem -LiteralPath $notebookTaskTarget -Recurse -File).Count) {
    throw 'Notebook target already contains files. No existing assets were overwritten.'
}
foreach ($notebookTaskRequired in @($notebookTaskScript, $notebookTaskEditor,
    (Join-Path $notebookTaskRoot '..\model_report.json'),
    (Join-Path $notebookTaskRoot '..\Exports\SK_Notebook.fbx'),
    (Join-Path $notebookTaskRoot '..\Exports\A_Notebook_FullCycle.fbx'))) {
    if (-not (Test-Path -LiteralPath $notebookTaskRequired -PathType Leaf)) { throw ('Missing required file: ' + $notebookTaskRequired) }
}
$notebookTaskProtected = @{}
$notebookTaskProtectedFiles = @(Get-ChildItem -LiteralPath (Join-Path $notebookTaskProject 'Content') -Filter '*.umap' -File -Recurse)
foreach ($notebookTaskDirectory in @('Config','Content\Yastar\UI','Content\Yastar\Items')) {
    $notebookTaskProtectedFiles += @(Get-ChildItem -LiteralPath (Join-Path $notebookTaskProject $notebookTaskDirectory) -File -Recurse)
}
foreach ($notebookTaskFile in $notebookTaskProtectedFiles) {
    $notebookTaskProtected[$notebookTaskFile.FullName] = (Get-FileHash -LiteralPath $notebookTaskFile.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
}
$notebookTaskProtected | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $notebookTaskRoot 'protected_content_sha256.json') -Encoding utf8
$notebookTaskScriptSha = (Get-FileHash -LiteralPath $notebookTaskScript -Algorithm SHA256).Hash.ToLowerInvariant()
$notebookTaskRunId = [Guid]::NewGuid().ToString()
$notebookTaskLog = Join-Path $notebookTaskRoot 'ue_import.log'
$notebookTaskPriorCache = [Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
$notebookTaskPriorRunId = [Environment]::GetEnvironmentVariable('NOTEBOOK_IMPORT_RUN_ID','Process')
$notebookTaskDDC = 'D:/UE/Project/HorrorGame/Saved/CodexDDC/EnvelopeReplacement'
$notebookTaskStarted = (Get-Date).ToUniversalTime()
$notebookTaskResult = [ordered]@{
    success = $false; run_id = $notebookTaskRunId; execution_mode = 'exclusive_editor';
    target_root = '/Game/Yastars/Mesh/Notebook'; script_sha256 = $notebookTaskScriptSha;
    started_utc = $notebookTaskStarted.ToString('o'); report = $notebookTaskReport;
    normal_zero_exit = $false; exit_code = $null; temporary_engine_world = '/Engine/Maps/Entry'
}
try {
    [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$notebookTaskDDC,'Process')
    [Environment]::SetEnvironmentVariable('NOTEBOOK_IMPORT_RUN_ID',$notebookTaskRunId,'Process')
    $notebookTaskProcess = Start-Process -FilePath $notebookTaskEditor -WindowStyle Hidden -ArgumentList @(
        '"D:\UE\Project\HorrorGame\HorrorGame.uproject"','/Engine/Maps/Entry',
        ('"-ExecutePythonScript=' + $notebookTaskScript.Replace('\','/') + '"'),
        '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities','-unattended','-RenderOffscreen',
        '-nosplash','-nop4','-NOINI','-NoAutoSave','-nocef','-NoLiveCoding',
        '"-ExecCmds=Interchange.FeatureFlags.Import.FBX 0"','-DDC=InstalledNoZenLocalFallback',
        ('-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path=' + $notebookTaskDDC + ',EnvPathOverride=UE-LocalDataCachePath)'),
        ('"-abslog=' + $notebookTaskLog + '"')) -PassThru -Wait
    $notebookTaskResult.editor_pid = $notebookTaskProcess.Id
    $notebookTaskResult.exit_code = $notebookTaskProcess.ExitCode
    $notebookTaskResult.normal_zero_exit = ($notebookTaskProcess.ExitCode -eq 0)
    if (-not $notebookTaskResult.normal_zero_exit) { throw ('UE exited with code ' + $notebookTaskProcess.ExitCode) }
    if ((Get-FileHash -LiteralPath $notebookTaskScript -Algorithm SHA256).Hash.ToLowerInvariant() -ne $notebookTaskScriptSha) { throw 'Import script changed during execution.' }
    if ((Get-Item -LiteralPath $notebookTaskReport).LastWriteTimeUtc -lt $notebookTaskStarted) { throw 'No fresh import report exists.' }
    $notebookTaskReportData = Get-Content -LiteralPath $notebookTaskReport -Raw | ConvertFrom-Json
    if (-not $notebookTaskReportData.success) { throw ('Notebook import failed: ' + $notebookTaskReportData.error) }
    if ($notebookTaskReportData.run_id -ne $notebookTaskRunId -or $notebookTaskReportData.editor_pid -ne $notebookTaskProcess.Id) { throw 'Report belongs to another UE run.' }
    if ($notebookTaskReportData.import_script_sha256 -ne $notebookTaskScriptSha) { throw 'Report script hash differs.' }
    if ($notebookTaskReportData.target_root -ne '/Game/Yastars/Mesh/Notebook' -or $notebookTaskReportData.new_package_count -lt 10) { throw 'Unexpected output target or missing packages.' }
    $notebookTaskFailures = @(Select-String -LiteralPath $notebookTaskLog -Pattern 'Failed to compile Material[^\r\n]*Notebook|Notebook[^\r\n]*Failed to compile|LogShaderCompilers: Error:')
    if ($notebookTaskFailures.Count) { throw 'Notebook material/shader compilation failed. Inspect ue_import.log.' }
    $notebookTaskResult.fresh_report_verified = $true
    $notebookTaskResult.report_sha256 = (Get-FileHash -LiteralPath $notebookTaskReport -Algorithm SHA256).Hash.ToLowerInvariant()
    $notebookTaskResult.material_compile_failure_log_count = $notebookTaskFailures.Count
    $notebookTaskResult.success = $true
} catch {
    $notebookTaskResult.error = $_.Exception.Message
    throw
} finally {
    $notebookTaskResult.completed_utc = (Get-Date).ToUniversalTime().ToString('o')
    $notebookTaskResult | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $notebookTaskCompletion -Encoding utf8
    [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$notebookTaskPriorCache,'Process')
    [Environment]::SetEnvironmentVariable('NOTEBOOK_IMPORT_RUN_ID',$notebookTaskPriorRunId,'Process')
}
Write-Output 'NOTEBOOK_IMPORT_COMPLETED_NORMAL_ZERO'
