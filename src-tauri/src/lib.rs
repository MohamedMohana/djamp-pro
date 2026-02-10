use std::sync::Mutex;
use tauri::State;

mod commands;
mod config;
mod privilege;
mod storage;
mod utils;

use storage::ConfigManager;

// Shared state type
#[derive(Debug, Clone)]
pub struct AppState {
    config_manager: Mutex<ConfigManager>,
}
