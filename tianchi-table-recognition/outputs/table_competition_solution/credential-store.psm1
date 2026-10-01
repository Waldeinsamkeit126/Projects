Set-StrictMode -Version Latest
$script:StoreDirectory = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../.private'))
$script:StoreFileName = 'tianchi-bailian.dpapi'
$script:Entropy = [Text.Encoding]::UTF8.GetBytes('tianchi-qwen-credential-v1')

function Assert-TianchiWindows {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'Credential storage requires Windows DPAPI; no plaintext fallback is permitted.'
    }
    Add-Type -AssemblyName System.Security -ErrorAction Stop
}

function Assert-TianchiSaveContext([string]$IdentityName = [Security.Principal.WindowsIdentity]::GetCurrent().Name) {
    # Codex uses a different Windows identity for network-enabled commands.
    # Saving under Offline would create a valid but unusable online credential.
    if ($IdentityName -match '(^|\\)CodexSandboxOffline$') {
        throw 'Enable approved network access before saving: CodexSandboxOffline cannot create a credential usable by CodexSandboxOnline. Clipboard was not read.'
    }
}

function Assert-TianchiEndpoint([string]$BaseUrl) {
    $uri = $null
    if (-not [Uri]::TryCreate($BaseUrl, [UriKind]::Absolute, [ref]$uri) -or
        $uri.Scheme -ne 'https' -or $uri.Port -ne 443 -or $uri.UserInfo -or $uri.Query -or $uri.Fragment -or
        $uri.Host -cnotmatch '^(?:dashscope(?:-intl)?\.aliyuncs\.com|[a-z0-9-]+\.cn-beijing\.maas\.aliyuncs\.com)$' -or
        $uri.AbsolutePath.TrimEnd('/') -ne '/compatible-mode/v1') {
        throw 'The credential endpoint must be an approved Alibaba Cloud HTTPS endpoint.'
    }
}

function Assert-TianchiPrivatePath([string]$Path, [bool]$IsDirectory) {
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    if ($item.PSIsContainer -ne $IsDirectory -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Credential path is not a regular local file/directory.'
    }
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $acl = Get-Acl -LiteralPath $Path -ErrorAction Stop
    if ($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $sid.Value -or -not $acl.AreAccessRulesProtected) {
        throw 'Credential permissions do not match the current Windows account.'
    }
    $rules = @($acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
    if ($rules.Count -ne 1 -or $rules[0].IdentityReference.Value -ne $sid.Value -or
        $rules[0].AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
        $rules[0].FileSystemRights -ne [Security.AccessControl.FileSystemRights]::FullControl) {
        throw 'Credential ACL must grant access only to the current Windows account.'
    }
}

function Set-TianchiPrivateAcl([string]$Path, [bool]$IsDirectory) {
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    if ($IsDirectory) {
        $acl = [Security.AccessControl.DirectorySecurity]::new()
        $rule = [Security.AccessControl.FileSystemAccessRule]::new($sid, 'FullControl', 'ContainerInherit, ObjectInherit', 'None', 'Allow')
    } else {
        $acl = [Security.AccessControl.FileSecurity]::new()
        $rule = [Security.AccessControl.FileSystemAccessRule]::new($sid, 'FullControl', 'Allow')
    }
    $acl.SetOwner($sid)
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule($rule)
    Set-Acl -LiteralPath $Path -AclObject $acl -ErrorAction Stop
    Assert-TianchiPrivatePath $Path $IsDirectory
}

function Read-TianchiStoredCredential {
    Assert-TianchiWindows
    $bytes = $null; $payloadText = $null; $payload = $null; $secureKey = $null
    try {
        Assert-TianchiPrivatePath $script:StoreDirectory $true
        $file = Join-Path $script:StoreDirectory $script:StoreFileName
        Assert-TianchiPrivatePath $file $false
        if ((Get-Item -LiteralPath $file).Length -gt 65536) { throw 'Oversized credential file.' }
        $cipher = [IO.File]::ReadAllBytes($file)
        $bytes = [Security.Cryptography.ProtectedData]::Unprotect($cipher, $script:Entropy, [Security.Cryptography.DataProtectionScope]::CurrentUser)
        $payloadText = [Text.Encoding]::UTF8.GetString($bytes)
        $payload = $payloadText | ConvertFrom-Json -ErrorAction Stop
        if ($payload.schema -ne 1 -or $payload.apiKey -isnot [string] -or $payload.apiKey -cnotmatch '^sk-[A-Za-z0-9._-]{20,}$') {
            throw 'Invalid credential payload.'
        }
        Assert-TianchiEndpoint $payload.baseUrl
        $secureKey = ConvertTo-SecureString -String $payload.apiKey -AsPlainText -Force
        # Returning SecureString instead of plaintext also prevents accidental display of the key.
        [pscustomobject]@{ SecureKey = $secureKey; BaseUrl = [string]$payload.baseUrl; Source = 'windows-dpapi-current-user' }
    } catch {
        if ($secureKey) { $secureKey.Dispose() }
        throw 'Stored credential could not be loaded. Check Windows account, file permissions, or replace the credential. No plaintext fallback was used.'
    } finally {
        if ($bytes) { [Array]::Clear($bytes, 0, $bytes.Length) }
        $payload = $null; $payloadText = $null
    }
}

function Save-TianchiCredentialCore([string]$Key, [string]$BaseUrl) {
    Assert-TianchiWindows
    if ($Key -cnotmatch '^sk-[A-Za-z0-9._-]{20,}$') { throw 'Clipboard does not contain a supported API key format.' }
    Assert-TianchiEndpoint $BaseUrl
    $file = Join-Path $script:StoreDirectory $script:StoreFileName
    if (Test-Path -LiteralPath $file -ErrorAction Stop) { throw 'An encrypted credential already exists; it was not overwritten.' }
    if (-not (Test-Path -LiteralPath $script:StoreDirectory -ErrorAction Stop)) {
        New-Item -ItemType Directory -Path $script:StoreDirectory -ErrorAction Stop | Out-Null
        Set-TianchiPrivateAcl $script:StoreDirectory $true
    } else {
        # Do not silently change permissions on a pre-existing directory.
        Assert-TianchiPrivatePath $script:StoreDirectory $true
    }
    $payloadText = $null; $bytes = $null; $stream = $null; $readback = $null
    $created = $false; $verified = $false; $pointer = [IntPtr]::Zero
    try {
        $payloadText = @{ schema = 1; apiKey = $Key; baseUrl = $BaseUrl.TrimEnd('/'); createdAt = [DateTime]::UtcNow.ToString('o') } | ConvertTo-Json -Compress
        $bytes = [Text.Encoding]::UTF8.GetBytes($payloadText)
        $cipher = [Security.Cryptography.ProtectedData]::Protect($bytes, $script:Entropy, [Security.Cryptography.DataProtectionScope]::CurrentUser)
        # Only encrypted bytes reach disk, including during a partial write.
        $stream = [IO.File]::Open($file, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        $created = $true
        $stream.Write($cipher, 0, $cipher.Length)
        $stream.Flush($true)
        $stream.Dispose(); $stream = $null
        Set-TianchiPrivateAcl $file $false
        $readback = Read-TianchiStoredCredential
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToGlobalAllocUnicode($readback.SecureKey)
        if ([Runtime.InteropServices.Marshal]::PtrToStringUni($pointer) -cne $Key -or $readback.BaseUrl -cne $BaseUrl.TrimEnd('/')) {
            throw 'Credential verification failed.'
        }
        $verified = $true
        [pscustomobject]@{ Saved = $true; Verified = $true; Protection = 'Windows DPAPI CurrentUser'; RestrictedAcl = $true }
    } catch {
        throw 'Encrypted credential save failed. No existing credential was overwritten and no plaintext file was created.'
    } finally {
        if ($stream) { $stream.Dispose() }
        if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeGlobalAllocUnicode($pointer) }
        if ($readback) { $readback.SecureKey.Dispose() }
        if ($bytes) { [Array]::Clear($bytes, 0, $bytes.Length) }
        $payloadText = $null; $Key = $null
        if ($created -and -not $verified) { [IO.File]::Delete($file) }
    }
}

function Save-TianchiCredentialFromClipboard([string]$BaseUrl) {
    Assert-TianchiWindows
    Assert-TianchiSaveContext
    $key = $null; $current = $null
    try {
        $key = Get-Clipboard -Raw -ErrorAction Stop
        if ($key -isnot [string]) { throw 'Clipboard does not contain text.' }
        $key = $key.Trim()
        $result = Save-TianchiCredentialCore $key $BaseUrl
        $current = Get-Clipboard -Raw -ErrorAction SilentlyContinue
        $cleared = $false
        if ($current -is [string] -and $current.Trim() -ceq $key) {
            try { Set-Clipboard -Value '' -ErrorAction Stop; $cleared = $true }
            catch { $cleared = $false }
        }
        $result | Add-Member -NotePropertyName CurrentClipboardCleared -NotePropertyValue $cleared -PassThru
    } finally { $key = $null; $current = $null }
}

function Get-TianchiCredentialStatus {
    $file = Join-Path $script:StoreDirectory $script:StoreFileName
    try { $exists = Test-Path -LiteralPath $file -ErrorAction Stop }
    catch { throw 'Credential status is inaccessible under this Windows account. Use the same network-enabled execution account that saved it; no missing-credential fallback was used.' }
    [pscustomobject]@{ Exists = $exists; Path = $file; ExpectedProtection = 'Windows DPAPI CurrentUser' }
}

Export-ModuleMember -Function Read-TianchiStoredCredential,Save-TianchiCredentialFromClipboard,Get-TianchiCredentialStatus
