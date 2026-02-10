use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::process::Command;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CertificateInfo {
    pub domain: String,
    pub certificate_path: String,
    pub key_path: String,
    pub expires_at: String,
    pub is_valid: bool,
}

pub async fn generate_certificate(domain: &str) -> Result<CertificateInfo, String> {
    let djamp_home = dirs::home_dir()
        .ok_or("Home directory not found")?
        .join(".djamp");
    
    let ca_dir = djamp_home.join("ca");
    let cert_dir = djamp_home.join("certs");
    
    let ca_cert = ca_dir.join("djamp-root-ca.crt");
    let ca_key = ca_dir.join("djamp-root-ca.key");
    
    if !ca_cert.exists() || !ca_key.exists() {
        return Err("Root CA not found. Please install Root CA first.".to_string());
    }
    
    let cert_key = cert_dir.join(format!("{}.key", domain));
    let cert_crt = cert_dir.join(format!("{}.crt", domain));
    
    fs::create_dir_all(&cert_dir).map_err(|e| format!("Failed to create cert directory: {}", e))?;
    
    // Generate private key
    Command::new("openssl")
        .args(["genrsa", "-out", cert_key.to_str().unwrap(), "2048"])
        .output()
        .map_err(|e| format!("Failed to generate private key: {}", e))?;
    
    // Generate CSR
    let config_file = cert_dir.join(format!("{}.conf", domain));
    let config_content = format!(
        r#"[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
CN = {}

[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = {}
DNS.2 = www.{}
"#,
        domain, domain, domain
    );
    
    std::fs::write(&config_file, config_content)
        .map_err(|e| format!("Failed to write config: {}", e))?;
    
    Command::new("openssl")
        .args([
            "req",
            "-new",
            "-key",
            cert_key.to_str().unwrap(),
            "-out",
            cert_dir.join(format!("{}.csr", domain)).to_str().unwrap(),
            "-config",
            config_file.to_str().unwrap(),
        ])
        .output()
        .map_err(|e| format!("Failed to generate CSR: {}", e))?;
    
    // Sign with CA
    Command::new("openssl")
        .args([
            "x509",
            "-req",
            "-in",
            cert_dir.join(format!("{}.csr", domain)).to_str().unwrap(),
            "-CA",
            ca_cert.to_str().unwrap(),
            "-CAkey",
            ca_key.to_str().unwrap(),
            "-CAcreateserial",
            "-out",
            cert_crt.to_str().unwrap(),
            "-days",
            "365",
            "-sha256",
            "-extensions",
            "v3_req",
            "-extfile",
            config_file.to_str().unwrap(),
        ])
        .output()
        .map_err(|e| format!("Failed to sign certificate: {}", e))?;
    
    // Clean up
    std::fs::remove_file(cert_dir.join(format!("{}.csr", domain))).ok();
    std::fs::remove_file(&config_file).ok();
    
    // Get expiration date
    let output = Command::new("openssl")
        .args(["x509", "-enddate", "-noout", "-in", cert_crt.to_str().unwrap()])
        .output()
        .map_err(|e| format!("Failed to get certificate expiration: {}", e))?;
    
    let expires_at = String::from_utf8_lossy(&output.stdout)
        .to_string()
        .replace("notAfter=", "")
        .trim()
        .to_string();
    
    Ok(CertificateInfo {
        domain: domain.to_string(),
        certificate_path: cert_crt.to_str().unwrap().to_string(),
        key_path: cert_key.to_str().unwrap().to_string(),
        expires_at,
        is_valid: true,
    })
}

pub async fn check_certificate_status(domain: &str) -> Result<CertificateInfo, String> {
    let djamp_home = dirs::home_dir()
        .ok_or("Home directory not found")?
        .join(".djamp");
    
    let cert_dir = djamp_home.join("certs");
    let cert_crt = cert_dir.join(format!("{}.crt", domain));
    let cert_key = cert_dir.join(format!("{}.key", domain));
    
    if !cert_crt.exists() || !cert_key.exists() {
        return Ok(CertificateInfo {
            domain: domain.to_string(),
            certificate_path: cert_crt.to_str().unwrap().to_string(),
            key_path: cert_key.to_str().unwrap().to_string(),
            expires_at: String::new(),
            is_valid: false,
        });
    }
    
    // Check validity
    let output = Command::new("openssl")
        .args(["x509", "-checkend", "0", "-in", cert_crt.to_str().unwrap()])
        .output()
        .map_err(|e| format!("Failed to check certificate: {}", e))?;
    
    let is_valid = output.status.success();
    
    // Get expiration date
    let output = Command::new("openssl")
        .args(["x509", "-enddate", "-noout", "-in", cert_crt.to_str().unwrap()])
        .output()
        .map_err(|e| format!("Failed to get certificate expiration: {}", e))?;
    
    let expires_at = String::from_utf8_lossy(&output.stdout)
        .to_string()
        .replace("notAfter=", "")
        .trim()
        .to_string();
    
    Ok(CertificateInfo {
        domain: domain.to_string(),
        certificate_path: cert_crt.to_str().unwrap().to_string(),
        key_path: cert_key.to_str().unwrap().to_string(),
        expires_at,
        is_valid,
    })
}

pub async fn install_root_ca() -> Result<(), String> {
    let djamp_home = dirs::home_dir()
        .ok_or("Home directory not found")?
        .join(".djamp");
    
    let ca_dir = djamp_home.join("ca");
    let ca_cert = ca_dir.join("djamp-root-ca.crt");
    let ca_key = ca_dir.join("djamp-root-ca.key");
    
    // Generate CA if it doesn't exist
    if !ca_cert.exists() || !ca_key.exists() {
        generate_root_ca(&ca_cert, &ca_key)?;
    }
    
    #[cfg(target_os = "macos")]
    {
        // Install to macOS Keychain
        let output = Command::new("sudo")
            .args([
                "security",
                "add-trusted-cert",
                "-d",
                "-r",
                "trustRoot",
                "-k",
                "/Library/Keychains/System.keychain",
                ca_cert.to_str().unwrap(),
            ])
            .output()
            .map_err(|e| format!("Failed to install Root CA: {}", e))?;
        
        if !output.status.success() {
            return Err(format!(
                "Failed to install Root CA: {}",
                String::from_utf8_lossy(&output.stderr)
            ));
        }
    }
    
    #[cfg(windows)]
    {
        // Install to Windows Certificate Store
        let output = Command::new("certutil")
            .args([
                "-addstore",
                "-f",
                "Root",
                ca_cert.to_str().unwrap(),
            ])
            .output()
            .map_err(|e| format!("Failed to install Root CA: {}", e))?;
        
        if !output.status.success() {
            return Err(format!(
                "Failed to install Root CA: {}",
                String::from_utf8_lossy(&output.stderr)
            ));
        }
    }
    
    Ok(())
}

pub async fn check_root_ca_status() -> Result<(bool, bool), String> {
    let djamp_home = dirs::home_dir()
        .ok_or("Home directory not found")?
        .join(".djamp");
    
    let ca_dir = djamp_home.join("ca");
    let ca_cert = ca_dir.join("djamp-root-ca.crt");
    
    if !ca_cert.exists() {
        return Ok((false, false));
    }
    
    #[cfg(target_os = "macos")]
    {
        let output = Command::new("security")
            .args([
                "find-certificate",
                "-c",
                "DJANGOForge",
                "/Library/Keychains/System.keychain",
            ])
            .output()
            .map_err(|e| format!("Failed to check Root CA: {}", e))?;
        
        let installed = output.status.success();
        
        // Check if trusted
        let output = Command::new("security")
            .args([
                "verify-cert",
                "-c",
                ca_cert.to_str().unwrap(),
            ])
            .output()
            .map_err(|e| format!("Failed to verify Root CA: {}", e))?;
        
        let valid = output.status.success();
        
        return Ok((installed, valid));
    }
    
    #[cfg(windows)]
    {
        let output = Command::new("certutil")
            .args([
                "-store",
                "Root",
                "DJANGOForge",
            ])
            .output()
            .map_err(|e| format!("Failed to check Root CA: {}", e))?;
        
        let installed = output.status.success();
        
        return Ok((installed, installed));
    }
    
    #[cfg(not(any(target_os = "macos", windows)))]
    {
        Ok((false, false))
    }
}

fn generate_root_ca(ca_cert: &Path, ca_key: &Path) -> Result<(), String> {
    let ca_dir = ca_cert.parent().ok_or("Invalid CA path")?;
    
    fs::create_dir_all(ca_dir).map_err(|e| format!("Failed to create CA directory: {}", e))?;
    
    Command::new("openssl")
        .args([
            "req",
            "-x509",
            "-newkey",
            "rsa:4096",
            "-keyout",
            ca_key.to_str().unwrap(),
            "-out",
            ca_cert.to_str().unwrap(),
            "-days",
            "3650",
            "-nodes",
            "-subj",
            "/C=US/ST=State/L=City/O=DJANGOForge/OU=Development/CN=DJANGOForge Root CA",
            "-addext",
            "basicConstraints=critical,CA:TRUE,pathlen:0",
            "-addext",
            "keyUsage=critical,keyCertSign,cRLSign",
        ])
        .output()
        .map_err(|e| format!("Failed to generate Root CA: {}", e))?;
    
    Ok(())
}
