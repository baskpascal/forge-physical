[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Project,
    [string]$Secret = "wokwi-cli-token"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    throw "gcloud CLI is required. Install it and authenticate before rotating the token."
}

& gcloud projects describe $Project --format="value(projectId)" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "The active gcloud account cannot access project '$Project'."
}

$secureToken = Read-Host "Paste the 44-character Wokwi CI token (input is hidden)" -AsSecureString
$tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
try {
    $plainToken = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer)
    if (-not $plainToken.StartsWith("wok_") -or $plainToken.Length -ne 44) {
        throw "Invalid token envelope. Expected a 44-character Wokwi CI token beginning with 'wok_'."
    }

    $plainToken | & gcloud secrets versions add $Secret --data-file=- --project=$Project
    if ($LASTEXITCODE -ne 0) {
        throw "gcloud could not add the Secret Manager version."
    }
}
finally {
    if ($plainToken) { $plainToken = $null }
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer)
}

Write-Host "Wokwi CI token rotated in Secret Manager. The next worker execution will use the latest version."
