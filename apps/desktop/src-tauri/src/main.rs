#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod sidecar;

#[tokio::main]
async fn main() {
    let context = tauri::generate_context!();

    tauri::Builder::default()
        .setup(|_app| {
            tauri::async_runtime::spawn(async {
                if let Err(err) = sidecar::ensure_sidecar_started().await {
                    eprintln!("failed to start sidecar: {err}");
                }
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::greet,
            commands::get_projects,
            commands::add_project,
            commands::update_project,
            commands::delete_project,
            commands::start_project,
            commands::stop_project,
            commands::restart_project,
            commands::run_migrate,
            commands::run_collectstatic,
            commands::create_superuser,
            commands::run_tests,
            commands::open_shell,
            commands::open_db_shell,
            commands::open_vscode,
            commands::get_settings,
            commands::get_proxy_status,
            commands::reload_proxy,
            commands::disable_standard_ports,
            commands::get_helper_status,
            commands::install_helper,
            commands::uninstall_helper,
            commands::update_settings,
            commands::add_domain,
            commands::remove_domain,
            commands::sync_domains,
            commands::clear_domains,
            commands::generate_certificate,
            commands::check_certificate_status,
            commands::install_root_ca,
            commands::uninstall_root_ca,
            commands::check_root_ca_status,
            commands::start_database,
            commands::stop_database,
            commands::test_database_connection,
            commands::get_logs,
            commands::detect_django_project,
            commands::create_venv,
            commands::install_dependencies,
            commands::open_in_browser,
        ])
        .build(context)
        .expect("error while building tauri application")
        .run(|_app_handle, event| match event {
            tauri::RunEvent::ExitRequested { .. } => {
                // Ensure the controller gets a chance to run shutdown handlers (stop processes).
                sidecar::stop_sidecar_best_effort();
            }
            tauri::RunEvent::Exit => {
                sidecar::stop_sidecar_best_effort();
            }
            _ => {}
        });
}
