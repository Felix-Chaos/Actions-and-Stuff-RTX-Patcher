use crate::utils::*;
use std::collections::HashMap;
use std::io::BufRead;
#[cfg(target_os = "windows")]
use std::os::windows::ffi::OsStrExt;
#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;
use std::path::{Path, PathBuf};
use tauri::Manager;
#[cfg(target_os = "windows")]
extern "system" {
    fn SetFileAttributesW(lpFileName: *const u16, dwFileAttributes: u32) -> i32;
}

#[tauri::command]
pub fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[tauri::command]
pub async fn scan_marketplace_packs() -> Result<Vec<MarketplaceCandidate>, String> {
    let mut candidates = Vec::new();
    let mut base_paths = Vec::new();
    let local_app_data = std::env::var("LOCALAPPDATA").ok();
    let app_data = std::env::var("APPDATA").ok();

    if let Some(ref lad) = local_app_data {
        base_paths.push(PathBuf::from(lad).join(r"Packages\Microsoft.MinecraftUWP_8wekyb3d8bbwe\LocalState\premium_cache\resource_packs"));
        base_paths.push(PathBuf::from(lad).join(r"Packages\Microsoft.MinecraftWindowsBeta_8wekyb3d8bbwe\LocalState\premium_cache\resource_packs"));
    }
    if let Some(ref ad) = app_data {
        base_paths.push(PathBuf::from(ad).join(r"Minecraft Bedrock\premium_cache\resource_packs"));
        base_paths.push(
            PathBuf::from(ad).join(r"Minecraft Bedrock Preview\premium_cache\resource_packs"),
        );
    }

    for base_path in base_paths {
        if !base_path.exists() {
            continue;
        }
        if let Ok(entries) = std::fs::read_dir(base_path) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.is_dir() {
                    let manifest_path = path.join("manifest.json");
                    let mut is_match = false;

                    if manifest_path.exists() {
                        if let Ok(manifest_content) = std::fs::read_to_string(&manifest_path) {
                            if manifest_content.contains("22ed17a6-ea7c-5ccd-93b4-b90e86ce0046")
                                || manifest_content.contains("Oreville Studios")
                            {
                                is_match = true;
                            }
                        }
                    }

                    if is_match {
                        let version =
                            get_lang_version(&path).unwrap_or_else(|| "Unknown".to_string());
                        let folder_name = entry.file_name().to_string_lossy().into_owned();
                        let (files_count, dirs_count) = get_folder_stats(&path);

                        let logo_path = path.join("pack_icon.png");
                        let logo_hash = if logo_path.exists() {
                            if let Ok(content) = std::fs::read(&logo_path) {
                                use sha2::{Digest, Sha256};
                                let mut hasher = Sha256::new();
                                hasher.update(&content);
                                let hash = hasher.finalize();
                                hash.iter().map(|b| format!("{:02x}", b)).collect()
                            } else {
                                String::new()
                            }
                        } else {
                            String::new()
                        };

                        candidates.push(MarketplaceCandidate {
                            path: path.to_string_lossy().into_owned(),
                            version,
                            folder_name,
                            files_count,
                            dirs_count,
                            logo_hash,
                        });
                    }
                }
            }
        }
    }
    Ok(candidates)
}

#[tauri::command]
pub async fn get_patch_configs(app: tauri::AppHandle) -> Result<Vec<serde_json::Value>, String> {
    let patches_dir = resolve_asset_path(&app, "assets/Patches")?;

    let mut configs = Vec::new();
    if !patches_dir.exists() {
        return Ok(configs);
    }

    if let Ok(entries) = std::fs::read_dir(patches_dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                let config_file = path.join("patch_config.json");
                if config_file.exists() {
                    if let Ok(content) = std::fs::read_to_string(&config_file) {
                        if let Ok(mut json_val) =
                            serde_json::from_str::<serde_json::Value>(&content)
                        {
                            if let Some(obj) = json_val.as_object_mut() {
                                let folder_name = entry.file_name().to_string_lossy().into_owned();
                                obj.insert(
                                    "folder_name".to_string(),
                                    serde_json::Value::String(folder_name),
                                );

                                // Standardize stats field
                                if let Some(mp_stats) = obj.get("marketplace_pack_stats") {
                                    if let Some(v1) = mp_stats.get("v1") {
                                        obj.insert("stats".to_string(), v1.clone());
                                    } else if let Some(stats) = mp_stats.get("stats") {
                                        obj.insert("stats".to_string(), stats.clone());
                                    } else {
                                        obj.insert("stats".to_string(), mp_stats.clone());
                                    }
                                }
                                configs.push(serde_json::Value::Object(obj.clone()));
                            }
                        }
                    }
                }
            }
        }
    }
    Ok(configs)
}

#[tauri::command]
pub async fn run_xdelta_patch(
    app: tauri::AppHandle,
    source_zip: String,
    patch_file: String,
    output_file: String,
) -> Result<String, String> {
    let xdelta_path = resolve_asset_path(&app, "assets/xdelta3/exec/xdelta3_x86_64_win.exe")?;

    if !xdelta_path.exists() {
        return Err(format!(
            "XDelta executable not found at resources: {:?}",
            xdelta_path
        ));
    }

    let mut actual_patch_file = Path::new(&patch_file).to_path_buf();
    if !actual_patch_file.is_absolute() {
        actual_patch_file = resolve_asset_path(&app, &patch_file)?;
    }
    let resolved_patch_str = actual_patch_file.to_string_lossy().to_string();

    emit_log(&app, "main", "Initiating XDelta patch execution...", "info");
    emit_log(
        &app,
        "main",
        &format!("  [Executable] -> {:?}", xdelta_path),
        "info",
    );
    emit_log(
        &app,
        "main",
        &format!("  [Source ZIP] -> {}", source_zip),
        "info",
    );
    emit_log(
        &app,
        "main",
        &format!("  [Patch File] -> {}", resolved_patch_str),
        "info",
    );
    emit_log(
        &app,
        "main",
        &format!("  [Output File] -> {}", output_file),
        "info",
    );

    let out_path = Path::new(&output_file);
    if let Some(parent) = out_path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| format!("Failed to create output dir: {}", e))?;
    }

    if out_path.exists() {
        emit_log(&app, "main", "Removing pre-existing output file...", "info");
        let _ = std::fs::remove_file(out_path);
    }

    let mut cmd = std::process::Command::new(&xdelta_path);
    cmd.args(&[
        "-f",
        "-v",
        "-d",
        "-s",
        &source_zip,
        &resolved_patch_str,
        &output_file,
    ]);

    #[cfg(target_os = "windows")]
    cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW

    let output = cmd
        .output()
        .map_err(|e| format!("Failed to run patch executable: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);

    if !stdout.trim().is_empty() {
        emit_log(&app, "main", &format!("XDelta stdout: {}", stdout), "info");
    }
    if !stderr.trim().is_empty() {
        emit_log(&app, "main", &format!("XDelta stderr: {}", stderr), "info");
    }

    if !output.status.success() {
        let err_msg = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Patching failed: {}", err_msg));
    }

    emit_log(
        &app,
        "main",
        "XDelta patch decoding completed successfully.",
        "success",
    );
    Ok("Patch applied successfully.".to_string())
}

#[tauri::command]
pub async fn install_mcpack(output_file: String) -> Result<String, String> {
    let src_path = Path::new(&output_file);
    if !src_path.exists() {
        return Err("Output file not found".to_string());
    }

    let parent = src_path.parent().unwrap_or_else(|| Path::new(""));
    let file_stem = src_path
        .file_stem()
        .ok_or_else(|| "Invalid filename".to_string())?;
    let mcpack_path = parent.join(format!("{}.mcpack", file_stem.to_string_lossy()));

    if src_path != mcpack_path {
        if mcpack_path.exists() {
            let _ = std::fs::remove_file(&mcpack_path);
        }
        std::fs::rename(src_path, &mcpack_path)
            .map_err(|e| format!("Failed to rename pack: {}", e))?;
    }

    #[cfg(target_os = "windows")]
    {
        let mut wide: Vec<u16> = mcpack_path.as_os_str().encode_wide().collect();
        wide.push(0);
        unsafe {
            SetFileAttributesW(wide.as_ptr(), 2); // FILE_ATTRIBUTE_HIDDEN = 2
        }
    }

    // Open the pack (starts Minecraft import)
    #[cfg(target_os = "windows")]
    {
        let mut cmd = std::process::Command::new("cmd");
        cmd.args(&["/c", "start", "", &mcpack_path.to_string_lossy()]);
        cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW
        cmd.spawn()
            .map_err(|e| format!("Failed to launch Minecraft installer: {}", e))?;
    }
    #[cfg(not(target_os = "windows"))]
    {
        open::that(&mcpack_path)
            .map_err(|e| format!("Failed to launch Minecraft installer: {}", e))?;
    }

    Ok(mcpack_path.to_string_lossy().into_owned())
}

#[tauri::command]
pub fn get_cleanable_packs() -> Result<Vec<String>, String> {
    let mut results = Vec::new();
    for path in get_mojang_paths() {
        for p in scan_cleanable_packs_in_mojang(&path) {
            results.push(p.to_string_lossy().into_owned());
        }
    }
    Ok(results)
}

#[tauri::command]
pub async fn delete_folders(folders: Vec<String>) -> Result<usize, String> {
    let mut deleted_count = 0;
    for f in folders {
        if robust_cleanup(Path::new(&f)) {
            deleted_count += 1;
        }
    }
    Ok(deleted_count)
}

#[tauri::command]
pub fn get_options_paths() -> Result<Vec<OptionsFile>, String> {
    let mut results = Vec::new();
    let local_app_data = std::env::var("LOCALAPPDATA").ok();
    let app_data = std::env::var("APPDATA").ok();

    if let Some(ref ad) = app_data {
        let roaming_users = PathBuf::from(ad).join(r"Minecraft Bedrock\Users");
        if roaming_users.exists() {
            if let Ok(entries) = std::fs::read_dir(roaming_users) {
                for entry in entries.flatten() {
                    let candidate = entry
                        .path()
                        .join(r"games\com.mojang\minecraftpe\options.txt");
                    if candidate.exists() {
                        let user_id = entry.file_name().to_string_lossy().into_owned();
                        results.push(OptionsFile {
                            label: format!("GDK — {}", user_id),
                            path: candidate.to_string_lossy().into_owned(),
                        });
                    }
                }
            }
        }
    }

    if let Some(ref lad) = local_app_data {
        let uwp_path = PathBuf::from(lad).join(r"Packages\Microsoft.MinecraftUWP_8wekyb3d8bbwe\LocalState\games\com.mojang\minecraftpe\options.txt");
        if uwp_path.exists() {
            results.push(OptionsFile {
                label: "UWP (Microsoft Store)".to_string(),
                path: uwp_path.to_string_lossy().into_owned(),
            });
        }
    }

    Ok(results)
}

#[tauri::command]
pub fn read_options(path: String) -> Result<HashMap<String, String>, String> {
    let content = std::fs::read_to_string(Path::new(&path))
        .map_err(|e| format!("Failed to read options.txt: {}", e))?;

    let mut map = HashMap::new();
    let lines: Vec<&str> = if content.contains("\\n") && !content.contains('\n') {
        content.split("\\n").collect()
    } else {
        content.lines().collect()
    };

    for line in lines {
        let line = line.trim();
        if line.is_empty() || !line.contains(':') {
            continue;
        }
        let parts: Vec<&str> = line.splitn(2, ':').collect();
        map.insert(parts[0].to_string(), parts[1].to_string());
    }
    Ok(map)
}

#[tauri::command]
pub fn write_options(path: String, changes: HashMap<String, String>) -> Result<(), String> {
    let file_path = Path::new(&path);
    let content = std::fs::read_to_string(file_path)
        .map_err(|e| format!("Failed to read options.txt: {}", e))?;

    let is_literal_newline = content.contains("\\n") && !content.contains('\n');
    let lines: Vec<&str> = if is_literal_newline {
        content.split("\\n").collect()
    } else {
        content.lines().collect()
    };

    let mut new_lines = Vec::new();
    let mut written_keys = std::collections::HashSet::new();

    for line in lines {
        let line_trimmed = line.trim();
        if line_trimmed.is_empty() || !line_trimmed.contains(':') {
            new_lines.push(line.to_string());
            continue;
        }

        let parts: Vec<&str> = line_trimmed.splitn(2, ':').collect();
        let key = parts[0];
        if let Some(new_val) = changes.get(key) {
            new_lines.push(format!("{}:{}", key, new_val));
            written_keys.insert(key.to_string());
        } else {
            new_lines.push(line.to_string());
        }
    }

    for (key, val) in &changes {
        if !written_keys.contains(key) {
            new_lines.push(format!("{}:{}", key, val));
        }
    }

    let join_char = if is_literal_newline { "\\n" } else { "\n" };
    let output = new_lines.join(join_char);

    std::fs::write(file_path, output).map_err(|e| format!("Failed to write options.txt: {}", e))?;
    Ok(())
}

#[tauri::command]
pub async fn pack_folder(
    app: tauri::AppHandle,
    folder_path: String,
    output_zip: String,
) -> Result<(), String> {
    pack_folder_impl(
        Some(&app),
        Path::new(&folder_path),
        Path::new(&output_zip),
        "main",
    )
}

#[tauri::command]
pub async fn extract_archive(
    app: tauri::AppHandle,
    zip_path: String,
    output_dir: String,
) -> Result<(), String> {
    extract_archive_impl(
        Some(&app),
        Path::new(&zip_path),
        Path::new(&output_dir),
        "main",
    )
}

#[tauri::command]
pub async fn normalize_extracted_pack(app: tauri::AppHandle, extract_dir: String) -> Result<(), String> {
    let dir = Path::new(&extract_dir);
    if !dir.exists() {
        return Err("Extraction directory does not exist".to_string());
    }

    emit_log(
        &app,
        "main",
        &format!("Normalizing extracted pack directory: {:?}", dir),
        "info",
    );

    let files_to_remove = [
        "contents.json",
        "signatures.json",
        "splashes.json",
        "sounds.json",
    ];
    let dirs_to_remove: [&str; 0] = [];

    let mut files_deleted = Vec::new();
    let mut dirs_deleted = Vec::new();

    find_files_to_clean(
        dir,
        &files_to_remove,
        &dirs_to_remove,
        &mut files_deleted,
        &mut dirs_deleted,
    );

    for f in &files_deleted {
        if let Some(file_name) = f.file_name() {
            emit_log(
                &app,
                "main",
                &format!("  [Removed signature/license file] -> {:?}", file_name),
                "info",
            );
        }
        let _ = std::fs::remove_file(f);
    }
    for d in &dirs_deleted {
        if let Some(dir_name) = d.file_name() {
            emit_log(
                &app,
                "main",
                &format!("  [Removed texts/translation folder] -> {:?}", dir_name),
                "info",
            );
        }
        let _ = std::fs::remove_dir_all(d);
    }
    let resource_dir = app
        .path()
        .resource_dir()
        .map_err(|e| format!("Failed to get resource dir: {}", e))?;
    let resource_manifest = resource_dir.join("assets/resources/manifest.json");

    if resource_manifest.exists() {
        emit_log(
            &app,
            "main",
            "Injecting custom manifest.json to ensure compatibility.",
            "info",
        );
        std::fs::copy(&resource_manifest, dir.join("manifest.json"))
            .map_err(|e| format!("Failed to copy manifest.json: {}", e))?;
        emit_log(
            &app,
            "main",
            "Custom manifest.json injected successfully.",
            "success",
        );
    } else {
        emit_log(
            &app,
            "main",
            "Warning: Custom manifest.json baseline not found in resources.",
            "warning",
        );
    }
    Ok(())
}

#[tauri::command]
pub async fn move_marketplace_folders() -> Result<usize, String> {
    let local_app_data =
        std::env::var("LOCALAPPDATA").map_err(|_| "LOCALAPPDATA env var not found".to_string())?;
    let uwp_path = PathBuf::from(local_app_data)
        .join(r"Packages\Microsoft.MinecraftUWP_8wekyb3d8bbwe\LocalState");

    let src_dir = uwp_path.join(r"premium_cache\resource_packs");
    let dst_dir = uwp_path.join(r"games\com.mojang\resource_packs");

    if !src_dir.exists() {
        return Err(format!("Source directory not found: {:?}", src_dir));
    }

    std::fs::create_dir_all(&dst_dir)
        .map_err(|e| format!("Failed to create destination directory: {}", e))?;

    let mut moved_count = 0;

    if let Ok(entries) = std::fs::read_dir(src_dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                let folder_name = entry.file_name().to_string_lossy().into_owned();

                let contents_path = path.join("contents.json");
                if contents_path.exists() {
                    let bak_path = path.join("contents.json.bak");
                    let _ = std::fs::rename(&contents_path, &bak_path);
                }

                let new_name = format!("{}_mp", folder_name);
                let target_path = dst_dir.join(new_name);

                if target_path.exists() {
                    continue;
                }

                if std::fs::rename(&path, &target_path).is_ok() {
                    moved_count += 1;
                }
            }
        }
    }

    Ok(moved_count)
}

#[tauri::command]
pub async fn restore_marketplace_folders() -> Result<usize, String> {
    let local_app_data =
        std::env::var("LOCALAPPDATA").map_err(|_| "LOCALAPPDATA env var not found".to_string())?;
    let uwp_path = PathBuf::from(local_app_data)
        .join(r"Packages\Microsoft.MinecraftUWP_8wekyb3d8bbwe\LocalState");

    let src_dir = uwp_path.join(r"games\com.mojang\resource_packs");
    let dst_dir = uwp_path.join(r"premium_cache\resource_packs");

    if !src_dir.exists() {
        return Err(format!("Source directory not found: {:?}", src_dir));
    }

    let mut moved_count = 0;

    if let Ok(entries) = std::fs::read_dir(src_dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                let folder_name = entry.file_name().to_string_lossy().into_owned();
                if folder_name.ends_with("_mp") {
                    let original_name = &folder_name[..folder_name.len() - 3];
                    let target_path = dst_dir.join(original_name);

                    if target_path.exists() {
                        let _ = std::fs::remove_dir_all(&target_path);
                    }

                    if std::fs::rename(&path, &target_path).is_ok() {
                        let bak_path = target_path.join("contents.json.bak");
                        if bak_path.exists() {
                            let contents_path = target_path.join("contents.json");
                            let _ = std::fs::rename(&bak_path, &contents_path);
                        }
                        moved_count += 1;
                    }
                }
            }
        }
    }

    Ok(moved_count)
}

#[tauri::command]
pub fn select_directory(title: String, default_path: Option<String>) -> Result<String, String> {
    let mut dialog = rfd::FileDialog::new().set_title(&title);
    if let Some(path_str) = default_path {
        if !path_str.is_empty() {
            if let Some(existing_dir) = get_existing_dir(&path_str) {
                dialog = dialog.set_directory(existing_dir);
            }
        }
    }
    if let Some(path) = dialog.pick_folder() {
        Ok(path.to_string_lossy().to_string())
    } else {
        Ok("".to_string())
    }
}

#[tauri::command]
pub fn select_file(
    title: String,
    filter: String,
    default_path: Option<String>,
) -> Result<String, String> {
    let mut dialog = rfd::FileDialog::new().set_title(&title);
    if let Some(path_str) = default_path {
        if !path_str.is_empty() {
            let mut cleaned = path_str.replace('/', "\\");
            if cleaned.starts_with(r"\\?\") {
                cleaned = cleaned[4..].to_string();
            } else if cleaned.starts_with(r"//?/") {
                cleaned = cleaned[4..].to_string();
            }

            let p = std::path::Path::new(&cleaned);
            if p.is_dir() {
                if let Some(existing_dir) = get_existing_dir(&cleaned) {
                    dialog = dialog.set_directory(existing_dir);
                }
            } else {
                if let Some(parent) = p.parent() {
                    if let Some(existing_dir) = get_existing_dir(&parent.to_string_lossy()) {
                        dialog = dialog.set_directory(existing_dir);
                    }
                }
                if let Some(file_name) = p.file_name() {
                    dialog = dialog.set_file_name(file_name.to_string_lossy().to_string());
                }
            }
        }
    }

    if !filter.is_empty() {
        if let Some(pipe_idx) = filter.find('|') {
            let name = &filter[..pipe_idx];
            let exts_part = &filter[pipe_idx + 1..];
            let extensions: Vec<&str> = exts_part
                .split(';')
                .map(|e| e.trim_start_matches('*').trim_start_matches('.'))
                .collect();
            dialog = dialog.add_filter(name, &extensions);
        }
    }

    if let Some(path) = dialog.pick_file() {
        Ok(path.to_string_lossy().to_string())
    } else {
        Ok("".to_string())
    }
}

#[tauri::command]
pub async fn stage_and_extract_brarchives(
    app: tauri::AppHandle,
    source_dir: String,
    temp_dir: String,
) -> Result<String, String> {
    let src = Path::new(&source_dir);
    let dst = Path::new(&temp_dir);

    let _ = robust_cleanup(dst);

    emit_log(
        &app,
        "main",
        &format!(
            "Staging files from {:?} to temporary workspace {:?}",
            src, dst
        ),
        "info",
    );
    copy_dir_all(src, dst).map_err(|e| format!("Failed to copy source folder: {}", e))?;

    let found = extract_brarchives_in_workspace_impl(Some(&app), dst, "main")?;

    if found {
        Ok("Staged and extracted brarchives successfully.".to_string())
    } else {
        Ok("Staged successfully (no brarchives found to extract).".to_string())
    }
}

#[tauri::command]
pub async fn extract_brarchives_in_workspace(
    app: tauri::AppHandle,
    workspace: String,
) -> Result<bool, String> {
    let ws = Path::new(&workspace);
    // This command can be called from utilities tab (so log container = "main" or we check which log console is used)
    extract_brarchives_in_workspace_impl(Some(&app), ws, "main")
}

#[tauri::command]
pub async fn generate_xdelta_patch(
    app: tauri::AppHandle,
    source_file: String,
    target_file: String,
    patch_file: String,
) -> Result<String, String> {
    let resource_dir = app
        .path()
        .resource_dir()
        .map_err(|e| format!("Failed to get resource dir: {}", e))?;
    let xdelta_path = resource_dir.join("assets/xdelta3/exec/xdelta3_x86_64_win.exe");

    if !xdelta_path.exists() {
        return Err(format!(
            "XDelta executable not found at resources: {:?}",
            xdelta_path
        ));
    }

    emit_log(
        &app,
        "genpatch-logs",
        "Encoding patch via XDelta...",
        "info",
    );
    emit_log(
        &app,
        "genpatch-logs",
        &format!("  [Executable] -> {:?}", xdelta_path),
        "info",
    );
    emit_log(
        &app,
        "genpatch-logs",
        &format!("  [Source File] -> {}", source_file),
        "info",
    );
    emit_log(
        &app,
        "genpatch-logs",
        &format!("  [Target File] -> {}", target_file),
        "info",
    );
    emit_log(
        &app,
        "genpatch-logs",
        &format!("  [Patch Output] -> {}", patch_file),
        "info",
    );

    let patch_path = Path::new(&patch_file);
    if let Some(parent) = patch_path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| format!("Failed to create output dir: {}", e))?;
    }

    if patch_path.exists() {
        emit_log(
            &app,
            "genpatch-logs",
            "Removing existing patch file...",
            "info",
        );
        let _ = std::fs::remove_file(patch_path);
    }

    let mut cmd = std::process::Command::new(&xdelta_path);
    cmd.args(&["-e", "-s", &source_file, &target_file, &patch_file]);

    #[cfg(target_os = "windows")]
    cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW

    let output = cmd
        .output()
        .map_err(|e| format!("Failed to run patch executable: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);

    if !stdout.trim().is_empty() {
        emit_log(
            &app,
            "genpatch-logs",
            &format!("XDelta stdout: {}", stdout),
            "info",
        );
    }
    if !stderr.trim().is_empty() {
        emit_log(
            &app,
            "genpatch-logs",
            &format!("XDelta stderr: {}", stderr),
            "info",
        );
    }

    if !output.status.success() {
        let err_msg = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Patch generation failed: {}", err_msg));
    }

    emit_log(
        &app,
        "genpatch-logs",
        "XDelta patch generation successful.",
        "success",
    );
    Ok("Patch generated successfully.".to_string())
}

/// Opens a path in Windows Explorer. If path is a file, Explorer selects it.
/// If path is a directory, Explorer opens it.
#[tauri::command]
pub fn open_in_explorer(path: String) -> Result<(), String> {
    let mut cleaned_path = path.replace("/", "\\");
    if cleaned_path.starts_with(r"\\?\") {
        cleaned_path = cleaned_path[4..].to_string();
    }
    let p = std::path::Path::new(&cleaned_path);
    if !p.exists() {
        // Try to open the parent directory instead
        if let Some(parent) = p.parent() {
            if parent.exists() {
                std::process::Command::new("explorer")
                    .arg(parent.to_str().unwrap_or("").replace("/", "\\"))
                    .spawn()
                    .map_err(|e| format!("Failed to open explorer: {}", e))?;
                return Ok(());
            }
        }
        return Err(format!("Path does not exist: {}", cleaned_path));
    }
    if p.is_file() {
        // /select, highlights the file in its parent folder
        std::process::Command::new("explorer")
            .args(&["/select,", &cleaned_path])
            .spawn()
            .map_err(|e| format!("Failed to open explorer: {}", e))?;
    } else {
        std::process::Command::new("explorer")
            .arg(&cleaned_path)
            .spawn()
            .map_err(|e| format!("Failed to open explorer: {}", e))?;
    }
    Ok(())
}

#[tauri::command]
pub fn open_project_dir(app: tauri::AppHandle, name: String) -> Result<(), String> {
    let project_root = get_project_root(&app);
    if project_root.to_string_lossy().is_empty() {
        return Err("Could not determine project root directory".to_string());
    }

    let target_path = match name.as_str() {
        "bundle" => {
            let p_nsis = project_root.join("src-tauri/target/release/bundle/nsis");
            if p_nsis.exists() {
                p_nsis
            } else {
                let p1 = project_root.join("src-tauri/target/release/bundle");
                if p1.exists() {
                    p1
                } else {
                    let p2 = project_root.join("src-tauri/target/release");
                    if p2.exists() {
                        p2
                    } else {
                        let p3 = project_root.join("src-tauri/target/release/bundle");
                        let _ = std::fs::create_dir_all(&p3);
                        p3
                    }
                }
            }
        }
        "patches" => {
            let p1 = project_root.join("src-tauri/assets/Patches");
            if p1.exists() {
                p1
            } else {
                let resource_dir = app.path().resource_dir().ok();
                let p2 = resource_dir
                    .as_ref()
                    .map(|rd| rd.join("assets/Patches"))
                    .unwrap_or_default();
                if p2.exists() {
                    p2
                } else {
                    let p3 = project_root.join("src-tauri/assets/Patches");
                    let _ = std::fs::create_dir_all(&p3);
                    p3
                }
            }
        }
        _ => return Err(format!("Unknown directory name: {}", name)),
    };

    open_in_explorer(target_path.to_string_lossy().to_string())
}

#[tauri::command]
pub fn get_default_paths(app: tauri::AppHandle) -> std::collections::HashMap<String, String> {
    let mut paths = std::collections::HashMap::new();
    let appdata = std::env::var("APPDATA").unwrap_or_default();
    let localappdata = std::env::var("LOCALAPPDATA").unwrap_or_default();
    let userprofile = std::env::var("USERPROFILE").unwrap_or_default();

    // GDK / Roaming path (preferred)
    let gdk_root = format!("{}/Minecraft Bedrock", appdata);
    let gdk_premium = format!("{}/premium_cache/resource_packs", gdk_root);
    let gdk_resource_packs = format!("{}/games/com.mojang/resource_packs", gdk_root);

    // UWP / Windows Store path
    let uwp_root = format!(
        "{}/Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState",
        localappdata
    );
    let uwp_premium = format!("{}/premium_cache/resource_packs", uwp_root);

    // Prefer GDK if it exists
    let premium_cache = if std::path::Path::new(&gdk_premium).exists() {
        gdk_premium.replace('\\', "/")
    } else if std::path::Path::new(&uwp_premium).exists() {
        uwp_premium.replace('\\', "/")
    } else {
        gdk_premium.replace('\\', "/") // fallback even if it doesn't exist
    };

    let resource_packs = if std::path::Path::new(&gdk_resource_packs).exists() {
        gdk_resource_packs.replace('\\', "/")
    } else {
        gdk_resource_packs.replace('\\', "/")
    };

    let downloads = format!("{}/Downloads", userprofile).replace('\\', "/");
    let resource_dir = app.path().resource_dir().ok().unwrap_or_default();
    let patches = resource_dir
        .join("assets/Patches")
        .to_string_lossy()
        .replace('\\', "/");

    let temp_dir = std::env::temp_dir().to_string_lossy().replace('\\', "/");

    paths.insert("premium_cache".to_string(), premium_cache);
    paths.insert("resource_packs".to_string(), resource_packs);
    paths.insert("downloads".to_string(), downloads);
    paths.insert("patches".to_string(), patches);
    paths.insert("temp".to_string(), temp_dir);
    paths.insert("gdk_root".to_string(), gdk_root.replace('\\', "/"));
    paths.insert("uwp_root".to_string(), uwp_root.replace('\\', "/"));
    paths
}

#[tauri::command]
pub fn update_app_version(app: tauri::AppHandle, version: String) -> Result<(), String> {
    let project_root = get_project_root(&app);
    if project_root.to_string_lossy().is_empty() {
        return Err("Could not determine project root directory".to_string());
    }

    let semver_version = version
        .replace("_b", "-0")
        .replace("_a", "-1")
        .replace("-b", "-0")
        .replace("-a", "-1");

    let mut base_version = version.clone();
    for suffix in ["_a", "_b", "-a", "-b", "-0", "-1"] {
        if base_version.ends_with(suffix) {
            let new_len = base_version.len().saturating_sub(suffix.len());
            base_version.truncate(new_len);
            break;
        }
    }

    // 1. Update tauri.conf.json
    let tauri_conf_path = project_root.join("src-tauri/tauri.conf.json");
    if tauri_conf_path.exists() {
        emit_log(
            &app,
            "build-logs",
            &format!(
                "Updating version to {} (semver: {}) in tauri.conf.json...",
                version, semver_version
            ),
            "info",
        );
        let content = std::fs::read_to_string(&tauri_conf_path)
            .map_err(|e| format!("Failed to read tauri.conf.json: {}", e))?;
        let mut val: serde_json::Value = serde_json::from_str(&content)
            .map_err(|e| format!("Failed to parse tauri.conf.json: {}", e))?;
        if let Some(obj) = val.as_object_mut() {
            obj.insert(
                "version".to_string(),
                serde_json::Value::String(semver_version.clone()),
            );
            if let Some(app_obj) = obj.get_mut("app") {
                if let Some(windows) = app_obj.get_mut("windows") {
                    if let Some(win_arr) = windows.as_array_mut() {
                        if let Some(win) = win_arr.get_mut(0) {
                            if let Some(win_obj) = win.as_object_mut() {
                                win_obj.insert(
                                    "title".to_string(),
                                    serde_json::Value::String(format!(
                                        "Actions & Stuff RTX Patcher v{}",
                                        version
                                    )),
                                );
                            }
                        }
                    }
                }
            }
        }
        let updated_content = serde_json::to_string_pretty(&val)
            .map_err(|e| format!("Failed to serialize tauri.conf.json: {}", e))?;
        std::fs::write(&tauri_conf_path, updated_content)
            .map_err(|e| format!("Failed to write tauri.conf.json: {}", e))?;
        emit_log(
            &app,
            "build-logs",
            "Successfully updated tauri.conf.json and window title.",
            "success",
        );
    } else {
        emit_log(
            &app,
            "build-logs",
            &format!(
                "Warning: tauri.conf.json not found at expected path: {:?}",
                tauri_conf_path
            ),
            "warning",
        );
    }

    // Set title on the active running window dynamically
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.set_title(&format!("Actions & Stuff RTX Patcher v{}", version));
    }

    // 2. Update package.json (base version only)
    let package_json_path = project_root.join("package.json");
    if package_json_path.exists() {
        emit_log(
            &app,
            "build-logs",
            &format!("Updating package.json version to {}...", base_version),
            "info",
        );
        let content = std::fs::read_to_string(&package_json_path)
            .map_err(|e| format!("Failed to read package.json: {}", e))?;
        let mut val: serde_json::Value = serde_json::from_str(&content)
            .map_err(|e| format!("Failed to parse package.json: {}", e))?;
        if let Some(obj) = val.as_object_mut() {
            obj.insert(
                "version".to_string(),
                serde_json::Value::String(base_version.clone()),
            );
        }
        let updated_content = serde_json::to_string_pretty(&val)
            .map_err(|e| format!("Failed to serialize package.json: {}", e))?;
        std::fs::write(&package_json_path, updated_content)
            .map_err(|e| format!("Failed to write package.json: {}", e))?;
        emit_log(
            &app,
            "build-logs",
            "Successfully updated package.json.",
            "success",
        );
    } else {
        emit_log(
            &app,
            "build-logs",
            &format!(
                "Warning: package.json not found at expected path: {:?}",
                package_json_path
            ),
            "warning",
        );
    }

    // 3. Update updater.json
    let updater_json_path = project_root.join("updater.json");
    if updater_json_path.exists() {
        emit_log(
            &app,
            "build-logs",
            &format!(
                "Updating version to {} (semver: {}) in updater.json...",
                version, semver_version
            ),
            "info",
        );
        let content = std::fs::read_to_string(&updater_json_path)
            .map_err(|e| format!("Failed to read updater.json: {}", e))?;
        let mut val: serde_json::Value = serde_json::from_str(&content)
            .map_err(|e| format!("Failed to parse updater.json: {}", e))?;
        if let Some(obj) = val.as_object_mut() {
            let old_version = obj
                .get("version")
                .and_then(|v| v.as_str())
                .unwrap_or("3.0.0")
                .to_string();
            obj.insert(
                "version".to_string(),
                serde_json::Value::String(semver_version.clone()),
            );
            if let Some(platforms) = obj.get_mut("platforms") {
                if let Some(win) = platforms.get_mut("windows-x86_64") {
                    if let Some(url_val) = win.get_mut("url") {
                        if let Some(url_str) = url_val.as_str() {
                            let new_url = url_str
                                .replace(
                                    &format!("v{}", old_version),
                                    &format!("v{}", semver_version),
                                )
                                .replace(&old_version, &semver_version);
                            *url_val = serde_json::Value::String(new_url);
                        }
                    }
                }
            }
        }
        let updated_content = serde_json::to_string_pretty(&val)
            .map_err(|e| format!("Failed to serialize updater.json: {}", e))?;
        std::fs::write(&updater_json_path, updated_content)
            .map_err(|e| format!("Failed to write updater.json: {}", e))?;
        emit_log(
            &app,
            "build-logs",
            "Successfully updated updater.json.",
            "success",
        );
    } else {
        emit_log(
            &app,
            "build-logs",
            &format!(
                "Warning: updater.json not found at expected path: {:?}",
                updater_json_path
            ),
            "warning",
        );
    }

    Ok(())
}

#[tauri::command]
pub fn check_build_exists(app: tauri::AppHandle, version: String) -> Result<bool, String> {
    let project_root = get_project_root(&app);
    let nsis_dir = project_root.join("src-tauri/target/release/bundle/nsis");
    let expected_exe = format!("Actions and Stuff RTX Patcher_{}_x64-setup.exe", version);
    if nsis_dir.join(&expected_exe).exists() {
        return Ok(true);
    }
    Ok(false)
}

#[tauri::command]
pub fn run_release_build(app: tauri::AppHandle) -> Result<(), String> {
    let project_root = get_project_root(&app);
    if project_root.to_string_lossy().is_empty() {
        return Err("Could not determine project root directory".to_string());
    }

    let app_clone = app.clone();
    std::thread::spawn(move || {
        emit_log(
            &app_clone,
            "build-logs",
            "Starting project release build...",
            "info",
        );
        emit_log(
            &app_clone,
            "build-logs",
            "Executing command: npm run tauri build",
            "info",
        );

        let mut cmd = std::process::Command::new("cmd");
        cmd.args(&["/c", "npm run tauri build"]);
        cmd.current_dir(&project_root);

        // Simple .env parser to pass TAURI_SIGNING_PRIVATE_KEY during local builds
        if let Ok(env_content) = std::fs::read_to_string(project_root.join(".env")) {
            emit_log(
                &app_clone,
                "build-logs",
                "Loaded environment variables from .env file.",
                "info",
            );
            for line in env_content.lines() {
                let line = line.trim();
                if line.is_empty() || line.starts_with('#') {
                    continue;
                }
                if let Some((k, v)) = line.split_once('=') {
                    let k = k.trim();
                    let v = v.trim().trim_matches(|c| c == '"' || c == '\'');
                    cmd.env(k, v);
                }
            }
        }

        #[cfg(target_os = "windows")]
        cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW

        match cmd
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped())
            .spawn()
        {
            Ok(mut child) => {
                let stdout = child.stdout.take().unwrap();
                let stderr = child.stderr.take().unwrap();

                let app_c1 = app_clone.clone();
                let app_c2 = app_clone.clone();

                std::thread::spawn(move || {
                    let mut reader = std::io::BufReader::new(stdout);
                    let mut line = String::new();
                    while let Ok(bytes) = reader.read_line(&mut line) {
                        if bytes == 0 {
                            break;
                        }
                        emit_log(&app_c1, "build-logs", line.trim_end(), "info");
                        line.clear();
                    }
                });

                std::thread::spawn(move || {
                    let mut reader = std::io::BufReader::new(stderr);
                    let mut line = String::new();
                    while let Ok(bytes) = reader.read_line(&mut line) {
                        if bytes == 0 {
                            break;
                        }
                        emit_log(&app_c2, "build-logs", line.trim_end(), "warning");
                        line.clear();
                    }
                });

                match child.wait() {
                    Ok(status) => {
                        if status.success() {
                            emit_log(
                                &app_clone,
                                "build-logs",
                                "Build finished successfully! Automating updater.json...",
                                "info",
                            );

                            // Automate updater.json signature injection
                            let conf_path = project_root.join("src-tauri/tauri.conf.json");
                            if let Ok(content) = std::fs::read_to_string(&conf_path) {
                                if let Ok(val) = serde_json::from_str::<serde_json::Value>(&content)
                                {
                                    if let Some(version) =
                                        val.get("version").and_then(|v| v.as_str())
                                    {
                                        let sig_path = project_root.join(format!("src-tauri/target/release/bundle/nsis/Actions and Stuff RTX Patcher_{}_x64-setup.exe.sig", version));
                                        if let Ok(signature) = std::fs::read_to_string(&sig_path) {
                                            let updater_path = project_root.join("updater.json");
                                            if let Ok(updater_content) =
                                                std::fs::read_to_string(&updater_path)
                                            {
                                                if let Ok(mut updater_val) =
                                                    serde_json::from_str::<serde_json::Value>(
                                                        &updater_content,
                                                    )
                                                {
                                                    // Also determine the user-facing version format for the github tag to match prepare_release.yml (e.g. V2.2.6a)
                                                    let user_version = version
                                                        .replace("-1", "a")
                                                        .replace("-b", "b")
                                                        .replace("-0", "b");
                                                    let url = format!("https://github.com/Felix-Chaos/Actions-and-Stuff-RTX-Patcher/releases/download/{}/Actions.and.Stuff.RTX.Patcher_{}_x64-setup.exe", user_version, version);

                                                    if let Some(platforms) =
                                                        updater_val.get_mut("platforms")
                                                    {
                                                        if let Some(win) =
                                                            platforms.get_mut("windows-x86_64")
                                                        {
                                                            win["signature"] =
                                                                serde_json::Value::String(
                                                                    signature.trim().to_string(),
                                                                );
                                                            win["url"] =
                                                                serde_json::Value::String(url);
                                                        }
                                                    }

                                                    if let Ok(new_content) =
                                                        serde_json::to_string_pretty(&updater_val)
                                                    {
                                                        let _ = std::fs::write(
                                                            &updater_path,
                                                            new_content,
                                                        );
                                                        emit_log(&app_clone, "build-logs", "Successfully injected new signature and URL into updater.json!", "success");
                                                    }
                                                }
                                            }
                                        } else {
                                            emit_log(&app_clone, "build-logs", "Could not find .sig file to inject into updater.json", "warning");
                                        }
                                    }
                                }
                            }
                        } else {
                            emit_log(
                                &app_clone,
                                "build-logs",
                                &format!("Build failed with exit status: {}", status),
                                "error",
                            );
                        }
                    }
                    Err(e) => {
                        emit_log(
                            &app_clone,
                            "build-logs",
                            &format!("Error waiting for build process: {}", e),
                            "error",
                        );
                    }
                }
            }
            Err(e) => {
                emit_log(
                    &app_clone,
                    "build-logs",
                    &format!("Failed to start build process: {}", e),
                    "error",
                );
            }
        }
    });

    Ok(())
}

#[tauri::command]
pub fn get_app_version(app: tauri::AppHandle) -> String {
    app.package_info().version.to_string()
}

#[tauri::command]
pub fn is_dev_build() -> bool {
    cfg!(debug_assertions)
}

#[tauri::command]
pub fn write_text_file(path: String, content: String) -> Result<(), String> {
    std::fs::write(&path, content).map_err(|e| format!("Failed to write file {}: {}", path, e))
}

#[tauri::command]
pub async fn calculate_patch_stats(folder_path: String) -> Result<PatchStats, String> {
    use sha2::{Digest, Sha256};

    let path = std::path::Path::new(&folder_path);
    if !path.exists() {
        return Err(format!("Path does not exist: {}", folder_path));
    }

    let (files, dirs) = get_folder_stats(path);

    let logo_path = path.join("pack_icon.png");
    let logo_hash = if logo_path.exists() {
        if let Ok(content) = std::fs::read(&logo_path) {
            let mut hasher = Sha256::new();
            hasher.update(&content);
            let hash = hasher.finalize();
            hash.iter().map(|b| format!("{:02x}", b)).collect()
        } else {
            String::new()
        }
    } else {
        String::new()
    };

    let mut has_lang_file = false;
    if path.join("texts/en_US.lang").exists() || path.join("texts\\en_US.lang").exists() {
        has_lang_file = true;
    }

    Ok(PatchStats {
        files,
        dirs,
        logo_hash,
        has_lang_file,
    })
}

#[tauri::command]
pub async fn inject_custom_manifest_to_target(
    app: tauri::AppHandle,
    target_dir: String,
    pack_ver: String,
    patch_ver: String,
) -> Result<(), String> {
    let resource_manifest = resolve_asset_path(&app, "assets/resources/manifest.json")?;

    if !resource_manifest.exists() {
        return Err("Custom manifest not found in resources".to_string());
    }

    let content = std::fs::read_to_string(&resource_manifest)
        .map_err(|e| format!("Failed to read custom manifest: {}", e))?;

    let mut val: serde_json::Value = serde_json::from_str(&content)
        .map_err(|e| format!("Failed to parse custom manifest: {}", e))?;

    if !pack_ver.is_empty() && !patch_ver.is_empty() {
        if let Some(obj) = val.as_object_mut() {
            if let Some(header) = obj.get_mut("header") {
                if let Some(header_obj) = header.as_object_mut() {
                    let formatted_name = format!(
                        "§eActions & Stuff §dRTX §b{} §5V{}",
                        pack_ver.replace("v", ""),
                        patch_ver
                    );
                    header_obj.insert(
                        "name".to_string(),
                        serde_json::Value::String(formatted_name),
                    );

                    if let Some(desc) = header_obj.get("description") {
                        if let Some(desc_str) = desc.as_str() {
                            if !desc_str.starts_with("§e") {
                                let new_desc = format!("§e{}", desc_str);
                                header_obj.insert(
                                    "description".to_string(),
                                    serde_json::Value::String(new_desc),
                                );
                            }
                        }
                    }
                }
            }
        }
    }

    let modified_content = serde_json::to_string_pretty(&val)
        .map_err(|e| format!("Failed to serialize custom manifest: {}", e))?;

    let target_path = std::path::Path::new(&target_dir).join("manifest.json");
    std::fs::write(&target_path, modified_content)
        .map_err(|e| format!("Failed to write modified manifest: {}", e))?;

    let texts_path = std::path::Path::new(&target_dir).join("texts");
    if texts_path.exists() && !pack_ver.is_empty() && !patch_ver.is_empty() {
        if let Ok(entries) = std::fs::read_dir(&texts_path) {
            for entry in entries.filter_map(Result::ok) {
                let path = entry.path();
                if path.extension().and_then(|s| s.to_str()) == Some("lang") {
                    if let Ok(lang_content) = std::fs::read_to_string(&path) {
                        let mut new_lang = String::new();
                        for line in lang_content.lines() {
                            if line.starts_with("pack.name=") {
                                let formatted_name = format!(
                                    "§eActions & Stuff §dRTX §b{} §5V{}",
                                    pack_ver.replace("v", ""),
                                    patch_ver
                                );
                                new_lang.push_str(&format!("pack.name={}\n", formatted_name));
                            } else if line.starts_with("pack.description=") {
                                let desc = line.trim_start_matches("pack.description=");
                                if !desc.starts_with("§e") {
                                    new_lang.push_str(&format!("pack.description=§e{}\n", desc));
                                } else {
                                    new_lang.push_str(line);
                                    new_lang.push('\n');
                                }
                            } else {
                                new_lang.push_str(line);
                                new_lang.push('\n');
                            }
                        }
                        let _ = std::fs::write(&path, new_lang);
                    }
                }
            }
        }
    }

    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
#[tauri::command]
pub fn open_url(url: String) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("cmd")
            .args(&["/c", "start", "", &url])
            .creation_flags(0x08000000)
            .spawn()
            .map_err(|e| format!("Failed to open URL: {}", e))?;
    }
    Ok(())
}
