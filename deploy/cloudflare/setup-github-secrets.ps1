param(
    [string]$Repo = "URSUgit/bot-society-markets",
    [string]$AccountId = "a906459201dc22d18e4d0acce7357bfc",
    [switch]$TriggerWorkflow
)

$ErrorActionPreference = "Stop"

function ConvertTo-PlainText {
    param([securestring]$SecureValue)

    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try {
        [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

Write-Host "Setting Cloudflare GitHub Actions secrets for $Repo..."

gh secret set CLOUDFLARE_ACCOUNT_ID --repo $Repo --body $AccountId | Out-Null

$secureToken = Read-Host "Paste Cloudflare API token for Worker deploy (input hidden)" -AsSecureString
$plainToken = ConvertTo-PlainText -SecureValue $secureToken
try {
    if ([string]::IsNullOrWhiteSpace($plainToken)) {
        throw "Cloudflare API token cannot be empty."
    }
    $plainToken | gh secret set CLOUDFLARE_API_TOKEN --repo $Repo | Out-Null
} finally {
    $plainToken = $null
    $secureToken.Dispose()
}

Write-Host "Cloudflare secrets now present:"
gh secret list --repo $Repo | Where-Object { $_ -match "^CLOUDFLARE_" }

if ($TriggerWorkflow) {
    Write-Host "Triggering Cloudflare Worker workflow..."
    gh workflow run cloudflare-worker.yml --repo $Repo --ref main
    Start-Sleep -Seconds 6
    $run = gh run list --repo $Repo --workflow cloudflare-worker.yml --limit 1 --json databaseId --jq ".[0].databaseId"
    if ($run) {
        gh run watch $run --repo $Repo --exit-status
    }
}
