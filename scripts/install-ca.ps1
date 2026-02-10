# scripts/install-ca.ps1

Write-Host "🔐 DJANGOForge - Root CA Installation (Windows)" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

$DJAMP_HOME = "$env:USERPROFILE\.djamp"
$CA_DIR = "$DJAMP_HOME\ca"
$CA_CERT = "$CA_DIR\djangoforge-root-ca.crt"
$CA_KEY = "$CA_DIR\djangoforge-root-ca.key"
$DAYS = 3650

# Check if CA already exists
if (Test-Path $CA_CERT) {
    Write-Host "⚠️  Root CA already exists at $CA_CERT" -ForegroundColor Yellow
    $regenerate = Read-Host "Regenerate CA? (y/N)"
    if ($regenerate -ne 'y' -and $regenerate -ne 'Y') {
        exit 0
    }
}

# Create directory
New-Item -ItemType Directory -Force -Path $CA_DIR | Out-Null

# Generate Root CA
Write-Host "📝 Generating Root CA certificate..."
openssl req -x509 -newkey rsa:4096 -keyout $CA_KEY -out $CA_CERT -days $DAYS -nodes `
    -subj "/C=US/ST=State/L=City/O=DJANGOForge/OU=Development/CN=DJANGOForge Root CA" `
    -addext "basicConstraints=critical,CA:TRUE,pathlen:0" `
    -addext "keyUsage=critical,keyCertSign,cRLSign"

# Install to Windows Certificate Store (requires admin)
Write-Host "🔑 Installing Root CA to Trusted Root Certification Authorities..."
Write-Host "⚠️  This requires administrator privileges" -ForegroundColor Yellow
Write-Host "Approve the UAC prompt when it appears"

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    # Relaunch with admin privileges
    Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

# Import certificate
$cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2
$cert.Import($CA_CERT)

$store = New-Object System.Security.Cryptography.X509Certificates.X509Store([System.Security.Cryptography.X509Certificates.StoreName]::Root, [System.Security.Cryptography.X509Certificates.StoreLocation]::LocalMachine)
$store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
try {
    $store.Add($cert)
    Write-Host "✅ Root CA installed successfully!" -ForegroundColor Green
    Write-Host "📁 Certificate location: $CA_CERT"
    Write-Host "🎉 You can now issue trusted certificates for .test domains"
} finally {
    $store.Close()
}
