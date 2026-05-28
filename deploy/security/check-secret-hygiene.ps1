param(
    [switch]$Strict
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Push-Location $repoRoot
try {
    $patterns = @(
        @{
            Name = "Neon-style password token"
            Pattern = "npg_[A-Za-z0-9_=-]{8,}"
        },
        @{
            Name = "Postgres URL with inline password"
            Pattern = "postgresql:\/\/[^:\s]+:[^@\s]+@[^)\s`"]+"
        },
        @{
            Name = "Google API key"
            Pattern = "AIza[0-9A-Za-z\-_]{20,}"
        },
        @{
            Name = "GitHub token"
            Pattern = "(ghp_|github_pat_)[0-9A-Za-z_]{20,}"
        },
        @{
            Name = "Stripe secret key"
            Pattern = "sk_(live|test)_[0-9A-Za-z]{16,}"
        },
        @{
            Name = "Private key block"
            Pattern = "BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY"
        }
    )

    $matches = @()
    foreach ($entry in $patterns) {
        $output = rg --hidden --glob "!.git/**" --glob "!*.pdf" --glob "!api/data/**" --glob "!deploy/akash/*.generated.yaml" --glob "!.venv/**" --glob "!.wrangler/**" --glob "!pytest-cache-files-*/**" -n -S $entry.Pattern . 2>$null
        if ($LASTEXITCODE -eq 0 -and $output) {
            foreach ($line in $output) {
                $matches += [pscustomobject]@{
                    Pattern = $entry.Name
                    Match = $line
                }
            }
        }
    }

    if ($matches.Count -eq 0) {
        Write-Output "Secret hygiene check passed. No high-risk secret patterns were found in tracked workspace text files."
        exit 0
    }

    $matches | Format-Table -AutoSize
    $message = "Secret hygiene check found $($matches.Count) potential issue(s). Rotate any exposed credentials and remove them before launch."
    if ($Strict) {
        throw $message
    }
    Write-Warning $message
} finally {
    Pop-Location
}
