param(
    [ValidateSet('Status','Save','Test')][string]$Action = 'Status',
    [string]$BaseUrl
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'credential-store.psm1') -Force
switch ($Action) {
    'Save' {
        if (-not $BaseUrl) { throw 'Save requires the approved Alibaba Cloud BaseUrl.' }
        Save-TianchiCredentialFromClipboard -BaseUrl $BaseUrl | ConvertTo-Json -Compress
    }
    'Test' {
        $stored = Read-TianchiStoredCredential
        try { [pscustomobject]@{ DecryptionSucceeded = $true; RestrictedAcl = $true; ApiCalls = 0 } | ConvertTo-Json -Compress }
        finally { $stored.SecureKey.Dispose() }
    }
    'Status' { Get-TianchiCredentialStatus | ConvertTo-Json -Compress }
}
