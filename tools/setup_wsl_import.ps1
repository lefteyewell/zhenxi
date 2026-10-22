# 阶段0 - 从 TUNA 镜像导入 Ubuntu 22.04 到 WSL2
# 需以管理员身份运行（内核更新需要）。
$ErrorActionPreference = 'Continue'
$log = 'D:\trae\software\photo management\logs\wsl_import.log'
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null

function Log($msg) {
    $line = "[{0:HH:mm:ss}] {1}" -f (Get-Date), $msg
    Add-Content -Path $log -Value $line -Encoding UTF8
}

try {
    Log "=== WSL2 内核更新 + Ubuntu 导入（PID $PID）==="

    Log "[1/3] 更新 WSL2 内核..."
    wsl.exe --update 2>&1 | Out-File -FilePath $log -Append -Encoding UTF8
    Log "退出码: $LASTEXITCODE"

    Log "[2/3] 导入 Ubuntu-22.04（tar.gz -> D:\wsl\Ubuntu-22.04）..."
    New-Item -ItemType Directory -Force -Path "D:\wsl\Ubuntu-22.04" | Out-Null
    wsl.exe --import Ubuntu-22.04 "D:\wsl\Ubuntu-22.04" "C:\Users\admin\AppData\Local\Temp\opencode\ubuntu-jammy-wsl-amd64.rootfs.tar.gz" --version 2 2>&1 | Out-File -FilePath $log -Append -Encoding UTF8
    Log "退出码: $LASTEXITCODE"

    Log "[3/3] 验证发行版列表..."
    wsl.exe -l -v 2>&1 | Out-File -FilePath $log -Append -Encoding UTF8
    Log "退出码: $LASTEXITCODE"

    Log "=== 完成 ==="
} catch {
    Log "发生异常: $_"
    Log $_.ScriptStackTrace
}
