$ErrorActionPreference = 'Stop'
$notebookVerifyRoot = 'D:\UE\Project\HorrorGame\SourceArt\Notebook\UE'
if (@(Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) { throw 'Wait for the import editor to exit; preserve any user editor.' }
$notebookVerifyScript = Join-Path $notebookVerifyRoot 'verify_persisted_ue.py'
$notebookVerifyReport = Join-Path $notebookVerifyRoot 'ue_reload_report.json'
$notebookVerifyCompletion = Join-Path $notebookVerifyRoot 'ue_reload_completion.json'
$notebookVerifyLog = Join-Path $notebookVerifyRoot 'ue_reload.log'
$notebookVerifySha = (Get-FileHash -LiteralPath $notebookVerifyScript -Algorithm SHA256).Hash.ToLowerInvariant()
$notebookVerifyStarted = (Get-Date).ToUniversalTime()
$notebookVerifyCache = [Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
$notebookVerifyDDC = 'D:/UE/Project/HorrorGame/Saved/CodexDDC/EnvelopeReplacement'
$notebookVerifyResult = [ordered]@{ success = $false; normal_zero_exit = $false; started_utc = $notebookVerifyStarted.ToString('o'); script_sha256 = $notebookVerifySha }
try {
    [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$notebookVerifyDDC,'Process')
    $notebookVerifyProcess = Start-Process -FilePath 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe' -WindowStyle Hidden -ArgumentList @(
        '"D:\UE\Project\HorrorGame\HorrorGame.uproject"','/Engine/Maps/Entry',
        ('"-ExecutePythonScript=' + $notebookVerifyScript.Replace('\','/') + '"'),
        '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities','-unattended','-NullRHI','-nosound',
        '-nosplash','-nop4','-NOINI','-NoAutoSave','-nocef','-NoLiveCoding','-DDC=InstalledNoZenLocalFallback',
        ('-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path=' + $notebookVerifyDDC + ',EnvPathOverride=UE-LocalDataCachePath)'),
        ('"-abslog=' + $notebookVerifyLog + '"')) -PassThru -Wait
    $notebookVerifyResult.editor_pid = $notebookVerifyProcess.Id
    $notebookVerifyResult.exit_code = $notebookVerifyProcess.ExitCode
    $notebookVerifyResult.normal_zero_exit = ($notebookVerifyProcess.ExitCode -eq 0)
    if (-not $notebookVerifyResult.normal_zero_exit) { throw ('Fresh UE exited with code ' + $notebookVerifyProcess.ExitCode) }
    if ((Get-FileHash -LiteralPath $notebookVerifyScript -Algorithm SHA256).Hash.ToLowerInvariant() -ne $notebookVerifySha) { throw 'Fresh validation script changed while running.' }
    if ((Get-Item -LiteralPath $notebookVerifyReport).LastWriteTimeUtc -lt $notebookVerifyStarted) { throw 'No fresh reload report.' }
    $notebookVerifyData = Get-Content -LiteralPath $notebookVerifyReport -Raw | ConvertFrom-Json
    if (-not $notebookVerifyData.success) { throw ('Saved Notebook verification failed: ' + $notebookVerifyData.error) }
    if ($notebookVerifyData.editor_pid -ne $notebookVerifyProcess.Id -or $notebookVerifyData.script_sha256 -ne $notebookVerifySha) { throw 'Reload report belongs to another run.' }
    $notebookVerifyResult.report_sha256 = (Get-FileHash -LiteralPath $notebookVerifyReport -Algorithm SHA256).Hash.ToLowerInvariant()
    $notebookVerifyResult.success = $true
} catch {
    $notebookVerifyResult.error = $_.Exception.Message
    throw
} finally {
    $notebookVerifyResult.completed_utc = (Get-Date).ToUniversalTime().ToString('o')
    $notebookVerifyResult | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $notebookVerifyCompletion -Encoding utf8
    [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$notebookVerifyCache,'Process')
}
Write-Output 'NOTEBOOK_PERSISTED_VERIFIED_NORMAL_ZERO'
