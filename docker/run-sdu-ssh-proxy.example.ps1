#Requires -Version 5.1

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# Copy this file to docker/run-sdu-ssh-proxy.ps1, then replace every CHANGE_ME
# value. The copied file is ignored by Git so credentials are not committed.
$AtrustContainerName = "atrust"
$AtrustImage = "koishikiss/docker-sdu-atrust-autologin:custom"
$AtrustOpts = '--cas=True --username="CHANGE_ME" --password="CHANGE_ME" --fingerprint="CHANGE_ME" --keepalive=100'
$AtrustVncPassword = "CHANGE_ME"

# Optional keepalive targets. Leave empty to disable either setting.
$AtrustPingAddr = ""
$AtrustPingUrl = ""

$SshProxyHost = "CHANGE_ME"
$SshProxyPort = "22"
$SshProxyUser = "CHANGE_ME"

# Authentication priority: private key, password file, password environment.
# Windows paths such as C:\Users\you\.ssh\atrust_proxy are supported.
$SshProxyIdentityFile = ""
$SshProxyPasswordFile = ""
$SshProxyPassword = "CHANGE_ME"

function Invoke-Docker {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

    & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker command failed with exit code $LASTEXITCODE"
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI was not found. Install and start Docker Desktop first."
}

[string]$DockerOsType = & docker info --format '{{.OSType}}' 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop is not running or is not accessible."
}
if ($DockerOsType.Trim() -ne "linux") {
    throw "This image requires Docker Desktop in Linux containers mode."
}

& docker container inspect $AtrustContainerName 1>$null 2>$null
$ContainerExists = $LASTEXITCODE -eq 0

if ($ContainerExists) {
    Write-Host "[Runner] Reusing existing container: $AtrustContainerName"
    [string]$IsRunning = & docker inspect -f '{{.State.Running}}' $AtrustContainerName
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect container $AtrustContainerName."
    }

    if ($IsRunning.Trim() -eq "true") {
        Write-Host "[Runner] Container is already running; following logs."
        & docker logs -f $AtrustContainerName
        exit $LASTEXITCODE
    }

    # Python files do not depend on Unix executable permissions, so they can be
    # safely hot-updated from a Windows checkout. The proxy shell script is
    # already included in the image built by this repository.
    Invoke-Docker cp (Join-Path $ProjectRoot "src\.") "${AtrustContainerName}:/opt/atrust-autologin/"
    Write-Host "[Runner] Updated login code without recreating the container."
    & docker start -ai $AtrustContainerName
    exit $LASTEXITCODE
}

$RequiredSettings = [ordered]@{
    ATRUST_OPTS = $AtrustOpts
    ATRUST_VNC_PASSWORD = $AtrustVncPassword
    SSH_PROXY_HOST = $SshProxyHost
    SSH_PROXY_USER = $SshProxyUser
}

$UnsetSettings = @(
    $RequiredSettings.GetEnumerator() |
        Where-Object { [string]::IsNullOrWhiteSpace([string]$_.Value) -or [string]$_.Value -match 'CHANGE_ME' } |
        ForEach-Object { $_.Key }
)

if ($UnsetSettings.Count -gt 0) {
    throw "Replace CHANGE_ME in these settings before the first start: $($UnsetSettings -join ', ')"
}

$HasIdentityFile = -not [string]::IsNullOrWhiteSpace($SshProxyIdentityFile)
$HasPasswordFile = -not [string]::IsNullOrWhiteSpace($SshProxyPasswordFile)
$HasPassword = -not [string]::IsNullOrWhiteSpace($SshProxyPassword) -and $SshProxyPassword -notmatch 'CHANGE_ME'

if (-not ($HasIdentityFile -or $HasPasswordFile -or $HasPassword)) {
    throw "Configure an SSH private key, password file, or SSH_PROXY_PASSWORD."
}

$AtrustDataDir = Join-Path $HOME ".atrust-data"
New-Item -ItemType Directory -Force -Path $AtrustDataDir | Out-Null

$DockerArgs = @(
    "run", "-it",
    "--name", $AtrustContainerName,
    "--shm-size", "256m",
    "--device", "/dev/net/tun",
    "--cap-add", "NET_ADMIN",
    "--sysctl", "net.ipv4.conf.default.route_localnet=1",
    "-e", "ATRUST_OPTS=$AtrustOpts",
    "-e", "PASSWORD=$AtrustVncPassword",
    "-e", "NODANTED=1",
    "-e", "SSH_PROXY_HOST=$SshProxyHost",
    "-e", "SSH_PROXY_PORT=$SshProxyPort",
    "-e", "SSH_PROXY_USER=$SshProxyUser",
    "-e", "SSH_PROXY_LOCAL_PORT=1081",
    "-e", "SSH_PROXY_PUBLISHED_HOST=127.0.0.1",
    "-e", "SSH_PROXY_PUBLISHED_PORT=1080",
    "-v", "${AtrustDataDir}:/root",
    "-p", "10022:22",
    "-p", "127.0.0.1:1080:1081"
)

if (-not [string]::IsNullOrWhiteSpace($AtrustPingAddr)) {
    $DockerArgs += @("-e", "PING_ADDR=$AtrustPingAddr")
}
if (-not [string]::IsNullOrWhiteSpace($AtrustPingUrl)) {
    $DockerArgs += @("-e", "PING_ADDR_URL=$AtrustPingUrl")
}

if ($HasIdentityFile) {
    $IdentityPath = (Resolve-Path -LiteralPath $SshProxyIdentityFile).Path
    $DockerArgs += @(
        "-e", "SSH_PROXY_IDENTITY_FILE=/run/secrets/ssh_proxy_key",
        "-v", "${IdentityPath}:/run/secrets/ssh_proxy_key:ro"
    )
}
elseif ($HasPasswordFile) {
    $PasswordPath = (Resolve-Path -LiteralPath $SshProxyPasswordFile).Path
    $DockerArgs += @(
        "-e", "SSH_PROXY_PASSWORD_FILE=/run/secrets/ssh_proxy_password",
        "-v", "${PasswordPath}:/run/secrets/ssh_proxy_password:ro"
    )
}
else {
    $DockerArgs += @("-e", "SSH_PROXY_PASSWORD=$SshProxyPassword")
}

$DockerArgs += $AtrustImage

Write-Host "[Runner] Starting $AtrustContainerName with Docker Desktop Linux containers."
& docker @DockerArgs
exit $LASTEXITCODE
