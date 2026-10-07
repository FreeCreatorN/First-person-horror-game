param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot '..\SourceArt\OldTownStreetRefinement_20261007')
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$outputRoot = [IO.Path]::GetFullPath($OutputDirectory)
[IO.Directory]::CreateDirectory($outputRoot) | Out-Null
$fontFamily = [System.Drawing.FontFamily]::new('Microsoft YaHei')

# Textures are completely opaque. Age is drawn into the background rather than
# supplied by a remote image or dense noise. Every seed is stable across reruns.
function Write-SignTexture {
    param([object]$Sign, [int]$Seed)
    $paper = $Sign.style -eq 'cream_paper'
    $width = if ($paper) { 768 } else { 2048 }
    $height = if ($paper) { 1024 } else { 544 }
    if ($Sign.kind -eq 'linen') { $width = 1536; $height = 512 }
    $bmp = [System.Drawing.Bitmap]::new($width, $height, [System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    $base = if ($paper) { [System.Drawing.Color]::FromArgb(225, 216, 191) } else { [System.Drawing.Color]::FromArgb(116, 146, 123) }
    $edge = if ($paper) { [System.Drawing.Color]::FromArgb(208, 196, 163) } else { [System.Drawing.Color]::FromArgb(145, 165, 143) }
    $ink = if ($paper) { [System.Drawing.Color]::FromArgb(67, 70, 56) } else { [System.Drawing.Color]::FromArgb(239, 232, 208) }
    $g.Clear($base)
    $whole = [System.Drawing.Rectangle]::new(0, 0, $width, $height)
    $wash = [System.Drawing.Drawing2D.LinearGradientBrush]::new($whole, $base, $edge, 27.0)
    $g.FillRectangle($wash, $whole)
    $wash.Dispose()
    $rng = [System.Random]::new($Seed)

    # Broad, quiet water/dust blooms remain under the print and keep it readable.
    for ($i = 0; $i -lt 8; $i++) {
        $bw = $rng.Next([int]($width * .04), [int]($width * .13))
        $bh = $rng.Next([int]($height * .04), [int]($height * .18))
        $bx = $rng.Next(0, $width - $bw)
        $by = $rng.Next(0, $height - $bh)
        $color = if ($paper) { [System.Drawing.Color]::FromArgb(10, 110, 96, 66) } else { [System.Drawing.Color]::FromArgb(8, 70, 90, 63) }
        $brush = [System.Drawing.SolidBrush]::new($color)
        $g.FillEllipse($brush, $bx, $by, $bw, $bh)
        $brush.Dispose()
    }
    for ($i = 0; $i -lt 5; $i++) {
        $offset = [single](3 + $i * 3)
        $color = if ($paper) { [System.Drawing.Color]::FromArgb(12, 123, 107, 74) } else { [System.Drawing.Color]::FromArgb(11, 234, 221, 186) }
        $pen = [System.Drawing.Pen]::new($color, 2.0)
        $g.DrawRectangle($pen, $offset, $offset, [single]($width - 2 * $offset - 1), [single]($height - 2 * $offset - 1))
        $pen.Dispose()
    }
    $border = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(90, $ink.R, $ink.G, $ink.B), 3.0)
    $margin = [single]($height * .065)
    $g.DrawRectangle($border, $margin, $margin, [single]($width - 2 * $margin), [single]($height - 2 * $margin))
    $border.Dispose()

    $format = [System.Drawing.StringFormat]::new()
    $format.Alignment = [System.Drawing.StringAlignment]::Center
    $format.LineAlignment = [System.Drawing.StringAlignment]::Center
    $format.FormatFlags = [System.Drawing.StringFormatFlags]::NoWrap
    $brush = [System.Drawing.SolidBrush]::new($ink)
    if ($Sign.kind -eq 'gallery') {
        $fontSize = [single]114
        do {
            $font = [System.Drawing.Font]::new($fontFamily, $fontSize, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
            $measured = $g.MeasureString($Sign.text, $font)
            if ($measured.Width -gt $width * .91) { $font.Dispose(); $fontSize -= 2 }
        } while ($measured.Width -gt $width * .91)
        $rect = [System.Drawing.RectangleF]::new([single]($width * .04), [single]($height * .12), [single]($width * .92), [single]($height * .76))
        $g.DrawString($Sign.text, $font, $brush, $rect, $format)
        $font.Dispose()
    } elseif ($Sign.kind -eq 'linen') {
        $font = [System.Drawing.Font]::new($fontFamily, 162.0, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
        $rect = [System.Drawing.RectangleF]::new(72.0, 64.0, [single]($width - 144), [single]($height - 128))
        $g.DrawString($Sign.text, $font, $brush, $rect, $format)
        $font.Dispose()
    } else {
        $heading = [System.Drawing.Font]::new($fontFamily, 111.0, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
        $lineFont = [System.Drawing.Font]::new($fontFamily, 62.0, [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
        $smallFont = [System.Drawing.Font]::new($fontFamily, 32.0, [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
        $g.DrawString('电梯停用', $heading, $brush, [System.Drawing.RectangleF]::new(44.0, 192.0, 680.0, 204.0), $format)
        $g.DrawString('请走楼梯', $lineFont, $brush, [System.Drawing.RectangleF]::new(44.0, 466.0, 680.0, 106.0), $format)
        $g.DrawString('老城旅馆管理处', $smallFont, $brush, [System.Drawing.RectangleF]::new(60.0, 738.0, 648.0, 80.0), $format)
        $rule = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(95, 93, 88, 65), 2.0)
        $g.DrawLine($rule, 111.0, 434.0, 657.0, 434.0)
        $rule.Dispose()
        $heading.Dispose(); $lineFont.Dispose(); $smallFont.Dispose()
        # A pale folded corner is part of the complete rectangular paper image.
        $fold = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(239, 232, 209))
        $points = [System.Drawing.PointF[]]@([System.Drawing.PointF]::new(704, 0), [System.Drawing.PointF]::new(768, 0), [System.Drawing.PointF]::new(768, 64))
        $g.FillPolygon($fold, $points)
        $fold.Dispose()
        $crease = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(60, 125, 109, 73), 1.5)
        $g.DrawLine($crease, 704.0, 0.0, 768.0, 64.0)
        $crease.Dispose()
    }
    $brush.Dispose(); $format.Dispose()
    $path = Join-Path $outputRoot $Sign.filename
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    $Sign | Add-Member -NotePropertyName pixel_size -NotePropertyValue @($width, $height)
    $Sign | Add-Member -NotePropertyName png_sha256 -NotePropertyValue (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
}

$signs = [System.Collections.Generic.List[object]]::new()
$floorHeights = @(11.0, 378.25, 745.5, 1112.75)
for ($f = 1; $f -le 3; $f++) {
    $roomPrefix = $f + 1
    $key = 'GalleryDirection_F' + $f
    $text = "← 南梯 ${roomPrefix}01—${roomPrefix}07     ${roomPrefix}08—${roomPrefix}13 北梯 →"
    $signs.Add([pscustomobject]@{
        key = $key; text = $text; filename = ('T_OTS_Refinement_' + $key + '.png')
        kind = 'gallery'; style = 'faded_green'; world_position_cm = @(9196.0, 325.0, ($floorHeights[$f] + 210.0))
        size_cm = @(105.0, 28.0); width_world_axis = 'Y'; facing_axis = 'negativeX'
        normal_world = @(-1.0, 0.0, 0.0); text_right_world = @(0.0, 1.0, 0.0); text_up_world = @(0.0, 0.0, 1.0)
        floor = $f; collision = $false
        placement_note = 'Corridor centre X=9110 is west of this X=9196 sign. Core door spans Y=110..250; sign spans Y=272.5..377.5.'
    })
}
for ($f = 0; $f -le 3; $f++) {
    $key = 'LiftOutOfService_F' + $f
    $signs.Add([pscustomobject]@{
        key = $key; text = "电梯停用`n请走楼梯`n老城旅馆管理处"; filename = ('T_OTS_Refinement_' + $key + '.png')
        kind = 'lift_notice'; style = 'cream_paper'; world_position_cm = @(9590.5, 235.0, ($floorHeights[$f] + 160.0))
        size_cm = @(32.0, 42.0); width_world_axis = 'Y'; facing_axis = 'negativeX'
        normal_world = @(-1.0, 0.0, 0.0); text_right_world = @(0.0, 1.0, 0.0); text_up_world = @(0.0, 0.0, 1.0)
        floor = $f; collision = $false
        placement_note = 'Existing lift front is X=9591; right leaf notice spans Y=219..251, clear of centre seam Y=210 and call panel Y=105.'
    })
}
$signs.Add([pscustomobject]@{
    key = 'DirtyLinenStore'; text = '污布草库'; filename = 'T_OTS_Refinement_DirtyLinenStore.png'
    kind = 'linen'; style = 'faded_green'; world_position_cm = @(9196.0, 2490.0, 185.0)
    size_cm = @(60.0, 20.0); width_world_axis = 'Y'; facing_axis = 'negativeX'
    normal_world = @(-1.0, 0.0, 0.0); text_right_world = @(0.0, 1.0, 0.0); text_up_world = @(0.0, 0.0, 1.0)
    floor = 0; collision = $false
    placement_note = 'West face of gallery wall; sign ends Y=2520, clear of dirty-store door opening Y=2555..2645.'
})
$signs.Add([pscustomobject]@{
    key = 'CleanLinenStore'; text = '清布草库'; filename = 'T_OTS_Refinement_CleanLinenStore.png'
    kind = 'linen'; style = 'faded_green'; world_position_cm = @(9860.0, 2388.0, 185.0)
    size_cm = @(60.0, 20.0); width_world_axis = 'X'; facing_axis = 'negativeY'
    normal_world = @(0.0, -1.0, 0.0); text_right_world = @(-1.0, 0.0, 0.0); text_up_world = @(0.0, 0.0, 1.0)
    floor = 0; collision = $false
    placement_note = 'South face of store wall at Y=2390, facing office Y=1800..2400. Sign X=9830..9890 is clear of clean-store door X=9655..9745.'
})

$index = 0
foreach ($sign in $signs) { Write-SignTexture -Sign $sign -Seed (202610070 + $index); $index++ }
$manifest = [ordered]@{
    schema_version = 1
    date = '2026-10-07'
    target_level = '/Game/Yastar/Maps/Scenes/L_OldTownSchoolStreet'
    source_map_sha256 = 'a39df284e235743958464cf8ca1d4502ac0d71404ab3dc4edf6a7df9d728a97e'
    font_family = $fontFamily.Name
    generated_by = 'Scripts/GenerateOldTownRefinementSigns.ps1'
    external_images = $false
    transparent_background = $false
    png_pixel_format = 'RGB24'
    units = 'centimetres; world_position is sign centre; size_cm is width,height'
    plane_rotation = $null
    orientation_note = 'Use explicit normal/right/up vectors. EnginePlane UV orientation must be checked by the UE importer; no unverified Euler rotation is asserted here. Texture U increases along text_right_world, texture V along negative text_up_world.'
    signs = @($signs.ToArray())
}
$manifestPath = Join-Path $outputRoot 'SignManifest.json'
$manifest | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
$fontFamily.Dispose()
[ordered]@{ passed = $true; png_count = $signs.Count; manifest = $manifestPath; opaque = $true } | ConvertTo-Json -Compress
