use crate::privilege::{HostsEntry, CertificateInfo};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[tauri::command]
pub async fn add_domain(domain: String) -> Result<(), String> {
    let entry = HostsEntry {
        ip: "127.0.0.1".to_string(),
        hostname: domain.clone(),
        aliases: vec![],
    };
    
    crate::privilege::add_hosts_entry(&entry).await
}

#[tauri::command]
pub async fn remove_domain(domain: String) -> Result<(), String> {
    crate::privilege::remove_hosts_entry(&domain).await
}

#[tauri::command]
pub async fn generate_certificate(domain: String) -> Result<CertificateInfo, String> {
    crate::privilege::generate_certificate(&domain).await
}

#[tauri::command]
pub async fn check_certificate_status(domain: String) -> Result<CertificateInfo, String> {
    crate::privilege::check_certificate_status(&domain).await
}

#[tauri::command]
pub async fn install_root_ca() -> Result<(), String> {
    crate::privilege::install_root_ca().await
}

#[tauri::command]
pub async fn check_root_ca_status() -> Result<serde_json::Value, String> {
    let (installed, valid) = crate::privilege::check_root_ca_status().await?;
    Ok(serde_json::json!({
        "installed": installed,
        "valid": valid
    }))
}
