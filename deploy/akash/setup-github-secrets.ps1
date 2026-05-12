param(
    [string]$Repo = "URSUgit/bot-society-markets",
    [string]$AkashApiKey = $env:AKASH_API_KEY,
    [string]$AkashDseq = $env:AKASH_DSEQ,
    [string]$DatabaseUrl = $env:BSM_DATABASE_URL,
    [string]$YouTubeApiKey = $env:BSM_YOUTUBE_API_KEY,
    [switch]$IncludeYouTube,
    [switch]$NonInteractive
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

function Convert-SecureStringToPlainText {
    param([Parameter(Mandatory = $true)][securestring]$SecureValue)

    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try {
        [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function Read-SecretValue {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [string]$ExistingValue,
        [switch]$Required
    )

    if ($ExistingValue) {
        return $ExistingValue
    }

    if ($NonInteractive) {
        if ($Required) {
            throw "$Name is required but was not provided through a parameter or environment variable."
        }
        return ""
    }

    if ($Required) {
        $secureValue = Read-Host "Enter $Name" -AsSecureString
        return Convert-SecureStringToPlainText -SecureValue $secureValue
    }

    $plainValue = Read-Host "Enter optional $Name, or press Enter to skip"
    return $plainValue
}

function Set-RepoSecret {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Value
    )

    if (-not $Value) {
        Write-Output "Skipped $Name because no value was provided."
        return
    }

    $Value | gh secret set $Name --repo $Repo | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to set GitHub secret $Name."
    }
    Write-Output "Configured GitHub secret: $Name"
}

Assert-GitHubCliReady

$resolvedAkashApiKey = Read-SecretValue -Name "AKASH_API_KEY" -ExistingValue $AkashApiKey -Required
$resolvedAkashDseq = Read-SecretValue -Name "AKASH_DSEQ" -ExistingValue $AkashDseq -Required
$resolvedDatabaseUrl = Read-SecretValue -Name "BSM_DATABASE_URL" -ExistingValue $DatabaseUrl -Required
$resolvedYouTubeApiKey = ""
if ($IncludeYouTube -or $YouTubeApiKey) {
    $resolvedYouTubeApiKey = Read-SecretValue -Name "BSM_YOUTUBE_API_KEY" -ExistingValue $YouTubeApiKey
}

Set-RepoSecret -Name "AKASH_API_KEY" -Value $resolvedAkashApiKey
Set-RepoSecret -Name "AKASH_DSEQ" -Value $resolvedAkashDseq
Set-RepoSecret -Name "BSM_DATABASE_URL" -Value $resolvedDatabaseUrl
if ($resolvedYouTubeApiKey) {
    Set-RepoSecret -Name "BSM_YOUTUBE_API_KEY" -Value $resolvedYouTubeApiKey
}

Write-Output ""
Write-Output "Current deployment secrets registered in ${Repo}:"
gh secret list --repo $Repo | Where-Object {
    $_ -match "^(AKASH_API_KEY|AKASH_DSEQ|BSM_DATABASE_URL|BSM_YOUTUBE_API_KEY)\s"
}
