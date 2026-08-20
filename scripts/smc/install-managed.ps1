# SMC Hermes managed runtime installer helper.
#
# Used by OPSI / MSI post-install validation. Enforces canonical layout paths
# and creates HERMES_HOME when missing.

param(
    [string]$ProgramRoot = "D:\Programs\SMC\Hermes",
    [string]$HermesHome = "C:\ProgramData\SMC\Hermes",
    [switch]$PreflightOnly
)

$ErrorActionPreference = "Stop"

function Test-FixedDrive([string]$DriveLetter) {
    if (-not (Test-Path "${DriveLetter}:\")) {
        throw "SMC_INSTALL_101 PROGRAM_ROOT_DRIVE_NOT_AVAILABLE — drive ${DriveLetter}: missing"
    }
    $drive = Get-PSDrive -Name $DriveLetter -ErrorAction Stop
    if ($drive.Provider.Name -ne "FileSystem") {
        throw "SMC_INSTALL_101 PROGRAM_ROOT_DRIVE_NOT_AVAILABLE — ${DriveLetter}: not a filesystem drive"
    }
    $vol = Get-Volume -DriveLetter $DriveLetter -ErrorAction SilentlyContinue
    if ($vol -and $vol.DriveType -ne "Fixed") {
        throw "SMC_INSTALL_101 PROGRAM_ROOT_DRIVE_NOT_AVAILABLE — ${DriveLetter}: must be a local fixed disk"
    }
}

function Set-DirectoryAclReadExecute {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    $acl = Get-Acl $Path
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        "BUILTIN\Users", "ReadAndExecute", "ContainerInherit,ObjectInherit", "None", "Allow"
    )
    $acl.AddAccessRule($rule)
    Set-Acl -Path $Path -AclObject $acl
}

$expectedDrive = ([System.IO.Path]::GetPathRoot($ProgramRoot)).TrimEnd('\').TrimEnd(':')
if (-not $expectedDrive) {
    throw "Could not parse drive letter from ProgramRoot=$ProgramRoot"
}
Test-FixedDrive -DriveLetter $expectedDrive

if ($PreflightOnly) {
    Write-Host "Preflight OK for $ProgramRoot"
    exit 0
}

foreach ($dir in @($HermesHome, "$HermesHome\logs", "$HermesHome\profiles")) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

if (Test-Path $ProgramRoot) {
    Set-DirectoryAclReadExecute -Path $ProgramRoot
}

Write-Host "Managed install validation complete."
Write-Host "  PROGRAM_ROOT=$ProgramRoot"
Write-Host "  HERMES_HOME=$HermesHome"
