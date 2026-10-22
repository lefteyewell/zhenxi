# 阶段0 - 重启后执行：安装 Ubuntu 22.04 发行版
# 需以管理员身份运行。日志固定写入项目 logs 目录。
$ErrorActionPreference = 'Continue'
$log = 'D:\trae\software\photo management\logs\wsl_setup2.log'
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null

function Log($msg) {
    $line = "[{0:HH:mm:ss}] {1}" -f (Get-Date), $msg
    Add-Content -Path $log -Value $line -Encoding UTF8
}

try {
    Log "=== 重启后安装 Ubuntu 22.04（PID $PID）==="

    Log "[1/3] 设置默认 WSL 版本为 2..."
    wsl.exe --set-default-version 2 2>&1 | Out-File -FilePath $log -Append -Encoding UTF8
    Log "退出码: $LASTEXITCODE"

    Log "[2/3] 安装 Ubuntu-22.04..."
    wsl.exe --install -d Ubuntu-22.04 2>&1 | Out-File -FilePath $log -Append -Encoding UTF8
    Log "退出码: $LASTEXITCODE"

    Log "[3/3] 检查已安装发行版..."
    wsl.exe -l -v 2>&1 | Out-File -FilePath $log -Append -Encoding UTF8
    Log "退出码: $LASTEXITCODE"

    Log "=== 完成。若发行版安装成功，下一步安装 Docker Desktop ==="
} catch {
    Log "发生异常: $_"
    Log $_.ScriptStackTrace
}
