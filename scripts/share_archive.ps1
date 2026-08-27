[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ArchivePath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath,

    [switch]$Encrypt,

    [string]$PasswordFile
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$archive = (Resolve-Path -LiteralPath $ArchivePath).Path
if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) {
    throw "ArchivePath must point to a JSON archive file: $archive"
}

$destination = if ([System.IO.Path]::IsPathRooted($OutputPath)) {
    [System.IO.Path]::GetFullPath($OutputPath)
} else {
    [System.IO.Path]::GetFullPath((Join-Path $projectRoot $OutputPath))
}
if (Test-Path -LiteralPath $destination) {
    throw "Output already exists; choose a new path: $destination"
}

if ($PasswordFile -and -not $Encrypt) {
    throw "-PasswordFile is only valid with -Encrypt"
}
$passwordPath = $null
if ($PasswordFile) {
    $passwordPath = (Resolve-Path -LiteralPath $PasswordFile).Path
    if (-not (Test-Path -LiteralPath $passwordPath -PathType Leaf)) {
        throw "PasswordFile must point to a private file: $passwordPath"
    }
}

$staging = Join-Path ([System.IO.Path]::GetTempPath()) ("catchthat-share-" + [guid]::NewGuid().ToString("N"))
$redactedArchive = Join-Path $staging "archive.safe.json"
$viewer = Join-Path $staging "viewer"
$plainBundle = Join-Path $staging "safe-share.catchthat.zip"
$previousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $projectRoot "src"

function Invoke-CatchThat {
    param([string[]]$Arguments)

    & python -m catchthat @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "CatchThat command failed with exit code $LASTEXITCODE"
    }
}

try {
    New-Item -ItemType Directory -Path $staging -Force | Out-Null
    Invoke-CatchThat @("redact", "--input", $archive, "--output", $redactedArchive)
    Invoke-CatchThat @("build", $redactedArchive, "--output", $viewer)
    Invoke-CatchThat @("verify", $viewer)
    Invoke-CatchThat @("export-bundle", "--input", $viewer, "--output", $plainBundle)

    if ($Encrypt) {
        $encryptArguments = @("encrypt-bundle", "--input", $plainBundle, "--output", $destination)
        if ($passwordPath) {
            $encryptArguments += @("--password-file", $passwordPath)
        }
        Invoke-CatchThat $encryptArguments
    } else {
        $destinationParent = Split-Path -Parent $destination
        New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null
        Move-Item -LiteralPath $plainBundle -Destination $destination
        Write-Output "Created redacted CatchThat bundle: $destination"
    }
}
finally {
    if ($previousPythonPath) {
        $env:PYTHONPATH = $previousPythonPath
    } else {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
    }
}
