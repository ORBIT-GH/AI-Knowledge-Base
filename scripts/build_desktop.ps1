param(
    [switch]$InstallBuildDeps
)

$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $Repo

try {
    if ($InstallBuildDeps) {
        uv sync --extra dev --extra desktop
    }
    uv run pytest
    if ($LASTEXITCODE -ne 0) { throw "pytest failed" }

    $Dist = Join-Path $Repo "dist\desktop"
    $Work = Join-Path $Repo "build\desktop"
    $Spec = Join-Path $Repo "build\desktop"
    New-Item -ItemType Directory -Force $Dist, $Work, $Spec | Out-Null

    uv run pyinstaller `
        --noconfirm `
        --clean `
        --onefile `
        --windowed `
        --name AIKnowledgeBase `
        --icon (Join-Path $Repo "src\futures_kb\resources\ai-knowledge.ico") `
        --add-data (Join-Path $Repo "src\futures_kb\resources\ai-knowledge.ico");futures_kb\resources `
        --distpath $Dist `
        --workpath $Work `
        --specpath $Spec `
        (Join-Path $Repo "src\futures_kb\desktop.py")

    Write-Host ""
    Get-Item (Join-Path $Dist "AIKnowledgeBase.exe") | Select-Object FullName, Length, LastWriteTime
}
finally {
    Pop-Location
}
