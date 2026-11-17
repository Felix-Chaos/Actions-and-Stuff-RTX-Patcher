//! Keeps the installed RTX pack healthy.
//!
//! A patched Marketplace pack keeps the original pack's UUID (it has to, or
//! its encrypted content would not decrypt), so an Actions & Stuff or
//! Minecraft update can write into the installed RTX folder. The result is a
//! broken mix of A&S and A&S RTX. This module:
//!
//! - records every installed RTX folder file by file (size, mtime, SHA-256),
//! - optionally write-protects those files (read-only attribute) so an update
//!   cannot overwrite them,
//! - optionally keeps the patched archive as a backup that reinstalls in
//!   seconds instead of patching again,
//! - compares the folders against their record on startup, so the app can
//!   offer to delete a pack an update has mixed up.
//!
//! State lives in `installed_packs.json` in the app data folder, backups in
//! `pack_backups/` next to it.

use crate::log_msg;
use crate::logmsg::emit_msg;
use crate::utils::{extract_archive_impl, get_install_target_paths, robust_cleanup, user_data_dir};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

const STATE_FILE: &str = "installed_packs.json";
const BACKUP_DIR: &str = "pack_backups";
/// Backups kept after a new one is saved; older ones are deleted.
const KEEP_BACKUPS: usize = 3;
/// Files Windows drops into folders by itself. Never a sign of damage.
const IGNORED_NAMES: [&str; 2] = ["desktop.ini", "thumbs.db"];

/// Size, modification time and hash of one installed file.
#[derive(serde::Serialize, serde::Deserialize, Clone, PartialEq)]
struct FileStamp {
    size: u64,
    /// Nanoseconds since the Unix epoch.
    mtime: u64,
    sha256: String,
}

/// One RTX pack folder the patcher installed.
#[derive(serde::Serialize, serde::Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
struct InstallRecord {
    dir: String,
    label: String,
    pack_version: Option<String>,
    patch_version: Option<String>,
    installed_at: u64,
    locked: bool,
    backup_id: Option<String>,
    files: BTreeMap<String, FileStamp>,
}

/// A saved copy of a patched archive.
#[derive(serde::Serialize, serde::Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct BackupEntry {
    pub id: String,
    /// File name inside the backup folder.
    pub file: String,
    /// Folder name the pack is installed under in `resource_packs`.
    pub folder_name: String,
    pub label: String,
    pub pack_version: Option<String>,
    pub patch_version: Option<String>,
    pub created_at: u64,
    pub size: u64,
}

#[derive(serde::Serialize, serde::Deserialize, Default)]
struct GuardState {
    installs: Vec<InstallRecord>,
    backups: Vec<BackupEntry>,
}

/// What the frontend passes to `install_mcpack` to have the install guarded.
#[derive(serde::Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct GuardOptions {
    pub label: String,
    pub pack_version: Option<String>,
    pub patch_version: Option<String>,
    /// Keep the patched archive as a backup.
    pub backup: bool,
    /// Write-protect the installed files.
    pub lock: bool,
}

/// Result of comparing one installed folder with its record.
#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PackHealth {
    pub dir: String,
    pub label: String,
    pub pack_version: Option<String>,
    pub patch_version: Option<String>,
    pub changed: usize,
    pub added: usize,
    pub missing: usize,
    /// A few affected paths, for the log.
    pub examples: Vec<String>,
    pub locked: bool,
    /// Backup that restores this pack, if it still exists.
    pub backup_id: Option<String>,
}

impl PackHealth {
    fn damaged(&self) -> bool {
        self.changed + self.added + self.missing > 0
    }
}

fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

fn state_path(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    Ok(user_data_dir(app)?.join(STATE_FILE))
}

fn backup_dir(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let dir = user_data_dir(app)?.join(BACKUP_DIR);
    std::fs::create_dir_all(&dir).map_err(|e| format!("Failed to create backup folder: {}", e))?;
    Ok(dir)
}

fn load_state(app: &tauri::AppHandle) -> GuardState {
    state_path(app)
        .ok()
        .and_then(|p| std::fs::read_to_string(p).ok())
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_default()
}

/// Writes the state through a temp file, so a crash never leaves half a JSON.
fn save_state(app: &tauri::AppHandle, state: &GuardState) -> Result<(), String> {
    let path = state_path(app)?;
    let tmp = path.with_extension("json.tmp");
    let json = serde_json::to_string_pretty(state).map_err(|e| e.to_string())?;
    std::fs::write(&tmp, json).map_err(|e| format!("Failed to save pack records: {}", e))?;
    std::fs::rename(&tmp, &path).map_err(|e| format!("Failed to save pack records: {}", e))
}

fn same_dir(a: &str, b: &Path) -> bool {
    Path::new(a) == b || a.eq_ignore_ascii_case(&b.to_string_lossy())
}

fn is_ignored(rel: &str) -> bool {
    let name = rel.rsplit('/').next().unwrap_or(rel).to_ascii_lowercase();
    IGNORED_NAMES.contains(&name.as_str())
}

fn mtime_nanos(meta: &std::fs::Metadata) -> u64 {
    meta.modified()
        .ok()
        .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
        .map(|d| d.as_nanos() as u64)
        .unwrap_or(0)
}

fn sha256_file(path: &Path) -> Result<String, String> {
    let mut file =
        std::fs::File::open(path).map_err(|e| format!("Failed to read {:?}: {}", path, e))?;
    let mut hasher = Sha256::new();
    let mut buf = vec![0u8; 1 << 16];
    loop {
        let n = std::io::Read::read(&mut file, &mut buf)
            .map_err(|e| format!("Failed to read {:?}: {}", path, e))?;
        if n == 0 {
            break;
        }
        hasher.update(&buf[..n]);
    }
    Ok(hasher
        .finalize()
        .iter()
        .map(|b| format!("{:02x}", b))
        .collect())
}

/// Every file below `dir` with its metadata, keyed by "/"-separated relative path.
fn list_files(dir: &Path) -> BTreeMap<String, (PathBuf, std::fs::Metadata)> {
    let mut out = BTreeMap::new();
    for entry in walkdir::WalkDir::new(dir).into_iter().flatten() {
        if !entry.file_type().is_file() {
            continue;
        }
        let Ok(rel) = entry.path().strip_prefix(dir) else {
            continue;
        };
        let rel = rel.to_string_lossy().replace('\\', "/");
        if is_ignored(&rel) {
            continue;
        }
        if let Ok(meta) = entry.metadata() {
            out.insert(rel, (entry.path().to_path_buf(), meta));
        }
    }
    out
}

fn snapshot(dir: &Path) -> Result<BTreeMap<String, FileStamp>, String> {
    let mut files = BTreeMap::new();
    for (rel, (path, meta)) in list_files(dir) {
        files.insert(
            rel,
            FileStamp {
                size: meta.len(),
                mtime: mtime_nanos(&meta),
                sha256: sha256_file(&path)?,
            },
        );
    }
    Ok(files)
}

/// Rights an RTX folder lock denies to everyone (well-known SID S-1-1-0, so
/// it works on every Windows language): write data / add file, append data /
/// add subfolder, write (extended) attributes, delete, delete child.
/// Reading stays allowed, so Minecraft loads the pack as usual. The ACE is
/// inheritable ((OI)(CI)), so it covers every file and subfolder.
#[cfg(windows)]
const LOCK_ACE: &str = "*S-1-1-0:(OI)(CI)(WD,AD,WEA,WA,DE,DC)";

#[cfg(windows)]
fn icacls(args: &[&std::ffi::OsStr]) -> Result<(), String> {
    use std::os::windows::process::CommandExt;
    let out = std::process::Command::new("icacls")
        .args(args)
        .creation_flags(0x0800_0000) // CREATE_NO_WINDOW
        .output()
        .map_err(|e| format!("Failed to run icacls: {}", e))?;
    if out.status.success() {
        Ok(())
    } else {
        Err(format!(
            "icacls failed: {} {}",
            String::from_utf8_lossy(&out.stdout).trim(),
            String::from_utf8_lossy(&out.stderr).trim()
        ))
    }
}

/// Locks an installed RTX folder against changes with an NTFS deny entry
/// (`icacls /deny`, i.e. `SetNamedSecurityInfoW` with a deny ACE).
///
/// Unlike a held file handle this lasts without the patcher running and
/// survives reboots: an A&S or Minecraft update can neither overwrite,
/// delete nor add files. The patcher undoes it with [`unlock_path`] before
/// deleting or replacing the folder; as the folder's owner it may always
/// change its permissions.
#[cfg(windows)]
pub fn lock_path(path: &Path) -> Result<(), String> {
    if !path.is_dir() {
        return Err(format!("{:?} is not a folder", path));
    }
    icacls(&[
        path.as_os_str(),
        "/deny".as_ref(),
        LOCK_ACE.as_ref(),
        "/C".as_ref(),
        "/Q".as_ref(),
    ])
}

/// Removes the deny entries [`lock_path`] adds (`icacls /remove:d`) and any
/// read-only attributes. Safe to call on folders that were never locked.
#[cfg(windows)]
pub fn unlock_path(path: &Path) {
    if path.is_dir() {
        // * /remove:d drops only the deny entries for Everyone; grants stay.
        let _ = icacls(&[
            path.as_os_str(),
            "/remove:d".as_ref(),
            "*S-1-1-0".as_ref(),
            "/C".as_ref(),
            "/Q".as_ref(),
        ]);
    }
    clear_readonly_recursive(path);
}

/// Other platforms (the patcher ships for Windows only; this keeps the crate
/// building elsewhere): read-only attributes stand in for the ACL.
#[cfg(not(windows))]
pub fn lock_path(path: &Path) -> Result<(), String> {
    for entry in walkdir::WalkDir::new(path)
        .into_iter()
        .flatten()
        .filter(|e| e.file_type().is_file())
    {
        if let Ok(meta) = entry.metadata() {
            let mut p = meta.permissions();
            p.set_readonly(true);
            let _ = std::fs::set_permissions(entry.path(), p);
        }
    }
    Ok(())
}

#[cfg(not(windows))]
pub fn unlock_path(path: &Path) {
    clear_readonly_recursive(path);
}

/// Clears the read-only attribute (`FILE_ATTRIBUTE_READONLY`) on every file
/// below `path`, which would otherwise make deleting fail.
#[allow(clippy::permissions_set_readonly_false)] // * Windows: clears FILE_ATTRIBUTE_READONLY only
fn clear_readonly_recursive(path: &Path) {
    if !path.is_dir() {
        return;
    }
    for entry in walkdir::WalkDir::new(path).into_iter().flatten() {
        if !entry.file_type().is_file() {
            continue;
        }
        if let Ok(meta) = entry.metadata() {
            let mut perms = meta.permissions();
            if perms.readonly() {
                perms.set_readonly(false);
                let _ = std::fs::set_permissions(entry.path(), perms);
            }
        }
    }
}

/// Extracts `archive` into `resource_packs/<folder_name>` of every Minecraft
/// install on this PC and returns the folders written.
///
/// An existing folder of that name is removed first (write protection
/// included), so the result is exactly the archive and not a mix with an
/// older install.
pub fn install_archive_to_targets(
    app: &tauri::AppHandle,
    archive: &Path,
    folder_name: &str,
) -> Result<Vec<PathBuf>, String> {
    let mojang_paths: Vec<PathBuf> = get_install_target_paths()
        .into_iter()
        .filter(|p| p.exists())
        .collect();
    if mojang_paths.is_empty() {
        return Err("Could not find Minecraft installation directory.".to_string());
    }

    let mut dests = Vec::new();
    for mojang_path in mojang_paths {
        let packs_dir = mojang_path.join("resource_packs");
        if !packs_dir.exists() {
            let _ = std::fs::create_dir_all(&packs_dir);
        }
        let dest_dir = packs_dir.join(folder_name);
        if dest_dir.exists() && !robust_cleanup(&dest_dir) {
            emit_msg(
                app,
                "main",
                &log_msg!(
                    "log.backend.install.failed",
                    path = format!("{:?}", dest_dir),
                    error = "the old folder could not be removed"
                ),
                "error",
            );
            continue;
        }
        match extract_archive_impl(Some(app), archive, &dest_dir, "main") {
            Ok(_) => dests.push(dest_dir),
            Err(e) => emit_msg(
                app,
                "main",
                &log_msg!(
                    "log.backend.install.failed",
                    path = format!("{:?}", dest_dir),
                    error = e
                ),
                "error",
            ),
        }
    }

    if dests.is_empty() {
        Err("Failed to install pack in any Minecraft directory.".to_string())
    } else {
        Ok(dests)
    }
}

fn sanitize(name: &str) -> String {
    let s: String = name
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || c == '.' || c == '-' {
                c
            } else {
                '_'
            }
        })
        .collect();
    s.trim_matches('_').chars().take(60).collect()
}

/// Copies the patched archive into the backup folder and drops the oldest
/// backups beyond [`KEEP_BACKUPS`].
fn save_backup(
    app: &tauri::AppHandle,
    state: &mut GuardState,
    archive: &Path,
    folder_name: &str,
    opts: &GuardOptions,
) -> Result<String, String> {
    let dir = backup_dir(app)?;
    let created_at = now_secs();
    let id = format!("{}-{}", created_at, sanitize(&opts.label));
    let file = format!("{}.zip", id);
    std::fs::copy(archive, dir.join(&file)).map_err(|e| format!("Failed to save backup: {}", e))?;
    let size = std::fs::metadata(dir.join(&file))
        .map(|m| m.len())
        .unwrap_or(0);
    state.backups.push(BackupEntry {
        id: id.clone(),
        file,
        folder_name: folder_name.to_string(),
        label: opts.label.clone(),
        pack_version: opts.pack_version.clone(),
        patch_version: opts.patch_version.clone(),
        created_at,
        size,
    });
    state
        .backups
        .sort_by_key(|b| std::cmp::Reverse(b.created_at));
    for old in state
        .backups
        .split_off(KEEP_BACKUPS.min(state.backups.len()))
    {
        let _ = std::fs::remove_file(dir.join(&old.file));
    }
    Ok(id)
}

/// Records freshly installed RTX folders, and backs up / write-protects them
/// as the options ask. Called by `install_mcpack` and the backup restore.
pub fn record_install(
    app: &tauri::AppHandle,
    dirs: &[PathBuf],
    archive: Option<&Path>,
    existing_backup: Option<String>,
    opts: &GuardOptions,
) -> Result<(), String> {
    let mut state = load_state(app);
    let folder_name = dirs
        .first()
        .and_then(|d| d.file_name())
        .map(|n| n.to_string_lossy().into_owned())
        .unwrap_or_default();

    let mut backup_id = existing_backup;
    if opts.backup && backup_id.is_none() {
        if let Some(archive) = archive {
            match save_backup(app, &mut state, archive, &folder_name, opts) {
                Ok(id) => {
                    emit_msg(
                        app,
                        "main",
                        &log_msg!("log.backend.guard.backupSaved", label = &opts.label),
                        "success",
                    );
                    backup_id = Some(id);
                }
                Err(e) => emit_msg(
                    app,
                    "main",
                    &log_msg!("log.backend.guard.backupFailed", error = e),
                    "warning",
                ),
            }
        }
    }

    for dir in dirs {
        let files = snapshot(dir)?;
        if opts.lock {
            match lock_path(dir) {
                Ok(()) => emit_msg(
                    app,
                    "main",
                    &log_msg!("log.backend.guard.locked", path = format!("{:?}", dir)),
                    "info",
                ),
                Err(e) => emit_msg(
                    app,
                    "main",
                    &log_msg!("log.backend.guard.lockFailed", error = e),
                    "warning",
                ),
            }
        }
        state.installs.retain(|r| !same_dir(&r.dir, dir));
        state.installs.push(InstallRecord {
            dir: dir.to_string_lossy().into_owned(),
            label: opts.label.clone(),
            pack_version: opts.pack_version.clone(),
            patch_version: opts.patch_version.clone(),
            installed_at: now_secs(),
            locked: opts.lock,
            backup_id: backup_id.clone(),
            files,
        });
    }
    save_state(app, &state)
}

/// Compares a folder with its record. Hashes only files whose size or mtime
/// moved, so a healthy pack checks in well under a second.
fn compare(record: &InstallRecord) -> PackHealth {
    let dir = Path::new(&record.dir);
    let current = list_files(dir);
    let mut changed = 0;
    let mut missing = 0;
    let mut examples = Vec::new();

    for (rel, stamp) in &record.files {
        match current.get(rel) {
            None => {
                missing += 1;
                if examples.len() < 5 {
                    examples.push(format!("- {}", rel));
                }
            }
            Some((path, meta)) => {
                let differs = if meta.len() != stamp.size {
                    true
                } else if mtime_nanos(meta) != stamp.mtime {
                    sha256_file(path).map(|h| h != stamp.sha256).unwrap_or(true)
                } else {
                    false
                };
                if differs {
                    changed += 1;
                    if examples.len() < 5 {
                        examples.push(format!("~ {}", rel));
                    }
                }
            }
        }
    }
    let mut added = 0;
    for rel in current.keys() {
        if !record.files.contains_key(rel) {
            added += 1;
            if examples.len() < 5 {
                examples.push(format!("+ {}", rel));
            }
        }
    }

    PackHealth {
        dir: record.dir.clone(),
        label: record.label.clone(),
        pack_version: record.pack_version.clone(),
        patch_version: record.patch_version.clone(),
        changed,
        added,
        missing,
        examples,
        locked: record.locked,
        backup_id: record.backup_id.clone(),
    }
}

/// Checks every recorded RTX folder and returns the damaged ones. Records of
/// folders that no longer exist (removed by the user or the Cleaner) are
/// dropped. Backup ids that point to deleted backups are reported as none.
#[tauri::command]
pub async fn check_installed_packs(app: tauri::AppHandle) -> Result<Vec<PackHealth>, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let mut state = load_state(&app);
        let before = state.installs.len();
        state.installs.retain(|r| Path::new(&r.dir).is_dir());
        if state.installs.len() != before {
            let _ = save_state(&app, &state);
        }
        let backups: Vec<String> = state.backups.iter().map(|b| b.id.clone()).collect();
        let mut damaged = Vec::new();
        for record in &state.installs {
            let mut health = compare(record);
            if health
                .backup_id
                .as_ref()
                .is_some_and(|id| !backups.contains(id))
            {
                health.backup_id = None;
            }
            if health.damaged() {
                damaged.push(health);
            }
        }
        Ok(damaged)
    })
    .await
    .map_err(|e| format!("Pack check failed: {}", e))?
}

/// Deletes a recorded RTX folder (write protection included) and its record.
/// Only folders the patcher recorded itself can be removed this way.
#[tauri::command]
pub async fn remove_installed_pack(app: tauri::AppHandle, dir: String) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        let mut state = load_state(&app);
        let path = PathBuf::from(&dir);
        if !state.installs.iter().any(|r| same_dir(&r.dir, &path)) {
            return Err("This folder was not installed by the patcher.".to_string());
        }
        if path.exists() && !robust_cleanup(&path) {
            return Err(format!(
                "Could not delete {:?}. Close Minecraft and try again.",
                path
            ));
        }
        state.installs.retain(|r| !same_dir(&r.dir, &path));
        save_state(&app, &state)
    })
    .await
    .map_err(|e| format!("Removing the pack failed: {}", e))?
}

/// Saved backups, newest first. Entries whose file is gone are dropped.
#[tauri::command]
pub fn list_pack_backups(app: tauri::AppHandle) -> Result<Vec<BackupEntry>, String> {
    let dir = backup_dir(&app)?;
    let mut state = load_state(&app);
    let before = state.backups.len();
    state.backups.retain(|b| dir.join(&b.file).is_file());
    if state.backups.len() != before {
        save_state(&app, &state)?;
    }
    Ok(state.backups)
}

/// Deletes one backup file and its entry.
#[tauri::command]
pub fn delete_pack_backup(app: tauri::AppHandle, id: String) -> Result<(), String> {
    let dir = backup_dir(&app)?;
    let mut state = load_state(&app);
    if let Some(b) = state.backups.iter().find(|b| b.id == id) {
        let _ = std::fs::remove_file(dir.join(&b.file));
    }
    state.backups.retain(|b| b.id != id);
    save_state(&app, &state)
}

/// Reinstalls a backup into every Minecraft install, without patching again,
/// and records the result like a normal install.
#[tauri::command]
pub async fn restore_pack_backup(
    app: tauri::AppHandle,
    id: String,
    lock: bool,
) -> Result<Vec<String>, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let state = load_state(&app);
        let entry = state
            .backups
            .iter()
            .find(|b| b.id == id)
            .cloned()
            .ok_or_else(|| "This backup no longer exists.".to_string())?;
        let archive = backup_dir(&app)?.join(&entry.file);
        if !archive.is_file() {
            return Err("The backup file is missing.".to_string());
        }
        let dests = install_archive_to_targets(&app, &archive, &entry.folder_name)?;
        let opts = GuardOptions {
            label: entry.label.clone(),
            pack_version: entry.pack_version.clone(),
            patch_version: entry.patch_version.clone(),
            backup: true,
            lock,
        };
        record_install(&app, &dests, None, Some(entry.id.clone()), &opts)?;
        Ok(dests
            .iter()
            .map(|d| d.to_string_lossy().into_owned())
            .collect())
    })
    .await
    .map_err(|e| format!("Restoring the backup failed: {}", e))?
}

/// Turns write protection on or off for every recorded RTX folder.
/// Returns how many folders were changed.
#[tauri::command]
pub async fn set_installed_packs_locked(
    app: tauri::AppHandle,
    locked: bool,
) -> Result<usize, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let mut state = load_state(&app);
        let mut count = 0;
        for record in state.installs.iter_mut() {
            let dir = Path::new(&record.dir);
            if dir.is_dir() {
                if locked {
                    lock_path(dir)?;
                } else {
                    unlock_path(dir);
                }
                record.locked = locked;
                count += 1;
            }
        }
        save_state(&app, &state)?;
        Ok(count)
    })
    .await
    .map_err(|e| format!("Changing write protection failed: {}", e))?
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp_dir(tag: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("rtx-guard-{}-{}", tag, uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&d).unwrap();
        d
    }

    fn record_for(dir: &Path) -> InstallRecord {
        InstallRecord {
            dir: dir.to_string_lossy().into_owned(),
            label: "test".into(),
            pack_version: None,
            patch_version: None,
            installed_at: 0,
            locked: false,
            backup_id: None,
            files: snapshot(dir).unwrap(),
        }
    }

    #[test]
    fn detects_changed_added_and_missing_files() {
        let dir = temp_dir("cmp");
        std::fs::create_dir_all(dir.join("textures")).unwrap();
        std::fs::write(dir.join("manifest.json"), b"rtx").unwrap();
        std::fs::write(dir.join("textures/a.png"), b"aaaa").unwrap();
        std::fs::write(dir.join("textures/b.png"), b"bbbb").unwrap();
        let record = record_for(&dir);
        assert!(!compare(&record).damaged());

        // Same size, new content: only the hash catches it.
        std::thread::sleep(std::time::Duration::from_millis(20));
        std::fs::write(dir.join("textures/a.png"), b"AAAA").unwrap();
        std::fs::remove_file(dir.join("textures/b.png")).unwrap();
        std::fs::write(dir.join("textures/c.png"), b"cc").unwrap();
        std::fs::write(dir.join("desktop.ini"), b"ignored").unwrap();
        let h = compare(&record);
        assert_eq!((h.changed, h.added, h.missing), (1, 1, 1));
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn touched_but_identical_files_are_fine() {
        let dir = temp_dir("touch");
        std::fs::write(dir.join("a.txt"), b"same").unwrap();
        let record = record_for(&dir);
        std::thread::sleep(std::time::Duration::from_millis(20));
        std::fs::write(dir.join("a.txt"), b"same").unwrap();
        assert!(!compare(&record).damaged());
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn locked_folders_block_writes_and_still_clean_up() {
        let dir = temp_dir("lock");
        std::fs::create_dir_all(dir.join("sub")).unwrap();
        std::fs::write(dir.join("sub/a.txt"), b"x").unwrap();
        lock_path(&dir).unwrap();
        assert_eq!(
            std::fs::read(dir.join("sub/a.txt")).unwrap(),
            b"x",
            "reading must keep working"
        );
        assert!(
            std::fs::write(dir.join("sub/a.txt"), b"overwrite").is_err(),
            "overwrite must fail"
        );
        assert!(
            std::fs::write(dir.join("sub/new.txt"), b"n").is_err(),
            "adding files must fail"
        );
        assert!(
            std::fs::remove_file(dir.join("sub/a.txt")).is_err(),
            "deleting must fail"
        );
        assert!(
            std::fs::remove_dir_all(&dir).is_err(),
            "deleting the folder must fail"
        );
        assert!(
            robust_cleanup(&dir),
            "cleanup must clear write protection first"
        );
        assert!(!dir.exists());
    }
}
