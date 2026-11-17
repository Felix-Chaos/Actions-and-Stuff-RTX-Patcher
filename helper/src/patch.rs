//! The Patch Library catalogue, downloading a patch and applying it with the
//! bundled xdelta3 (the same build the desktop patcher ships).

use std::io::Read;
use std::path::{Path, PathBuf};

/// Same source as the Web Patcher (raw main), so entries published only for the
/// web are included. `ASRTX_LIBRARY` overrides it for local tests; the website
/// can never choose where the helper downloads from.
fn library() -> String {
    std::env::var("ASRTX_LIBRARY")
        .ok()
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "https://raw.githubusercontent.com/Felix-Chaos/AS-RTX-Patch-Library/main".into())
        .trim_end_matches('/')
        .to_string()
}

static XDELTA: &[u8] = include_bytes!("../../src-tauri/assets/xdelta3/exec/xdelta3_x86_64_win.exe");

#[derive(Clone, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Entry {
    pub slug: String,
    // The catalogue mixes styles: folder_name is snake_case, the rest camelCase.
    #[serde(rename = "folder_name")]
    pub folder_name: String,
    pub pack_version: String,
    pub patch_version: Option<String>,
    pub patches: Patches,
}

#[derive(Clone, serde::Deserialize)]
pub struct Patches {
    pub encrypted: Option<Asset>,
}

#[derive(Clone, serde::Deserialize)]
pub struct Asset {
    pub sha256: Option<String>,
    pub size: Option<u64>,
}

#[derive(serde::Deserialize)]
struct Index {
    entries: Vec<Entry>,
}

fn agent() -> ureq::Agent {
    ureq::AgentBuilder::new()
        .timeout_connect(std::time::Duration::from_secs(20))
        .timeout_read(std::time::Duration::from_secs(60))
        .user_agent(concat!("asrtx-helper/", env!("CARGO_PKG_VERSION")))
        .build()
}

/// Looks up a catalogue entry by slug.
pub fn find_entry(slug: &str) -> Result<Entry, String> {
    let url = format!("{}/patch_index.json", library());
    let text = agent()
        .get(&url)
        .call()
        .map_err(|e| format!("Could not load the patch list: {e}"))?
        .into_string()
        .map_err(|e| format!("Could not load the patch list: {e}"))?;
    let index: Index = serde_json::from_str(&text).map_err(|e| format!("The patch list is broken: {e}"))?;
    index
        .entries
        .into_iter()
        .find(|e| e.slug == slug)
        .ok_or_else(|| format!("Patch \"{slug}\" is not in the patch list."))
}

/// Percent-encodes one URL path segment.
fn encode_segment(s: &str) -> String {
    let mut out = String::new();
    for b in s.bytes() {
        if b.is_ascii_alphanumeric() || b"-._~".contains(&b) {
            out.push(b as char);
        } else {
            out.push_str(&format!("%{:02X}", b));
        }
    }
    out
}

/// Downloads the entry's encrypted.vcdiff to `dest`, checking size and SHA-256.
pub fn download(entry: &Entry, dest: &Path, mut progress: impl FnMut(u64, u64)) -> Result<(), String> {
    let asset = entry.patches.encrypted.as_ref().ok_or("This patch has no Marketplace (encrypted) version.")?;
    let folder = entry.folder_name.split('/').map(encode_segment).collect::<Vec<_>>().join("/");
    let url = format!("{}/Patches/{}/encrypted.vcdiff", library(), folder);
    let resp = agent().get(&url).call().map_err(|e| format!("Patch download failed: {e}"))?;
    let total = resp.header("content-length").and_then(|v| v.parse().ok()).or(asset.size).unwrap_or(0);

    let mut reader = resp.into_reader();
    let mut bytes = Vec::with_capacity(total as usize);
    let mut buf = vec![0u8; 1 << 16];
    loop {
        let n = reader.read(&mut buf).map_err(|e| format!("Patch download failed: {e}"))?;
        if n == 0 {
            break;
        }
        bytes.extend_from_slice(&buf[..n]);
        progress(bytes.len() as u64, total.max(bytes.len() as u64));
    }
    if let Some(size) = asset.size {
        if bytes.len() as u64 != size {
            return Err(format!("Patch download is incomplete ({} of {} bytes)", bytes.len(), size));
        }
    }
    if let Some(want) = &asset.sha256 {
        if crate::pack::sha256_hex(&bytes) != want.to_ascii_lowercase() {
            return Err("Patch download is corrupted (SHA-256 mismatch)".into());
        }
    }
    std::fs::write(dest, &bytes).map_err(|e| format!("Could not save the patch: {e}"))
}

/// Writes the bundled xdelta3 into `dir` (once) and returns its path.
fn xdelta_exe(dir: &Path) -> Result<PathBuf, String> {
    let path = dir.join(format!("xdelta3-{}.exe", &crate::pack::sha256_hex(XDELTA)[..12]));
    if !path.exists() {
        std::fs::write(&path, XDELTA).map_err(|e| format!("Could not prepare xdelta3: {e}"))?;
    }
    Ok(path)
}

/// `xdelta3 -d -s source patch output`, exactly as run_xdelta_patch does it.
pub fn apply(tools_dir: &Path, source: &Path, patch: &Path, output: &Path) -> Result<(), String> {
    let exe = xdelta_exe(tools_dir)?;
    let mut cmd = std::process::Command::new(exe);
    cmd.arg("-f").arg("-d").arg("-s").arg(source).arg(patch).arg(output);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000);
    }
    let out = cmd.output().map_err(|e| format!("Could not run xdelta3: {e}"))?;
    if out.status.success() {
        Ok(())
    } else {
        let err = String::from_utf8_lossy(&out.stderr);
        Err(if err.contains("checksum") || err.contains("source") {
            format!("The patch does not fit your A&S copy (is it fully downloaded and unmodified?). xdelta3: {}", err.trim())
        } else {
            format!("Applying the patch failed: {}", err.trim())
        })
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn encodes_folder_names() {
        assert_eq!(super::encode_segment("Actions & Stuff for RTX 1.13 V0.1"), "Actions%20%26%20Stuff%20for%20RTX%201.13%20V0.1");
    }
}
