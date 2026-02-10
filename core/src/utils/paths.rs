use std::env;
use std::path::PathBuf;

pub fn get_djamp_home() -> Result<PathBuf, String> {
    dirs::home_dir()
        .map(|h| h.join(".djamp"))
        .ok_or_else(|| "Home directory not found".to_string())
}

pub fn get_projects_dir() -> Result<PathBuf, String> {
    get_djamp_home().map(|p| p.join("projects"))
}

pub fn get_venvs_dir() -> Result<PathBuf, String> {
    get_djamp_home().map(|p| p.join("venvs"))
}

pub fn get_certs_dir() -> Result<PathBuf, String> {
    get_djamp_home().map(|p| p.join("certs"))
}

pub fn get_logs_dir() -> Result<PathBuf, String> {
    get_djamp_home().map(|p| p.join("logs"))
}
