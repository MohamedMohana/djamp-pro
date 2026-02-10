use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use anyhow::{Context, Result};
use tokio::fs;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Project {
    pub id: String,
    pub name: String,
    pub path: String,
    pub settings_module: String,
    pub domain: String,
    pub aliases: Vec<String>,
    pub port: u16,
    pub python_version: String,
    pub venv_path: String,
    pub debug: bool,
    pub allowed_hosts: Vec<String>,
    pub https_enabled: bool,
    pub certificate_path: String,
    pub static_path: String,
    pub media_path: String,
    pub database: DatabaseConfig,
    pub cache: CacheConfig,
    pub status: String,
    pub environment_vars: HashMap<String, String>,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DatabaseConfig {
    #[serde(rename = "type")]
    pub type_: String,
    pub port: u16,
    pub name: String,
    pub username: String,
    pub password: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheConfig {
    #[serde(rename = "type")]
    pub type_: String,
    pub port: u16,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppSettings {
    pub ca_installed: bool,
    pub default_python: String,
    pub auto_start_projects: Vec<String>,
    pub proxy_port: u16,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Config {
    pub projects: HashMap<String, Project>,
    pub settings: AppSettings,
}

pub struct ConfigManager {
    config_path: PathBuf,
    config: Config,
}

impl ConfigManager {
    pub async fn new() -> Result<Self> {
        let djamp_home = dirs::home_dir()
            .context("Home directory not found")?
            .join(".djamp");
        
        fs::create_dir_all(&djamp_home)
            .await
            .context("Failed to create DJAMP directory")?;
        
        let config_path = djamp_home.join("config.json");
        
        let config = if config_path.exists() {
            let content = fs::read_to_string(&config_path)
                .await
                .context("Failed to read config file")?;
            serde_json::from_str(&content)
                .context("Failed to parse config file")?
        } else {
            let default_config = Config {
                projects: HashMap::new(),
                settings: AppSettings {
                    ca_installed: false,
                    default_python: "3.11".to_string(),
                    auto_start_projects: vec![],
                    proxy_port: 80,
                },
            };
            Self::save_config(&config_path, &default_config).await?;
            default_config
        };
        
        Ok(Self {
            config_path,
            config,
        })
    }
    
    pub async fn get_projects(&self) -> Result<Vec<Project>> {
        Ok(self.config.projects.values().cloned().collect())
    }
    
    pub async fn add_project(&mut self, mut project: Project) -> Result<()> {
        project.id = Uuid::new_v4().to_string();
        project.created_at = chrono::Utc::now().to_rfc3339();
        project.status = "stopped".to_string();
        
        self.config.projects.insert(project.id.clone(), project);
        Self::save_config(&self.config_path, &self.config).await?;
        Ok(())
    }
    
    pub async fn update_project(&mut self, id: &str, updates: serde_json::Value) -> Result<()> {
        if let Some(project) = self.config.projects.get_mut(id) {
            if let Some(name) = updates.get("name").and_then(|v| v.as_str()) {
                project.name = name.to_string();
            }
            if let Some(domain) = updates.get("domain").and_then(|v| v.as_str()) {
                project.domain = domain.to_string();
            }
            if let Some(port) = updates.get("port").and_then(|v| v.as_u64()) {
                project.port = port as u16;
            }
            // Add more fields as needed
            
            Self::save_config(&self.config_path, &self.config).await?;
        }
        Ok(())
    }
    
    pub async fn delete_project(&mut self, id: &str) -> Result<()> {
        self.config.projects.remove(id);
        Self::save_config(&self.config_path, &self.config).await?;
        Ok(())
    }
    
    fn save_config(config_path: &PathBuf, config: &Config) -> Result<()> {
        let content = serde_json::to_string_pretty(config)
            .context("Failed to serialize config")?;
        std::fs::write(config_path, content)
            .context("Failed to write config file")?;
        Ok(())
    }
    
    pub fn get_settings(&self) -> Result<AppSettings> {
        Ok(self.config.settings.clone())
    }
    
    pub fn update_settings(&mut self, settings: serde_json::Value) -> Result<()> {
        if let Some(ca_installed) = settings.get("caInstalled").and_then(|v| v.as_bool()) {
            self.config.settings.ca_installed = ca_installed;
        }
        if let Some(default_python) = settings.get("defaultPython").and_then(|v| v.as_str()) {
            self.config.settings.default_python = default_python.to_string();
        }
        Self::save_config(&self.config_path, &self.config)?;
        Ok(())
    }
}
