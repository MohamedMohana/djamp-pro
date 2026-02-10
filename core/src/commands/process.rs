use crate::storage::{ConfigManager, Project};
use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use std::process::{Command, Stdio};
use std::path::Path;
use tauri::State;

#[derive(Debug, Serialize, Deserialize)]
pub struct CommandResult {
    pub success: bool,
    pub output: String,
    pub error: Option<String>,
}

#[tauri::command]
pub async fn start_project(
    config: State<'_, Mutex<ConfigManager>>,
    project_id: String,
) -> Result<(), String> {
    let config = config.lock().map_err(|e| format!("Lock error: {}", e))?;
    let project = config.get_project(&project_id).await.ok_or("Project not found")?;
    
    // Start database if configured
    if project.database.type_ != "none" {
        start_database(&project).await?;
    }
    
    // Start Django server
    start_django_server(&project).await?;
    
    // Update status
    let mut config = config.lock().map_err(|e| format!("Lock error: {}", e))?;
    config.update_project_status(&project_id, "starting").await?;
    
    Ok(())
}

#[tauri::command]
pub async fn stop_project(
    config: State<'_, Mutex<ConfigManager>>,
    project_id: String,
) -> Result<(), String> {
    let mut config = config.lock().map_err(|e| format!("Lock error: {}", e))?;
    config.update_project_status(&project_id, "stopping").await?;
    
    let project = config.get_project(&project_id).await.ok_or("Project not found")?;
    
    // Stop Django server
    stop_django_server(&project_id).await?;
    
    // Stop database if configured
    if project.database.type_ != "none" {
        stop_database(&project_id).await?;
    }
    
    config.update_project_status(&project_id, "stopped").await?;
    
    Ok(())
}

#[tauri::command]
pub async fn restart_project(
    config: State<'_, Mutex<ConfigManager>>,
    project_id: String,
) -> Result<(), String> {
    stop_project(config, project_id.clone()).await?;
    tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;
    start_project(config, project_id).await
}

#[tauri::command]
pub async fn run_migrate(
    project_id: String,
) -> Result<CommandResult, String> {
    let result = run_django_command(&project_id, "migrate", &[]).await?;
    Ok(result)
}

#[tauri::command]
pub async fn run_collectstatic(
    project_id: String,
) -> Result<CommandResult, String> {
    let result = run_django_command(&project_id, "collectstatic", &[]).await?;
    Ok(result)
}

#[tauri::command]
pub async fn create_superuser(
    project_id: String,
    username: String,
    email: String,
) -> Result<CommandResult, String> {
    let args = ["createsuperuser", "--noinput", &format!("--username={}", username), &format!("--email={}", email)];
    let result = run_django_command(&project_id, "createsuperuser", &args[1..]).await?;
    Ok(result)
}

#[tauri::command]
pub async fn run_tests(
    project_id: String,
) -> Result<CommandResult, String> {
    let result = run_django_command(&project_id, "test", &[]).await?;
    Ok(result)
}

#[tauri::command]
pub async fn open_shell(
    project_id: String,
) -> Result<(), String> {
    // This would open a shell terminal in the project directory
    // Implementation depends on OS
    #[cfg(target_os = "macos")]
    {
        Command::new("osascript")
            .arg("-e")
            .arg(format!("tell application \"Terminal\" to do script \"cd {}\"", project_id))
            .spawn()
            .map_err(|e| format!("Failed to open terminal: {}", e))?;
    }
    
    #[cfg(windows)]
    {
        Command::new("cmd")
            .args(["/c", "start", "cmd", "/k", &format!("cd /d {}", project_id)])
            .spawn()
            .map_err(|e| format!("Failed to open terminal: {}", e))?;
    }
    
    Ok(())
}

#[tauri::command]
pub async fn open_vscode(
    project_id: String,
) -> Result<(), String> {
    let config_path = dirs::home_dir()
        .ok_or("Home directory not found")?
        .join(".djamp")
        .join("projects.json");
    
    let projects_json = std::fs::read_to_string(&config_path)
        .map_err(|e| format!("Failed to read projects: {}", e))?;
    
    let projects: serde_json::Value = serde_json::from_str(&projects_json)
        .map_err(|e| format!("Failed to parse projects: {}", e))?;
    
    let project = projects["projects"][&project_id]
        .ok_or("Project not found")?;
    
    let path = project["path"]
        .as_str()
        .ok_or("Project path not found")?;
    
    Command::new("code")
        .arg(path)
        .spawn()
        .map_err(|e| format!("Failed to open VS Code: {}", e))?;
    
    Ok(())
}

#[tauri::command]
pub async fn detect_django_project(
    path: String,
) -> Result<serde_json::Value, String> {
    let project_path = Path::new(&path);
    
    let manage_py_path = find_manage_py(project_path)?;
    let settings_modules = find_settings_modules(project_path, &manage_py_path)?;
    
    Ok(serde_json::json!({
        "found": true,
        "managePyPath": manage_py_path,
        "settingsModules": settings_modules
    }))
}

#[tauri::command]
pub async fn create_venv(
    path: String,
    python_version: String,
) -> Result<(), String> {
    let venv_path = Path::new(&path).join(".venv");
    
    Command::new("python3")
        .args(["-m", "venv", venv_path.to_str().unwrap()])
        .spawn()
        .map_err(|e| format!("Failed to create venv: {}", e))?;
    
    Ok(())
}

#[tauri::command]
pub async fn install_dependencies(
    project_id: String,
) -> Result<CommandResult, String> {
    let config_path = dirs::home_dir()
        .ok_or("Home directory not found")?
        .join(".djamp")
        .join("projects.json");
    
    let projects_json = std::fs::read_to_string(&config_path)
        .map_err(|e| format!("Failed to read projects: {}", e))?;
    
    let projects: serde_json::Value = serde_json::from_str(&projects_json)
        .map_err(|e| format!("Failed to parse projects: {}", e))?;
    
    let project = projects["projects"][&project_id]
        .ok_or("Project not found")?;
    
    let venv_path = project["venvPath"]
        .as_str()
        .ok_or("Venv path not found")?;
    
    let project_path = project["path"]
        .as_str()
        .ok_or("Project path not found")?;
    
    let pip_path = Path::new(venv_path).join("bin").join("pip");
    
    let output = Command::new(pip_path)
        .args(["install", "-r", "requirements.txt"])
        .current_dir(project_path)
        .output()
        .map_err(|e| format!("Failed to install dependencies: {}", e))?;
    
    Ok(CommandResult {
        success: output.status.success(),
        output: String::from_utf8_lossy(&output.stdout).to_string(),
        error: if output.status.success() {
            None
        } else {
            Some(String::from_utf8_lossy(&output.stderr).to_string())
        },
    })
}

// Helper functions

async fn start_django_server(project: &Project) -> Result<(), String> {
    let python_path = Path::new(&project.venv_path).join("bin").join("python");
    let manage_path = Path::new(&project.path).join("manage.py");
    
    Command::new(python_path)
        .arg(manage_path)
        .args(["runserver", &format!("127.0.0.1:{}", project.port)])
        .current_dir(&project.path)
        .env("DJANGO_SETTINGS_MODULE", &project.settings_module)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to start Django server: {}", e))?;
    
    Ok(())
}

async fn stop_django_server(project_id: &str) -> Result<(), String> {
    #[cfg(target_os = "macos")]
    {
        Command::new("pkill")
            .args(["-f", &format!("manage.py runserver.*{}", project_id)])
            .spawn()
            .map_err(|e| format!("Failed to stop Django server: {}", e))?;
    }
    
    #[cfg(windows)]
    {
        Command::new("taskkill")
            .args(["/F", "/IM", "python.exe"])
            .spawn()
            .map_err(|e| format!("Failed to stop Django server: {}", e))?;
    }
    
    Ok(())
}

async fn start_database(project: &Project) -> Result<(), String> {
    // Placeholder - would implement actual database start logic
    log::info!("Starting database for project: {}", project.name);
    Ok(())
}

async fn stop_database(project_id: &str) -> Result<(), String> {
    // Placeholder - would implement actual database stop logic
    log::info!("Stopping database for project: {}", project_id);
    Ok(())
}

async fn run_django_command(project_id: &str, command: &str, args: &[&str]) -> Result<CommandResult, String> {
    let config_path = dirs::home_dir()
        .ok_or("Home directory not found")?
        .join(".djamp")
        .join("projects.json");
    
    let projects_json = std::fs::read_to_string(&config_path)
        .map_err(|e| format!("Failed to read projects: {}", e))?;
    
    let projects: serde_json::Value = serde_json::from_str(&projects_json)
        .map_err(|e| format!("Failed to parse projects: {}", e))?;
    
    let project = projects["projects"][project_id]
        .ok_or("Project not found")?;
    
    let venv_path = project["venvPath"]
        .as_str()
        .ok_or("Venv path not found")?;
    
    let project_path = project["path"]
        .as_str()
        .ok_or("Project path not found")?;
    
    let settings_module = project["settingsModule"]
        .as_str()
        .ok_or("Settings module not found")?;
    
    let python_path = Path::new(venv_path).join("bin").join("python");
    let manage_path = Path::new(project_path).join("manage.py");
    
    let mut cmd_args = vec![manage_path.to_str().unwrap(), command];
    cmd_args.extend(args);
    
    let output = Command::new(python_path)
        .args(cmd_args)
        .current_dir(project_path)
        .env("DJANGO_SETTINGS_MODULE", settings_module)
        .output()
        .map_err(|e| format!("Failed to run Django command: {}", e))?;
    
    Ok(CommandResult {
        success: output.status.success(),
        output: String::from_utf8_lossy(&output.stdout).to_string(),
        error: if output.status.success() {
            None
        } else {
            Some(String::from_utf8_lossy(&output.stderr).to_string())
        },
    })
}

fn find_manage_py(path: &Path) -> Result<String, String> {
    for entry in path.read_dir().map_err(|e| format!("Failed to read directory: {}", e))? {
        let entry = entry.map_err(|e| format!("Failed to read entry: {}", e))?;
        let file_name = entry.file_name();
        if file_name == "manage.py" {
            return Ok(entry.path().to_str().unwrap().to_string());
        }
    }
    Err("manage.py not found".to_string())
}

fn find_settings_modules(path: &Path, manage_py_path: &str) -> Result<Vec<String>, String> {
    let manage_py_path = Path::new(manage_py_path);
    
    // Look for settings.py files
    let mut settings_modules = Vec::new();
    
    for entry in path.read_dir().map_err(|e| format!("Failed to read directory: {}", e))? {
        let entry = entry.map_err(|e| format!("Failed to read entry: {}", e))?;
        let file_name = entry.file_name();
        
        if entry.path().is_dir() {
            // Check for settings.py in subdirectory
            let settings_path = entry.path().join("settings.py");
            if settings_path.exists() {
                settings_modules.push(format!("{}.settings", file_name.to_string_lossy()));
            }
        } else if file_name == "settings.py" {
            // Check for settings.py in root
            let module_name = path.file_name()
                .map(|n| n.to_string_lossy().to_string())
                .unwrap_or_else(|| "myproject".to_string());
            settings_modules.push(format!("{}.settings", module_name));
        }
    }
    
    if settings_modules.is_empty() {
        Err("No settings modules found".to_string())
    } else {
        Ok(settings_modules)
    }
}
