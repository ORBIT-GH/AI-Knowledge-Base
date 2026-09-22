param(
    [string]$Version = "0.2.9"
)

$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $Repo

try {
    if (git status --porcelain) {
        throw "Working tree is not clean. Commit or stash changes before building a release."
    }

    uv sync --extra dev
    uv run pytest
    uv run python -m compileall -q src tests
    uv build

    New-Item -ItemType Directory -Force dist | Out-Null
    $SourceZip = Join-Path $Repo "dist\futures-ai-kb-v$Version-source.zip"
    git archive --format=zip --output=$SourceZip HEAD

    Write-Host ""
    Write-Host "Release artifacts:"
    Get-ChildItem dist | Select-Object Name, Length
}
finally {
    Pop-Location
}
