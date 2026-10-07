param([string[]]$Cameras = @('CAM_OTS_Hero', 'CAM_OTS_MainHome', 'CAM_Enterable_ShopEntry', 'CAM_Enterable_SchoolEntry', 'CAM_Enterable_Stair', 'CAM_Enterable_Bedroom'), [switch]$ForceRecapture)
# Isolate each high-resolution screenshot in its own hidden editor process.
$ErrorActionPreference = 'Stop'
$streetProject = 'D:\UE\Project\HorrorGame'
$streetOutput = Join-Path $streetProject 'Saved\CodexOutputs\EnterableStreet_20261002'
Set-Item -LiteralPath 'Env:UE-LocalDataCachePath' -Value (Join-Path $streetProject 'Saved\CodexDDC')
$streetCameras = $Cameras
$streetResults = @()
$streetMapHash = (Get-FileHash -LiteralPath (Join-Path $streetProject 'Content\Yastar\Maps\Scenes\L_OldTownSchoolStreet.umap') -Algorithm SHA256).Hash.ToLowerInvariant()
foreach ($streetCamera in $streetCameras) {
    $streetPng = Join-Path $streetOutput ('Renders\' + $streetCamera + '.png')
    $streetMeta = Join-Path $streetOutput ('Renders\' + $streetCamera + '.json')
    if (-not $ForceRecapture -and (Test-Path -LiteralPath $streetPng) -and (Test-Path -LiteralPath $streetMeta)) {
        $streetExisting = Get-Content -LiteralPath $streetMeta -Raw | ConvertFrom-Json
        if ($streetExisting.status -eq 'PASS' -and $streetExisting.map_sha256 -eq $streetMapHash -and (Get-Item -LiteralPath $streetPng).Length -gt 20000) {
            $streetResults += [pscustomobject]@{camera=$streetCamera; captured=$true; exit_code=$null; reused=$true; path=$streetPng}
            $streetResults | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $streetOutput 'CaptureRuns.json') -Encoding utf8
            Write-Output ($streetCamera + ': verified existing capture')
            continue
        }
    }
    Set-Item -LiteralPath 'Env:OTS_CAPTURE_CAMERA' -Value $streetCamera
    $streetStart = Get-Date
    $streetLog = Join-Path $streetOutput ('Capture_' + $streetCamera + '.log')
    $streetProcess = Start-Process -FilePath 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe' -ArgumentList @(
        (Join-Path $streetProject 'HorrorGame.uproject'), '/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet',
        ('-ExecutePythonScript=' + (Join-Path $streetProject 'Scripts\CaptureEnterableOldTown.py')),
        '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities,GeometryScripting,MainHomeInteractive',
        '-ddc=InstalledNoZenLocalFallback', '-unattended', '-NoSound', '-NoSplash', '-nop4',
        '-RenderOffscreen', '-NoAutoSave', ('-abslog=' + $streetLog)
    ) -WindowStyle Hidden -PassThru
    # Bound waiting to this owned helper. A completed PNG is independent of
    # editor shutdown; never leave a hidden capture process hanging indefinitely.
    $streetFinishedAt = $null
    while (-not $streetProcess.HasExited) {
        $streetCaptureReady = $false
        if ((Test-Path -LiteralPath $streetMeta) -and (Test-Path -LiteralPath $streetPng)) {
            $streetCurrentMeta = Get-Content -LiteralPath $streetMeta -Raw | ConvertFrom-Json
            $streetCaptureReady = $streetCurrentMeta.status -eq 'PASS' -and $streetCurrentMeta.map_sha256 -eq $streetMapHash -and (Get-Item -LiteralPath $streetMeta).LastWriteTime -ge $streetStart
        }
        if ($streetCaptureReady -and $null -eq $streetFinishedAt) { $streetFinishedAt = Get-Date }
        if (($null -ne $streetFinishedAt -and ((Get-Date) - $streetFinishedAt).TotalSeconds -gt 20) -or ((Get-Date) - $streetStart).TotalSeconds -gt 600) {
            $streetProcess.Refresh()
            if (-not $streetProcess.HasExited) { $streetProcess.Kill() }
            break
        }
        [void]$streetProcess.WaitForExit(1000)
    }
    [void]$streetProcess.WaitForExit(10000)
    $streetSaved = (Test-Path -LiteralPath $streetPng) -and (Test-Path -LiteralPath $streetMeta)
    $streetStatus = $false
    if ($streetSaved) {
        $streetImage = Get-Item -LiteralPath $streetPng
        $streetMetadata = Get-Content -LiteralPath $streetMeta -Raw | ConvertFrom-Json
        $streetStatus = $streetImage.Length -gt 20000 -and $streetImage.LastWriteTime -ge $streetStart -and $streetMetadata.status -eq 'PASS' -and $streetMetadata.map_sha256 -eq $streetMapHash
    }
    $streetResults += [pscustomobject]@{camera=$streetCamera; captured=$streetStatus; exit_code=$streetProcess.ExitCode; path=$streetPng}
    $streetResults | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $streetOutput 'CaptureRuns.json') -Encoding utf8
    Write-Output ($streetCamera + ': captured=' + $streetStatus + ' exit=' + $streetProcess.ExitCode)
    if (-not $streetStatus) { throw ('Capture failed: ' + $streetCamera) }
}
