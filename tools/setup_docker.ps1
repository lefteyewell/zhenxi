# 阶段0 - 下载并静默安装 Docker Desktop（WSL2 后端）
# 需以管理员身份运行。
$ErrorActionPreference = 'Continue'
$log = 'D:\trae\software\photo management\logs\docker_setup.log'
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null

function Log($msg) {
    $line = "[{0:HH:mm:ss}] {1}" -f (Get-Date), $msg
    Add-Content -Path $log -Value $line -Encoding UTF8
}

try {
    Log "=== Docker Desktop 安装（PID $PID）==="

    $installer = Join-Path $env:TEMP "DockerDesktopInstaller.exe"
    $url = "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"

    Log "[1/3] 下载 Docker Desktop 安装包（约 600MB）..."
    if (-not (Test-Path $installer)) {
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing
    }
    Log "下载完成: $installer ($([math]::Round((Get-Item $installer).Length / 1MB)) MB)"

    Log "[2/3] 静默安装（WSL2 后端）..."
    $so = Join-Path (Split-Path $log) "docker_install_stdout.log"
    $se = Join-Path (Split-Path $log) "docker_install_stderr.log"
    $p = Start-Process -FilePath $installer -ArgumentList 'install','--quiet','--accept-license','--backend=wsl-2' -Wait -PassThru -RedirectStandardOutput $so -RedirectStandardError $se
    Log "安装器退出码: $($p.ExitCode)"
    if (Test-Path $so) { Log "--- stdout ---"; Get-Content $so | Out-File -FilePath $log -Append -Encoding UTF8 }
    if (Test-Path $se) { Log "--- stderr ---"; Get-Content $se | Out-File -FilePath $log -Append -Encoding UTF8 }

    Log "[3/3] 检查 Docker 命令..."
    & docker --version 2>&1 | Out-File -FilePath $log -Append -Encoding UTF8

    Log "=== 完成。请打开 Docker Desktop 完成首次启动（如提示登录可跳过）==="
} catch {
    Log "发生异常: $_"
    Log $_.ScriptStackTrace
}
