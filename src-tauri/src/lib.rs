use std::collections::HashMap;
use std::fs::File;
use std::io::{Read, Write, BufRead};
use std::path::{Path, PathBuf};
use zip::write::SimpleFileOptions;
use zip::ZipWriter;
use tauri::{Manager, Emitter};

#[cfg(target_os = "windows")]
use std::os::windows::ffi::OsStrExt;
#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

#[cfg(target_os = "windows")]
extern "system" {
    fn SetFileAttributesW(lpFileName: *const u16, dwFileAttributes: u32) -> i32;
}

#[derive(Clone, serde::Serialize)]
struct LogPayload {
    container: String,
    message: String,
    log_type: String,
}

fn emit_log(app: &tauri::AppHandle, container: &str, msg: &str, log_type: &str) {
    let _ = app.emit("app-log", LogPayload {
        container: container.to_string(),
        message: msg.to_string(),
        log_type: log_type.to_string(),
    });
}

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

// Helper: robust cleanup with retries
fn robust_cleanup(path: &Path) -> bool {
    if !path.exists() {
        return true;
    }
    for _ in 0..3 {
        let res = if path.is_dir() {
            std::fs::remove_dir_all(path)
        } else {
            std::fs::remove_file(path)
        };
        if res.is_ok() {
            return true;
        }
        std::thread::sleep(std::time::Duration::from_millis(500));
    }
    false
}

// Helper: collect files for deterministic zip
fn collect_files(root: &Path, current: &Path, files: &mut Vec<(PathBuf, String)>) -> Result<(), String> {
    if current.is_dir() {
        for entry in std::fs::read_dir(current).map_err(|e| e.to_string())? {
            let entry = entry.map_err(|e| e.to_string())?;
            let path = entry.path();
            collect_files(root, &path, files)?;
        }
    } else if current.is_file() {
        let rel_path = current.strip_prefix(root)
            .map_err(|e| e.to_string())?
            .to_string_lossy()
            .replace("\\", "/");
        files.push((current.to_path_buf(), rel_path));
    }
    Ok(())
}

// Helper: deterministic ZIP packer
fn pack_folder_impl(app: Option<&tauri::AppHandle>, folder_path: &Path, output_zip: &Path, container: &str) -> Result<(), String> {
    let file = File::create(output_zip).map_err(|e| format!("Failed to create zip: {}", e))?;
    let mut zip = ZipWriter::new(file);

    // Fixed timestamp (Jan 1, 1980) for deterministic output
    let fixed_time = zip::DateTime::from_date_and_time(1980, 1, 1, 0, 0, 0)
        .map_err(|e| format!("Failed to parse zip time: {}", e))?;

    let options = SimpleFileOptions::default()
        .compression_method(zip::CompressionMethod::Stored)
        .last_modified_time(fixed_time);

    let mut files: Vec<(PathBuf, String)> = Vec::new();
    collect_files(folder_path, folder_path, &mut files)?;
    files.sort_by(|a, b| a.1.cmp(&b.1));

    if let Some(app_handle) = app {
        emit_log(app_handle, container, &format!("Scanning folder to pack: {:?}", folder_path), "info");
        emit_log(app_handle, container, &format!("Found {} files to compress deterministically.", files.len()), "info");
    }

    for (abs_path, rel_path) in files {
        if let Some(app_handle) = app {
            emit_log(app_handle, container, &format!("  [Compressing] -> {}", rel_path), "info");
        }
        let mut f = File::open(&abs_path)
            .map_err(|e| format!("Failed to open file {:?}: {}", abs_path, e))?;
        let mut buffer = Vec::new();
        f.read_to_end(&mut buffer)
            .map_err(|e| format!("Failed to read file {:?}: {}", abs_path, e))?;

        zip.start_file(rel_path, options)
            .map_err(|e| format!("Failed to start file in zip: {}", e))?;
        zip.write_all(&buffer)
            .map_err(|e| format!("Failed to write file to zip: {}", e))?;
    }

    zip.finish().map_err(|e| format!("Failed to finalize zip: {}", e))?;
    if let Some(app_handle) = app {
        emit_log(app_handle, container, &format!("Deterministic pack created successfully at: {:?}", output_zip), "success");
    }
    Ok(())
}

// Helper: zip/mcpack extraction with smart folder unwrapping
fn extract_archive_impl(app: Option<&tauri::AppHandle>, zip_path: &Path, output_dir: &Path, container: &str) -> Result<(), String> {
    let file = File::open(zip_path).map_err(|e| format!("Failed to open zip: {}", e))?;
    let mut archive = zip::ZipArchive::new(file).map_err(|e| format!("Failed to read zip: {}", e))?;
    
    if output_dir.exists() {
        if let Some(app_handle) = app {
            emit_log(app_handle, container, &format!("Cleaning existing extraction directory: {:?}", output_dir), "info");
        }
        let _ = std::fs::remove_dir_all(output_dir);
    }
    std::fs::create_dir_all(output_dir).map_err(|e| format!("Failed to create output dir: {}", e))?;
    
    if let Some(app_handle) = app {
        emit_log(app_handle, container, &format!("Extracting archive {:?} (contains {} files)", zip_path, archive.len()), "info");
    }

    for i in 0..archive.len() {
        let mut file = archive.by_index(i).map_err(|e| format!("Failed to read zip file: {}", e))?;
        let outpath = match file.enclosed_name() {
            Some(path) => output_dir.join(path),
            None => continue,
        };
        
        if file.name().ends_with('/') {
            if let Some(app_handle) = app {
                emit_log(app_handle, container, &format!("  [Dir Created] -> {}", file.name()), "info");
            }
            std::fs::create_dir_all(&outpath).map_err(|e| format!("Failed to create directory: {}", e))?;
        } else {
            if let Some(app_handle) = app {
                emit_log(app_handle, container, &format!("  [Extracted] -> {} ({} bytes)", file.name(), file.size()), "info");
            }
            if let Some(p) = outpath.parent() {
                if !p.exists() {
                    std::fs::create_dir_all(p).map_err(|e| format!("Failed to create directory: {}", e))?;
                }
            }
            let mut outfile = File::create(&outpath).map_err(|e| format!("Failed to create output file: {}", e))?;
            std::io::copy(&mut file, &mut outfile).map_err(|e| format!("Failed to copy file contents: {}", e))?;
        }
    }
    
    // Smart folder detection: if the extract_dir contains only a single directory, move all its contents up
    let mut entries = Vec::new();
    if let Ok(rd) = std::fs::read_dir(output_dir) {
        for entry in rd.flatten() {
            entries.push(entry.path());
        }
    }
    if entries.len() == 1 && entries[0].is_dir() {
        let single_dir = &entries[0];
        if let Some(app_handle) = app {
            emit_log(app_handle, container, &format!("Smart Unwrap: single root folder {:?} detected. Moving contents up...", single_dir.file_name().unwrap()), "info");
        }
        if let Ok(rd) = std::fs::read_dir(single_dir) {
            for entry in rd.flatten() {
                let path = entry.path();
                let dest = output_dir.join(path.file_name().unwrap());
                if let Some(app_handle) = app {
                    emit_log(app_handle, container, &format!("  [Moving up] -> {:?}", path.file_name().unwrap()), "info");
                }
                std::fs::rename(&path, &dest)
                    .map_err(|e| format!("Failed to move file during smart unwrap: {}", e))?;
            }
        }
        let _ = std::fs::remove_dir(single_dir);
    }
    
    if let Some(app_handle) = app {
        emit_log(app_handle, container, &format!("Successfully extracted all files to {:?}", output_dir), "success");
    }
    Ok(())
}

// Helper: extract pack version from en_US.lang
fn get_lang_version(path: &Path) -> Option<String> {
    let lang_path = path.join("texts").join("en_US.lang");
    if !lang_path.exists() {
        return None;
    }
    if let Ok(content) = std::fs::read_to_string(&lang_path) {
        for line in content.lines() {
            if line.starts_with("pack.name=") {
                if let Some(idx) = line.find("Actions & Stuf") {
                    let raw_ver = &line[idx + 14..];
                    let clean_ver: String = raw_ver.chars()
                        .filter(|c| c.is_numeric() || *c == '.')
                        .collect();
                    let clean_ver = clean_ver.trim_matches('.').to_string();
                    if !clean_ver.is_empty() {
                        return Some(clean_ver);
                    }
                }
            }
        }
    }
    None
}

// Helper: get standard Minecraft com.mojang paths
fn get_mojang_paths() -> Vec<PathBuf> {
    let mut paths = Vec::new();
    let local_app_data = std::env::var("LOCALAPPDATA").ok().map(PathBuf::from);
    let app_data = std::env::var("APPDATA").ok().map(PathBuf::from);
    
    if let Some(ref lad) = local_app_data {
        paths.push(lad.join(r"Packages\Microsoft.MinecraftUWP_8wekyb3d8bbwe\LocalState\games\com.mojang"));
        paths.push(lad.join(r"Packages\Microsoft.MinecraftWindowsBeta_8wekyb3d8bbwe\LocalState\games\com.mojang"));
    }
    
    if let Some(ref ad) = app_data {
        paths.push(ad.join(r"Minecraft Bedrock\games\com.mojang"));
        paths.push(ad.join(r"Minecraft Bedrock Preview\games\com.mojang"));
        
        let users_dir = ad.join(r"Minecraft Bedrock\Users");
        if users_dir.exists() {
            if let Ok(entries) = std::fs::read_dir(users_dir) {
                for entry in entries.flatten() {
                    if entry.path().is_dir() {
                        paths.push(entry.path().join(r"games\com.mojang"));
                    }
                }
            }
        }
    }
    
    paths.retain(|p| p.exists());
    paths
}

// Helper: scan a com.mojang directory for cleanable packs matching prefixes
fn scan_cleanable_packs_in_mojang(mojang_path: &Path) -> Vec<PathBuf> {
    let mut results = Vec::new();
    let prefixes = vec!["a&s", "actions & st", "actions&st", "a&sforrtx", "actions & stuff enhanced", "actions & stuff rtx"];
    
    let check_dir_and_collect = |dir_path: &Path, results: &mut Vec<PathBuf>| {
        if let Ok(entries) = std::fs::read_dir(dir_path) {
            for entry in entries.flatten() {
                if entry.path().is_dir() {
                    if let Some(name) = entry.file_name().to_str() {
                        let lower_name = name.to_lowercase();
                        if prefixes.iter().any(|prefix| lower_name.starts_with(prefix)) {
                            results.push(entry.path());
                        }
                    }
                }
            }
        }
    };
    
    check_dir_and_collect(&mojang_path.join("resource_packs"), &mut results);
    check_dir_and_collect(&mojang_path.join("development_resource_packs"), &mut results);
    
    let worlds_dir = mojang_path.join("minecraftWorlds");
    if worlds_dir.exists() {
        if let Ok(world_entries) = std::fs::read_dir(worlds_dir) {
            for world_entry in world_entries.flatten() {
                if world_entry.path().is_dir() {
                    check_dir_and_collect(&world_entry.path().join("resource_packs"), &mut results);
                }
            }
        }
    }
    
    results
}

// Helper: count files and folders recursively
fn get_folder_stats(dir: &Path) -> (usize, usize) {
    let mut files = 0;
    let mut dirs = 0;
    if let Ok(entries) = std::fs::read_dir(dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                dirs += 1;
                let (f, d) = get_folder_stats(&path);
                files += f;
                dirs += d;
            } else if path.is_file() {
                files += 1;
            }
        }
    }
    (files, dirs)
}

#[derive(serde::Serialize)]
struct MarketplaceCandidate {
    path: String,
    version: String,
    folder_name: String,
    files_count: usize,
    dirs_count: usize,
}

#[tauri::command]
fn scan_marketplace_packs() -> Result<Vec<MarketplaceCandidate>, String> {
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
        base_paths.push(PathBuf::from(ad).join(r"Minecraft Bedrock Preview\premium_cache\resource_packs"));
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
                            if manifest_content.contains("22ed17a6-ea7c-5ccd-93b4-b90e86ce0046") || 
                               manifest_content.contains("Oreville Studios") {
                                is_match = true;
                            }
                        }
                    }
                    
                    if is_match {
                        let version = get_lang_version(&path).unwrap_or_else(|| "Unknown".to_string());
                        let folder_name = entry.file_name().to_string_lossy().into_owned();
                        let (files_count, dirs_count) = get_folder_stats(&path);
                        candidates.push(MarketplaceCandidate {
                            path: path.to_string_lossy().into_owned(),
                            version,
                            folder_name,
                            files_count,
                            dirs_count,
                        });
                    }
                }
            }
        }
    }
    Ok(candidates)
}

#[tauri::command]
fn get_patch_configs(app: tauri::AppHandle) -> Result<Vec<serde_json::Value>, String> {
    let resource_dir = app.path().resource_dir()
        .map_err(|e| format!("Failed to get resource dir: {}", e))?;
    let patches_dir = resource_dir.join("assets/Patches");
        
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
                        if let Ok(mut json_val) = serde_json::from_str::<serde_json::Value>(&content) {
                            if let Some(obj) = json_val.as_object_mut() {
                                let folder_name = entry.file_name().to_string_lossy().into_owned();
                                obj.insert("folder_name".to_string(), serde_json::Value::String(folder_name));
                                
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
fn run_xdelta_patch(
    app: tauri::AppHandle,
    source_zip: String,
    patch_file: String,
    output_file: String
) -> Result<String, String> {
    let resource_dir = app.path().resource_dir()
        .map_err(|e| format!("Failed to get resource dir: {}", e))?;
    let xdelta_path = resource_dir.join("assets/xdelta3/exec/xdelta3_x86_64_win.exe");
        
    if !xdelta_path.exists() {
        return Err(format!("XDelta executable not found at resources: {:?}", xdelta_path));
    }
    
    emit_log(&app, "main", "Initiating XDelta patch execution...", "info");
    emit_log(&app, "main", &format!("  [Executable] -> {:?}", xdelta_path), "info");
    emit_log(&app, "main", &format!("  [Source ZIP] -> {}", source_zip), "info");
    emit_log(&app, "main", &format!("  [Patch File] -> {}", patch_file), "info");
    emit_log(&app, "main", &format!("  [Output File] -> {}", output_file), "info");

    let out_path = Path::new(&output_file);
    if let Some(parent) = out_path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("Failed to create output dir: {}", e))?;
    }
    
    if out_path.exists() {
        emit_log(&app, "main", "Removing pre-existing output file...", "info");
        let _ = std::fs::remove_file(out_path);
    }
    
    let mut cmd = std::process::Command::new(&xdelta_path);
    cmd.args(&["-f", "-v", "-d", "-s", &source_zip, &patch_file, &output_file]);
    
    #[cfg(target_os = "windows")]
    cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW
    
    let output = cmd.output().map_err(|e| format!("Failed to run patch executable: {}", e))?;
    
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
    
    emit_log(&app, "main", "XDelta patch decoding completed successfully.", "success");
    Ok("Patch applied successfully.".to_string())
}

#[tauri::command]
fn install_mcpack(output_file: String) -> Result<String, String> {
    let src_path = Path::new(&output_file);
    if !src_path.exists() {
        return Err("Output file not found".to_string());
    }
    
    let parent = src_path.parent().unwrap_or_else(|| Path::new(""));
    let file_stem = src_path.file_stem().ok_or_else(|| "Invalid filename".to_string())?;
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
        cmd.spawn().map_err(|e| format!("Failed to launch Minecraft installer: {}", e))?;
    }
    #[cfg(not(target_os = "windows"))]
    {
        open::that(&mcpack_path).map_err(|e| format!("Failed to launch Minecraft installer: {}", e))?;
    }
    
    Ok(mcpack_path.to_string_lossy().into_owned())
}

#[tauri::command]
fn get_cleanable_packs() -> Result<Vec<String>, String> {
    let mut results = Vec::new();
    for path in get_mojang_paths() {
        for p in scan_cleanable_packs_in_mojang(&path) {
            results.push(p.to_string_lossy().into_owned());
        }
    }
    Ok(results)
}

#[tauri::command]
fn delete_folders(folders: Vec<String>) -> Result<usize, String> {
    let mut deleted_count = 0;
    for f in folders {
        if robust_cleanup(Path::new(&f)) {
            deleted_count += 1;
        }
    }
    Ok(deleted_count)
}

#[derive(serde::Serialize)]
struct OptionsFile {
    label: String,
    path: String,
}

#[tauri::command]
fn get_options_paths() -> Result<Vec<OptionsFile>, String> {
    let mut results = Vec::new();
    let local_app_data = std::env::var("LOCALAPPDATA").ok();
    let app_data = std::env::var("APPDATA").ok();
    
    if let Some(ref ad) = app_data {
        let roaming_users = PathBuf::from(ad).join(r"Minecraft Bedrock\Users");
        if roaming_users.exists() {
            if let Ok(entries) = std::fs::read_dir(roaming_users) {
                for entry in entries.flatten() {
                    let candidate = entry.path().join(r"games\com.mojang\minecraftpe\options.txt");
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
fn read_options(path: String) -> Result<HashMap<String, String>, String> {
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
fn write_options(path: String, changes: HashMap<String, String>) -> Result<(), String> {
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
    
    std::fs::write(file_path, output)
        .map_err(|e| format!("Failed to write options.txt: {}", e))?;
    Ok(())
}

#[tauri::command]
fn pack_folder(app: tauri::AppHandle, folder_path: String, output_zip: String) -> Result<(), String> {
    pack_folder_impl(Some(&app), Path::new(&folder_path), Path::new(&output_zip), "main")
}

#[tauri::command]
fn extract_archive(app: tauri::AppHandle, zip_path: String, output_dir: String) -> Result<(), String> {
    extract_archive_impl(Some(&app), Path::new(&zip_path), Path::new(&output_dir), "main")
}

#[tauri::command]
fn normalize_extracted_pack(app: tauri::AppHandle, extract_dir: String) -> Result<(), String> {
    let dir = Path::new(&extract_dir);
    if !dir.exists() {
        return Err("Extraction directory does not exist".to_string());
    }
    
    emit_log(&app, "main", &format!("Normalizing extracted pack directory: {:?}", dir), "info");
    
    let files_to_remove = ["contents.json", "signatures.json", "splashes.json", "sounds.json"];
    let dirs_to_remove = ["texts"];
    
    let mut files_deleted = Vec::new();
    let mut dirs_deleted = Vec::new();
    
    find_files_to_clean(dir, &files_to_remove, &dirs_to_remove, &mut files_deleted, &mut dirs_deleted);
    
    for f in &files_deleted {
        if let Some(file_name) = f.file_name() {
            emit_log(&app, "main", &format!("  [Removed signature/license file] -> {:?}", file_name), "info");
        }
        let _ = std::fs::remove_file(f);
    }
    for d in &dirs_deleted {
        if let Some(dir_name) = d.file_name() {
            emit_log(&app, "main", &format!("  [Removed texts/translation folder] -> {:?}", dir_name), "info");
        }
        let _ = std::fs::remove_dir_all(d);
    }
    let resource_dir = app.path().resource_dir()
        .map_err(|e| format!("Failed to get resource dir: {}", e))?;
    let resource_manifest = resource_dir.join("assets/resources/manifest.json");
        
    if resource_manifest.exists() {
        emit_log(&app, "main", "Injecting custom manifest.json to ensure compatibility.", "info");
        std::fs::copy(&resource_manifest, dir.join("manifest.json"))
            .map_err(|e| format!("Failed to copy manifest.json: {}", e))?;
        emit_log(&app, "main", "Custom manifest.json injected successfully.", "success");
    } else {
        emit_log(&app, "main", "Warning: Custom manifest.json baseline not found in resources.", "warning");
    }
    Ok(())
}

fn find_files_to_clean(
    dir: &Path,
    files_to_remove: &[&str],
    dirs_to_remove: &[&str],
    files_deleted: &mut Vec<PathBuf>,
    dirs_deleted: &mut Vec<PathBuf>,
) {
    if let Ok(entries) = std::fs::read_dir(dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
                    if dirs_to_remove.contains(&name) {
                        dirs_deleted.push(path);
                        continue;
                    }
                }
                find_files_to_clean(&path, files_to_remove, dirs_to_remove, files_deleted, dirs_deleted);
            } else if path.is_file() {
                if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
                    if files_to_remove.contains(&name) {
                        files_deleted.push(path);
                    }
                }
            }
        }
    }
}

#[tauri::command]
fn move_marketplace_folders() -> Result<usize, String> {
    let local_app_data = std::env::var("LOCALAPPDATA")
        .map_err(|_| "LOCALAPPDATA env var not found".to_string())?;
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
fn restore_marketplace_folders() -> Result<usize, String> {
    let local_app_data = std::env::var("LOCALAPPDATA")
        .map_err(|_| "LOCALAPPDATA env var not found".to_string())?;
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

fn get_existing_dir(path_str: &str) -> Option<std::path::PathBuf> {
    let mut cleaned = path_str.replace('/', "\\");
    // Remove UNC prefix or double slashes
    if cleaned.starts_with(r"\\?\") {
        cleaned = cleaned[4..].to_string();
    } else if cleaned.starts_with(r"//?/") {
        cleaned = cleaned[4..].to_string();
    }
    
    let mut path = std::path::PathBuf::from(cleaned);
    while !path.exists() && path.parent().is_some() {
        path.pop();
    }
    if path.exists() && path.is_dir() {
        Some(path)
    } else {
        None
    }
}

#[tauri::command]
fn select_directory(title: String, default_path: Option<String>) -> Result<String, String> {
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
fn select_file(title: String, filter: String, default_path: Option<String>) -> Result<String, String> {
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
            let extensions: Vec<&str> = exts_part.split(';')
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

struct EntryDescriptor {
    name: String,
    contents_offset: u32,
    contents_len: u32,
}

fn deserialize_brarchive(data: &[u8]) -> Result<HashMap<String, Vec<u8>>, String> {
    if data.len() < 16 {
        return Err("Data too short to contain header".to_string());
    }

    let magic = u64::from_le_bytes(data[0..8].try_into().unwrap());
    let entries = u32::from_le_bytes(data[8..12].try_into().unwrap());
    let version = u32::from_le_bytes(data[12..16].try_into().unwrap());

    if magic != 0x267052A0B125277D {
        return Err(format!("Magic Mismatch: expected 0x267052A0B125277D, got 0x{:X}", magic));
    }

    if version != 1 {
        return Err(format!("Unsupported Version: {}", version));
    }

    let mut offset = 16;
    let mut descriptors = Vec::new();

    for _ in 0..entries {
        if offset >= data.len() {
            return Err("Unexpected EOF while reading descriptors".to_string());
        }

        let name_len = data[offset] as usize;
        offset += 1;

        if name_len > 247 {
            return Err(format!("Entry Name too long in read: {}", name_len));
        }

        if offset + 247 + 8 > data.len() {
            return Err("Unexpected EOF while reading entry name padding or bounds".to_string());
        }

        let name_bytes = &data[offset..offset + name_len];
        // Clean null bytes if any
        let clean_name_bytes: Vec<u8> = name_bytes.iter().cloned().filter(|&b| b != 0).collect();
        let name = String::from_utf8(clean_name_bytes)
            .map_err(|e| format!("Invalid UTF-8 in entry name: {}", e))?;

        // Skip the rest of the 247 bytes padded array
        offset += 247;

        let contents_offset = u32::from_le_bytes(data[offset..offset + 4].try_into().unwrap());
        let contents_len = u32::from_le_bytes(data[offset + 4..offset + 8].try_into().unwrap());
        offset += 8;

        descriptors.push(EntryDescriptor {
            name,
            contents_offset,
            contents_len,
        });
    }

    let contents_start_offset = offset;
    let mut entry_map = HashMap::new();

    for entry in descriptors {
        let start = contents_start_offset + entry.contents_offset as usize;
        let end = start + entry.contents_len as usize;

        if end > data.len() {
            return Err(format!("Offset out of bounds reading content for {}", entry.name));
        }

        entry_map.insert(entry.name, data[start..end].to_vec());
    }

    Ok(entry_map)
}

fn find_brarchive_dirs(dir: &Path, results: &mut Vec<PathBuf>) -> Result<(), String> {
    if dir.is_dir() {
        for entry in std::fs::read_dir(dir).map_err(|e| e.to_string())? {
            let entry = entry.map_err(|e| e.to_string())?;
            let path = entry.path();
            if path.is_dir() {
                if path.file_name().and_then(|n| n.to_str()) == Some("__brarchive") {
                    results.push(path);
                } else {
                    find_brarchive_dirs(&path, results)?;
                }
            }
        }
    }
    Ok(())
}

fn collect_brarchive_files(current: &Path, files: &mut Vec<PathBuf>) -> Result<(), String> {
    if current.is_dir() {
        for entry in std::fs::read_dir(current).map_err(|e| e.to_string())? {
            let entry = entry.map_err(|e| e.to_string())?;
            let path = entry.path();
            collect_brarchive_files(&path, files)?;
        }
    } else if current.is_file() {
        if current.extension().and_then(|e| e.to_str()) == Some("brarchive") {
            files.push(current.to_path_buf());
        }
    }
    Ok(())
}

fn remove_brarchive_pointers(dir: &Path) -> Result<(), String> {
    if dir.is_dir() {
        for entry in std::fs::read_dir(dir).map_err(|e| e.to_string())? {
            let entry = entry.map_err(|e| e.to_string())?;
            let path = entry.path();
            if path.is_dir() {
                remove_brarchive_pointers(&path)?;
            } else if path.is_file() {
                if path.extension().and_then(|e| e.to_str()) == Some("brarchive") {
                    let _ = std::fs::remove_file(path);
                }
            }
        }
    }
    Ok(())
}

fn extract_brarchives_in_workspace_impl(app: Option<&tauri::AppHandle>, workspace: &Path, container: &str) -> Result<bool, String> {
    let mut brarchive_dirs = Vec::new();
    find_brarchive_dirs(workspace, &mut brarchive_dirs)?;

    if brarchive_dirs.is_empty() {
        return Ok(false);
    }

    if let Some(app_handle) = app {
        emit_log(app_handle, container, &format!("Scanning workspace for brarchives: {:?}", workspace), "info");
        emit_log(app_handle, container, &format!("Found {} __brarchive directories.", brarchive_dirs.len()), "info");
    }

    let mut brarchives_found = 0;
    let mut extracted_files = 0;
    let mut skipped_placeholders = 0;

    for brarchive_root in &brarchive_dirs {
        let pack_context = brarchive_root.parent().ok_or("No parent for __brarchive folder")?;

        let mut files_to_extract = Vec::new();
        collect_brarchive_files(brarchive_root, &mut files_to_extract)?;
        files_to_extract.sort();

        for brarchive_path in files_to_extract {
            brarchives_found += 1;
            let rel_to_brarchive_root = brarchive_path.strip_prefix(brarchive_root)
                .map_err(|e| e.to_string())?;

            let file_name_str = rel_to_brarchive_root.to_string_lossy();
            if !file_name_str.ends_with(".brarchive") {
                continue;
            }
            let target_rel_str = &file_name_str[..file_name_str.len() - 10]; // strip ".brarchive"
            let extract_dir = pack_context.join(target_rel_str);

            if let Some(app_handle) = app {
                emit_log(app_handle, container, &format!("  [Brarchive Found] -> {}", file_name_str), "info");
            }

            let mut data = Vec::new();
            let mut file = File::open(&brarchive_path)
                .map_err(|e| format!("Failed to open {}: {}", brarchive_path.display(), e))?;
            file.read_to_end(&mut data)
                .map_err(|e| format!("Failed to read {}: {}", brarchive_path.display(), e))?;

            if data.len() <= 16 {
                skipped_placeholders += 1;
                if let Some(app_handle) = app {
                    emit_log(app_handle, container, "    (Skipped placeholder / empty brarchive)", "info");
                }
                continue;
            }

            let entry_map = deserialize_brarchive(&data)
                .map_err(|e| format!("Error deserializing {}: {}", brarchive_path.display(), e))?;

            std::fs::create_dir_all(&extract_dir)
                .map_err(|e| format!("Failed to create extract dir {}: {}", extract_dir.display(), e))?;

            for (entry_name, content) in entry_map {
                let out_file = extract_dir.join(&entry_name);
                if content.is_empty() {
                    skipped_placeholders += 1;
                    continue;
                }

                extracted_files += 1;
                if let Some(app_handle) = app {
                    emit_log(app_handle, container, &format!("    -> Decompressing nested: {}", entry_name), "info");
                }
                if let Some(parent) = out_file.parent() {
                    std::fs::create_dir_all(parent)
                        .map_err(|e| format!("Failed to create parent dir for {}: {}", out_file.display(), e))?;
                }

                let mut out_f = File::create(&out_file)
                    .map_err(|e| format!("Failed to create output file {}: {}", out_file.display(), e))?;
                out_f.write_all(&content)
                    .map_err(|e| format!("Failed to write to {}: {}", out_file.display(), e))?;
            }
        }
    }

    // Remove all __brarchive directories now that everything is extracted
    for brarchive_root in &brarchive_dirs {
        if let Some(app_handle) = app {
            if let Some(dir_name) = brarchive_root.file_name() {
                emit_log(app_handle, container, &format!("Cleaning up raw brarchive folder: {:?}", dir_name), "info");
            }
        }
        let _ = robust_cleanup(brarchive_root);
    }

    // Remove loose .brarchive pointer files in the workspace
    remove_brarchive_pointers(workspace)?;

    if let Some(app_handle) = app {
        emit_log(app_handle, container, &format!("Brarchive extraction complete! Extracted {} files from {} archives (skipped {} placeholders).", extracted_files, brarchives_found, skipped_placeholders), "success");
    }

    Ok(true)
}

fn copy_dir_all(src: impl AsRef<Path>, dst: impl AsRef<Path>) -> std::io::Result<()> {
    std::fs::create_dir_all(&dst)?;
    for entry in std::fs::read_dir(src)? {
        let entry = entry?;
        let ty = entry.file_type()?;
        if ty.is_dir() {
            copy_dir_all(entry.path(), dst.as_ref().join(entry.file_name()))?;
        } else {
            std::fs::copy(entry.path(), dst.as_ref().join(entry.file_name()))?;
        }
    }
    Ok(())
}

#[tauri::command]
fn stage_and_extract_brarchives(app: tauri::AppHandle, source_dir: String, temp_dir: String) -> Result<String, String> {
    let src = Path::new(&source_dir);
    let dst = Path::new(&temp_dir);

    let _ = robust_cleanup(dst);

    emit_log(&app, "main", &format!("Staging files from {:?} to temporary workspace {:?}", src, dst), "info");
    copy_dir_all(src, dst).map_err(|e| format!("Failed to copy source folder: {}", e))?;

    let found = extract_brarchives_in_workspace_impl(Some(&app), dst, "main")?;

    if found {
        Ok("Staged and extracted brarchives successfully.".to_string())
    } else {
        Ok("Staged successfully (no brarchives found to extract).".to_string())
    }
}

#[tauri::command]
fn extract_brarchives_in_workspace(app: tauri::AppHandle, workspace: String) -> Result<bool, String> {
    let ws = Path::new(&workspace);
    // This command can be called from utilities tab (so log container = "main" or we check which log console is used)
    extract_brarchives_in_workspace_impl(Some(&app), ws, "main")
}

#[tauri::command]
fn generate_xdelta_patch(
    app: tauri::AppHandle,
    source_file: String,
    target_file: String,
    patch_file: String
) -> Result<String, String> {
    let resource_dir = app.path().resource_dir()
        .map_err(|e| format!("Failed to get resource dir: {}", e))?;
    let xdelta_path = resource_dir.join("assets/xdelta3/exec/xdelta3_x86_64_win.exe");
        
    if !xdelta_path.exists() {
        return Err(format!("XDelta executable not found at resources: {:?}", xdelta_path));
    }
    
    emit_log(&app, "genpatch-logs", "Encoding patch via XDelta...", "info");
    emit_log(&app, "genpatch-logs", &format!("  [Executable] -> {:?}", xdelta_path), "info");
    emit_log(&app, "genpatch-logs", &format!("  [Source File] -> {}", source_file), "info");
    emit_log(&app, "genpatch-logs", &format!("  [Target File] -> {}", target_file), "info");
    emit_log(&app, "genpatch-logs", &format!("  [Patch Output] -> {}", patch_file), "info");

    let patch_path = Path::new(&patch_file);
    if let Some(parent) = patch_path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("Failed to create output dir: {}", e))?;
    }
    
    if patch_path.exists() {
        emit_log(&app, "genpatch-logs", "Removing existing patch file...", "info");
        let _ = std::fs::remove_file(patch_path);
    }
    
    let mut cmd = std::process::Command::new(&xdelta_path);
    cmd.args(&["-e", "-s", &source_file, &target_file, &patch_file]);
    
    #[cfg(target_os = "windows")]
    cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW
    
    let output = cmd.output().map_err(|e| format!("Failed to run patch executable: {}", e))?;
    
    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    
    if !stdout.trim().is_empty() {
        emit_log(&app, "genpatch-logs", &format!("XDelta stdout: {}", stdout), "info");
    }
    if !stderr.trim().is_empty() {
        emit_log(&app, "genpatch-logs", &format!("XDelta stderr: {}", stderr), "info");
    }

    if !output.status.success() {
        let err_msg = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Patch generation failed: {}", err_msg));
    }
    
    emit_log(&app, "genpatch-logs", "XDelta patch generation successful.", "success");
    Ok("Patch generated successfully.".to_string())
}

/// Opens a path in Windows Explorer. If path is a file, Explorer selects it.
/// If path is a directory, Explorer opens it.
#[tauri::command]
fn open_in_explorer(path: String) -> Result<(), String> {
    let p = std::path::Path::new(&path);
    if !p.exists() {
        // Try to open the parent directory instead
        if let Some(parent) = p.parent() {
            if parent.exists() {
                std::process::Command::new("explorer")
                    .arg(parent.to_str().unwrap_or(""))
                    .spawn()
                    .map_err(|e| format!("Failed to open explorer: {}", e))?;
                return Ok(());
            }
        }
        return Err(format!("Path does not exist: {}", path));
    }
    if p.is_file() {
        // /select, highlights the file in its parent folder
        std::process::Command::new("explorer")
            .args(&["/select,", &path])
            .spawn()
            .map_err(|e| format!("Failed to open explorer: {}", e))?;
    } else {
        std::process::Command::new("explorer")
            .arg(&path)
            .spawn()
            .map_err(|e| format!("Failed to open explorer: {}", e))?;
    }
    Ok(())
}

fn get_project_root(app: &tauri::AppHandle) -> PathBuf {
    if let Ok(cwd) = std::env::current_dir() {
        if cwd.join("src-tauri").exists() {
            return cwd;
        }
        if cwd.file_name().and_then(|n| n.to_str()) == Some("src-tauri") {
            if let Some(parent) = cwd.parent() {
                return parent.to_path_buf();
            }
        }
    }
    if let Ok(resource_dir) = app.path().resource_dir() {
        let mut root = resource_dir.clone();
        if root.file_name().and_then(|n| n.to_str()) == Some("src-tauri") {
            root.pop();
            return root;
        }
        while root.parent().is_some() {
            if root.join("src-tauri").exists() {
                return root;
            }
            root.pop();
        }
        return resource_dir;
    }
    PathBuf::new()
}

#[tauri::command]
fn open_project_dir(app: tauri::AppHandle, name: String) -> Result<(), String> {
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
                let p2 = resource_dir.as_ref().map(|rd| rd.join("assets/Patches")).unwrap_or_default();
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
fn get_default_paths(app: tauri::AppHandle) -> std::collections::HashMap<String, String> {
    let mut paths = std::collections::HashMap::new();
    let appdata = std::env::var("APPDATA").unwrap_or_default();
    let localappdata = std::env::var("LOCALAPPDATA").unwrap_or_default();
    let userprofile = std::env::var("USERPROFILE").unwrap_or_default();

    // GDK / Roaming path (preferred)
    let gdk_root = format!("{}/Minecraft Bedrock", appdata);
    let gdk_premium = format!("{}/premium_cache/resource_packs", gdk_root);
    let gdk_resource_packs = format!("{}/games/com.mojang/resource_packs", gdk_root);

    // UWP / Windows Store path
    let uwp_root = format!("{}/Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState", localappdata);
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
    let patches = resource_dir.join("assets/Patches").to_string_lossy().replace('\\', "/");

    paths.insert("premium_cache".to_string(), premium_cache);
    paths.insert("resource_packs".to_string(), resource_packs);
    paths.insert("downloads".to_string(), downloads);
    paths.insert("patches".to_string(), patches);
    paths.insert("gdk_root".to_string(), gdk_root.replace('\\', "/"));
    paths.insert("uwp_root".to_string(), uwp_root.replace('\\', "/"));
    paths
}

#[tauri::command]
fn update_app_version(app: tauri::AppHandle, version: String, ping_everyone: bool) -> Result<(), String> {
    let project_root = get_project_root(&app);
    if project_root.to_string_lossy().is_empty() {
        return Err("Could not determine project root directory".to_string());
    }

    let semver_version = version
        .replace("_b", "-0")
        .replace("_a", "-1")
        .replace("-b", "-0")
        .replace("-a", "-1");
    
    // 1. Update tauri.conf.json
    let tauri_conf_path = project_root.join("src-tauri/tauri.conf.json");
    if tauri_conf_path.exists() {
        emit_log(&app, "build-logs", &format!("Updating version to {} (semver: {}) in tauri.conf.json...", version, semver_version), "info");
        let content = std::fs::read_to_string(&tauri_conf_path)
            .map_err(|e| format!("Failed to read tauri.conf.json: {}", e))?;
        let mut val: serde_json::Value = serde_json::from_str(&content)
            .map_err(|e| format!("Failed to parse tauri.conf.json: {}", e))?;
        if let Some(obj) = val.as_object_mut() {
            obj.insert("version".to_string(), serde_json::Value::String(semver_version.clone()));
            if let Some(app_obj) = obj.get_mut("app") {
                if let Some(windows) = app_obj.get_mut("windows") {
                    if let Some(win_arr) = windows.as_array_mut() {
                        if let Some(win) = win_arr.get_mut(0) {
                            if let Some(win_obj) = win.as_object_mut() {
                                win_obj.insert("title".to_string(), serde_json::Value::String(format!("Actions & Stuff RTX Patcher v{}", version)));
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
        emit_log(&app, "build-logs", "Successfully updated tauri.conf.json and window title.", "success");
    } else {
        emit_log(&app, "build-logs", &format!("Warning: tauri.conf.json not found at expected path: {:?}", tauri_conf_path), "warning");
    }

    // Set title on the active running window dynamically
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.set_title(&format!("Actions & Stuff RTX Patcher v{}", version));
    }

    // 2. Update updater.json
    let updater_json_path = project_root.join("updater.json");
    if updater_json_path.exists() {
        emit_log(&app, "build-logs", &format!("Updating version to {} (semver: {}) in updater.json...", version, semver_version), "info");
        let content = std::fs::read_to_string(&updater_json_path)
            .map_err(|e| format!("Failed to read updater.json: {}", e))?;
        let mut val: serde_json::Value = serde_json::from_str(&content)
            .map_err(|e| format!("Failed to parse updater.json: {}", e))?;
        if let Some(obj) = val.as_object_mut() {
            let old_version = obj.get("version").and_then(|v| v.as_str()).unwrap_or("3.0.0").to_string();
            obj.insert("version".to_string(), serde_json::Value::String(semver_version.clone()));
            obj.insert("ping_everyone".to_string(), serde_json::Value::Bool(ping_everyone));
            if let Some(platforms) = obj.get_mut("platforms") {
                if let Some(win) = platforms.get_mut("windows-x86_64") {
                    if let Some(url_val) = win.get_mut("url") {
                        if let Some(url_str) = url_val.as_str() {
                            let new_url = url_str.replace(&format!("v{}", old_version), &format!("v{}", semver_version))
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
        emit_log(&app, "build-logs", "Successfully updated updater.json.", "success");
    } else {
        emit_log(&app, "build-logs", &format!("Warning: updater.json not found at expected path: {:?}", updater_json_path), "warning");
    }

    Ok(())
}

#[tauri::command]
fn run_release_build(app: tauri::AppHandle) -> Result<(), String> {
    let project_root = get_project_root(&app);
    if project_root.to_string_lossy().is_empty() {
        return Err("Could not determine project root directory".to_string());
    }

    let app_clone = app.clone();
    std::thread::spawn(move || {
        emit_log(&app_clone, "build-logs", "Starting project release build...", "info");
        emit_log(&app_clone, "build-logs", "Executing command: npm run tauri build", "info");

        let mut cmd = std::process::Command::new("cmd");
        cmd.args(&["/c", "npm run tauri build"]);
        cmd.current_dir(&project_root);
        
        #[cfg(target_os = "windows")]
        cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW

        match cmd.stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped())
            .spawn() {
            Ok(mut child) => {
                let stdout = child.stdout.take().unwrap();
                let stderr = child.stderr.take().unwrap();
                
                let app_c1 = app_clone.clone();
                let app_c2 = app_clone.clone();
                
                std::thread::spawn(move || {
                    let mut reader = std::io::BufReader::new(stdout);
                    let mut line = String::new();
                    while let Ok(bytes) = reader.read_line(&mut line) {
                        if bytes == 0 { break; }
                        emit_log(&app_c1, "build-logs", line.trim_end(), "info");
                        line.clear();
                    }
                });

                std::thread::spawn(move || {
                    let mut reader = std::io::BufReader::new(stderr);
                    let mut line = String::new();
                    while let Ok(bytes) = reader.read_line(&mut line) {
                        if bytes == 0 { break; }
                        emit_log(&app_c2, "build-logs", line.trim_end(), "warning");
                        line.clear();
                    }
                });

                match child.wait() {
                    Ok(status) => {
                        if status.success() {
                            emit_log(&app_clone, "build-logs", "Build finished successfully!", "success");
                        } else {
                            emit_log(&app_clone, "build-logs", &format!("Build failed with exit status: {}", status), "error");
                        }
                    }
                    Err(e) => {
                        emit_log(&app_clone, "build-logs", &format!("Error waiting for build process: {}", e), "error");
                    }
                }
            }
            Err(e) => {
                emit_log(&app_clone, "build-logs", &format!("Failed to start build process: {}", e), "error");
            }
        }
    });

    Ok(())
}

#[tauri::command]
fn get_app_version(app: tauri::AppHandle) -> String {
    app.package_info().version.to_string()
}

#[tauri::command]
fn is_dev_build() -> bool {
    cfg!(debug_assertions)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
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
            is_dev_build
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
