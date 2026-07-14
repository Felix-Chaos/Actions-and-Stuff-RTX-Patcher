use std::collections::HashMap;
use std::fs::File;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use tauri::Emitter;
use tauri::Manager;
use zip::write::SimpleFileOptions;
use zip::ZipWriter;

#[derive(Clone, serde::Serialize)]
pub struct LogPayload {
    pub container: String,
    pub message: String,
    pub log_type: String,
}

pub fn emit_log(app: &tauri::AppHandle, container: &str, msg: &str, log_type: &str) {
    let _ = app.emit(
        "app-log",
        LogPayload {
            container: container.to_string(),
            message: msg.to_string(),
            log_type: log_type.to_string(),
        },
    );
}

// Helper: robust cleanup with retries
pub fn robust_cleanup(path: &Path) -> bool {
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
pub fn collect_files(
    root: &Path,
    current: &Path,
    files: &mut Vec<(PathBuf, String)>,
) -> Result<(), String> {
    if current.is_dir() {
        for entry in std::fs::read_dir(current).map_err(|e| e.to_string())? {
            let entry = entry.map_err(|e| e.to_string())?;
            let path = entry.path();
            collect_files(root, &path, files)?;
        }
    } else if current.is_file() {
        let rel_path = current
            .strip_prefix(root)
            .map_err(|e| e.to_string())?
            .to_string_lossy()
            .replace("\\", "/");
        files.push((current.to_path_buf(), rel_path));
    }
    Ok(())
}

// Helper: deterministic ZIP packer
pub fn pack_folder_impl(
    app: Option<&tauri::AppHandle>,
    folder_path: &Path,
    output_zip: &Path,
    container: &str,
) -> Result<(), String> {
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
        emit_log(
            app_handle,
            container,
            &format!("Scanning folder to pack: {:?}", folder_path),
            "info",
        );
        emit_log(
            app_handle,
            container,
            &format!("Found {} files to compress deterministically.", files.len()),
            "info",
        );
    }

    for (abs_path, rel_path) in files {
        let mut f = File::open(&abs_path)
            .map_err(|e| format!("Failed to open file {:?}: {}", abs_path, e))?;

        zip.start_file(rel_path, options)
            .map_err(|e| format!("Failed to start file in zip: {}", e))?;
        std::io::copy(&mut f, &mut zip)
            .map_err(|e| format!("Failed to write file to zip: {}", e))?;
    }

    zip.finish()
        .map_err(|e| format!("Failed to finalize zip: {}", e))?;
    if let Some(app_handle) = app {
        emit_log(
            app_handle,
            container,
            &format!(
                "Deterministic pack created successfully at: {:?}",
                output_zip
            ),
            "success",
        );
    }
    Ok(())
}

// Helper: zip/mcpack extraction with smart folder unwrapping
pub fn extract_archive_impl(
    app: Option<&tauri::AppHandle>,
    zip_path: &Path,
    output_dir: &Path,
    container: &str,
) -> Result<(), String> {
    let file = File::open(zip_path).map_err(|e| format!("Failed to open zip: {}", e))?;
    let mut archive =
        zip::ZipArchive::new(file).map_err(|e| format!("Failed to read zip: {}", e))?;

    if output_dir.exists() {
        if let Some(app_handle) = app {
            emit_log(
                app_handle,
                container,
                &format!("Cleaning existing extraction directory: {:?}", output_dir),
                "info",
            );
        }
        let _ = std::fs::remove_dir_all(output_dir);
    }
    std::fs::create_dir_all(output_dir)
        .map_err(|e| format!("Failed to create output dir: {}", e))?;

    if let Some(app_handle) = app {
        emit_log(
            app_handle,
            container,
            &format!(
                "Extracting archive {:?} (contains {} files)",
                zip_path,
                archive.len()
            ),
            "info",
        );
    }

    for i in 0..archive.len() {
        let mut file = archive
            .by_index(i)
            .map_err(|e| format!("Failed to read zip file: {}", e))?;
        let outpath = match file.enclosed_name() {
            Some(path) => output_dir.join(path),
            None => continue,
        };

        if file.name().ends_with('/') {
            std::fs::create_dir_all(&outpath)
                .map_err(|e| format!("Failed to create directory: {}", e))?;
        } else {
            if let Some(p) = outpath.parent() {
                if !p.exists() {
                    std::fs::create_dir_all(p)
                        .map_err(|e| format!("Failed to create directory: {}", e))?;
                }
            }
            let mut outfile = File::create(&outpath)
                .map_err(|e| format!("Failed to create output file: {}", e))?;
            std::io::copy(&mut file, &mut outfile)
                .map_err(|e| format!("Failed to copy file contents: {}", e))?;
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
            emit_log(
                app_handle,
                container,
                &format!(
                    "Smart Unwrap: single root folder {:?} detected. Moving contents up...",
                    single_dir.file_name().unwrap()
                ),
                "info",
            );
        }
        if let Ok(rd) = std::fs::read_dir(single_dir) {
            for entry in rd.flatten() {
                let path = entry.path();
                let dest = output_dir.join(path.file_name().unwrap());
                if let Some(app_handle) = app {
                    emit_log(
                        app_handle,
                        container,
                        &format!("  [Moving up] -> {:?}", path.file_name().unwrap()),
                        "info",
                    );
                }
                std::fs::rename(&path, &dest)
                    .map_err(|e| format!("Failed to move file during smart unwrap: {}", e))?;
            }
        }
        let _ = std::fs::remove_dir(single_dir);
    }

    if let Some(app_handle) = app {
        emit_log(
            app_handle,
            container,
            &format!("Successfully extracted all files to {:?}", output_dir),
            "success",
        );
    }
    Ok(())
}

// Helper: extract pack version from en_US.lang
pub fn get_lang_version(path: &Path) -> Option<String> {
    let lang_path = path.join("texts").join("en_US.lang");
    if !lang_path.exists() {
        return None;
    }
    if let Ok(content) = std::fs::read_to_string(&lang_path) {
        for line in content.lines() {
            if line.starts_with("pack.name=") {
                if let Some(idx) = line.find("Actions & Stuf") {
                    let raw_ver = &line[idx + 14..];
                    let clean_ver: String = raw_ver
                        .chars()
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

    // Fallback to manifest.json
    let manifest_path = path.join("manifest.json");
    if manifest_path.exists() {
        if let Ok(content) = std::fs::read_to_string(&manifest_path) {
            if let Ok(val) = serde_json::from_str::<serde_json::Value>(&content) {
                if let Some(header) = val.get("header") {
                    if let Some(version) = header.get("version") {
                        if let Some(arr) = version.as_array() {
                            let mut ver_str = String::new();
                            for (i, v) in arr.iter().enumerate() {
                                if i > 0 {
                                    ver_str.push('.');
                                }
                                ver_str.push_str(&v.to_string());
                            }
                            if !ver_str.is_empty() {
                                return Some(ver_str);
                            }
                        } else if let Some(s) = version.as_str() {
                            return Some(s.to_string());
                        }
                    }
                }
            }
        }
    }

    None
}

// Helper: get standard Minecraft com.mojang paths
pub fn get_mojang_paths() -> Vec<PathBuf> {
    let mut paths = Vec::new();
    let local_app_data = std::env::var("LOCALAPPDATA").ok().map(PathBuf::from);
    let app_data = std::env::var("APPDATA").ok().map(PathBuf::from);

    if let Some(ref lad) = local_app_data {
        paths.push(
            lad.join(r"Packages\Microsoft.MinecraftUWP_8wekyb3d8bbwe\LocalState\games\com.mojang"),
        );
        paths.push(lad.join(
            r"Packages\Microsoft.MinecraftWindowsBeta_8wekyb3d8bbwe\LocalState\games\com.mojang",
        ));
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
pub fn scan_cleanable_packs_in_mojang(mojang_path: &Path) -> Vec<PathBuf> {
    let mut results = Vec::new();
    let prefixes = vec![
        "a&s",
        "actions & st",
        "actions&st",
        "a&sforrtx",
        "actions & stuff enhanced",
        "actions & stuff rtx",
    ];

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
    check_dir_and_collect(
        &mojang_path.join("development_resource_packs"),
        &mut results,
    );

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
pub fn get_folder_stats(dir: &Path) -> (usize, usize) {
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
pub struct MarketplaceCandidate {
    pub path: String,
    pub version: String,
    pub folder_name: String,
    pub files_count: usize,
    pub dirs_count: usize,
    pub logo_hash: String,
    pub score: i32,
}

#[derive(serde::Serialize)]
pub struct OptionsFile {
    pub label: String,
    pub path: String,
}

pub fn find_files_to_clean(
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
                find_files_to_clean(
                    &path,
                    files_to_remove,
                    dirs_to_remove,
                    files_deleted,
                    dirs_deleted,
                );
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

pub fn resolve_asset_path(app: &tauri::AppHandle, path: &str) -> Result<PathBuf, String> {
    #[cfg(debug_assertions)]
    {
        if let Ok(current_dir) = std::env::current_dir() {
            let dev_path = current_dir.join(path);
            if dev_path.exists() {
                return Ok(dev_path);
            }
        }
    }

    let resource_dir = app
        .path()
        .resource_dir()
        .map_err(|e| format!("Failed to get resource dir: {}", e))?;
    Ok(resource_dir.join(path))
}

/// Per-user, per-Windows-account directory for local app state that must
/// never live inside the project/install directory: settings.json,
/// telemetry.json, last_hardware_ping.json. Using the OS app-data dir
/// (rather than the process's current working directory) means this can't
/// end up inside the git repo again, and each Windows user account
/// naturally gets its own copy instead of sharing one file.
pub fn user_data_dir(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let dir = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("Failed to resolve app data directory: {}", e))?;
    std::fs::create_dir_all(&dir)
        .map_err(|e| format!("Failed to create app data directory: {}", e))?;
    Ok(dir)
}

pub fn get_existing_dir(path_str: &str) -> Option<std::path::PathBuf> {
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

pub struct EntryDescriptor {
    pub name: String,
    pub contents_offset: u32,
    pub contents_len: u32,
}

pub fn deserialize_brarchive(data: &[u8]) -> Result<HashMap<String, Vec<u8>>, String> {
    if data.len() < 16 {
        return Err("Data too short to contain header".to_string());
    }

    let magic = u64::from_le_bytes(data[0..8].try_into().unwrap());
    let entries = u32::from_le_bytes(data[8..12].try_into().unwrap());
    let version = u32::from_le_bytes(data[12..16].try_into().unwrap());

    if magic != 0x267052A0B125277D {
        return Err(format!(
            "Magic Mismatch: expected 0x267052A0B125277D, got 0x{:X}",
            magic
        ));
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
            return Err(format!(
                "Offset out of bounds reading content for {}",
                entry.name
            ));
        }

        entry_map.insert(entry.name, data[start..end].to_vec());
    }

    Ok(entry_map)
}

pub fn find_brarchive_dirs(dir: &Path, results: &mut Vec<PathBuf>) -> Result<(), String> {
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

pub fn collect_brarchive_files(current: &Path, files: &mut Vec<PathBuf>) -> Result<(), String> {
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

pub fn remove_brarchive_pointers(dir: &Path) -> Result<(), String> {
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

pub fn extract_brarchives_in_workspace_impl(
    app: Option<&tauri::AppHandle>,
    workspace: &Path,
    container: &str,
) -> Result<bool, String> {
    let mut brarchive_dirs = Vec::new();
    find_brarchive_dirs(workspace, &mut brarchive_dirs)?;

    if brarchive_dirs.is_empty() {
        return Ok(false);
    }

    if let Some(app_handle) = app {
        emit_log(
            app_handle,
            container,
            &format!("Scanning workspace for brarchives: {:?}", workspace),
            "info",
        );
        emit_log(
            app_handle,
            container,
            &format!("Found {} __brarchive directories.", brarchive_dirs.len()),
            "info",
        );
    }

    let mut brarchives_found = 0;
    let mut extracted_files = 0;
    let mut skipped_placeholders = 0;

    for brarchive_root in &brarchive_dirs {
        let pack_context = brarchive_root
            .parent()
            .ok_or("No parent for __brarchive folder")?;

        let mut files_to_extract = Vec::new();
        collect_brarchive_files(brarchive_root, &mut files_to_extract)?;
        files_to_extract.sort();

        for brarchive_path in files_to_extract {
            brarchives_found += 1;
            let rel_to_brarchive_root = brarchive_path
                .strip_prefix(brarchive_root)
                .map_err(|e| e.to_string())?;

            let file_name_str = rel_to_brarchive_root.to_string_lossy();
            if !file_name_str.ends_with(".brarchive") {
                continue;
            }
            let target_rel_str = &file_name_str[..file_name_str.len() - 10]; // strip ".brarchive"
            let extract_dir = pack_context.join(target_rel_str);

            if let Some(app_handle) = app {
                emit_log(
                    app_handle,
                    container,
                    &format!("  [Brarchive Found] -> {}", file_name_str),
                    "info",
                );
            }

            let mut data = Vec::new();
            let mut file = File::open(&brarchive_path)
                .map_err(|e| format!("Failed to open {}: {}", brarchive_path.display(), e))?;
            file.read_to_end(&mut data)
                .map_err(|e| format!("Failed to read {}: {}", brarchive_path.display(), e))?;

            if data.len() <= 16 {
                skipped_placeholders += 1;
                if let Some(app_handle) = app {
                    emit_log(
                        app_handle,
                        container,
                        "    (Skipped placeholder / empty brarchive)",
                        "info",
                    );
                }
                continue;
            }

            let entry_map = deserialize_brarchive(&data)
                .map_err(|e| format!("Error deserializing {}: {}", brarchive_path.display(), e))?;

            std::fs::create_dir_all(&extract_dir).map_err(|e| {
                format!(
                    "Failed to create extract dir {}: {}",
                    extract_dir.display(),
                    e
                )
            })?;

            for (entry_name, content) in entry_map {
                let out_file = extract_dir.join(&entry_name);
                if content.is_empty() {
                    skipped_placeholders += 1;
                    continue;
                }

                extracted_files += 1;
                if let Some(parent) = out_file.parent() {
                    std::fs::create_dir_all(parent).map_err(|e| {
                        format!(
                            "Failed to create parent dir for {}: {}",
                            out_file.display(),
                            e
                        )
                    })?;
                }

                let mut out_f = File::create(&out_file).map_err(|e| {
                    format!("Failed to create output file {}: {}", out_file.display(), e)
                })?;
                out_f
                    .write_all(&content)
                    .map_err(|e| format!("Failed to write to {}: {}", out_file.display(), e))?;
            }
        }
    }

    // Remove all __brarchive directories now that everything is extracted
    for brarchive_root in &brarchive_dirs {
        if let Some(app_handle) = app {
            if let Some(dir_name) = brarchive_root.file_name() {
                emit_log(
                    app_handle,
                    container,
                    &format!("Cleaning up raw brarchive folder: {:?}", dir_name),
                    "info",
                );
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

pub fn copy_dir_all(src: impl AsRef<Path>, dst: impl AsRef<Path>) -> std::io::Result<()> {
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

pub fn get_project_root(app: &tauri::AppHandle) -> PathBuf {
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

#[derive(serde::Serialize)]
pub struct PatchStats {
    pub files: usize,
    pub dirs: usize,
    pub logo_hash: String,
    pub has_lang_file: bool,
}
