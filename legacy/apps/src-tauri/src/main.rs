#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;

use tauri::Manager;

#[tokio::main]
async fn main() {
    tauri::Builder::default()
        .setup(|app| {
            app.manage(tauri::generate_context!())
        })
        .invoke_handler(tauri::generate_handler![
            commands::greet,
        commands::get_projects,
            commands::add_project,
            commands::start_project,
            commands::stop_project,
            commands::open_in_browser,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
