# 阶段0 - 启用 WSL2 并安装 Ubuntu 22.04
# 需以管理员身份运行。日志固定写入项目 logs 目录。
$ErrorActionPreference = 'Continue'
$log = Join-Path $PSScriptRoot '..\logs\wsl_setup.log'
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null

function Log($msg) {
    $line = "[{0:HH:mm:ss}] {1}" -f (Get-Date), $msg
    Add-Content -Path $log -Value $line -Encoding UTF8
}

try {
Log "=== 开始 WSL 环境安装（PID $PID）==="
Log "[1/4] 启用 Microsoft-Windows-Subsystem-Linux 功能..."
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart 2>&1 | Out-File -FilePath $log -Append -Encoding UTF8
Log "退出码: $LASTEXITCODE"

Log "[2/4] 启用 VirtualMachinePlatform 功能..."
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart 2>&1 | Out-File -FilePath $log -Append -Encoding UTF8
Log "退出码: $LASTEXITCODE"

Log "[3/4] 设置默认 WSL 版本为 2..."
wsl.exe --set-default-version 2 2>&1 | Out-File -FilePath $log -Append -Encoding UTF8
Log "退出码: $LASTEXITCODE"

Log "[4/4] 安装 Ubuntu 22.04 发行版..."
wsl.exe --install -d Ubuntu-22.04 2>&1 | Out-File -FilePath $log -Append -Encoding UTF8
Log "退出码: $LASTEXITCODE"

Log "=== 安装步骤完成，请查看上方输出。若提示重启，请重启后再运行 wsl -l -v ==="
} catch {
    Log "发生异常: $_"
    Log $_.ScriptStackTrace
}
