param(
    [string]$OutputPath = (
        Join-Path $PSScriptRoot (
            "..\SourceArt\Generated\MainHome\T_MainHome_SignText.png"
        )
    )
)

Add-Type -AssemblyName System.Drawing

$outputDirectory = Split-Path -Parent $OutputPath
if (-not (Test-Path -LiteralPath $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory | Out-Null
}

$width = 2048
$height = 512
$bitmap = New-Object System.Drawing.Bitmap $width, $height, (
    [System.Drawing.Imaging.PixelFormat]::Format32bppArgb
)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.Clear([System.Drawing.Color]::Transparent)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
$graphics.InterpolationMode = (
    [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
)
$graphics.PixelOffsetMode = (
    [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
)
$graphics.TextRenderingHint = (
    [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
)

$fontCollection = (
    New-Object System.Drawing.Text.PrivateFontCollection
)
$fontPath = "C:\Windows\Fonts\Noto Sans SC Medium (TrueType).otf"
$fontCollection.AddFontFile($fontPath)
$fontFamily = $fontCollection.Families[0]
$font = New-Object System.Drawing.Font(
    $fontFamily,
    286,
    [System.Drawing.FontStyle]::Regular,
    [System.Drawing.GraphicsUnit]::Pixel
)

$text = [string]::Concat(
    [char]0x5927,
    [char]0x4F17,
    [char]0x5C0F,
    [char]0x5356,
    [char]0x90E8
)
$format = New-Object System.Drawing.StringFormat
$format.Alignment = [System.Drawing.StringAlignment]::Center
$format.LineAlignment = [System.Drawing.StringAlignment]::Center
$format.FormatFlags = (
    [System.Drawing.StringFormatFlags]::NoWrap
)
$brush = New-Object System.Drawing.SolidBrush(
    [System.Drawing.Color]::FromArgb(238, 116, 48, 31)
)
$layout = New-Object System.Drawing.RectangleF 32, 20, 1984, 472
$graphics.DrawString($text, $font, $brush, $layout, $format)

# Deterministic small missing-print flecks keep the lettering old without
# destroying readability from player distance.
$graphics.CompositingMode = (
    [System.Drawing.Drawing2D.CompositingMode]::SourceCopy
)
$transparent = New-Object System.Drawing.SolidBrush(
    [System.Drawing.Color]::Transparent
)
$random = New-Object System.Random 500800400
for ($index = 0; $index -lt 190; $index++) {
    $x = $random.Next(250, 1798)
    $y = $random.Next(112, 402)
    $w = $random.Next(2, 10)
    $h = $random.Next(2, 7)
    $graphics.FillRectangle($transparent, $x, $y, $w, $h)
}

$bitmap.Save(
    $OutputPath,
    [System.Drawing.Imaging.ImageFormat]::Png
)

$transparent.Dispose()
$brush.Dispose()
$font.Dispose()
$fontCollection.Dispose()
$format.Dispose()
$graphics.Dispose()
$bitmap.Dispose()

Write-Output $OutputPath
