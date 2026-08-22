use crate::utils::*;
use std::collections::HashMap;
use std::io::BufRead;
#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;
use std::path::{Path, PathBuf};
use tauri::Manager;

#[tauri::command]
pub fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[derive(serde::Deserialize, Debug, Clone)]
pub struct ValidStats {
    pub files: usize,
    pub dirs: usize,
    pub version: Option<String>,
    pub is_latest: bool,
}

// Hard identity gate for scan_marketplace_packs: is this folder actually an
// Actions & Stuff pack at all, as opposed to some other installed pack
// (including other Oreville Studios products)? Checked once, up front,
// before any of the scoring below runs. The scoring further down is only
// ever meant to pick the best-matching *version* among genuine Actions &
// Stuff candidates — it must never be what decides "is this even Actions &
// Stuff", since several of its signals (has_lang_file, a manifest version
// number, a files/dirs count) can coincidentally match an unrelated pack too.
fn is_actions_and_stuff_pack(path: &Path) -> bool {
    for lang_rel in ["texts/en_US.lang", "texts/en_US.txt", "en_US.lang", "en_US.txt"] {
        if let Ok(content) = std::fs::read_to_string(path.join(lang_rel)) {
            for line in content.lines() {
                if line.starts_with("pack.name=") && line.contains("Actions & Stuf") {
                    return true;
                }
            }
        }
    }

    if let Ok(manifest_content) = std::fs::read_to_string(path.join("manifest.json")) {
        if manifest_content.contains("22ed17a6-ea7c-5ccd-93b4-b90e86ce0046") {
            return true;
        }
    }

    false
}

#[tauri::command]
pub async fn scan_marketplace_packs(
    expected_logo_hash: Option<String>,
    expected_has_lang_file: Option<bool>,
    valid_stats_list: Option<Vec<ValidStats>>,
) -> Result<Vec<MarketplaceCandidate>, String> {
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
                    if !is_actions_and_stuff_pack(&path) {
                        continue;
                    }
                    let version = get_lang_version(&path).unwrap_or_else(|| "Unknown".to_string());
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

                    let has_lang_file = path.join("texts/en_US.lang").exists() || path.join("texts/en_US.txt").exists() || path.join("en_US.lang").exists() || path.join("en_US.txt").exists();

                    let mut score = 0;
                    
                    // Score +1 for matching logo hash
                    if let Some(ref expected) = expected_logo_hash {
                        if &logo_hash == expected {
                            score += 1;
                        }
                    }
                    
                    // Score +1 for having the language file as expected
                    if let Some(expected) = expected_has_lang_file {
                        if has_lang_file == expected {
                            score += 1;
                        }
                    }
                    
                    // Score +1 for matching ANY files+dirs, and an extra +1 if it matches the LATEST version
                    // Score +1 for matching ANY version extracted from lang file
                    if let Some(ref valid_list) = valid_stats_list {
                        let mut matched = false;
                        let mut matched_latest = false;
                        let mut matched_version = false;
                        
                        for valid in valid_list {
                            if files_count == valid.files && dirs_count == valid.dirs {
                                matched = true;
                                if valid.is_latest {
                                    matched_latest = true;
                                }
                            }
                            if let Some(ref ev) = valid.version {
                                if version == *ev || version.starts_with(ev) || ev.starts_with(&version) {
                                    matched_version = true;
                                }
                            }
                        }
                        
                        if matched {
                            score += 1;
                        }
                        if matched_latest {
                            score += 1;
                        }
                        if matched_version {
                            score += 1;
                        }
                    }
                    
                    // If no expected stats are passed, just give score 1 (legacy fallback for
                    // bug reporter) — the is_actions_and_stuff_pack() gate above already
                    // confirmed this candidate really is Actions & Stuff, so there's nothing
                    // left to re-check here.
                    if valid_stats_list.is_none() && expected_logo_hash.is_none() {
                        score = 1;
                    }

                    // Include if score > 0
                    if score > 0 {
                        candidates.push(MarketplaceCandidate {
                            path: path.to_string_lossy().into_owned(),
                            version,
                            folder_name,
                            files_count,
                            dirs_count,
                            logo_hash,
                            score,
                        });
                    }
                }
            }
        }
    }
    
    candidates.sort_by(|a, b| b.score.cmp(&a.score));
    
    // If we have expected stats and no candidate fits, throw error
    if (valid_stats_list.is_some() || expected_logo_hash.is_some()) && candidates.is_empty() {
        return Err("No pack fits the expected stats in premium_cache. Please ensure the official pack is downloaded.".to_string());
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
pub async fn install_mcpack(app: tauri::AppHandle, output_file: String) -> Result<String, String> {
    let src_path = Path::new(&output_file);
    if !src_path.exists() {
        return Err("Output file not found".to_string());
    }

    let file_stem = src_path
        .file_stem()
        .ok_or_else(|| "Invalid filename".to_string())?;

    let mojang_paths: Vec<PathBuf> = get_install_target_paths()
        .into_iter()
        .filter(|p| p.exists())
        .collect();

    if mojang_paths.is_empty() {
        return Err("Could not find Minecraft installation directory.".to_string());
    }

    let mut last_dest = String::new();

    for mojang_path in mojang_paths {
        let packs_dir = mojang_path.join("resource_packs");
        if !packs_dir.exists() {
            let _ = std::fs::create_dir_all(&packs_dir);
        }

        let dest_dir = packs_dir.join(file_stem);

        if let Err(e) = extract_archive_impl(Some(&app), src_path, &dest_dir, "main") {
            crate::utils::emit_log(&app, "main", &format!("Failed to install to {:?}: {}", dest_dir, e), "error");
        } else {
            last_dest = dest_dir.to_string_lossy().into_owned();
        }
    }

    if last_dest.is_empty() {
        Err("Failed to install pack in any Minecraft directory.".to_string())
    } else {
        Ok(last_dest)
    }
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
    exclude_names: Option<Vec<String>>,
) -> Result<(), String> {
    pack_folder_impl(
        Some(&app),
        Path::new(&folder_path),
        Path::new(&output_zip),
        "main",
        &exclude_names.unwrap_or_default(),
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
    let resource_manifest = resolve_asset_path(&app, "assets/resources/manifest.json")?;

    if resource_manifest.exists() {
        emit_log(
            &app,
            "main",
            "Injecting custom manifest.json to ensure compatibility.",
            "info",
        );
        // Preserves this pack's own header/module uuid+version (from the
        // manifest.json still sitting in `dir` right now, before this
        // overwrites it) — see build_manifest_json's doc comment for why:
        // it's what lets a "Replace Unchanged" build's still-encrypted
        // content keep decrypting correctly after this replaces the manifest.
        let modified_content = build_manifest_json(&resource_manifest, dir, "", "")?;
        std::fs::write(dir.join("manifest.json"), modified_content)
            .map_err(|e| format!("Failed to write manifest.json: {}", e))?;
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
            let conf_path = project_root.join("src-tauri/tauri.conf.json");
            let mut version_str = String::new();
            if let Ok(content) = std::fs::read_to_string(&conf_path) {
                if let Ok(val) = serde_json::from_str::<serde_json::Value>(&content) {
                    if let Some(v) = val.get("version").and_then(|v| v.as_str()) {
                        version_str = v.to_string();
                    }
                }
            }

            if !version_str.is_empty() {
                let release_dir = project_root.join(format!("Releases/v{}", version_str));
                if release_dir.exists() {
                    release_dir
                } else {
                    let fallback_dir = project_root.join("Releases");
                    if fallback_dir.exists() { fallback_dir } else { project_root.clone() }
                }
            } else {
                let fallback_dir = project_root.join("Releases");
                if fallback_dir.exists() { fallback_dir } else { project_root.clone() }
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
    let uwp_resource_packs = format!("{}/games/com.mojang/resource_packs", uwp_root);

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
    } else if std::path::Path::new(&uwp_resource_packs).exists() {
        uwp_resource_packs.replace('\\', "/")
    } else {
        gdk_resource_packs.replace('\\', "/") // fallback even if it doesn't exist
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
pub fn run_release_build(app: tauri::AppHandle, build_type: String) -> Result<(), String> {
    let project_root = get_project_root(&app);
    if project_root.to_string_lossy().is_empty() {
        return Err("Could not determine project root directory".to_string());
    }

    let app_clone = app.clone();
    std::thread::spawn(move || {
        let cmd_str = match build_type.as_str() {
            "portable_only" => "npm run tauri build -- --no-bundle",
            "installers_only" => "npm run tauri build -- --bundles msi,nsis",
            _ => "npm run tauri build",
        };

        emit_log(
            &app_clone,
            "build-logs",
            "Starting project release build...",
            "info",
        );
        emit_log(
            &app_clone,
            "build-logs",
            &format!("Executing command: {}", cmd_str),
            "info",
        );

        let mut cmd = std::process::Command::new("cmd");
        cmd.args(&["/c", cmd_str]);
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

                            // Automate updater.json signature injection and copy artifacts
                            let conf_path = project_root.join("src-tauri/tauri.conf.json");
                            if let Ok(content) = std::fs::read_to_string(&conf_path) {
                                if let Ok(val) = serde_json::from_str::<serde_json::Value>(&content)
                                {
                                    if let Some(version) =
                                        val.get("version").and_then(|v| v.as_str())
                                    {
                                        // Sort build artifacts into Releases folder
                                        let release_dir = project_root.join(format!("Releases/v{}", version));
                                        let _ = std::fs::create_dir_all(&release_dir);
                                        
                                        emit_log(&app_clone, "build-logs", &format!("Sorting build artifacts into Releases/v{}...", version), "info");
                                        
                                        // Package portable build into zip
                                        let portable_src = project_root.join("src-tauri/target/release/tauri-app.exe");
                                        if portable_src.exists() {
                                            let staging_dir = project_root.join(format!("src-tauri/target/release/portable_staging_{}", version));
                                            let _ = std::fs::remove_dir_all(&staging_dir); // Clean old staging if any
                                            let _ = std::fs::create_dir_all(&staging_dir);
                                            
                                            // Copy exe to staging
                                            let _ = std::fs::copy(&portable_src, staging_dir.join(format!("Actions.and.Stuff.RTX.Patcher_{}_portable.exe", version)));
                                            
                                            // Copy assets to staging
                                            let assets_src = project_root.join("src-tauri/assets");
                                            if assets_src.exists() {
                                                let _ = copy_dir_all(&assets_src, staging_dir.join("assets"));
                                            }
                                            
                                            // Pack staging folder
                                            let zip_dest = release_dir.join(format!("Actions.and.Stuff.RTX.Patcher_{}_portable.zip", version));
                                            emit_log(&app_clone, "build-logs", "Compressing portable release package into ZIP...", "info");
                                            if let Err(e) = pack_folder_impl(None, &staging_dir, &zip_dest, "build-logs", &[]) {
                                                emit_log(&app_clone, "build-logs", &format!("Failed to create portable ZIP: {}", e), "error");
                                            } else {
                                                emit_log(&app_clone, "build-logs", "Portable release package ZIP created successfully.", "info");
                                            }
                                            
                                            // Clean up staging
                                            let _ = std::fs::remove_dir_all(&staging_dir);
                                        }
                                        
                                        // Copy NSIS installer
                                        let nsis_src = project_root.join(format!("src-tauri/target/release/bundle/nsis/Actions and Stuff RTX Patcher_{}_x64-setup.exe", version));
                                        let nsis_dest = release_dir.join(format!("Actions.and.Stuff.RTX.Patcher_{}_x64-setup.exe", version));
                                        if nsis_src.exists() {
                                            let _ = std::fs::copy(&nsis_src, &nsis_dest);
                                        }
                                        
                                        // Copy MSI installer
                                        let msi_src = project_root.join(format!("src-tauri/target/release/bundle/msi/Actions and Stuff RTX Patcher_{}_x64_en-US.msi", version));
                                        let msi_dest = release_dir.join(format!("Actions.and.Stuff.RTX.Patcher_{}_x64_en-US.msi", version));
                                        if msi_src.exists() {
                                            let _ = std::fs::copy(&msi_src, &msi_dest);
                                        }

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
                                                    let url = format!("https://github.com/Felix-Chaos/Actions-and-Stuff-RTX-Patcher/releases/download/V{}/Actions.and.Stuff.RTX.Patcher_{}_x64-setup.exe", user_version, version);

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
                                                    // Keep the top-level "version" field in sync too — this is
                                                    // what the updater plugin actually compares against the
                                                    // running app's version. Without this, a build that skips
                                                    // the separate "apply version" step leaves this stale and
                                                    // the update never shows up as available.
                                                    updater_val["version"] =
                                                        serde_json::Value::String(
                                                            version.to_string(),
                                                        );

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

/// Builds the manifest.json content for a target pack directory: starts from
/// the bundled custom RTX manifest template (capabilities, subpacks, in-game
/// settings — all required for RTX features to work at all), but preserves
/// the ORIGINAL pack's own header/module `uuid` and `version`, read from
/// `identity_source_dir`'s manifest.json if one exists there (a real
/// Marketplace-purchased pack's identity). This matters: Marketplace DRM
/// decryption checks the signed-in account's purchase entitlement against
/// that identity, so swapping in the custom template's own fixed placeholder
/// UUIDs instead would make Minecraft unable to decrypt anything left in
/// encrypted form (see Create Patch's "Replace Unchanged") even though
/// contents.json/signatures.json themselves are otherwise untouched — the
/// pack would no longer look like something the player actually owns.
///
/// `identity_source_dir` is deliberately a separate parameter from
/// `target_dir` (where the result gets written): a working "Decrypted Dir"
/// folder can easily have already had a previous custom manifest written
/// into it (e.g. by an earlier Create Patch run) and no longer carry the
/// pack's real purchased identity at all, whereas the raw Encrypted Dir
/// (the untouched Marketplace cache) always does. Callers should point
/// `identity_source_dir` at whichever directory is actually guaranteed to
/// still hold the genuine identity — Create Patch uses the Encrypted Dir for
/// this; normalize_extracted_pack uses the pack currently being normalized,
/// since there's no separate reference available at apply time.
///
/// If `pack_ver`/`patch_ver` are both non-empty, also brands header.name/
/// description with the patch version — purely cosmetic, independent of the
/// identity fields.
///
/// Used by both inject_custom_manifest_to_target (Create Patch's reference
/// source) and normalize_extracted_pack (real end-user packs at apply time) —
/// they must produce identical bytes for a given input, since one becomes the
/// baseline decrypted.vcdiff is diffed against and the other is what a real
/// pack looks like when the patch actually gets applied to it.
fn build_manifest_json(
    resource_manifest: &Path,
    identity_source_dir: &Path,
    pack_ver: &str,
    patch_ver: &str,
) -> Result<String, String> {
    let content = std::fs::read_to_string(resource_manifest)
        .map_err(|e| format!("Failed to read custom manifest: {}", e))?;
    let mut val: serde_json::Value = serde_json::from_str(&content)
        .map_err(|e| format!("Failed to parse custom manifest: {}", e))?;

    if let Ok(existing_content) = std::fs::read_to_string(identity_source_dir.join("manifest.json")) {
        if let Ok(existing_val) = serde_json::from_str::<serde_json::Value>(&existing_content) {
            if let Some(orig_header) = existing_val.get("header").and_then(|h| h.as_object()) {
                if let Some(new_header) = val.get_mut("header").and_then(|h| h.as_object_mut()) {
                    for key in ["uuid", "version"] {
                        if let Some(v) = orig_header.get(key) {
                            new_header.insert(key.to_string(), v.clone());
                        }
                    }
                }
            }
            if let Some(orig_modules) = existing_val.get("modules").and_then(|m| m.as_array()) {
                if let Some(new_modules) = val.get_mut("modules").and_then(|m| m.as_array_mut()) {
                    for new_mod in new_modules.iter_mut() {
                        let new_type = new_mod.get("type").and_then(|t| t.as_str()).map(String::from);
                        let matching_orig = new_type.as_ref().and_then(|nt| {
                            orig_modules
                                .iter()
                                .find(|m| m.get("type").and_then(|t| t.as_str()) == Some(nt.as_str()))
                        });
                        if let (Some(matching_orig), Some(new_mod_obj)) = (matching_orig, new_mod.as_object_mut()) {
                            for key in ["uuid", "version"] {
                                if let Some(v) = matching_orig.get(key) {
                                    new_mod_obj.insert(key.to_string(), v.clone());
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    if !pack_ver.is_empty() && !patch_ver.is_empty() {
        if let Some(header_obj) = val.get_mut("header").and_then(|h| h.as_object_mut()) {
            let formatted_name = format!(
                "§eActions & Stuff §dRTX §b{} §5V{}",
                pack_ver.replace("v", ""),
                patch_ver
            );
            header_obj.insert("name".to_string(), serde_json::Value::String(formatted_name));

            if let Some(desc) = header_obj.get("description") {
                if let Some(desc_str) = desc.as_str() {
                    if !desc_str.starts_with("§e") {
                        let new_desc = format!("§e{}", desc_str);
                        header_obj.insert("description".to_string(), serde_json::Value::String(new_desc));
                    }
                }
            }
        }
    }

    serde_json::to_string_pretty(&val).map_err(|e| format!("Failed to serialize custom manifest: {}", e))
}

#[tauri::command]
pub async fn inject_custom_manifest_to_target(
    app: tauri::AppHandle,
    target_dir: String,
    pack_ver: String,
    patch_ver: String,
    // Where to read the pack's real, purchased identity (header/module
    // uuid+version) from — should be the raw Encrypted Dir, which (unlike a
    // working Decrypted Dir) can't have already lost it to a previous custom
    // manifest injection. Falls back to target_dir itself if omitted, which
    // only recovers the real identity if target_dir hasn't been touched yet.
    identity_source_dir: Option<String>,
) -> Result<(), String> {
    let resource_manifest = resolve_asset_path(&app, "assets/resources/manifest.json")?;

    if !resource_manifest.exists() {
        return Err("Custom manifest not found in resources".to_string());
    }

    let target_path = std::path::Path::new(&target_dir);
    let identity_path = identity_source_dir
        .as_deref()
        .map(std::path::Path::new)
        .unwrap_or(target_path);
    let modified_content = build_manifest_json(&resource_manifest, identity_path, &pack_ver, &patch_ver)?;
    std::fs::write(target_path.join("manifest.json"), modified_content)
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

#[tauri::command]
pub fn open_url(url: String) -> Result<(), String> {
    // `cmd /c start` re-parses the whole command line, so metacharacters like
    // `&`/`|` in `url` are not fully neutralized by argv quoting alone.
    // Restricting to http(s) URLs keeps this command from being usable to
    // launch arbitrary local files/protocol handlers or smuggle shell syntax.
    if !(url.starts_with("https://") || url.starts_with("http://")) {
        return Err("Refusing to open a non-http(s) URL".to_string());
    }
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

#[tauri::command]
pub async fn fetch_motd() -> Result<serde_json::Value, String> {
    let api_url = std::option_env!("PATCHER_API_URL").unwrap_or("http://localhost:3000");
    let api_key = std::option_env!("PATCHER_API_KEY").unwrap_or("");

    let client = reqwest::Client::new();
    let res = client.get(&format!("{}/api/patcher/motd", api_url))
        .header("Authorization", format!("Bearer {}", api_key))
        .send()
        .await
        .map_err(|e| format!("Request failed: {}", e))?;
        
    let json: serde_json::Value = res.json()
        .await
        .map_err(|e| format!("Failed to parse JSON: {}", e))?;
        
    Ok(json)
}

fn encode_file_base64(path: &Path) -> Result<String, String> {
    use std::io::Read;
    use base64::prelude::*;
    if !path.exists() {
        return Err(format!("File not found: {:?}", path));
    }
    let mut file = std::fs::File::open(path).map_err(|e| e.to_string())?;
    let mut buffer = Vec::new();
    file.read_to_end(&mut buffer).map_err(|e| e.to_string())?;
    
    Ok(BASE64_STANDARD.encode(buffer))
}

// get_hwid() removed: it read the Windows MachineGuid, a persistent device
// identifier. For DSGVO conformity reports are now keyed by the random,
// locally generated install id from the telemetry module instead.

#[tauri::command]
pub async fn submit_bug_report(
    app: tauri::AppHandle,
    // None/omitted means an anonymous submission (e.g. the one-click "Known
    // Issue" reporter) — the server then skips linking the report to any
    // Discord account and just posts it to whichever server is configured
    // to receive Patcher reports.
    discord_name: Option<String>,
    description: String,
    log_path: Option<String>,
    pack_path: Option<String>,
    content_log_zip_path: Option<String>,
    include_driver_events: Option<bool>,
    include_hardware: Option<bool>,
    categories: Option<Vec<String>>,
) -> Result<serde_json::Value, String> {
    let api_url = std::option_env!("PATCHER_API_URL").unwrap_or("http://localhost:3000");
    let api_key = std::option_env!("PATCHER_API_KEY").unwrap_or("");
    // DSGVO: identify reports by the random install id, never by MachineGuid.
    let install_id = crate::telemetry::load_state(&app)
        .map(|s| s.install_id)
        .unwrap_or_else(|_| "unknown".to_string());

    let mut payload = serde_json::json!({
        "discordName": discord_name,
        "description": description,
        "hwid": install_id.clone(),
        "installId": install_id,
        "includeLog": log_path.is_some(),
        "includePack": pack_path.is_some(),
        "includeContentLog": content_log_zip_path.is_some(),
        "categories": categories.unwrap_or_default(),
    });

    if let Some(ref path) = log_path {
        if let Ok(b64) = encode_file_base64(Path::new(path)) {
            payload.as_object_mut().unwrap().insert("logBase64".to_string(), serde_json::Value::String(b64));
        }
    }

    if let Some(ref path) = pack_path {
        if let Ok(b64) = encode_file_base64(Path::new(path)) {
            payload.as_object_mut().unwrap().insert("packBase64".to_string(), serde_json::Value::String(b64));
        }
    }

    if let Some(ref path) = content_log_zip_path {
        if let Ok(b64) = encode_file_base64(Path::new(path)) {
            payload.as_object_mut().unwrap().insert("contentLogBase64".to_string(), serde_json::Value::String(b64));
        }
    }

    if include_driver_events.unwrap_or(false) {
        if let Ok(events_json) = crate::telemetry::collect_driver_events() {
            if let Ok(events) = serde_json::from_str::<serde_json::Value>(&events_json) {
                payload.as_object_mut().unwrap().insert("driverEvents".to_string(), events);
            }
        }
    }

    if include_hardware.unwrap_or(false) {
        if let Ok(hw) = crate::telemetry::collect_hardware_info(app.clone()) {
            payload.as_object_mut().unwrap().insert("hardware".to_string(), hw);
        }
    }
    
    let client = reqwest::Client::new();
    let res = client.post(&format!("{}/api/patcher/bug-report", api_url))
        .header("Authorization", format!("Bearer {}", api_key))
        .json(&payload)
        .send()
        .await
        .map_err(|e| format!("Request failed: {}", e))?;
        
    let status = res.status();
    let json: serde_json::Value = res.json()
        .await
        .map_err(|e| format!("Failed to parse response: {}", e))?;
        
    if !status.is_success() {
        if let Some(err) = json.get("error") {
            return Err(err.as_str().unwrap_or("Unknown error").to_string());
        }
        return Err(format!("Server returned {}", status));
    }
        
    Ok(json)
}

#[tauri::command]
pub async fn prepare_patch_target(
    app: tauri::AppHandle,
    rtx_dir: String,
    temp_target_dir: String,
) -> Result<(), String> {
    let rtx_path = Path::new(&rtx_dir);
    let tgt_path = Path::new(&temp_target_dir);

    emit_log(&app, "genpatch-logs", "Starting patch target preparation...", "info");

    if !tgt_path.exists() {
        std::fs::create_dir_all(tgt_path).map_err(|e| e.to_string())?;
    }

    emit_log(&app, "genpatch-logs", "Copying modified assets...", "info");
    copy_dir_all(rtx_path, tgt_path).map_err(|e| format!("Failed to copy RTX dir: {}", e))?;

    emit_log(&app, "genpatch-logs", "Patch target ready.", "success");

    Ok(())
}

#[derive(serde::Serialize, serde::Deserialize, Clone)]
pub struct PatchVersions {
    #[serde(rename = "packVersion")]
    pub pack_version: String,
    #[serde(rename = "patchVersion")]
    pub patch_version: String,
}

#[tauri::command]
pub fn get_patch_versions(_app: tauri::AppHandle) -> Result<PatchVersions, String> {
    let project_root = std::env::current_dir().map_err(|e| e.to_string())?;
    let config_path = project_root.join("patch_versions.json");
    
    if !config_path.exists() {
        return Err("patch_versions.json does not exist".to_string());
    }
    
    let content = std::fs::read_to_string(&config_path).map_err(|e| e.to_string())?;
    let versions = serde_json::from_str::<PatchVersions>(&content).map_err(|e| e.to_string())?;
    
    Ok(versions)
}

#[tauri::command]
pub fn save_patch_versions(_app: tauri::AppHandle, pack_version: String, patch_version: String) -> Result<(), String> {
    let project_root = std::env::current_dir().map_err(|e| e.to_string())?;
    let config_path = project_root.join("patch_versions.json");
    
    let versions = PatchVersions {
        pack_version,
        patch_version,
    };
    
    let content = serde_json::to_string_pretty(&versions).map_err(|e| e.to_string())?;
    std::fs::write(&config_path, content).map_err(|e| e.to_string())?;
    
    Ok(())
}


#[tauri::command]
pub fn load_settings(app: tauri::AppHandle) -> Result<String, String> {
    let settings_path = user_data_dir(&app)?.join("settings.json");
    if settings_path.exists() {
        std::fs::read_to_string(settings_path).map_err(|e| e.to_string())
    } else {
        Ok("{}".to_string())
    }
}

#[tauri::command]
pub fn save_settings(app: tauri::AppHandle, settings: String) -> Result<(), String> {
    let settings_path = user_data_dir(&app)?.join("settings.json");
    std::fs::write(settings_path, settings).map_err(|e| e.to_string())
}
