//! Remote patch library: catalogue fetching and on-demand patch downloads.
//!
//! Patch payloads used to be bundled into the installer (~254 MB of .vcdiff
//! under assets/Patches). They now live in a separate repo,
//! Felix-Chaos/AS-RTX-Patch-Library, published as assets on a permanent
//! `patch-library` release. Only one patch stays bundled, as an offline
//! fallback; everything else is downloaded on demand and cached per user.
//!
//! This is deliberately kept apart from the app's own update flow: a new patch
//! is published by pushing a folder to that repo, and reaches every installed
//! copy with no app update, no version bump and no updater prompt.

use serde::Serialize;
use sha2::{Digest, Sha256};
use std::io::Read;
use std::path::{Path, PathBuf};
use tauri::Emitter;

use crate::utils::{emit_log, user_data_dir};

const PATCH_INDEX_URL: &str = "https://github.com/Felix-Chaos/AS-RTX-Patch-Library/releases/download/patch-library/patch_index.json";

/// The catalogue is small; a hung request must not stall app startup, since
/// loadPatchConfigs is awaited during DOMContentLoaded.
const INDEX_TIMEOUT_SECS: u64 = 10;
const DOWNLOAD_TIMEOUT_SECS: u64 = 600;
const PROGRESS_INTERVAL_MS: u128 = 200;
const HASH_CHUNK: usize = 64 * 1024;

/// Mirrors utils::LogPayload's shape: a plain serializable struct emitted as a
/// Tauri event the frontend listens for.
#[derive(Clone, Serialize)]
pub struct DownloadProgress {
    pub slug: String,
    pub variant: String,
    pub bytes_downloaded: u64,
    pub total_bytes: u64,
}

fn user_agent() -> String {
    format!("AS-RTX-Patcher/{}", env!("CARGO_PKG_VERSION"))
}

fn cache_root(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    Ok(user_data_dir(app)?.join("patch_cache"))
}

/// Streaming SHA-256. The existing hashing sites all read whole files into
/// memory, which is the wrong shape for a 24 MB payload.
fn sha256_file(path: &Path) -> Result<String, String> {
    let mut file = std::fs::File::open(path)
        .map_err(|e| format!("Failed to open {} for hashing: {}", path.display(), e))?;
    let mut hasher = Sha256::new();
    let mut buf = vec![0u8; HASH_CHUNK];
    loop {
        let n = file
            .read(&mut buf)
            .map_err(|e| format!("Failed to read {} while hashing: {}", path.display(), e))?;
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

/// Fetches the remote patch catalogue.
///
/// Never fails in practice: on any network, HTTP or parse error it falls back
/// to the last good copy on disk, and to an empty catalogue if there is none.
/// The frontend then simply carries on with the bundled patch.
#[tauri::command]
pub async fn fetch_patch_index(app: tauri::AppHandle) -> Result<serde_json::Value, String> {
    let cache_path = user_data_dir(&app)?.join("patch_index_cache.json");

    // Release asset URLs are stable across re-uploads and CDN-fronted, so
    // without a cache-buster a user can launch into a stale catalogue and miss
    // a patch published minutes ago.
    let nonce = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    let url = format!("{}?t={}", PATCH_INDEX_URL, nonce);

    let fetched = async {
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(INDEX_TIMEOUT_SECS))
            .user_agent(user_agent())
            .build()
            .map_err(|e| format!("Failed to build HTTP client: {}", e))?;

        let res = client
            .get(&url)
            .header("Cache-Control", "no-cache")
            .send()
            .await
            .map_err(|e| format!("Request failed: {}", e))?;

        if !res.status().is_success() {
            return Err(format!("Patch index returned HTTP {}", res.status()));
        }

        let body = res
            .text()
            .await
            .map_err(|e| format!("Failed to read patch index body: {}", e))?;

        let parsed: serde_json::Value = serde_json::from_str(&body)
            .map_err(|e| format!("Failed to parse patch index: {}", e))?;

        Ok::<(String, serde_json::Value), String>((body, parsed))
    }
    .await;

    match fetched {
        Ok((body, parsed)) => {
            if let Err(e) = std::fs::write(&cache_path, &body) {
                emit_log(
                    &app,
                    "main",
                    &format!("Could not cache the patch index locally: {}", e),
                    "warning",
                );
            }
            Ok(build_result(parsed, "remote"))
        }
        Err(err) => {
            emit_log(
                &app,
                "main",
                &format!("Could not fetch the remote patch index ({}). Falling back to the local cache.", err),
                "warning",
            );

            match std::fs::read_to_string(&cache_path)
                .ok()
                .and_then(|s| serde_json::from_str::<serde_json::Value>(&s).ok())
            {
                Some(parsed) => Ok(build_result(parsed, "cache")),
                None => Ok(serde_json::json!({
                    "entries": [],
                    "updated": serde_json::Value::Null,
                    "source": "none",
                })),
            }
        }
    }
}

fn build_result(parsed: serde_json::Value, source: &str) -> serde_json::Value {
    serde_json::json!({
        "entries": parsed.get("entries").cloned().unwrap_or(serde_json::json!([])),
        "updated": parsed.get("updated").cloned().unwrap_or(serde_json::Value::Null),
        "source": source,
    })
}

/// Ensures one patch variant is present in the local cache, downloading and
/// verifying it if needed. Returns an absolute path.
///
/// run_xdelta_patch only resolves a patch path through resolve_asset_path when
/// it is relative, so an absolute cache path flows straight through unchanged.
#[tauri::command]
pub async fn ensure_patch_downloaded(
    app: tauri::AppHandle,
    slug: String,
    variant: String,
    url: String,
    sha256: String,
    size: u64,
) -> Result<String, String> {
    if slug.is_empty() || slug.contains(['/', '\\', ':']) || slug.starts_with('.') {
        return Err(format!("Refusing to use an unsafe patch id: {}", slug));
    }
    if variant != "encrypted" && variant != "decrypted" {
        return Err(format!("Unknown patch variant: {}", variant));
    }

    let dir = cache_root(&app)?.join(&slug);
    std::fs::create_dir_all(&dir)
        .map_err(|e| format!("Failed to create the patch cache directory: {}", e))?;

    let final_path = dir.join(format!("{}.vcdiff", variant));
    let meta_path = dir.join(format!("{}.vcdiff.meta.json", variant));
    let part_path = dir.join(format!("{}.vcdiff.part", variant));

    if final_path.exists() {
        match verify_cached(&final_path, &meta_path, &sha256, size) {
            Ok(true) => {
                emit_log(
                    &app,
                    "main",
                    &format!("Using the cached {} patch for {}.", variant, slug),
                    "info",
                );
                return Ok(final_path.to_string_lossy().to_string());
            }
            Ok(false) => {
                emit_log(
                    &app,
                    "main",
                    &format!("Cached {} patch for {} failed verification. Re-downloading.", variant, slug),
                    "warning",
                );
                let _ = std::fs::remove_file(&final_path);
                let _ = std::fs::remove_file(&meta_path);
            }
            Err(e) => {
                emit_log(&app, "main", &format!("Could not verify the cached patch ({}). Re-downloading.", e), "warning");
                let _ = std::fs::remove_file(&final_path);
                let _ = std::fs::remove_file(&meta_path);
            }
        }
    }

    download_verified(&app, &slug, &variant, &url, &sha256, size, &part_path, &final_path, &meta_path).await?;
    Ok(final_path.to_string_lossy().to_string())
}

/// A matching sidecar plus a matching size is accepted without re-hashing, so
/// the common case does not re-read 24 MB on every run. A missing or stale
/// sidecar forces one full hash before the file is trusted.
fn verify_cached(file: &Path, meta: &Path, want_sha: &str, want_size: u64) -> Result<bool, String> {
    let actual_size = std::fs::metadata(file)
        .map_err(|e| format!("Failed to stat the cached patch: {}", e))?
        .len();
    if want_size > 0 && actual_size != want_size {
        return Ok(false);
    }

    if let Ok(raw) = std::fs::read_to_string(meta) {
        if let Ok(v) = serde_json::from_str::<serde_json::Value>(&raw) {
            let sha_ok = v.get("sha256").and_then(|s| s.as_str()) == Some(want_sha);
            let size_ok = v.get("size").and_then(|s| s.as_u64()) == Some(actual_size);
            if sha_ok && size_ok {
                return Ok(true);
            }
        }
    }

    Ok(sha256_file(file)?.eq_ignore_ascii_case(want_sha))
}

#[allow(clippy::too_many_arguments)]
async fn download_verified(
    app: &tauri::AppHandle,
    slug: &str,
    variant: &str,
    url: &str,
    want_sha: &str,
    want_size: u64,
    part_path: &Path,
    final_path: &Path,
    meta_path: &Path,
) -> Result<(), String> {
    use futures_util::StreamExt;
    use std::io::Write;

    emit_log(
        app,
        "main",
        &format!("Downloading the {} patch for {} ({:.1} MB)...", variant, slug, want_size as f64 / 1_048_576.0),
        "info",
    );

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(DOWNLOAD_TIMEOUT_SECS))
        .user_agent(user_agent())
        .build()
        .map_err(|e| format!("Failed to build HTTP client: {}", e))?;

    let res = client
        .get(url)
        .send()
        .await
        .map_err(|e| format!("Patch download failed: {}", e))?;

    if !res.status().is_success() {
        return Err(format!("Patch download returned HTTP {}", res.status()));
    }

    let total = res.content_length().unwrap_or(want_size);
    let _ = std::fs::remove_file(part_path);
    let mut file = std::fs::File::create(part_path)
        .map_err(|e| format!("Failed to create the download file: {}", e))?;

    let mut downloaded: u64 = 0;
    let mut last_emit = std::time::Instant::now();
    let mut stream = res.bytes_stream();

    while let Some(chunk) = stream.next().await {
        let chunk = chunk.map_err(|e| format!("Patch download interrupted: {}", e))?;
        file.write_all(&chunk)
            .map_err(|e| format!("Failed to write the downloaded patch: {}", e))?;
        downloaded += chunk.len() as u64;

        if last_emit.elapsed().as_millis() >= PROGRESS_INTERVAL_MS {
            emit_progress(app, slug, variant, downloaded, total);
            last_emit = std::time::Instant::now();
        }
    }

    file.flush()
        .map_err(|e| format!("Failed to flush the downloaded patch: {}", e))?;
    drop(file);
    emit_progress(app, slug, variant, downloaded, total);

    // Verify before the file is ever visible under its final name, so a
    // corrupt download can never be picked up as a valid cache entry.
    let actual_sha = sha256_file(part_path)?;
    if !actual_sha.eq_ignore_ascii_case(want_sha) {
        let _ = std::fs::remove_file(part_path);
        return Err(format!(
            "Downloaded patch failed its integrity check (expected {}, got {}). The file was discarded.",
            want_sha, actual_sha
        ));
    }
    if want_size > 0 && downloaded != want_size {
        let _ = std::fs::remove_file(part_path);
        return Err(format!(
            "Downloaded patch has the wrong size (expected {} bytes, got {}).",
            want_size, downloaded
        ));
    }

    let _ = std::fs::remove_file(final_path);
    std::fs::rename(part_path, final_path)
        .map_err(|e| format!("Failed to finalise the downloaded patch: {}", e))?;

    let meta = serde_json::json!({ "sha256": actual_sha, "size": downloaded });
    if let Err(e) = std::fs::write(meta_path, serde_json::to_string_pretty(&meta).unwrap_or_default()) {
        emit_log(app, "main", &format!("Could not write the patch cache sidecar: {}", e), "warning");
    }

    emit_log(
        app,
        "main",
        &format!("Patch downloaded and verified: {} ({}).", slug, variant),
        "success",
    );
    Ok(())
}

fn emit_progress(app: &tauri::AppHandle, slug: &str, variant: &str, done: u64, total: u64) {
    let _ = app.emit(
        "patch-download-progress",
        DownloadProgress {
            slug: slug.to_string(),
            variant: variant.to_string(),
            bytes_downloaded: done,
            total_bytes: total,
        },
    );
}

// ---------------------------------------------------------------------------
// Publishing a freshly created patch to the patch library.
//
// The Patch Creator already writes exactly the folder shape the library
// consumes (encrypted.vcdiff, decrypted.vcdiff, patch_config.json), so
// publishing is a copy plus a commit. Git is used rather than the GitHub API
// deliberately: this is maintainer-only tooling behind Advanced Mode, and the
// maintainer already has git credentials configured, so no token needs to be
// stored in the app.
// ---------------------------------------------------------------------------

/// Marker the frontend looks for to offer a "republish and overwrite?" prompt
/// instead of showing a raw error.
pub const ALREADY_EXISTS: &str = "ALREADY_EXISTS";

const PATCH_FILES: [&str; 3] = ["patch_config.json", "encrypted.vcdiff", "decrypted.vcdiff"];

/// Runs one command in `dir`, echoing what it did to the Patch Creator log.
/// Shared by `run_git` and `run_gh` - both are "shell out, log output" in the
/// exact same shape.
fn run_cmd(app: &tauri::AppHandle, program: &str, dir: &Path, args: &[&str]) -> Result<String, String> {
    let mut cmd = std::process::Command::new(program);
    cmd.current_dir(dir).args(args);

    // * CREATE_NO_WINDOW, same as the xdelta invocation: no console flash.
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x08000000);
    }

    let out = cmd.output().map_err(|e| {
        format!("Could not run {} (is it installed and on PATH?): {}", program, e)
    })?;

    let stdout = String::from_utf8_lossy(&out.stdout).trim().to_string();
    let stderr = String::from_utf8_lossy(&out.stderr).trim().to_string();

    if !stdout.is_empty() {
        emit_log(app, "genpatch-logs", &format!("  {}: {}", program, stdout), "info");
    }
    // ! git and gh both write ordinary progress to stderr, so this is not
    // ! necessarily an error.
    if !stderr.is_empty() {
        emit_log(app, "genpatch-logs", &format!("  {}: {}", program, stderr), "info");
    }

    if !out.status.success() {
        return Err(format!(
            "{} {} failed: {}",
            program,
            args.join(" "),
            if stderr.is_empty() { stdout } else { stderr }
        ));
    }
    Ok(stdout)
}

fn run_git(app: &tauri::AppHandle, dir: &Path, args: &[&str]) -> Result<String, String> {
    run_cmd(app, "git", dir, args)
}

/// Requires the GitHub CLI, already assumed available for maintainer-only
/// tooling: it is what actually opens the pull request, since plain git has
/// no concept of one.
fn run_gh(app: &tauri::AppHandle, dir: &Path, args: &[&str]) -> Result<String, String> {
    run_cmd(app, "gh", dir, args)
}

/// Turns a patch folder name into a safe git branch name fragment.
fn slugify(input: &str) -> String {
    let mut out = String::new();
    let mut last_dash = false;
    for c in input.chars() {
        if c.is_ascii_alphanumeric() {
            out.push(c.to_ascii_lowercase());
            last_dash = false;
        } else if !last_dash {
            out.push('-');
            last_dash = true;
        }
    }
    out.trim_matches('-').to_string()
}

/// Recursive directory copy. std has no equivalent, and the payloads are large
/// enough that streaming a file at a time matters.
fn copy_dir_all(src: &Path, dst: &Path) -> std::io::Result<()> {
    std::fs::create_dir_all(dst)?;
    for entry in std::fs::read_dir(src)? {
        let entry = entry?;
        let from = entry.path();
        let to = dst.join(entry.file_name());
        if entry.file_type()?.is_dir() {
            copy_dir_all(&from, &to)?;
        } else {
            std::fs::copy(&from, &to)?;
        }
    }
    Ok(())
}

/// Copies a created patch folder into the patch library repo and opens a
/// pull request for it, returning the PR URL.
///
/// A PR rather than a direct push so a publish can be reviewed (and CI can
/// run) before it reaches every installed patcher. CI in that repo hashes the
/// payloads, uploads them and regenerates the catalogue once the PR is
/// merged. Nothing here touches the patcher's own release flow.
///
/// Refuses rather than guessing when anything looks off: a directory that is
/// not a git work tree, a library with no `Patches/`, a source folder missing
/// one of its three files, an entry that already exists (unless `overwrite`),
/// a work tree with any uncommitted changes at all (a fresh branch must start
/// clean), or a local clone that cannot fast-forward to `origin`.
#[tauri::command]
pub async fn publish_patch_to_library(
    app: tauri::AppHandle,
    library_dir: String,
    patch_folder: String,
    creator: String,
    title: String,
    description: String,
    overwrite: bool,
) -> Result<String, String> {
    let lib = Path::new(&library_dir);
    let src = Path::new(&patch_folder);

    if !lib.is_dir() {
        return Err(format!("Patch library folder does not exist: {}", library_dir));
    }
    if !src.is_dir() {
        return Err(format!("Patch folder does not exist: {}", patch_folder));
    }

    // ! Never create a repo implicitly - an accidental path must fail loudly.
    let inside = run_git(&app, lib, &["rev-parse", "--is-inside-work-tree"])?;
    if inside.trim() != "true" {
        return Err(format!("{} is not a git repository.", library_dir));
    }

    let patches_dir = lib.join("Patches");
    if !patches_dir.is_dir() {
        return Err(format!(
            "{} has no Patches folder, so it does not look like the patch library.",
            library_dir
        ));
    }

    for f in PATCH_FILES {
        if !src.join(f).exists() {
            return Err(format!("Patch folder is missing {}.", f));
        }
    }

    let name = src
        .file_name()
        .ok_or_else(|| "Could not read the patch folder name.".to_string())?
        .to_string_lossy()
        .to_string();
    let rel = format!("Patches/{}", name);
    let dest = patches_dir.join(&name);

    if dest.exists() && !overwrite {
        return Err(format!("{}: \"{}\" is already published.", ALREADY_EXISTS, name));
    }

    let base_branch = run_git(&app, lib, &["rev-parse", "--abbrev-ref", "HEAD"])?
        .trim()
        .to_string();
    if base_branch.is_empty() || base_branch == "HEAD" {
        return Err(
            "The patch library repo is on a detached HEAD. Check out its default branch first."
                .to_string(),
        );
    }

    // ! A fresh publish branch must start clean - anything already sitting in
    // ! the work tree means the user has unrelated work in progress there.
    let status = run_git(&app, lib, &["status", "--porcelain"])?;
    if !status.trim().is_empty() {
        return Err(format!(
            "The patch library has uncommitted changes, so publishing was stopped:\n{}\n\nCommit or discard them first.",
            status.trim()
        ));
    }

    emit_log(&app, "genpatch-logs", &format!("Updating {}...", base_branch), "info");
    run_git(&app, lib, &["fetch", "origin", &base_branch])
        .map_err(|e| format!("Could not fetch the latest {}: {}", base_branch, e))?;
    run_git(&app, lib, &["pull", "--ff-only", "origin", &base_branch]).map_err(|e| {
        format!(
            "Could not fast-forward {} to origin (resolve this manually first): {}",
            base_branch, e
        )
    })?;

    let title = if title.trim().is_empty() {
        format!("Publish {}", name)
    } else {
        title.trim().to_string()
    };
    let creator = if creator.trim().is_empty() {
        "unknown".to_string()
    } else {
        creator.trim().to_string()
    };
    let body = if description.trim().is_empty() {
        format!("Submitted by: {}", creator)
    } else {
        format!("{}\n\n---\nSubmitted by: {}", description.trim(), creator)
    };

    let branch = format!(
        "publish/{}-{}",
        slugify(&name),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0)
    );

    emit_log(
        &app,
        "genpatch-logs",
        &format!("Publishing \"{}\" to the patch library on branch {}...", name, branch),
        "info",
    );

    // From here on, anything that fails must leave the repo back on the
    // branch the maintainer started on rather than stranded mid-publish.
    let result = (|| -> Result<String, String> {
        run_git(&app, lib, &["checkout", "-b", &branch])?;

        if dest.exists() {
            emit_log(&app, "genpatch-logs", "  Replacing the existing entry...", "warning");
            std::fs::remove_dir_all(&dest)
                .map_err(|e| format!("Could not replace the existing entry: {}", e))?;
        }

        copy_dir_all(src, &dest)
            .map_err(|e| format!("Could not copy the patch into the library: {}", e))?;
        emit_log(&app, "genpatch-logs", &format!("  Copied into {}", rel), "info");

        run_git(&app, lib, &["add", "--", &rel])?;
        run_git(&app, lib, &["commit", "-m", &title, "-m", &body])?;
        run_git(&app, lib, &["push", "-u", "origin", &branch])?;

        emit_log(&app, "genpatch-logs", "  Opening the pull request...", "info");
        let pr_output = run_gh(
            &app,
            lib,
            &[
                "pr",
                "create",
                "--base",
                &base_branch,
                "--head",
                &branch,
                "--title",
                &title,
                "--body",
                &body,
            ],
        )?;
        // `gh pr create` prints the PR URL as the last line of stdout.
        Ok(pr_output.lines().last().unwrap_or(&pr_output).trim().to_string())
    })();

    let _ = run_git(&app, lib, &["checkout", &base_branch]);
    if result.is_err() {
        // The branch either never got pushed or is now an abandoned attempt;
        // either way, leaving it lying around only invites confusion.
        let _ = run_git(&app, lib, &["branch", "-D", &branch]);
    }

    let pr_url = result?;

    emit_log(
        &app,
        "genpatch-logs",
        &format!(
            "Pull request opened: {}. Once merged, the patch library's CI hashes, uploads and rebuilds the catalogue, and every installed patcher offers it without an update.",
            pr_url
        ),
        "success",
    );

    Ok(pr_url)
}

/// One downloaded patch in the local cache.
#[derive(Serialize)]
pub struct CachedPatch {
    pub slug: String,
    pub variants: Vec<String>,
    pub size: u64,
}

fn dir_size(path: &Path) -> u64 {
    let mut total = 0;
    if let Ok(entries) = std::fs::read_dir(path) {
        for entry in entries.flatten() {
            match entry.metadata() {
                Ok(m) if m.is_file() => total += m.len(),
                Ok(m) if m.is_dir() => total += dir_size(&entry.path()),
                _ => {}
            }
        }
    }
    total
}

/// Lists the patches currently downloaded to this user's cache, so the UI can
/// show what is available offline and offer to remove individual entries.
#[tauri::command]
pub async fn list_cached_patches(app: tauri::AppHandle) -> Result<Vec<CachedPatch>, String> {
    let root = cache_root(&app)?;
    if !root.exists() {
        return Ok(Vec::new());
    }

    let mut out = Vec::new();
    for entry in std::fs::read_dir(&root)
        .map_err(|e| format!("Failed to read the patch cache: {}", e))?
        .flatten()
    {
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }

        let mut variants = Vec::new();
        for variant in ["encrypted", "decrypted"] {
            if path.join(format!("{}.vcdiff", variant)).exists() {
                variants.push(variant.to_string());
            }
        }
        if variants.is_empty() {
            continue;
        }

        out.push(CachedPatch {
            slug: entry.file_name().to_string_lossy().to_string(),
            variants,
            size: dir_size(&path),
        });
    }

    out.sort_by(|a, b| a.slug.cmp(&b.slug));
    Ok(out)
}

/// Removes one downloaded patch from the cache. Returns the bytes freed.
#[tauri::command]
pub async fn delete_cached_patch(app: tauri::AppHandle, slug: String) -> Result<u64, String> {
    if slug.is_empty() || slug.contains(['/', '\\', ':']) || slug.starts_with('.') {
        return Err(format!("Refusing to delete an unsafe patch id: {}", slug));
    }

    let dir = cache_root(&app)?.join(&slug);
    if !dir.is_dir() {
        return Ok(0);
    }

    let freed = dir_size(&dir);
    std::fs::remove_dir_all(&dir)
        .map_err(|e| format!("Failed to remove the downloaded patch {}: {}", slug, e))?;
    emit_log(
        &app,
        "main",
        &format!("Removed the downloaded patch {} ({:.1} MB freed).", slug, freed as f64 / 1_048_576.0),
        "info",
    );
    Ok(freed)
}

/// Removes every downloaded patch. Returns (entries removed, bytes freed).
/// Bundled patches live in the install directory and are never touched.
#[tauri::command]
pub async fn clear_patch_cache(app: tauri::AppHandle) -> Result<(u32, u64), String> {
    let root = cache_root(&app)?;
    if !root.exists() {
        return Ok((0, 0));
    }

    let mut removed = 0u32;
    let mut freed = 0u64;
    for entry in std::fs::read_dir(&root)
        .map_err(|e| format!("Failed to read the patch cache: {}", e))?
        .flatten()
    {
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }
        let size = dir_size(&path);
        match std::fs::remove_dir_all(&path) {
            Ok(()) => {
                removed += 1;
                freed += size;
            }
            Err(e) => emit_log(
                &app,
                "main",
                &format!("Could not remove {}: {}", entry.file_name().to_string_lossy(), e),
                "warning",
            ),
        }
    }

    emit_log(
        &app,
        "main",
        &format!("Removed {} downloaded patch(es), freeing {:.1} MB.", removed, freed as f64 / 1_048_576.0),
        "success",
    );
    Ok((removed, freed))
}

/// Removes every cached patch except `keep_slug`. Called after a successful
/// patch run when the user has the cleanup setting enabled.
#[tauri::command]
pub async fn prune_patch_cache(app: tauri::AppHandle, keep_slug: String) -> Result<u32, String> {
    let root = cache_root(&app)?;
    if !root.exists() {
        return Ok(0);
    }

    let mut removed = 0u32;
    for entry in std::fs::read_dir(&root)
        .map_err(|e| format!("Failed to read the patch cache: {}", e))?
        .flatten()
    {
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }
        let name = entry.file_name().to_string_lossy().to_string();
        if name == keep_slug {
            continue;
        }
        match std::fs::remove_dir_all(&path) {
            Ok(()) => {
                removed += 1;
                emit_log(&app, "main", &format!("Removed the cached patch {}.", name), "info");
            }
            Err(e) => emit_log(
                &app,
                "main",
                &format!("Could not remove the cached patch {}: {}", name, e),
                "warning",
            ),
        }
    }

    Ok(removed)
}
