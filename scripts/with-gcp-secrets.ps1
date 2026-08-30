[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Command,
    [string[]]$CommandArgs = @(),
    [string]$Project = $env:GOOGLE_CLOUD_PROJECT,
    [hashtable]$Secrets = @{ WOKWI_CLI_TOKEN = "wokwi-cli-token" }
)

$ErrorActionPreference = "Stop"
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    throw "gcloud CLI is required. Install it and run: gcloud auth login"
}

$previous = @{}
try {
    foreach ($entry in $Secrets.GetEnumerator()) {
        $previous[$entry.Key] = [Environment]::GetEnvironmentVariable($entry.Key, "Process")
        $arguments = @("secrets", "versions", "access", "latest", "--secret=$($entry.Value)")
        if ($Project) { $arguments += "--project=$Project" }
        $value = & gcloud @arguments
        if ($LASTEXITCODE -ne 0) { throw "Unable to access Secret Manager secret '$($entry.Value)'." }
        [Environment]::SetEnvironmentVariable($entry.Key, ($value -join "`n").Trim(), "Process")
    }
    & $Command @CommandArgs
    exit $LASTEXITCODE
}
finally {
    foreach ($entry in $Secrets.GetEnumerator()) {
        [Environment]::SetEnvironmentVariable($entry.Key, $previous[$entry.Key], "Process")
    }
}
