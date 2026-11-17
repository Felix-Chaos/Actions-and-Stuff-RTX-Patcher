//! Finding Actions & Stuff in the Marketplace cache, the deterministic patch
//! source zip, and extracting the patched result into Minecraft.
//!
//! Ported from the desktop patcher (src-tauri/src/utils.rs, commands.rs,
//! packguard.rs) so the helper builds on its own. The zip format must stay
//! byte-identical to `utils::write_stored_zip`: every published patch is an
//! xdelta diff against exactly that archive.

use sha2::{Digest, Sha256};
use std::io::Write;
use std::path::{Path, PathBuf};

pub const AS_MODULE_UUID: &str = "22ed17a6-ea7c-5ccd-93b4-b90e86ce0046";

/// Every premium_cache resource_packs folder Minecraft may use (GDK, Preview, UWP).
pub fn premium_resource_pack_dirs() -> Vec<PathBuf> {
    let mut dirs = Vec::new();
    if let Ok(lad) = std::env::var("LOCALAPPDATA") {
        dirs.push(PathBuf::from(&lad).join(r"Packages\Microsoft.MinecraftUWP_8wekyb3d8bbwe\LocalState\premium_cache\resource_packs"));
        dirs.push(PathBuf::from(&lad).join(r"Packages\Microsoft.MinecraftWindowsBeta_8wekyb3d8bbwe\LocalState\premium_cache\resource_packs"));
    }
    if let Ok(ad) = std::env::var("APPDATA") {
        dirs.push(PathBuf::from(&ad).join(r"Minecraft Bedrock\premium_cache\resource_packs"));
        dirs.push(PathBuf::from(&ad).join(r"Minecraft Bedrock Preview\premium_cache\resource_packs"));
    }
    dirs
}

/// Every com.mojang folder the RTX pack is installed into (same list as
/// `utils::get_install_target_paths`). Only existing ones are returned.
pub fn install_target_dirs() -> Vec<PathBuf> {
    let mut paths = Vec::new();
    if let Ok(lad) = std::env::var("LOCALAPPDATA") {
        let lad = PathBuf::from(lad);
        paths.push(lad.join(r"Packages\Microsoft.MinecraftUWP_8wekyb3d8bbwe\LocalState\games\com.mojang"));
        paths.push(lad.join(r"Packages\Microsoft.MinecraftWindowsBeta_8wekyb3d8bbwe\LocalState\games\com.mojang"));
    }
    if let Ok(ad) = std::env::var("APPDATA") {
        let ad = PathBuf::from(ad);
        paths.push(ad.join(r"Minecraft Bedrock\games\com.mojang"));
        paths.push(ad.join(r"Minecraft Bedrock Preview\games\com.mojang"));
        paths.push(ad.join(r"Minecraft Bedrock\Users\Shared\games\com.mojang"));
    }
    paths.retain(|p| p.exists());
    paths
}

fn is_actions_and_stuff_pack(path: &Path) -> bool {
    for lang_rel in ["texts/en_US.lang", "texts/en_US.txt", "en_US.lang", "en_US.txt"] {
        if let Ok(content) = std::fs::read_to_string(path.join(lang_rel)) {
            if content.lines().any(|l| l.starts_with("pack.name=") && l.contains("Actions & Stuf")) {
                return true;
            }
        }
    }
    std::fs::read_to_string(path.join("manifest.json"))
        .map(|m| m.contains(AS_MODULE_UUID))
        .unwrap_or(false)
}

/// Version from the pack's own name ("pack.name=Actions & Stuff 1.13" -> "1.13"),
/// falling back to the manifest header version.
fn pack_version(path: &Path) -> Option<String> {
    if let Ok(content) = std::fs::read_to_string(path.join("texts").join("en_US.lang")) {
        for line in content.lines().filter(|l| l.starts_with("pack.name=")) {
            if let Some(idx) = line.find("Actions & Stuf") {
                let v: String = line[idx + 14..].chars().filter(|c| c.is_numeric() || *c == '.').collect();
                let v = v.trim_matches('.');
                if !v.is_empty() {
                    return Some(v.to_string());
                }
            }
        }
    }
    let manifest: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(path.join("manifest.json")).ok()?).ok()?;
    match manifest.get("header")?.get("version")? {
        serde_json::Value::String(s) => Some(s.clone()),
        serde_json::Value::Array(a) => Some(a.iter().map(|v| v.to_string()).collect::<Vec<_>>().join(".")),
        _ => None,
    }
}

/// "v1.11.0" and "1.11" name the same pack version.
pub fn normalize_version(v: &str) -> String {
    let v = v.trim().trim_start_matches(['v', 'V']);
    let mut parts: Vec<&str> = v.split('.').collect();
    while parts.len() > 1 && parts.last().is_some_and(|p| p.chars().all(|c| c == '0')) {
        parts.pop();
    }
    parts.join(".")
}

fn folder_stats(dir: &Path) -> (usize, usize) {
    let (mut files, mut dirs) = (0, 0);
    if let Ok(entries) = std::fs::read_dir(dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                dirs += 1;
                let (f, d) = folder_stats(&path);
                files += f;
                dirs += d;
            } else if path.is_file() {
                files += 1;
            }
        }
    }
    (files, dirs)
}

pub fn sha256_hex(bytes: &[u8]) -> String {
    Sha256::digest(bytes).iter().map(|b| format!("{:02x}", b)).collect()
}

#[derive(Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PackInfo {
    pub id: String,
    pub version: Option<String>,
    pub files: usize,
    pub dirs: usize,
    pub logo_hash: Option<String>,
    #[serde(skip)]
    pub path: PathBuf,
}

/// Every Actions & Stuff copy in the Marketplace cache.
pub fn scan_packs() -> Vec<PackInfo> {
    let mut out = Vec::new();
    for base in premium_resource_pack_dirs() {
        let Ok(entries) = std::fs::read_dir(&base) else { continue };
        for entry in entries.flatten() {
            let path = entry.path();
            if !path.is_dir() || !is_actions_and_stuff_pack(&path) {
                continue;
            }
            let (files, dirs) = folder_stats(&path);
            out.push(PackInfo {
                id: out.len().to_string(),
                version: pack_version(&path),
                files,
                dirs,
                logo_hash: std::fs::read(path.join("pack_icon.png")).ok().map(|b| sha256_hex(&b)),
                path,
            });
        }
    }
    out
}

fn collect_files(root: &Path, current: &Path, files: &mut Vec<(PathBuf, String)>) -> std::io::Result<()> {
    if current.is_dir() {
        for entry in std::fs::read_dir(current)? {
            collect_files(root, &entry?.path(), files)?;
        }
    } else if current.is_file() {
        let rel = current.strip_prefix(root).unwrap_or(current).to_string_lossy().replace('\\', "/");
        files.push((current.to_path_buf(), rel));
    }
    Ok(())
}

const ZIP_DOS_TIME: u16 = 0x0000;
const ZIP_DOS_DATE: u16 = 0x0021;

/// Same bytes as `utils::pack_folder_impl` / `write_stored_zip` in the desktop
/// patcher (see the format notes there). `progress(done, total)` per file.
pub fn zip_folder(folder: &Path, output: &Path, mut progress: impl FnMut(usize, usize)) -> Result<(), String> {
    let mut files = Vec::new();
    collect_files(folder, folder, &mut files).map_err(|e| format!("Could not read the pack: {e}"))?;
    files.sort_by(|a, b| a.1.cmp(&b.1));
    if files.len() > 0xffff {
        return Err("Too many files for a non-ZIP64 archive".into());
    }
    let file = std::fs::File::create(output).map_err(|e| format!("Could not create {output:?}: {e}"))?;
    let mut out = std::io::BufWriter::with_capacity(1 << 20, file);
    let mut central: Vec<u8> = Vec::new();
    let mut offset: u64 = 0;
    let total = files.len();
    let werr = |e: std::io::Error| format!("Could not write the zip: {e}");

    for (n, (abs, rel)) in files.iter().enumerate() {
        let data = std::fs::read(abs).map_err(|e| format!("Could not read {abs:?}: {e}"))?;
        let name = rel.as_bytes();
        if data.len() as u64 >= 0xffff_ffff || offset >= 0xffff_ffff || name.len() > 0xffff {
            return Err(format!("{rel} is too large for a non-ZIP64 archive"));
        }
        let crc = crc32fast::hash(&data);
        let size = data.len() as u32;
        let flags: u16 = if name.is_ascii() { 0 } else { 0x0800 };

        let mut lfh = Vec::with_capacity(30 + name.len());
        lfh.extend_from_slice(&0x0403_4b50u32.to_le_bytes());
        lfh.extend_from_slice(&10u16.to_le_bytes());
        lfh.extend_from_slice(&flags.to_le_bytes());
        lfh.extend_from_slice(&0u16.to_le_bytes());
        lfh.extend_from_slice(&ZIP_DOS_TIME.to_le_bytes());
        lfh.extend_from_slice(&ZIP_DOS_DATE.to_le_bytes());
        lfh.extend_from_slice(&crc.to_le_bytes());
        lfh.extend_from_slice(&size.to_le_bytes());
        lfh.extend_from_slice(&size.to_le_bytes());
        lfh.extend_from_slice(&(name.len() as u16).to_le_bytes());
        lfh.extend_from_slice(&0u16.to_le_bytes());
        lfh.extend_from_slice(name);
        out.write_all(&lfh).map_err(werr)?;
        out.write_all(&data).map_err(werr)?;

        central.extend_from_slice(&0x0201_4b50u32.to_le_bytes());
        central.extend_from_slice(&0x030au16.to_le_bytes());
        central.extend_from_slice(&10u16.to_le_bytes());
        central.extend_from_slice(&flags.to_le_bytes());
        central.extend_from_slice(&0u16.to_le_bytes());
        central.extend_from_slice(&ZIP_DOS_TIME.to_le_bytes());
        central.extend_from_slice(&ZIP_DOS_DATE.to_le_bytes());
        central.extend_from_slice(&crc.to_le_bytes());
        central.extend_from_slice(&size.to_le_bytes());
        central.extend_from_slice(&size.to_le_bytes());
        central.extend_from_slice(&(name.len() as u16).to_le_bytes());
        central.extend_from_slice(&[0u8; 8]);
        central.extend_from_slice(&(0o100644u32 << 16).to_le_bytes());
        central.extend_from_slice(&(offset as u32).to_le_bytes());
        central.extend_from_slice(name);

        offset += lfh.len() as u64 + data.len() as u64;
        progress(n + 1, total);
    }
    if offset >= 0xffff_ffff || central.len() as u64 >= 0xffff_ffff {
        return Err("Pack too large for a non-ZIP64 archive".into());
    }
    out.write_all(&central).map_err(werr)?;
    let mut eocd = Vec::with_capacity(22);
    eocd.extend_from_slice(&0x0605_4b50u32.to_le_bytes());
    eocd.extend_from_slice(&[0u8; 4]);
    eocd.extend_from_slice(&(files.len() as u16).to_le_bytes());
    eocd.extend_from_slice(&(files.len() as u16).to_le_bytes());
    eocd.extend_from_slice(&(central.len() as u32).to_le_bytes());
    eocd.extend_from_slice(&(offset as u32).to_le_bytes());
    eocd.extend_from_slice(&0u16.to_le_bytes());
    out.write_all(&eocd).map_err(werr)?;
    out.flush().map_err(werr)
}

fn u16_at(b: &[u8], i: usize) -> usize {
    u16::from_le_bytes([b[i], b[i + 1]]) as usize
}
fn u32_at(b: &[u8], i: usize) -> usize {
    u32::from_le_bytes([b[i], b[i + 1], b[i + 2], b[i + 3]]) as usize
}

/// Entries (name, data range) of an uncompressed zip such as the patch output.
pub fn read_stored_zip(bytes: &[u8]) -> Result<Vec<(String, std::ops::Range<usize>)>, String> {
    let bad = || "The patched pack is not a valid zip".to_string();
    if bytes.len() < 22 {
        return Err(bad());
    }
    let lo = bytes.len().saturating_sub(22 + 0xffff);
    let eocd = (lo..=bytes.len() - 22).rev().find(|&i| u32_at(bytes, i) == 0x0605_4b50).ok_or_else(bad)?;
    let count = u16_at(bytes, eocd + 10);
    let mut p = u32_at(bytes, eocd + 16);
    let mut out = Vec::with_capacity(count);
    for _ in 0..count {
        if p + 46 > bytes.len() || u32_at(bytes, p) != 0x0201_4b50 {
            return Err(bad());
        }
        let method = u16_at(bytes, p + 10);
        let size = u32_at(bytes, p + 20);
        let (nlen, xlen, clen) = (u16_at(bytes, p + 28), u16_at(bytes, p + 30), u16_at(bytes, p + 32));
        let local = u32_at(bytes, p + 42);
        let name = String::from_utf8_lossy(bytes.get(p + 46..p + 46 + nlen).ok_or_else(bad)?).into_owned();
        if method != 0 {
            return Err(format!("Unexpected compressed entry in the patched pack: {name}"));
        }
        if local + 30 > bytes.len() || u32_at(bytes, local) != 0x0403_4b50 {
            return Err(bad());
        }
        let start = local + 30 + u16_at(bytes, local + 26) + u16_at(bytes, local + 28);
        if start + size > bytes.len() {
            return Err(bad());
        }
        out.push((name, start..start + size));
        p += 46 + nlen + xlen + clen;
    }
    Ok(out)
}

/// Rejects zip entry names that would leave the target folder.
fn safe_relative(name: &str) -> Option<PathBuf> {
    let mut p = PathBuf::new();
    for seg in name.split('/').filter(|s| !s.is_empty()) {
        if seg == "." || seg == ".." || seg.contains(['\\', ':', '*', '?', '"', '<', '>', '|']) {
            return None;
        }
        p.push(seg);
    }
    (!p.as_os_str().is_empty()).then_some(p)
}

/// Removes the desktop patcher's write protection (deny ACE for Everyone and
/// read-only attributes) so an old install can be replaced.
fn unlock_path(path: &Path) {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        let _ = std::process::Command::new("icacls")
            .arg(path)
            .args(["/remove:d", "*S-1-1-0", "/C", "/Q"])
            .creation_flags(0x0800_0000)
            .output();
    }
    for entry in walk(path) {
        if let Ok(meta) = std::fs::metadata(&entry) {
            let mut perms = meta.permissions();
            #[allow(clippy::permissions_set_readonly_false)]
            if perms.readonly() {
                perms.set_readonly(false);
                let _ = std::fs::set_permissions(&entry, perms);
            }
        }
    }
}

fn walk(dir: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    if let Ok(entries) = std::fs::read_dir(dir) {
        for e in entries.flatten() {
            let p = e.path();
            if p.is_dir() {
                out.extend(walk(&p));
            } else {
                out.push(p);
            }
        }
    }
    out
}

/// Extracts the patched zip into `<com.mojang>/resource_packs/<folder_name>` of
/// every Minecraft install, replacing an older folder of that name.
/// Returns the folders written.
pub fn install_zip(zip: &Path, folder_name: &str, mut progress: impl FnMut(usize, usize)) -> Result<Vec<PathBuf>, String> {
    let targets = install_target_dirs();
    if targets.is_empty() {
        return Err("No Minecraft installation found (games\\com.mojang). Start Minecraft once and try again.".into());
    }
    let bytes = std::fs::read(zip).map_err(|e| format!("Could not read the patched pack: {e}"))?;
    let entries: Vec<_> = read_stored_zip(&bytes)?.into_iter().filter(|(n, _)| !n.ends_with('/')).collect();
    let total = entries.len() * targets.len();
    let mut done = 0;
    let mut written = Vec::new();

    for mojang in targets {
        let packs = mojang.join("resource_packs");
        std::fs::create_dir_all(&packs).map_err(|e| format!("Could not create {packs:?}: {e}"))?;
        let dest = packs.join(folder_name);
        if dest.exists() {
            unlock_path(&dest);
            std::fs::remove_dir_all(&dest)
                .map_err(|e| format!("Could not replace the old pack in {dest:?} (close Minecraft and try again): {e}"))?;
        }
        for (name, range) in &entries {
            let rel = safe_relative(name).ok_or_else(|| format!("Unsafe path in the patched pack: {name}"))?;
            let path = dest.join(rel);
            if let Some(parent) = path.parent() {
                std::fs::create_dir_all(parent).map_err(|e| format!("Could not create {parent:?}: {e}"))?;
            }
            std::fs::write(&path, &bytes[range.clone()]).map_err(|e| format!("Could not write {path:?}: {e}"))?;
            done += 1;
            if done % 64 == 0 || done == total {
                progress(done, total);
            }
        }
        written.push(dest);
    }
    Ok(written)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_escaping_names() {
        assert!(safe_relative("../evil").is_none());
        assert!(safe_relative("a/../../b").is_none());
        assert!(safe_relative("C:/x").is_none());
        assert_eq!(safe_relative("textures/a.png"), Some(PathBuf::from("textures").join("a.png")));
    }

    #[test]
    fn zip_round_trip() {
        let dir = std::env::temp_dir().join(format!("asrtx-helper-test-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(dir.join("src/sub")).unwrap();
        std::fs::write(dir.join("src/manifest.json"), b"{}").unwrap();
        std::fs::write(dir.join("src/sub/ä.txt"), b"hello").unwrap();
        zip_folder(&dir.join("src"), &dir.join("out.zip"), |_, _| {}).unwrap();
        let bytes = std::fs::read(dir.join("out.zip")).unwrap();
        let entries = read_stored_zip(&bytes).unwrap();
        let names: Vec<_> = entries.iter().map(|(n, _)| n.as_str()).collect();
        assert_eq!(names, ["manifest.json", "sub/ä.txt"]);
        assert_eq!(&bytes[entries[1].1.clone()], b"hello");
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// The source zip of the real A&S 1.13 Marketplace copy must match the one
    /// the published patch was made against (same hash the Web Patcher's
    /// zipstore.js and the desktop app produce). Skipped when the pack is absent.
    #[test]
    fn golden_source_zip_for_as_1_13() {
        let Some(pack) = std::env::var("APPDATA").ok().map(|a| PathBuf::from(a).join(r"Minecraft Bedrock\premium_cache\resource_packs\TxWmFlm2Nvo=")) else { return };
        if !pack.exists() {
            return;
        }
        let out = std::env::temp_dir().join(format!("asrtx-golden-{}.zip", std::process::id()));
        zip_folder(&pack, &out, |_, _| {}).unwrap();
        let hash = sha256_hex(&std::fs::read(&out).unwrap());
        let _ = std::fs::remove_file(&out);
        assert_eq!(hash, "867c56bc11bcbdbdc236bc543ed06502cb3ebcd7c16ef60154f853e11c78c849");
    }
}
