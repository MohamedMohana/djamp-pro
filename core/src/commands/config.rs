use std::sync::Mutex;
use tauri::State;
use crate::storage::{ConfigManager, Project, AppSettings};

#[tauri::command]
pub async fn get_projects(
    config: State<'_, Mutex<ConfigManager>>
) -> Result<Vec<Project>, String> {
    let config = config.lock().map_err(|e| format!("Lock error: {}", e))?;
    config.get_projects().await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn add_project(
    config: State<'_, Mutex<ConfigManager>>,
    project: Project,
) -> Result<(), String> {
    let mut config = config.lock().map_err(|e| format!("Lock error: {}", e))?;
    config.add_project(project).await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn update_project(
    config: State<'_, Mutex<ConfigManager>>,
    id: String,
    updates: serde_json::Value,
) -> Result<(), String> {
    let mut config = config.lock().map_err(|e| format!("Lock error: {}", e))?;
    config.update_project(&id, updates).await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn delete_project(
    config: State<'_, Mutex<ConfigManager>>,
    id: String,
) -> Result<(), String> {
    let mut config = config.lock().map_err(|e| format!("Lock error: {}", e))?;
    config.delete_project(&id).await.map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn get_settings(
    config: State<'_, Mutex<ConfigManager>>
) -> Result<AppSettings, String> {
    let config = config.lock().map_err(|e| format!("Lock error: {}", e))?;
    config.get_settings().map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn update_settings(
    config: State<'_, Mutex<ConfigManager>>,
    settings: serde_json::Value,
) -> Result<(), String> {
    let mut config = config.lock().map_err(|e| format!("Lock error: {}", e))?;
    config.update_settings(settings).map_err(|e| e.to_string())
}
