# SMC Hermes Agent — Windows client runtime release builder.
#
# Produces:
#   out/client-release/<version>/<build-id>/
#     hermes-runtime_<version>_windows-amd64.zip
#     release-manifest.json
#     checksums.txt
#     build-info.json
#     smc-hermes-agent_<version>_windows-amd64.msi   (when WiX is available)
#
# Usage:
#   pwsh -File scripts/build-client-release.ps1
#   pwsh -File scripts/build-client-release.ps1 -SkipMsi
#   pwsh -File scripts/build-client-release.ps1 -ProgramRoot "E:\staging\program" -HermesHome "E:\staging\data"

param(
    [string]$Version = "",
    [string]$ProgramRoot = "D:\Programs\SMC\Hermes",
    [string]$HermesHome = "C:\ProgramData\SMC\Hermes",
    [string]$OutputDir = "",
    [string]$NodeMajor = "22",
    [string]$PythonVersion = "3.11.9",
    [switch]$SkipMsi,
    [switch]$SkipBuildGate
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Get-ProjectVersion {
    param([string]$Root)
    $pyproject = Join-Path $Root "pyproject.toml"
    if (-not (Test-Path $pyproject)) {
        throw "pyproject.toml not found at $pyproject"
    }
    $match = Select-String -Path $pyproject -Pattern '^\s*version\s*=\s*"([^"]+)"' | Select-Object -First 1
    if (-not $match) {
        throw "Could not read version from pyproject.toml"
    }
    return $match.Matches[0].Groups[1].Value
}

function Get-GitCommit {
    param([string]$Root)
    Push-Location $Root
    try {
        return (git rev-parse HEAD).Trim()
    } finally {
        Pop-Location
    }
}

function Invoke-External {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory = $RepoRoot
    )
    Write-Host "→ $FilePath $($ArgumentList -join ' ')"
    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed ($LASTEXITCODE): $FilePath $($ArgumentList -join ' ')"
    }
}

function Get-Sha256Hex {
    param([string]$Path)
    return (Get-FileHash -Algorithm SHA256 -Path $Path).Hash.ToLowerInvariant()
}

function New-Directory([string]$Path) {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
}

function Expand-ArchiveZip {
    param([string]$ZipPath, [string]$Destination)
    Expand-Archive -Path $ZipPath -DestinationPath $Destination -Force
}

if (-not $Version) {
    $Version = Get-ProjectVersion -Root $RepoRoot
}

$BuildId = Get-Date -Format "yyyyMMddHHmmss"
if (-not $OutputDir) {
    $OutputDir = Join-Path $RepoRoot "out\client-release\$Version\$BuildId"
}
New-Directory $OutputDir

$StagingRoot = Join-Path $env:TEMP "hermes-runtime-staging-$BuildId"
$RuntimeRoot = Join-Path $StagingRoot "runtime"
if (Test-Path $StagingRoot) {
    Remove-Item -Recurse -Force $StagingRoot
}
New-Directory $RuntimeRoot

Write-Host "Building SMC Hermes runtime $Version (build $BuildId)"
Write-Host "  Program root : $ProgramRoot"
Write-Host "  Hermes home  : $HermesHome"
Write-Host "  Staging      : $RuntimeRoot"

# --- Layout directories ---------------------------------------------------
$BinDir = Join-Path $RuntimeRoot "bin"
$PythonDir = Join-Path $RuntimeRoot "python"
$NodeDir = Join-Path $RuntimeRoot "node"
$WorkspaceDir = Join-Path $NodeDir "hermes-agent"
$ScriptsDir = Join-Path $RuntimeRoot "scripts"
$ManifestDir = Join-Path $RuntimeRoot "manifest"
foreach ($dir in @($BinDir, $PythonDir, $NodeDir, $WorkspaceDir, $ScriptsDir, $ManifestDir)) {
    New-Directory $dir
}

Set-Content -Path (Join-Path $RuntimeRoot "VERSION") -Value $Version -Encoding ascii

# --- Node 22 portable -----------------------------------------------------
$nodeIndexUrl = "https://nodejs.org/dist/latest-v$NodeMajor.x/"
$nodeIndex = Invoke-WebRequest -Uri $nodeIndexUrl -UseBasicParsing
$nodeZipName = [regex]::Match(
    $nodeIndex.Content,
    "node-v$NodeMajor\.\d+\.\d+-win-x64\.zip"
).Value
if (-not $nodeZipName) {
    throw "Could not resolve Node $NodeMajor win-x64 zip from $nodeIndexUrl"
}
$nodeZipPath = Join-Path $StagingRoot $nodeZipName
Invoke-WebRequest -Uri "$nodeIndexUrl$nodeZipName" -OutFile $nodeZipPath
$nodeExtract = Join-Path $StagingRoot "node-extract"
Expand-ArchiveZip -ZipPath $nodeZipPath -Destination $nodeExtract
$nodeFolder = Get-ChildItem -Path $nodeExtract -Directory | Select-Object -First 1
Copy-Item -Path (Join-Path $nodeFolder.FullName "*") -Destination $NodeDir -Recurse -Force
$nodeExe = Join-Path $NodeDir "node.exe"
$npmCmd = Join-Path $NodeDir "npm.cmd"

# --- Node workspace (canonical root package.json) ---------------------------
Copy-Item (Join-Path $RepoRoot "package.json") $WorkspaceDir
Copy-Item (Join-Path $RepoRoot "package-lock.json") $WorkspaceDir
Push-Location $WorkspaceDir
try {
    Invoke-External -FilePath $npmCmd -ArgumentList @(
        "ci", "--omit=dev", "--workspaces=false"
    ) -WorkingDirectory $WorkspaceDir
} finally {
    Pop-Location
}

# --- Python embeddable + wheel install ------------------------------------
$pyZipName = "python-$PythonVersion-embed-amd64.zip"
$pyZipUrl = "https://www.python.org/ftp/python/$PythonVersion/$pyZipName"
$pyZipPath = Join-Path $StagingRoot $pyZipName
Invoke-WebRequest -Uri $pyZipUrl -OutFile $pyZipPath
Expand-ArchiveZip -ZipPath $pyZipPath -Destination $PythonDir
$pythonExe = Join-Path $PythonDir "python.exe"

# Enable site-packages in embeddable distro.
$pthFile = Get-ChildItem -Path $PythonDir -Filter "python*._pth" | Select-Object -First 1
if ($pthFile) {
    $pthContent = Get-Content $pthFile.FullName
    $pthContent = $pthContent | ForEach-Object {
        if ($_ -eq "#import site") { "import site" } else { $_ }
    }
    Set-Content -Path $pthFile.FullName -Value $pthContent -Encoding ascii
}

$wheelDir = Join-Path $StagingRoot "wheel"
New-Directory $wheelDir
$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) {
    Invoke-External -FilePath $uv.Source -ArgumentList @("build", "--wheel", "--out-dir", $wheelDir) -WorkingDirectory $RepoRoot
    $wheel = Get-ChildItem -Path $wheelDir -Filter "*.whl" | Select-Object -First 1
    if (-not $wheel) { throw "uv build produced no wheel" }
    Invoke-External -FilePath $pythonExe -ArgumentList @(
        "-m", "pip", "install", "--upgrade", "pip", "wheel"
    )
    Invoke-External -FilePath $pythonExe -ArgumentList @(
        "-m", "pip", "install", $wheel.FullName
    )
} else {
    Write-Warning "uv not found — copying source tree into python/Lib/site-packages/hermes fallback"
    $sitePackages = Join-Path $PythonDir "Lib\site-packages"
    New-Directory $sitePackages
    Copy-Item -Path $RepoRoot -Destination (Join-Path $sitePackages "hermes-agent-src") -Recurse
}

# --- Launcher + helper scripts --------------------------------------------
$agentRoot = Join-Path $ProgramRoot "node\hermes-agent"
$hermesCmd = @"
@echo off
set "HERMES_HOME=$HermesHome"
set "HERMES_AGENT_ROOT=$agentRoot"
set "HERMES_MANAGED_INSTALL=1"
"$ProgramRoot\python\python.exe" -m hermes_cli %*
"@
Set-Content -Path (Join-Path $BinDir "hermes.cmd") -Value $hermesCmd -Encoding ascii

$doctorPs1 = @'
param([switch]$Fix)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
& "$root\bin\hermes.cmd" doctor @args
exit $LASTEXITCODE
'@
Set-Content -Path (Join-Path $ScriptsDir "doctor.ps1") -Value $doctorPs1 -Encoding utf8
Copy-Item (Join-Path $ScriptsDir "doctor.ps1") (Join-Path $ScriptsDir "repair.ps1")

# --- Manifest -------------------------------------------------------------
$lockSha = Get-Sha256Hex -Path (Join-Path $WorkspaceDir "package-lock.json")
$commit = Get-GitCommit -Root $RepoRoot
$manifest = [ordered]@{
    schema_version          = 1
    product                 = "smc-hermes-agent"
    version                 = $Version
    runtime_layout_version  = 2
    hermes                  = @{
        repository = "loudon84/copilot-hermes"
        branch     = "main"
        commit     = $commit
    }
    python                  = @{ version = $PythonVersion }
    node                    = @{ version = $NodeMajor }
    node_workspace          = @{
        relative_path       = "node/hermes-agent"
        package_lock_sha256 = $lockSha
    }
    paths                   = @{
        hermes_home  = $HermesHome
        program_root = $ProgramRoot
    }
}
$manifestPath = Join-Path $ManifestDir "release-manifest.json"
$manifest | ConvertTo-Json -Depth 6 | Set-Content -Path $manifestPath -Encoding utf8
Copy-Item $manifestPath (Join-Path $OutputDir "release-manifest.json")

# --- Zip + checksums ------------------------------------------------------
$zipName = "hermes-runtime_${Version}_windows-amd64.zip"
$zipPath = Join-Path $OutputDir $zipName
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
Compress-Archive -Path (Join-Path $RuntimeRoot "*") -DestinationPath $zipPath -Force

$checksumLines = @(
    "$(Get-Sha256Hex $zipPath)  $zipName"
)
Set-Content -Path (Join-Path $OutputDir "checksums.txt") -Value $checksumLines -Encoding ascii

$buildInfo = [ordered]@{
    version      = $Version
    build_id     = $BuildId
    commit       = $commit
    program_root = $ProgramRoot
    hermes_home  = $HermesHome
    zip          = $zipName
}
$buildInfo | ConvertTo-Json -Depth 4 | Set-Content -Path (Join-Path $OutputDir "build-info.json") -Encoding utf8

# --- Build gate -----------------------------------------------------------
if (-not $SkipBuildGate) {
    $required = @(
        (Join-Path $WorkspaceDir "package.json"),
        (Join-Path $WorkspaceDir "package-lock.json"),
        (Join-Path $WorkspaceDir "node_modules\agent-browser\package.json"),
        $nodeExe,
        $npmCmd,
        $pythonExe
    )
    foreach ($path in $required) {
        if (-not (Test-Path $path)) {
            throw "Build gate failed — missing $path"
        }
    }
    Write-Host "Build gate passed."
}

# --- MSI (optional) -------------------------------------------------------
$msiName = "smc-hermes-agent_${Version}_windows-amd64.msi"
$msiPath = Join-Path $OutputDir $msiName
if (-not $SkipMsi) {
    $wix = Get-Command wix -ErrorAction SilentlyContinue
    if (-not $wix) {
        Write-Warning "WiX Toolset (wix.exe) not found — skipping MSI. Runtime zip is ready."
    } else {
        $wixDir = Join-Path $RepoRoot "scripts\smc\wix"
        $wxsPath = Join-Path $wixDir "Product.wxs"
        if (-not (Test-Path $wxsPath)) {
            throw "Missing WiX source: $wxsPath"
        }
        $wixStaging = Join-Path $StagingRoot "wix"
        New-Directory $wixStaging
        $runtimeFilesRoot = Join-Path $wixStaging "runtime"
        Copy-Item -Path $RuntimeRoot -Destination $runtimeFilesRoot -Recurse -Force
        Invoke-External -FilePath $wix.Source -ArgumentList @(
            "build",
            $wxsPath,
            "-d", "ProductVersion=$Version",
            "-d", "RuntimeSourceRoot=$runtimeFilesRoot",
            "-d", "ProgramRoot=$ProgramRoot",
            "-d", "HermesHome=$HermesHome",
            "-o", $msiPath
        ) -WorkingDirectory $wixDir
        Write-Host "MSI written: $msiPath"
    }
}

Write-Host ""
Write-Host "Release artifacts:"
Write-Host "  $zipPath"
if (Test-Path $msiPath) { Write-Host "  $msiPath" }
Write-Host "  $(Join-Path $OutputDir 'release-manifest.json')"
