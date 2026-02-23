#[tauri::command]
pub fn greet(name: &str) -> String {
    format!("Hello, {}! Welcome to DJANGOForge.", name)
}

#[tauri::command]
pub fn get_projects() -> String {
    "[]".to_string()
}

#[tauri::command]
pub fn add_project(name: &str, path: &str) -> String {
    format!("Added project: {} at {}", name, path)
}

#[tauri::command]
pub async fn start_project(id: &str) -> Result<(), String> {
    println!("Starting project: {}", id);
    Ok(())
}

#[tauri::command]
pub async fn stop_project(id: &str) -> Result<(), String> {
    println!("Stopping project: {}", id);
    Ok(())
}

#[tauri::command]
pub async fn open_in_browser(url: &str) -> Result<(), String> {
    println!("Opening: {}", url);
    Ok(())
}
