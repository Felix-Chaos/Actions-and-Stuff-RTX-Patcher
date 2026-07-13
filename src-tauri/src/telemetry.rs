// Telemetry & diagnostics module (DSGVO/GDPR-conform)
//
// Design rules:
// - NOTHING is sent without explicit user consent (opt-in, stored locally).
// - Identification is a RANDOM install UUID (no MachineGuid, no hardware fingerprint).
// - Hardware ping is sent at most once per patcher version.
// - Every payload we send is also written to disk next to settings.json so the
//   user can inspect exactly what left their machine (transparency).
// - "Delete my data" wipes server-side rows for this install id and rotates the
//   local id, fulfilling the right to erasure (Art. 17 DSGVO).

use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

const CREATE_NO_WINDOW: u32 = 0x0800_0000;

// ---------------------------------------------------------------------------
// Local telemetry state (telemetry.json next to settings.json)
// ---------------------------------------------------------------------------

#[derive(Serialize, Deserialize, Clone, Default)]
pub struct TelemetryState {
    /// Random UUID v4 generated locally. Not derived from hardware.
    pub install_id: String,
    /// None = user has not decided yet (show consent modal). Some(true/false) = decided.
    pub consent: Option<bool>,
    /// Unix ms timestamp of the consent decision.
    pub consent_ts: Option<u64>,
    /// Patcher version the hardware ping was last sent for.
    pub hw_sent_for_version: Option<String>,
}

fn telemetry_path() -> Result<PathBuf, String> {
    let root = std::env::current_dir().map_err(|e| e.to_string())?;
    Ok(root.join("telemetry.json"))
}

fn now_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

fn new_install_id() -> String {
    uuid::Uuid::new_v4().to_string()
}

pub fn load_state() -> Result<TelemetryState, String> {
    let path = telemetry_path()?;
    if path.exists() {
        let content = std::fs::read_to_string(&path).map_err(|e| e.to_string())?;
        let mut state: TelemetryState =
            serde_json::from_str(&content).unwrap_or_default();
        if state.install_id.is_empty() {
            state.install_id = new_install_id();
            save_state(&state)?;
        }
        Ok(state)
    } else {
        let state = TelemetryState {
            install_id: new_install_id(),
            ..Default::default()
        };
        save_state(&state)?;
        Ok(state)
    }
}

fn save_state(state: &TelemetryState) -> Result<(), String> {
    let path = telemetry_path()?;
    let content = serde_json::to_string_pretty(state).map_err(|e| e.to_string())?;
    std::fs::write(path, content).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn get_telemetry_state() -> Result<TelemetryState, String> {
    load_state()
}

#[tauri::command]
pub fn set_telemetry_consent(consent: bool) -> Result<TelemetryState, String> {
    let mut state = load_state()?;
    state.consent = Some(consent);
    state.consent_ts = Some(now_ms());
    save_state(&state)?;
    Ok(state)
}

// ---------------------------------------------------------------------------
// PowerShell helper
// ---------------------------------------------------------------------------

fn run_powershell(script: &str) -> Result<String, String> {
    #[cfg(target_os = "windows")]
    {
        let output = std::process::Command::new("powershell")
            .args(["-NoProfile", "-NonInteractive", "-Command", script])
            .creation_flags(CREATE_NO_WINDOW)
            .output()
            .map_err(|e| format!("Failed to run PowerShell: {}", e))?;
        Ok(String::from_utf8_lossy(&output.stdout).into_owned())
    }
    #[cfg(not(target_os = "windows"))]
    {
        let _ = script;
        Err("Hardware collection is only supported on Windows.".to_string())
    }
}

// ---------------------------------------------------------------------------
// Hardware info collection
// ---------------------------------------------------------------------------

/// Collects hardware information relevant for diagnosing RTX rendering issues.
/// Contains NO usernames, NO paths, NO serial numbers, NO MAC addresses.
#[tauri::command]
pub fn collect_hardware_info(app: tauri::AppHandle) -> Result<serde_json::Value, String> {
    let script = r#"
$ErrorActionPreference = 'SilentlyContinue'
$gpus = @(Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, DriverDate, AdapterRAM, CurrentHorizontalResolution, CurrentVerticalResolution, CurrentRefreshRate)
# AdapterRAM is a uint32 and caps at 4GB; qwMemorySize from the driver registry is accurate.
$qw = @(Get-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0*' -Name 'HardwareInformation.qwMemorySize' -ErrorAction SilentlyContinue | ForEach-Object { $_.'HardwareInformation.qwMemorySize' })
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1 Name, NumberOfCores, NumberOfLogicalProcessors
$os = Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber, OSArchitecture
$cs = Get-CimInstance Win32_ComputerSystem | Select-Object TotalPhysicalMemory
@{ gpus = $gpus; vram_qw_bytes = $qw; cpu = $cpu; os = $os; ram_bytes = $cs.TotalPhysicalMemory } | ConvertTo-Json -Depth 4
"#;
    let stdout = run_powershell(script)?;
    let hw: serde_json::Value = serde_json::from_str(stdout.trim())
        .map_err(|e| format!("Failed to parse hardware info: {}", e))?;

    // Detect which Bedrock editions are installed (paths are NOT included, only flags).
    let gdk_installed = std::env::var("APPDATA")
        .map(|a| Path::new(&a).join("Minecraft Bedrock").exists())
        .unwrap_or(false);
    let uwp_installed = std::env::var("LOCALAPPDATA")
        .map(|l| {
            Path::new(&l)
                .join("Packages")
                .join("Microsoft.MinecraftUWP_8wekyb3d8bbwe")
                .exists()
        })
        .unwrap_or(false);

    let state = load_state()?;
    let payload = serde_json::json!({
        "schema_version": 1,
        "install_id": state.install_id,
        "patcher_version": app.package_info().version.to_string(),
        "collected_at": now_ms(),
        "hardware": hw,
        "bedrock_gdk": gdk_installed,
        "bedrock_uwp": uwp_installed,
        "rtx": collect_rtx_environment(),
    });
    Ok(payload)
}

/// Collects RTX-relevant environment: the in-game graphics settings, a BetterRTX
/// install fingerprint, and which A&S subpacks are active. These are the variables
/// most likely to explain why the same GPU renders differently between users.
/// No personal data — only setting values, pack UUIDs, and file sizes/dates.
fn collect_rtx_environment() -> serde_json::Value {
    serde_json::json!({
        "settings": collect_rtx_settings(),
        "betterrtx": collect_betterrtx_fingerprint(),
        "active_subpacks": collect_active_subpacks(),
    })
}

/// RTX-relevant keys from the first options.txt found.
fn collect_rtx_settings() -> serde_json::Value {
    const KEYS: &[&str] = &[
        "graphics_mode",
        "graphics_api",
        "graphics_quality_preset_mode",
        "raytracing_viewdistance",
        "deferred_viewdistance",
        "upscaling_mode",
        "upscaling_percentage",
    ];
    let mut out = serde_json::Map::new();
    if let Ok(files) = crate::commands::get_options_paths() {
        if let Some(of) = files.first() {
            if let Ok(map) = crate::commands::read_options(of.path.clone()) {
                for k in KEYS {
                    if let Some(v) = map.get(*k) {
                        out.insert((*k).to_string(), serde_json::Value::String(v.clone()));
                    }
                }
            }
        }
    }
    serde_json::Value::Object(out)
}

/// Fingerprints the installed BetterRTX build/preset by enumerating
/// %LOCALAPPDATA%\graphics.bedrock\packs\*\RTXStub.material.bin (pack UUID +
/// file size + mtime). Different BetterRTX presets/versions ship different stubs.
fn collect_betterrtx_fingerprint() -> serde_json::Value {
    let mut stubs = Vec::new();
    if let Ok(local) = std::env::var("LOCALAPPDATA") {
        let packs_dir = Path::new(&local).join("graphics.bedrock").join("packs");
        if let Ok(entries) = std::fs::read_dir(&packs_dir) {
            for entry in entries.flatten() {
                let uuid = entry.file_name().to_string_lossy().into_owned();
                let stub = entry.path().join("RTXStub.material.bin");
                if let Ok(meta) = std::fs::metadata(&stub) {
                    let mtime = meta
                        .modified()
                        .ok()
                        .and_then(|m| m.duration_since(std::time::UNIX_EPOCH).ok())
                        .map(|d| d.as_secs())
                        .unwrap_or(0);
                    stubs.push(serde_json::json!({
                        "pack_uuid": uuid,
                        "stub_size": meta.len(),
                        "stub_mtime": mtime,
                    }));
                }
            }
        }
    }
    serde_json::json!({
        "installed": !stubs.is_empty(),
        "pack_count": stubs.len(),
        "stubs": stubs,
    })
}

/// Best-effort: which A&S subpack(s) are selected across recent worlds, read from
/// each world's world_resource_packs.json (has pack uuid + subpack_name). Bounded
/// to the 15 most-recently-modified worlds to stay cheap.
fn collect_active_subpacks() -> Vec<String> {
    let mut worlds_dirs = Vec::new();
    if let Ok(appdata) = std::env::var("APPDATA") {
        let users = Path::new(&appdata).join("Minecraft Bedrock").join("Users");
        if let Ok(entries) = std::fs::read_dir(&users) {
            for e in entries.flatten() {
                worlds_dirs.push(e.path().join("games").join("com.mojang").join("minecraftWorlds"));
            }
        }
    }
    if let Ok(local) = std::env::var("LOCALAPPDATA") {
        worlds_dirs.push(
            Path::new(&local)
                .join("Packages")
                .join("Microsoft.MinecraftUWP_8wekyb3d8bbwe")
                .join("LocalState")
                .join("games")
                .join("com.mojang")
                .join("minecraftWorlds"),
        );
    }

    // Gather (mtime, world_resource_packs.json path), newest first, cap at 15.
    let mut candidates: Vec<(std::time::SystemTime, PathBuf)> = Vec::new();
    for wd in worlds_dirs {
        if let Ok(entries) = std::fs::read_dir(&wd) {
            for e in entries.flatten() {
                let wrp = e.path().join("world_resource_packs.json");
                if let Ok(meta) = std::fs::metadata(&wrp) {
                    let mtime = meta.modified().unwrap_or(std::time::UNIX_EPOCH);
                    candidates.push((mtime, wrp));
                }
            }
        }
    }
    candidates.sort_by(|a, b| b.0.cmp(&a.0));
    candidates.truncate(15);

    let mut found = std::collections::BTreeSet::new();
    for (_, path) in candidates {
        if let Ok(content) = std::fs::read_to_string(&path) {
            if let Ok(json) = serde_json::from_str::<serde_json::Value>(&content) {
                if let Some(arr) = json.as_array() {
                    for pack in arr {
                        if let Some(name) = pack.get("subpack_name").and_then(|v| v.as_str()) {
                            if !name.is_empty() {
                                found.insert(name.to_string());
                            }
                        }
                    }
                }
            }
        }
    }
    found.into_iter().collect()
}

/// Sends the one-time hardware ping. Requires consent; sends at most once per
/// patcher version. Writes the exact payload to last_hardware_ping.json first.
#[tauri::command]
pub async fn submit_hardware_ping(app: tauri::AppHandle) -> Result<serde_json::Value, String> {
    let state = load_state()?;
    if state.consent != Some(true) {
        return Ok(serde_json::json!({ "skipped": "no_consent" }));
    }
    let version = app.package_info().version.to_string();
    if state.hw_sent_for_version.as_deref() == Some(version.as_str()) {
        return Ok(serde_json::json!({ "skipped": "already_sent_for_version" }));
    }

    let payload = collect_hardware_info(app)?;

    // Transparency: persist exactly what we send so the user can inspect it.
    if let Ok(root) = std::env::current_dir() {
        let _ = std::fs::write(
            root.join("last_hardware_ping.json"),
            serde_json::to_string_pretty(&payload).unwrap_or_default(),
        );
    }

    let api_url = std::option_env!("PATCHER_API_URL").unwrap_or("http://localhost:3000");
    let api_key = std::option_env!("PATCHER_API_KEY").unwrap_or("");
    let client = reqwest::Client::new();
    let res = client
        .post(&format!("{}/api/patcher/hardware", api_url))
        .header("Authorization", format!("Bearer {}", api_key))
        .json(&payload)
        .send()
        .await
        .map_err(|e| format!("Request failed: {}", e))?;

    if !res.status().is_success() {
        return Err(format!("Server returned {}", res.status()));
    }

    let mut new_state = load_state()?;
    new_state.hw_sent_for_version = Some(version);
    save_state(&new_state)?;

    Ok(serde_json::json!({ "sent": true }))
}

/// Right to erasure (Art. 17 DSGVO): asks the server to delete everything tied
/// to this install id, then rotates the local id so past and future data can
/// never be linked.
#[tauri::command]
pub async fn telemetry_delete_my_data() -> Result<serde_json::Value, String> {
    let state = load_state()?;
    let api_url = std::option_env!("PATCHER_API_URL").unwrap_or("http://localhost:3000");
    let api_key = std::option_env!("PATCHER_API_KEY").unwrap_or("");
    let client = reqwest::Client::new();
    let res = client
        .post(&format!("{}/api/patcher/delete-my-data", api_url))
        .header("Authorization", format!("Bearer {}", api_key))
        .json(&serde_json::json!({ "install_id": state.install_id }))
        .send()
        .await
        .map_err(|e| format!("Request failed: {}", e))?;

    if !res.status().is_success() {
        return Err(format!("Server returned {}", res.status()));
    }

    // Rotate local id and clear the sent-marker.
    let new_state = TelemetryState {
        install_id: new_install_id(),
        consent: state.consent,
        consent_ts: state.consent_ts,
        hw_sent_for_version: None,
    };
    save_state(&new_state)?;
    Ok(serde_json::json!({ "deleted": true }))
}

// ---------------------------------------------------------------------------
// Display driver event log collection (for GPU bugs that leave no content log)
// ---------------------------------------------------------------------------

/// Collects display-driver related events (driver resets/TDRs, nvlddmkm/amdkmdag
/// errors) from the Windows System event log, last 7 days, max 50 events.
/// Messages are the driver's own diagnostics; they contain no personal data.
#[tauri::command]
pub fn collect_driver_events() -> Result<String, String> {
    let script = r#"
$ErrorActionPreference = 'SilentlyContinue'
$providers = @('Display','nvlddmkm','amdkmdag','amdkmdap','amdkmdap64','igfxn','igfx')
$events = Get-WinEvent -FilterHashtable @{ LogName = 'System'; StartTime = (Get-Date).AddDays(-7) } -MaxEvents 5000 -ErrorAction SilentlyContinue |
    Where-Object { $providers -contains $_.ProviderName -or $_.Id -eq 4101 } |
    Select-Object -First 50 |
    ForEach-Object {
        @{
            time = $_.TimeCreated.ToUniversalTime().ToString('o')
            provider = $_.ProviderName
            id = $_.Id
            level = $_.LevelDisplayName
            message = if ($_.Message) { $_.Message.Substring(0, [Math]::Min(500, $_.Message.Length)) } else { '' }
        }
    }
if ($null -eq $events) { $events = @() }
ConvertTo-Json @($events) -Depth 3
"#;
    let stdout = run_powershell(script)?;
    let trimmed = stdout.trim();
    if trimmed.is_empty() {
        return Ok("[]".to_string());
    }
    // Cap at 200 KB to keep the report payload small.
    const MAX: usize = 200 * 1024;
    if trimmed.len() > MAX {
        Ok(trimmed.chars().take(MAX).collect())
    } else {
        Ok(trimmed.to_string())
    }
}

// ---------------------------------------------------------------------------
// Minecraft content log handling ("Send Content Log" switch)
// ---------------------------------------------------------------------------

#[derive(Serialize)]
pub struct ContentLogResult {
    /// "ok" | "logging_was_off" | "no_log" | "log_too_small"
    pub status: String,
    /// True if we flipped content_log_file to 1 in options.txt.
    pub options_edited: bool,
    /// Prepared zip ready for upload (only when status == "ok").
    pub zip_path: Option<String>,
    /// Size of the source log in MB (for the UI message).
    pub log_size_mb: Option<f64>,
}

fn find_log_dirs() -> Vec<PathBuf> {
    let mut dirs = Vec::new();
    if let Ok(appdata) = std::env::var("APPDATA") {
        dirs.push(Path::new(&appdata).join("Minecraft Bedrock").join("logs"));
    }
    if let Ok(local) = std::env::var("LOCALAPPDATA") {
        dirs.push(
            Path::new(&local)
                .join("Packages")
                .join("Microsoft.MinecraftUWP_8wekyb3d8bbwe")
                .join("LocalState")
                .join("logs"),
        );
    }
    dirs.into_iter().filter(|d| d.exists()).collect()
}

fn newest_content_log() -> Option<(PathBuf, u64)> {
    let mut best: Option<(PathBuf, std::time::SystemTime, u64)> = None;
    for dir in find_log_dirs() {
        if let Ok(entries) = std::fs::read_dir(&dir) {
            for entry in entries.flatten() {
                let name = entry.file_name().to_string_lossy().into_owned();
                if !name.starts_with("ContentLog") || !name.ends_with(".txt") {
                    continue;
                }
                if let Ok(meta) = entry.metadata() {
                    let mtime = meta.modified().unwrap_or(std::time::UNIX_EPOCH);
                    let size = meta.len();
                    if best.as_ref().map(|(_, t, _)| mtime > *t).unwrap_or(true) {
                        best = Some((entry.path(), mtime, size));
                    }
                }
            }
        }
    }
    best.map(|(p, _, s)| (p, s))
}

/// Ensures content_log_file:1 in every options.txt found. Returns true if any
/// file was changed (meaning Minecraft must be restarted).
fn ensure_content_log_enabled() -> Result<bool, String> {
    let options_files = crate::commands::get_options_paths()?;
    let mut edited = false;
    for of in options_files {
        let map = crate::commands::read_options(of.path.clone())?;
        let current = map.get("content_log_file").map(String::as_str).unwrap_or("0");
        if current != "1" {
            let mut changes = std::collections::HashMap::new();
            changes.insert("content_log_file".to_string(), "1".to_string());
            crate::commands::write_options(of.path, changes)?;
            edited = true;
        }
    }
    Ok(edited)
}

/// Removes Windows usernames from log content: C:\Users\<name>\ -> C:\Users\<user>\
fn scrub_usernames(content: &str) -> String {
    let mut result = String::with_capacity(content.len());
    let mut rest = content;
    loop {
        // Handle both slash directions and both "Users" spellings seen in logs.
        let idx = rest.find("Users\\").map(|i| (i, '\\')).or_else(|| rest.find("Users/").map(|i| (i, '/')));
        match idx {
            Some((i, sep)) => {
                let after = i + "Users".len() + 1;
                result.push_str(&rest[..after]);
                let tail = &rest[after..];
                // Skip the username segment up to the next separator.
                if let Some(end) = tail.find(['\\', '/', '\n']) {
                    if tail.as_bytes().get(end) == Some(&b'\n') {
                        // No separator before EOL: leave untouched.
                        result.push_str(&tail[..end]);
                        rest = &tail[end..];
                    } else {
                        result.push_str("<user>");
                        result.push(sep);
                        rest = &tail[end + 1..];
                    }
                } else {
                    result.push_str("<user>");
                    rest = "";
                }
            }
            None => {
                result.push_str(rest);
                break;
            }
        }
        if rest.is_empty() {
            break;
        }
    }
    result
}

const MIN_LOG_BYTES: u64 = 5 * 1024 * 1024; // log must be > 5 MB (has enough content)
const MAX_LOG_BYTES: u64 = 500 * 1024 * 1024; // reject logs bigger than 500 MB (stale/bloated)
const MAX_LOG_AGE_SECS: u64 = 60 * 60; // log must have been written within the last hour
const TAIL_BYTES: u64 = 20 * 1024 * 1024; // upload at most the last 20 MB

fn file_age_secs(path: &Path) -> u64 {
    std::fs::metadata(path)
        .and_then(|m| m.modified())
        .ok()
        .and_then(|mtime| std::time::SystemTime::now().duration_since(mtime).ok())
        .map(|d| d.as_secs())
        .unwrap_or(u64::MAX)
}

/// Implements the "Send Content Log" flow:
/// 1. If content logging is disabled in options.txt -> enable it, tell the user
///    to restart MC, join the world with the broken entity/block, retry.
/// 2. If no log, or newest log < 5 MB, > 500 MB, or older than 1 hour -> instruct.
/// 3. Otherwise scrub usernames, take the last 20 MB, zip it, return the path.
#[tauri::command]
pub fn prepare_content_log() -> Result<ContentLogResult, String> {
    let options_edited = ensure_content_log_enabled()?;
    if options_edited {
        return Ok(ContentLogResult {
            status: "logging_was_off".to_string(),
            options_edited: true,
            zip_path: None,
            log_size_mb: None,
        });
    }

    let Some((log_path, size)) = newest_content_log() else {
        return Ok(ContentLogResult {
            status: "no_log".to_string(),
            options_edited: false,
            zip_path: None,
            log_size_mb: None,
        });
    };

    let size_mb = size as f64 / (1024.0 * 1024.0);
    let rounded_mb = Some((size_mb * 100.0).round() / 100.0);

    // Freshness: the log must reflect a bug reproduced just now, not an old session.
    if file_age_secs(&log_path) > MAX_LOG_AGE_SECS {
        return Ok(ContentLogResult {
            status: "log_too_old".to_string(),
            options_edited: false,
            zip_path: None,
            log_size_mb: rounded_mb,
        });
    }

    if size <= MIN_LOG_BYTES {
        return Ok(ContentLogResult {
            status: "log_too_small".to_string(),
            options_edited: false,
            zip_path: None,
            log_size_mb: rounded_mb,
        });
    }

    if size > MAX_LOG_BYTES {
        return Ok(ContentLogResult {
            status: "log_too_large".to_string(),
            options_edited: false,
            zip_path: None,
            log_size_mb: rounded_mb,
        });
    }

    // Read only the tail of very large logs (they can reach gigabytes).
    use std::io::{Read, Seek, SeekFrom};
    let mut file = std::fs::File::open(&log_path).map_err(|e| e.to_string())?;
    let start = size.saturating_sub(TAIL_BYTES);
    file.seek(SeekFrom::Start(start)).map_err(|e| e.to_string())?;
    let mut buffer = Vec::with_capacity((size - start) as usize);
    file.read_to_end(&mut buffer).map_err(|e| e.to_string())?;
    let content = String::from_utf8_lossy(&buffer).into_owned();
    let scrubbed = scrub_usernames(&content);

    // Zip it (repetitive error logs compress extremely well).
    let temp_dir = std::env::temp_dir();
    let zip_path = temp_dir.join(format!("content_log_{}.zip", now_ms()));
    let zip_file = std::fs::File::create(&zip_path).map_err(|e| e.to_string())?;
    let mut writer = zip::ZipWriter::new(zip_file);
    let opts = zip::write::SimpleFileOptions::default()
        .compression_method(zip::CompressionMethod::Deflated);
    writer
        .start_file("content_log_tail.txt", opts)
        .map_err(|e| e.to_string())?;
    use std::io::Write;
    writer
        .write_all(scrubbed.as_bytes())
        .map_err(|e| e.to_string())?;
    writer.finish().map_err(|e| e.to_string())?;

    Ok(ContentLogResult {
        status: "ok".to_string(),
        options_edited: false,
        zip_path: Some(zip_path.to_string_lossy().into_owned()),
        log_size_mb: Some((size_mb * 100.0).round() / 100.0),
    })
}
