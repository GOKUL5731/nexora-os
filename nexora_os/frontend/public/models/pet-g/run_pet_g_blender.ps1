param(
    [string]$BlenderPath = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Generator = Join-Path $ScriptDir "make_pet_g_blender.py"

function Find-Blender {
    param([string]$ExplicitPath)

    if ($ExplicitPath -and (Test-Path -LiteralPath $ExplicitPath)) {
        return (Resolve-Path -LiteralPath $ExplicitPath).Path
    }

    $cmd = Get-Command blender -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    $candidates = @(
        "$env:ProgramFiles\Blender Foundation\Blender 4.5\blender.exe",
        "$env:ProgramFiles\Blender Foundation\Blender 4.4\blender.exe",
        "$env:ProgramFiles\Blender Foundation\Blender 4.3\blender.exe",
        "$env:ProgramFiles\Blender Foundation\Blender 4.2\blender.exe",
        "$env:ProgramFiles\Blender Foundation\Blender 4.1\blender.exe",
        "$env:ProgramFiles\Blender Foundation\Blender 4.0\blender.exe",
        "${env:ProgramFiles(x86)}\Blender Foundation\Blender 4.5\blender.exe",
        "${env:ProgramFiles(x86)}\Blender Foundation\Blender 4.4\blender.exe",
        "${env:ProgramFiles(x86)}\Blender Foundation\Blender 4.3\blender.exe",
        "${env:ProgramFiles(x86)}\Blender Foundation\Blender 4.2\blender.exe",
        "${env:LOCALAPPDATA}\Microsoft\WinGet\Packages\BlenderFoundation.Blender_Microsoft.Winget.Source_8wekyb3d8bbwe\blender.exe"
    )

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    return ""
}

if (!(Test-Path -LiteralPath $Generator)) {
    throw "Missing generator script: $Generator"
}

$ResolvedBlender = Find-Blender -ExplicitPath $BlenderPath
if (!$ResolvedBlender) {
    Write-Host ""
    Write-Host "Blender was not found on PATH or in common Windows install folders." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Install Blender with one of these options:" -ForegroundColor Cyan
    Write-Host "  winget install --id BlenderFoundation.Blender -e" -ForegroundColor White
    Write-Host "  or download from https://www.blender.org/download/" -ForegroundColor White
    Write-Host ""
    Write-Host "If Blender is already installed, run this script with the full path:" -ForegroundColor Cyan
    Write-Host '  .\run_pet_g_blender.ps1 -BlenderPath "C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"' -ForegroundColor White
    exit 1
}

Write-Host "Using Blender: $ResolvedBlender" -ForegroundColor Green
Push-Location $ScriptDir
try {
    & $ResolvedBlender --background --python $Generator
    if ($LASTEXITCODE -ne 0) {
        throw "Blender exited with code $LASTEXITCODE"
    }
    Write-Host ""
    Write-Host "Pet G Blender model generated:" -ForegroundColor Green
    Write-Host "  $(Join-Path $ScriptDir 'pet_g.blend')"
    Write-Host "  $(Join-Path $ScriptDir 'pet_g.glb')"
    Write-Host "  $(Join-Path $ScriptDir 'pet_g_preview.png')"
}
finally {
    Pop-Location
}
