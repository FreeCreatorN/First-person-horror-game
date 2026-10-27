$ErrorActionPreference = 'Stop'
$photoTaskRoot = 'D:\UE\Project\HorrorGame\SourceArt\PhotoPaper'
$photoTaskScript = Join-Path $photoTaskRoot 'import_ue.py'
$photoTaskReportPath = Join-Path $photoTaskRoot 'ue_import_report.json'
$photoTaskCompletionPath = Join-Path $photoTaskRoot 'ue_import_completion.json'
$photoTaskEditorExe = 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'
$photoTaskContentRoot = 'D:\UE\Project\HorrorGame\Content\Yastars\Mesh\PhotoPaper'
if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) {
    throw 'Preserve the running UE editor. Save and close it before this exclusive import.'
}
if (-not (Test-Path -LiteralPath $photoTaskScript -PathType Leaf)) { throw 'PhotoPaper import script is missing.' }
if (-not (Test-Path -LiteralPath $photoTaskEditorExe -PathType Leaf)) { throw 'UE 5.7 editor is missing.' }
if (Test-Path -LiteralPath $photoTaskContentRoot) {
    $photoTaskExistingFiles = @(Get-ChildItem -LiteralPath $photoTaskContentRoot -Recurse -File)
    if ($photoTaskExistingFiles.Count) { throw 'PhotoPaper target already contains files. Nothing was overwritten.' }
}
$photoTaskScriptSha = (Get-FileHash -LiteralPath $photoTaskScript -Algorithm SHA256).Hash.ToLowerInvariant()
$photoTaskLog = Join-Path $photoTaskRoot 'ue_import.log'
$photoTaskCache = [Environment]::GetEnvironmentVariable('UE-LocalDataCachePath', 'Process')
$photoTaskPriorRunId = [Environment]::GetEnvironmentVariable('PHOTOPAPER_IMPORT_RUN_ID', 'Process')
$photoTaskPrivateDDC = 'D:/UE/Project/HorrorGame/Saved/CodexDDC/EnvelopeReplacement'
$photoTaskRunId = [Guid]::NewGuid().ToString()
$photoTaskStarted = (Get-Date).ToUniversalTime()
$photoTaskCompletion = [ordered]@{
    success = $false; script = 'import_ue.py'; execution_mode = 'exclusive_editor';
    run_id = $photoTaskRunId; script_sha256 = $photoTaskScriptSha;
    started_utc = $photoTaskStarted.ToString('o'); target_root = '/Game/Yastars/Mesh/PhotoPaper';
    report = $photoTaskReportPath; normal_zero_exit = $false; exit_code = $null;
    temporary_engine_world = '/Engine/Maps/Entry'; private_ddc = $photoTaskPrivateDDC
}
try {
    [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath', $photoTaskPrivateDDC, 'Process')
    [Environment]::SetEnvironmentVariable('PHOTOPAPER_IMPORT_RUN_ID', $photoTaskRunId, 'Process')
    $photoTaskProcess = Start-Process -FilePath $photoTaskEditorExe -WindowStyle Hidden -ArgumentList @(
        '"D:\UE\Project\HorrorGame\HorrorGame.uproject"', '/Engine/Maps/Entry',
        ('"-ExecutePythonScript=' + $photoTaskScript.Replace('\','/') + '"'),
        '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities', '-unattended', '-RenderOffscreen',
        '-nosplash', '-nop4', '-NOINI', '-NoAutoSave', '-nocef', '-NoLiveCoding',
        '"-ExecCmds=Interchange.FeatureFlags.Import.FBX 0"', '-DDC=InstalledNoZenLocalFallback',
        ('-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path=' + $photoTaskPrivateDDC + ',EnvPathOverride=UE-LocalDataCachePath)'),
        ('"-abslog=' + $photoTaskLog + '"')
    ) -PassThru -Wait
    $photoTaskCompletion.pid = $photoTaskProcess.Id
    $photoTaskCompletion.editor_pid = $photoTaskProcess.Id
    $photoTaskCompletion.exit_code = $photoTaskProcess.ExitCode
    $photoTaskCompletion.normal_zero_exit = ($photoTaskProcess.ExitCode -eq 0)
    if (-not $photoTaskCompletion.normal_zero_exit) { throw ('UE import exited with code ' + $photoTaskProcess.ExitCode) }
    if ((Get-FileHash -LiteralPath $photoTaskScript -Algorithm SHA256).Hash.ToLowerInvariant() -ne $photoTaskScriptSha) {
        throw 'The import script changed while UE was running.'
    }
    $photoTaskReportFile = Get-Item -LiteralPath $photoTaskReportPath
    if ($photoTaskReportFile.LastWriteTimeUtc -lt $photoTaskStarted) { throw 'No fresh import report exists.' }
    $photoTaskReport = Get-Content -LiteralPath $photoTaskReportPath -Raw | ConvertFrom-Json
    if (-not $photoTaskReport.success) { throw ('PhotoPaper import failed: ' + $photoTaskReport.error) }
    if ($photoTaskReport.run_id -ne $photoTaskRunId -or $photoTaskReport.editor_pid -ne $photoTaskProcess.Id) {
        throw 'The report belongs to another run or editor process.'
    }
    if ($photoTaskReport.import_script_sha256 -ne $photoTaskScriptSha) { throw 'The report used a different import script.' }
    $photoTaskReportStart = ([DateTimeOffset]::Parse($photoTaskReport.started_utc)).UtcDateTime
    $photoTaskReportEnd = ([DateTimeOffset]::Parse($photoTaskReport.completed_utc)).UtcDateTime
    if ($photoTaskReportStart -lt $photoTaskStarted -or $photoTaskReportEnd -lt $photoTaskReportStart -or $photoTaskReportEnd -gt (Get-Date).ToUniversalTime()) {
        throw 'The report timestamps do not belong to this run.'
    }
    if ($photoTaskReport.target_root -ne '/Game/Yastars/Mesh/PhotoPaper' -or $photoTaskReport.new_package_count -ne 6) {
        throw 'Unexpected PhotoPaper target or package count.'
    }
    $photoTaskMaterialFailures = @(Select-String -LiteralPath $photoTaskLog -Pattern 'Failed to compile Material[^\r\n]*PhotoPaper|PhotoPaper[^\r\n]*Failed to compile|LogShaderCompilers: Error:')
    if ($photoTaskMaterialFailures.Count) { throw 'UE logged a material or shader compilation failure; inspect ue_import.log.' }
    $photoTaskCompletion.report_sha256 = (Get-FileHash -LiteralPath $photoTaskReportPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $photoTaskCompletion.fresh_report_verified = $true
    $photoTaskCompletion.material_compile_failure_log_count = $photoTaskMaterialFailures.Count
    $photoTaskCompletion.success = $true
} catch {
    $photoTaskCompletion.error = $_.Exception.Message
    throw
} finally {
    $photoTaskCompletion.completed_utc = (Get-Date).ToUniversalTime().ToString('o')
    $photoTaskCompletion | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $photoTaskCompletionPath -Encoding utf8
    [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath', $photoTaskCache, 'Process')
    [Environment]::SetEnvironmentVariable('PHOTOPAPER_IMPORT_RUN_ID', $photoTaskPriorRunId, 'Process')
}
Write-Output 'PHOTOPAPER_IMPORT_COMPLETED_NORMAL_ZERO'
