$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
$hotelSheetRoot='D:/UE/Project/HorrorGame/Saved/CodexOutputs/HotelArchitecture_20261005'
$hotelSheetPlan=Get-Content -LiteralPath ($hotelSheetRoot+'/ArchitecturePlan.json') -Raw | ConvertFrom-Json
$hotelSheetBitmap=[System.Drawing.Bitmap]::new(2100,850)
$hotelSheetGraphics=[System.Drawing.Graphics]::FromImage($hotelSheetBitmap)
$hotelSheetGraphics.SmoothingMode='AntiAlias'
$hotelSheetGraphics.Clear([System.Drawing.ColorTranslator]::FromHtml('#f5f2e9'))
$hotelSheetFont=[System.Drawing.Font]::new('Microsoft YaHei',13)
$hotelSheetSmall=[System.Drawing.Font]::new('Microsoft YaHei',10)
$hotelSheetTitle=[System.Drawing.Font]::new('Microsoft YaHei',25,[System.Drawing.FontStyle]::Bold)
$hotelSheetDark=[System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#29352f'))
$hotelSheetPen=[System.Drawing.Pen]::new([System.Drawing.ColorTranslator]::FromHtml('#46514a'),1)
function Paint-HotelRect($low,$high,$base,$color,$outline=$true) {
    $px=70+([double]$low[1]+3500)*.28
    $py=$base+(10040-[double]$high[0])*.28
    $pw=([double]$high[1]-[double]$low[1])*.28
    $ph=([double]$high[0]-[double]$low[0])*.28
    $brush=[System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml($color))
    $hotelSheetGraphics.FillRectangle($brush,[single]$px,[single]$py,[single]$pw,[single]$ph)
    if($outline){$hotelSheetGraphics.DrawRectangle($hotelSheetPen,[single]$px,[single]$py,[single]$pw,[single]$ph)}
    $brush.Dispose()
}
function Paint-HotelText($text,$x,$y,$base) {
    $px=70+($y+3500)*.28
    $py=$base+(10040-$x)*.28
    $hotelSheetGraphics.DrawString($text,$hotelSheetSmall,$hotelSheetDark,[single]$px,[single]$py)
}
$hotelSheetGraphics.DrawString('老城旧旅馆 · 建筑布局',$hotelSheetTitle,$hotelSheetDark,65,20)
$hotelSheetGraphics.DrawString('70.0 × 10.4 m ｜ 四层 / 41间客房 ｜ 南北双梯独立出口 ｜ 1.8 m街侧长廊',$hotelSheetFont,$hotelSheetDark,70,62)
foreach($floor in @(0,1)) {
    $base=if($floor -eq 0){125}else{495}
    $hotelSheetGraphics.DrawString($(if($floor -eq 0){'首层：公共接待、卫浴与后勤'}else{'典型客房层：二至四层各13间'}),$hotelSheetFont,$hotelSheetDark,70,($base-28))
    Paint-HotelRect @(9000,-3500) @(10040,3500) $base '#e7e1d3'
    Paint-HotelRect @(9020,-3480) @(9200,3480) $base '#dde6c7' $false
    foreach($room in $hotelSheetPlan.rooms | Where-Object floor -eq $floor) {
        Paint-HotelRect $room.world_min $room.world_max $base '#ece6d3'
        Paint-HotelRect $room.bathroom_bounds[0] $room.bathroom_bounds[1] $base '#bfdbdc'
        Paint-HotelText $room.id 9780 ($room.world_min[1]+85) $base
    }
    if($floor -eq 0) {
        $labels=@{FrontDesk='前台 / 大堂';Lounge='会客厅';TeaBreakfast='茶餐区';Office='办公室';DryPantry='备餐间';PublicWC='公共卫浴';StaffWC='员工卫浴';DirtyLinenStore='污布草';CleanLinenStore='清洁布草'}
        foreach($zone in $hotelSheetPlan.spatial_program | Where-Object floor -eq 0) {
            $r=$zone.rect
            $color=if($zone.role -match 'toilet'){'#bfdbdc'}elseif($zone.role -match 'linen'){'#d7c8b7'}else{'#e9ddbc'}
            Paint-HotelRect @($r[0],$r[1]) @($r[2],$r[3]) $base $color
            Paint-HotelText $labels[$zone.id] ($r[2]-75) ($r[1]+35) $base
        }
    } else {
        Paint-HotelRect @(9220,0) @(10020,407.142857) $base '#d7c8b7'
        Paint-HotelText '电梯 / 布草' 9950 25 $base
    }
    foreach($sign in @(-1,1)) {
        $stairYs=@(($sign*2870),($sign*3480)) | Sort-Object
        Paint-HotelRect @(9220,$stairYs[0]) @(10020,$stairYs[1]) $base '#c8d1c6'
        Paint-HotelText $(if($sign -eq -1){'南楼梯'}else{'北楼梯'}) 9960 ($stairYs[0]+60) $base
    }
    foreach($box in $hotelSheetPlan.boxes | Where-Object {($_.floor -eq $floor) -or ($_.role -in @('stair_tread','landing'))}) {
        if($box.role -in @('wall','wet_shaft','column')) { Paint-HotelRect $box.world_min $box.world_max $base '#58615a' $false }
        elseif($box.role -in @('bed','desk','reception','table','shelf','worktop','linen_bin')) { Paint-HotelRect $box.world_min $box.world_max $base '#b9a78c' }
    }
    foreach($door in $hotelSheetPlan.doors | Where-Object floor -eq $floor) {
        $p=$door.position_cm
        $px=70+($p[1]+3500)*.28
        $py=$base+(10040-$p[0])*.28
        $brush=[System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#835b35'))
        $hotelSheetGraphics.FillEllipse($brush,[single]($px-3),[single]($py-3),6,6)
        $brush.Dispose()
    }
    Paint-HotelText '街侧走廊 1.8m → 两端楼梯' 9160 -800 $base
    $hotelSheetGraphics.DrawString('南端', $hotelSheetSmall,$hotelSheetDark,20,($base+305))
    $hotelSheetGraphics.DrawString('北端', $hotelSheetSmall,$hotelSheetDark,2030,($base+305))
}
$hotelSheetGraphics.DrawString('图例：浅绿=通行带  蓝=卫浴  灰绿=楼梯  米色=住客/公共空间  棕灰=服务空间  深灰=墙/管井  圆点=门',$hotelSheetSmall,$hotelSheetDark,70,810)
$hotelSheetBitmap.Save(($hotelSheetRoot+'/DesignPlan.png'),[System.Drawing.Imaging.ImageFormat]::Png)
$hotelSheetGraphics.Dispose()
$hotelSheetBitmap.Dispose()
Write-Output 'Hotel design sheet saved.'
