Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$proc = Start-Process -FilePath "C:\Users\user\AppData\Local\Programs\Python\Python313\python.exe" `
    -ArgumentList "D:\teach_tracker\main.py" `
    -WorkingDirectory "D:\teach_tracker" `
    -PassThru

Start-Sleep -Seconds 4

$screen = [System.Windows.Forms.Screen]::PrimaryScreen
$bitmap = New-Object System.Drawing.Bitmap($screen.Bounds.Width, $screen.Bounds.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($screen.Bounds.Location, [System.Drawing.Point]::Empty, $screen.Bounds.Size)
$bitmap.Save("D:\teach_tracker\screenshot.png")
$graphics.Dispose()
$bitmap.Dispose()

Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
Write-Host "Screenshot saved: D:\teach_tracker\screenshot.png"
