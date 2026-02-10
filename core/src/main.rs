#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod config;
mod privilege;
mod storage;
mod utils;

use std::sync::Mutex;
use commands::{config, process, privilege};
use storage::ConfigManager;
use tauri::Manager;

#[tokio::main]
async fn main() {
    // Initialize config manager
    let config_manager = ConfigManager::new().await.expect("Failed to initialize config manager");
    let config_manager = Mutex::new(config_manager);

    // Initialize logger
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    tauri::Builder::default()
        .setup(|app| {
            app.manage(config_manager);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            config::get_projects,
            config::add_project,
            config::update_project,
            config::delete_project,
            config::get_settings,
            config::update_settings,
            process::start_project,
            process::stop_project,
            process::restart_project,
            process::run_migrate,
            process::run_collectstatic,
            process::create_superuser,
            process::run_tests,
            process::open_shell,
            process::open_vscode,
            process::detect_django_project,
            process::create_venv,
            process::install_dependencies,
            privilege::add_domain,
            privilege::remove_domain,
            privilege::generate_certificate,
            privilege::check_certificate_status,
            privilege::install_root_ca,
            privilege::check_root_ca_status,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
