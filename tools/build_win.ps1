# 阶段0 - Windows x86_64 打包脚本
# 用法: powershell -ExecutionPolicy Bypass -File tools\build_win.ps1
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "=== [1/3] 安装 PyInstaller ===" -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m pip install pyinstaller -q
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 安装失败" }

Write-Host "=== [2/3] 执行打包 ===" -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean photo_manager.spec
if ($LASTEXITCODE -ne 0) { throw "打包失败" }

Write-Host "=== [3/3] 自检：运行打包产物 (--smoke) ===" -ForegroundColor Cyan
$exe = "dist\PhotoManager\PhotoManager.exe"
if (-not (Test-Path $exe)) { throw "未找到产物: $exe" }
$env:QT_QPA_PLATFORM = "offscreen"
$p = Start-Process -FilePath (Resolve-Path $exe) -ArgumentList "--smoke" -PassThru -Wait
if ($p.ExitCode -ne 0) { throw "打包产物自检失败，退出码 $($p.ExitCode)" }

$size = [math]::Round(((Get-ChildItem "dist\PhotoManager" -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB), 0)
Write-Host "=== 打包成功：dist\PhotoManager（约 $size MB）===" -ForegroundColor Green
