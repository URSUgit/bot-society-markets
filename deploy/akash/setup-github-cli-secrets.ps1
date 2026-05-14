param(
    [string]$Repo = "URSUgit/bot-society-markets",
    [string]$AkashMnemonic = $env:AKASH_CLI_MNEMONIC,
    [string]$AkashDseq = $env:AKASH_CLI_DSEQ,
    [string]$AkashProvider = $env:AKASH_CLI_PROVIDER,
    [string]$DatabaseUrl = $env:BSM_DATABASE_URL,
    [string]$YouTubeApiKey = $env:BSM_YOUTUBE_API_KEY,
    [switch]$IncludeDseq,
    [switch]$IncludeProvider,
    [switch]$IncludeYouTube
)

$ErrorActionPreference = "Stop"

function Assert-GitHubCliReady {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw "GitHub CLI is required. Install gh and run gh auth login first."
    }

    gh auth status 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub CLI is not authenticated. Run gh auth login, then retry."
    }
}

function Read-SecretValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [string]$ExistingValue,
        [switch]$Required
    )

    if ($ExistingValue) {
        return $ExistingValue
    }

    if (-not $Required) {
        return ""
    }

    $secure = Read-Host "Enter $Name" -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
}

function Set-RepoSecret {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [string]$Value
    )

    if (-not $Value) {
        return
    }

    $Value | gh secret set $Name --repo $Repo | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to set GitHub secret $Name."
    }
}

Assert-GitHubCliReady

Write-Output "This stores an Akash wallet mnemonic in GitHub Actions secrets for CLI deploys."
Write-Output "Use a dedicated deploy wallet with limited AKT, not your main wallet."

$resolvedMnemonic = Read-SecretValue -Name "AKASH_CLI_MNEMONIC" -ExistingValue $AkashMnemonic -Required
$resolvedDatabaseUrl = Read-SecretValue -Name "BSM_DATABASE_URL" -ExistingValue $DatabaseUrl -Required
$resolvedDseq = if ($IncludeDseq) { Read-SecretValue -Name "AKASH_CLI_DSEQ" -ExistingValue $AkashDseq -Required } else { $AkashDseq }
$resolvedProvider = if ($IncludeProvider) { Read-SecretValue -Name "AKASH_CLI_PROVIDER" -ExistingValue $AkashProvider -Required } else { $AkashProvider }
$resolvedYouTubeApiKey = if ($IncludeYouTube) { Read-SecretValue -Name "BSM_YOUTUBE_API_KEY" -ExistingValue $YouTubeApiKey -Required } else { $YouTubeApiKey }

Set-RepoSecret -Name "AKASH_CLI_MNEMONIC" -Value $resolvedMnemonic
Set-RepoSecret -Name "BSM_DATABASE_URL" -Value $resolvedDatabaseUrl
Set-RepoSecret -Name "AKASH_CLI_DSEQ" -Value $resolvedDseq
Set-RepoSecret -Name "AKASH_CLI_PROVIDER" -Value $resolvedProvider
Set-RepoSecret -Name "BSM_YOUTUBE_API_KEY" -Value $resolvedYouTubeApiKey

Write-Output "Akash CLI GitHub secrets updated for $Repo."
gh secret list --repo $Repo | Where-Object {
    $_ -match "^(AKASH_CLI_MNEMONIC|AKASH_CLI_DSEQ|AKASH_CLI_PROVIDER|BSM_DATABASE_URL|BSM_YOUTUBE_API_KEY)\s"
}
