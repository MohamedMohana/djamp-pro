use serde_json::{json, Value};
use std::process::Command;

use crate::sidecar;

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CommandResult {
    pub success: bool,
    pub output: String,
    pub error: Option<String>,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DetectionResult {
    pub found: bool,
    #[serde(alias = "manage_py_path", alias = "managePyPath")]
    #[serde(rename = "managePyPath")]
    pub manage_py_path: Option<String>,
    #[serde(alias = "settings_modules", alias = "settingsModules")]
    #[serde(rename = "settingsModules")]
    pub settings_modules: Option<Vec<String>>,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
struct MessageResponse {
    message: String,
}

#[tauri::command]
pub fn greet(name: &str) -> String {
    format!("Hello, {name}! Welcome to DJAMP PRO.")
}

#[tauri::command]
pub async fn get_projects() -> Result<Value, String> {
    sidecar::get_json("/api/projects").await
}

#[tauri::command]
pub async fn add_project(project: Value) -> Result<(), String> {
    let _: Value = sidecar::post_json("/api/projects", &json!({ "project": project })).await?;
    Ok(())
}

#[tauri::command]
pub async fn update_project(id: String, updates: Value) -> Result<(), String> {
    let _: Value = sidecar::patch_json(&format!("/api/projects/{id}"), &updates).await?;
    Ok(())
}

#[tauri::command]
pub async fn delete_project(id: String) -> Result<(), String> {
    sidecar::delete(&format!("/api/projects/{id}")).await
}

#[tauri::command]
pub async fn start_project(id: String) -> Result<Value, String> {
    sidecar::post_json(&format!("/api/projects/{id}/start"), &json!({})).await
}

#[tauri::command]
pub async fn stop_project(id: String) -> Result<(), String> {
    let _: Value = sidecar::post_json(&format!("/api/projects/{id}/stop"), &json!({})).await?;
    Ok(())
}

#[tauri::command]
pub async fn restart_project(id: String) -> Result<(), String> {
    let _: Value = sidecar::post_json(&format!("/api/projects/{id}/restart"), &json!({})).await?;
    Ok(())
}

#[tauri::command]
pub async fn run_migrate(project_id: String) -> Result<CommandResult, String> {
    sidecar::post_json(&format!("/api/projects/{project_id}/migrate"), &json!({})).await
}

#[tauri::command]
pub async fn run_collectstatic(project_id: String) -> Result<CommandResult, String> {
    sidecar::post_json(&format!("/api/projects/{project_id}/collectstatic"), &json!({})).await
}

#[tauri::command]
pub async fn create_superuser(
    project_id: String,
    username: String,
    email: String,
) -> Result<CommandResult, String> {
    sidecar::post_json(
        &format!("/api/projects/{project_id}/createsuperuser"),
        &json!({ "projectId": project_id, "username": username, "email": email }),
    )
    .await
}

#[tauri::command]
pub async fn run_tests(project_id: String) -> Result<CommandResult, String> {
    sidecar::post_json(&format!("/api/projects/{project_id}/test"), &json!({})).await
}

#[tauri::command]
pub async fn open_shell(project_id: String) -> Result<(), String> {
    let response: MessageResponse =
        sidecar::post_json(&format!("/api/utilities/{project_id}/shell"), &json!({})).await?;

    if cfg!(target_os = "macos") {
        let _ = Command::new("osascript")
            .arg("-e")
            .arg(format!(
                "tell application \"Terminal\" to do script \"{}\"",
                response.message.replace('"', "\\\"")
            ))
            .status();
    }

    Ok(())
}

#[tauri::command]
pub async fn open_db_shell(project_id: String) -> Result<(), String> {
    let response: MessageResponse =
        sidecar::post_json(&format!("/api/utilities/{project_id}/db-shell"), &json!({})).await?;

    if cfg!(target_os = "macos") {
        let _ = Command::new("osascript")
            .arg("-e")
            .arg(format!(
                "tell application \"Terminal\" to do script \"{}\"",
                response.message.replace('"', "\\\"")
            ))
            .status();
    }

    Ok(())
}

#[tauri::command]
pub async fn open_vscode(project_id: String) -> Result<(), String> {
    let response: MessageResponse =
        sidecar::post_json(&format!("/api/utilities/{project_id}/vscode"), &json!({})).await?;

    let status = Command::new("code").arg(&response.message).status();
    if status.is_err() {
        open_with_os(&response.message)?;
    }
    Ok(())
}

#[tauri::command]
pub async fn get_settings() -> Result<Value, String> {
    sidecar::get_json("/api/settings").await
}

#[tauri::command]
pub async fn get_proxy_status() -> Result<Value, String> {
    sidecar::get_json("/api/proxy/status").await
}

#[tauri::command]
pub async fn reload_proxy() -> Result<CommandResult, String> {
    sidecar::post_json("/api/proxy/reload", &json!({})).await
}

#[tauri::command]
pub async fn disable_standard_ports() -> Result<CommandResult, String> {
    sidecar::post_json("/api/proxy/standard-ports/disable", &json!({})).await
}

#[tauri::command]
pub async fn get_helper_status() -> Result<Value, String> {
    sidecar::get_json("/api/helper/status").await
}

#[tauri::command]
pub async fn install_helper() -> Result<CommandResult, String> {
    sidecar::post_json("/api/helper/install", &json!({})).await
}

#[tauri::command]
pub async fn uninstall_helper() -> Result<CommandResult, String> {
    sidecar::post_json("/api/helper/uninstall", &json!({})).await
}

#[tauri::command]
pub async fn update_settings(settings: Value) -> Result<(), String> {
    let _: Value = sidecar::patch_json("/api/settings", &settings).await?;
    Ok(())
}

#[tauri::command]
pub async fn add_domain(domain: String) -> Result<(), String> {
    let _: Value = sidecar::post_json("/api/domains/add", &json!({ "domain": domain })).await?;
    Ok(())
}

#[tauri::command]
pub async fn remove_domain(domain: String) -> Result<(), String> {
    let _: Value = sidecar::post_json("/api/domains/remove", &json!({ "domain": domain })).await?;
    Ok(())
}

#[tauri::command]
pub async fn sync_domains() -> Result<CommandResult, String> {
    sidecar::post_json("/api/domains/sync", &json!({})).await
}

#[tauri::command]
pub async fn clear_domains() -> Result<CommandResult, String> {
    sidecar::post_json("/api/domains/clear", &json!({})).await
}

#[tauri::command]
pub async fn generate_certificate(domain: String) -> Result<Value, String> {
    sidecar::post_json("/api/certificates/generate", &json!({ "domain": domain })).await
}

#[tauri::command]
pub async fn check_certificate_status(domain: String) -> Result<Value, String> {
    sidecar::get_json(&format!("/api/certificates/{domain}")).await
}

#[tauri::command]
pub async fn install_root_ca() -> Result<(), String> {
    let _: Value = sidecar::post_json("/api/certificates/install-ca", &json!({})).await?;
    Ok(())
}

#[tauri::command]
pub async fn uninstall_root_ca() -> Result<CommandResult, String> {
    sidecar::post_json("/api/certificates/uninstall-ca", &json!({})).await
}

#[tauri::command]
pub async fn check_root_ca_status() -> Result<Value, String> {
    sidecar::get_json("/api/certificates/ca/status").await
}

#[tauri::command]
pub async fn start_database(project_id: String) -> Result<(), String> {
    let _: Value = sidecar::post_json(&format!("/api/databases/{project_id}/start"), &json!({})).await?;
    Ok(())
}

#[tauri::command]
pub async fn stop_database(project_id: String) -> Result<(), String> {
    let _: Value = sidecar::post_json(&format!("/api/databases/{project_id}/stop"), &json!({})).await?;
    Ok(())
}

#[tauri::command]
pub async fn test_database_connection(project_id: String) -> Result<CommandResult, String> {
    sidecar::post_json(&format!("/api/databases/{project_id}/test"), &json!({})).await
}

#[tauri::command]
pub async fn get_database_admin_url(project_id: String) -> Result<Value, String> {
    sidecar::get_json(&format!("/api/databases/{project_id}/admin-url")).await
}

#[tauri::command]
pub async fn get_logs(project_id: String, source: String) -> Result<String, String> {
    sidecar::get_json(&format!("/api/logs/{project_id}/{source}")).await
}

#[tauri::command]
pub async fn detect_django_project(path: String) -> Result<DetectionResult, String> {
    sidecar::post_json("/api/utilities/detect-django", &json!({ "path": path })).await
}

#[tauri::command]
pub async fn create_venv(path: String, python_version: String) -> Result<(), String> {
    let _: Value = sidecar::post_json(
        "/api/utilities/create-venv",
        &json!({ "path": path, "pythonVersion": python_version }),
    )
    .await?;
    Ok(())
}

#[tauri::command]
pub async fn install_dependencies(project_id: String) -> Result<CommandResult, String> {
    sidecar::post_json(
        "/api/utilities/install-dependencies",
        &json!({ "projectId": project_id }),
    )
    .await
}

#[tauri::command]
pub async fn open_in_browser(url: String) -> Result<(), String> {
    open_with_os(&url)
}

fn open_with_os(target: &str) -> Result<(), String> {
    if cfg!(target_os = "macos") {
        Command::new("open")
            .arg(target)
            .status()
            .map_err(|err| format!("open failed: {err}"))?;
        return Ok(());
    }

    if cfg!(target_os = "windows") {
        Command::new("cmd")
            .args(["/C", "start", "", target])
            .status()
            .map_err(|err| format!("start failed: {err}"))?;
        return Ok(());
    }

    Command::new("xdg-open")
        .arg(target)
        .status()
        .map_err(|err| format!("xdg-open failed: {err}"))?;
    Ok(())
}
