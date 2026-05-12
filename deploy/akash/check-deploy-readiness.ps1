param(
    [string]$Repo = "URSUgit/bot-society-markets",
    [string]$ImageRef,
    [switch]$VerifyProduction
)

$ErrorActionPreference = "Stop"

function Get-CurrentImageRef {
    $repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $shortSha = (git -C $repoRoot rev-parse --short=7 HEAD | Out-String).Trim()
    if (-not $shortSha) {
        return ""
    }
    return "ghcr.io/ursugit/bot-society-markets:sha-$shortSha"
}

function Test-GhReady {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        return $false
    }
    gh auth status 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
}

$resolvedImageRef = if ($ImageRef) { $ImageRef.Trim() } else { Get-CurrentImageRef }
$requiredSecrets = @("AKASH_API_KEY", "AKASH_DSEQ", "BSM_DATABASE_URL")
$optionalSecrets = @("BSM_YOUTUBE_API_KEY")

$rows = [System.Collections.Generic.List[object]]::new()

$ghReady = Test-GhReady
$rows.Add([pscustomobject]@{
    Check = "GitHub CLI authenticated"
    Status = if ($ghReady) { "pass" } else { "fail" }
    Detail = if ($ghReady) { "gh auth is ready" } else { "Install gh and run gh auth login" }
})

if ($ghReady) {
    $secretList = gh secret list --repo $Repo | ForEach-Object {
        ($_ -split "\s+")[0]
    }
    foreach ($secret in $requiredSecrets) {
        $rows.Add([pscustomobject]@{
            Check = "Secret $secret"
            Status = if ($secretList -contains $secret) { "pass" } else { "missing" }
            Detail = if ($secretList -contains $secret) { "configured" } else { "run deploy\akash\setup-github-secrets.ps1" }
        })
    }
    foreach ($secret in $optionalSecrets) {
        $rows.Add([pscustomobject]@{
            Check = "Optional secret $secret"
            Status = if ($secretList -contains $secret) { "pass" } else { "optional" }
            Detail = if ($secretList -contains $secret) { "configured" } else { "only needed for YouTube live discovery" }
        })
    }

    if ($resolvedImageRef -match ":sha-(?<ShortSha>[0-9a-f]{7,})$") {
        $shortSha = $Matches.ShortSha
        $runs = gh run list --repo $Repo --workflow "Container Image" --branch main --limit 20 --json headSha,status,conclusion,url | ConvertFrom-Json
        $imageRun = @($runs | Where-Object { $_.headSha -like "$shortSha*" } | Select-Object -First 1)
        $rows.Add([pscustomobject]@{
            Check = "Container image $resolvedImageRef"
            Status = if ($imageRun -and $imageRun.status -eq "completed" -and $imageRun.conclusion -eq "success") { "pass" } else { "attention" }
            Detail = if ($imageRun) { "$($imageRun.status)/$($imageRun.conclusion) $($imageRun.url)" } else { "no image workflow run found for this SHA" }
        })
    } else {
        $rows.Add([pscustomobject]@{
            Check = "Container image"
            Status = "skipped"
            Detail = "image ref is not an immutable sha tag"
        })
    }
}

$rows | Format-Table -AutoSize

if ($VerifyProduction) {
    $repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $verifyScript = Join-Path $repoRoot "deploy\verify-production.ps1"
    & $verifyScript -ExpectOperatorStrip -ExpectSocialTrading
}

