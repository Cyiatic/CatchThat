[CmdletBinding()]
param(
    [string]$OutputPath = "dist\catchthat-release.zip"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$zipPath = if ([System.IO.Path]::IsPathRooted($OutputPath)) {
    [System.IO.Path]::GetFullPath($OutputPath)
} else {
    [System.IO.Path]::GetFullPath((Join-Path $projectRoot $OutputPath))
}
$staging = Join-Path ([System.IO.Path]::GetTempPath()) ("catchthat-release-" + [guid]::NewGuid().ToString("N"))
$releaseRoot = Join-Path $staging "catchthat"
$sampleOutput = Join-Path $releaseRoot "dist\sample"
$previousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $releaseRoot "src"

try {
    New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null
    foreach ($relative in @(".gitignore", "README.md", "PRODUCT.md", "DESIGN.md", "AGENTS.md", "security_best_practices_report.md", "pyproject.toml")) {
        Copy-Item -LiteralPath (Join-Path $projectRoot $relative) -Destination (Join-Path $releaseRoot $relative)
    }
    foreach ($relative in @(".github", "docs", "src", "viewer", "tools", "fixtures", "plugins", "scripts", "tests")) {
        Copy-Item -LiteralPath (Join-Path $projectRoot $relative) -Destination (Join-Path $releaseRoot $relative) -Recurse
    }

    & python -m catchthat validate (Join-Path $releaseRoot "fixtures\sample\archive.json")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & python -m catchthat build (Join-Path $releaseRoot "fixtures\sample\archive.json") --output $sampleOutput
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & python -m catchthat verify $sampleOutput
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Get-ChildItem -LiteralPath $releaseRoot -Recurse -Force -Directory |
        Where-Object { $_.Name -eq "__pycache__" -or $_.Name -eq ".pytest_cache" -or $_.Name -like "*.egg-info" } |
        Sort-Object FullName -Descending |
        Remove-Item -Recurse -Force
    Get-ChildItem -LiteralPath $releaseRoot -Recurse -Force -File |
        Where-Object { $_.Extension -in @(".pyc", ".pyo") } |
        Remove-Item -Force

    & python (Join-Path $releaseRoot "scripts\validate_public_package.py") --root $releaseRoot
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    $zipParent = Split-Path -Parent $zipPath
    New-Item -ItemType Directory -Path $zipParent -Force | Out-Null
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -Path (Join-Path $releaseRoot "*") -DestinationPath $zipPath -CompressionLevel Optimal
    Write-Output "Created source-only CatchThat release: $zipPath"
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
