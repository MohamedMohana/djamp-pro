use std::env;
use std::process::Command;

pub fn generate_password(length: usize) -> String {
    use rand::Rng;
    const CHARSET: &[u8] =
        b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*";
    let mut rng = rand::thread_rng();

    (0..length)
        .map(|_| {
            let idx = rng.gen_range(0..CHARSET.len());
            CHARSET[idx] as char
        })
        .collect()
}

pub fn hash_password(password: &str) -> Result<String, String> {
    use sha2::{Digest, Sha256};

    let mut hasher = Sha256::new();
    hasher.update(password.as_bytes());
    let result = hasher.finalize();

    Ok(format!("{:x}", result))
}

#[cfg(target_os = "macos")]
pub fn store_secret(service: &str, account: &str, secret: &str) -> Result<(), String> {
    Command::new("security")
        .args([
            "add-generic-password",
            "-a",
            account,
            "-s",
            service,
            "-w",
            secret,
            "-U",
        ])
        .output()
        .map_err(|e| format!("Failed to store secret: {}", e))?;

    Ok(())
}

#[cfg(target_os = "macos")]
pub fn get_secret(service: &str, account: &str) -> Result<String, String> {
    let output = Command::new("security")
        .args(["find-generic-password", "-a", account, "-s", service, "-w"])
        .output()
        .map_err(|e| format!("Failed to get secret: {}", e))?;

    if !output.status.success() {
        return Err("Secret not found".to_string());
    }

    String::from_utf8(output.stdout)
        .map(|s| s.trim().to_string())
        .map_err(|e| format!("Failed to parse secret: {}", e))
}

#[cfg(windows)]
pub fn store_secret(service: &str, account: &str, secret: &str) -> Result<(), String> {
    Command::new("cmdkey")
        .args([
            "/generic:*",
            &format!("/user:{}", account),
            &format!("/pass:{}", secret),
        ])
        .output()
        .map_err(|e| format!("Failed to store secret: {}", e))?;

    Ok(())
}

#[cfg(windows)]
pub fn get_secret(service: &str, account: &str) -> Result<String, String> {
    // Windows implementation would use Windows Credential Manager API
    Err("Windows secret retrieval not implemented yet".to_string())
}
