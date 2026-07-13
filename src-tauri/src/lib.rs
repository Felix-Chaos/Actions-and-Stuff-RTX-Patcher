pub mod commands;
pub mod telemetry;
pub mod utils;
use commands::*;
use telemetry::*;

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            greet,
            get_patch_configs,
            scan_marketplace_packs,
            run_xdelta_patch,
            install_mcpack,
            delete_folders,
            get_options_paths,
            read_options,
            write_options,
            pack_folder,
            extract_archive,
            normalize_extracted_pack,
            move_marketplace_folders,
            restore_marketplace_folders,
            get_cleanable_packs,
            select_directory,
            select_file,
            stage_and_extract_brarchives,
            extract_brarchives_in_workspace,
            generate_xdelta_patch,
            open_in_explorer,
            open_project_dir,
            get_default_paths,
            update_app_version,
            run_release_build,
            get_app_version,
            check_build_exists,
            is_dev_build,
            open_url,
            write_text_file,
            calculate_patch_stats,
            inject_custom_manifest_to_target,
            fetch_motd,
            submit_bug_report,
            prepare_patch_target,
            get_patch_versions,
            save_patch_versions,
            load_settings,
            save_settings,
            get_telemetry_state,
            set_telemetry_consent,
            collect_hardware_info,
            submit_hardware_ping,
            telemetry_delete_my_data,
            collect_driver_events,
            prepare_content_log
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
