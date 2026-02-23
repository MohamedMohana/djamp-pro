#![cfg_attr(not(debug_assertions), windows_subsystem = "windows"]

use tauri::Manager;

#[tokio::main]
async fn main() {
    tauri::Builder::default()
        .setup(|app| {
            app.manage(tauri::generate_context!())
        })
        .invoke_handler(tauri::generate_handler![])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
