//! A&S RTX Helper.
//!
//! Started by the Web Patcher through an `asrtx://start?s=<session>` link. It
//! finds the user's own Actions & Stuff in the Marketplace cache, downloads
//! the RTX patch the page picked from the Patch Library, applies it and
//! extracts the result straight into Minecraft's resource_packs. No .mcpack or
//! zip that could be passed on is ever left behind. The page follows along
//! through a small HTTP API on 127.0.0.1 (see `server`).
//!
//! Run without arguments (double-click after downloading) it installs itself
//! to %LOCALAPPDATA%\ASRTX and registers the asrtx:// link for the current
//! user; `--uninstall` undoes that.

#![cfg_attr(not(test), windows_subsystem = "windows")]

mod pack;
mod patch;
mod server;

fn main() {
    let arg = std::env::args().nth(1).unwrap_or_default();
    if arg.to_ascii_lowercase().starts_with("asrtx:") {
        match session_from_link(&arg) {
            Some(s) => server::run(s),
            None => message("A&S RTX Helper", "This link is not valid. Start again from the Web Patcher.", true),
        }
    } else if arg == "--uninstall" {
        match setup::uninstall() {
            Ok(()) => message("A&S RTX Helper", "The helper was removed.", false),
            Err(e) => message("A&S RTX Helper", &format!("Removing the helper failed: {e}"), true),
        }
    } else {
        match setup::install() {
            Ok(()) => message(
                "A&S RTX Helper",
                "The helper is ready.\n\nGo back to the Web Patcher in your browser and click \"Find my Actions & Stuff\". \
                 When the browser asks whether to open the A&S RTX Helper, allow it.",
                false,
            ),
            Err(e) => message("A&S RTX Helper", &format!("Setting up the helper failed: {e}"), true),
        }
    }
}

/// `asrtx://start?s=<session>` -> session, if it looks like one the page made.
fn session_from_link(link: &str) -> Option<String> {
    let query = link.split_once('?')?.1;
    let s = query.split('&').find_map(|kv| kv.strip_prefix("s="))?;
    (s.len() >= 16 && s.len() <= 64 && s.bytes().all(|b| b.is_ascii_alphanumeric())).then(|| s.to_string())
}

pub fn message(title: &str, text: &str, error: bool) {
    #[cfg(windows)]
    {
        use windows_sys::Win32::UI::WindowsAndMessaging::{MessageBoxW, MB_ICONERROR, MB_ICONINFORMATION, MB_OK};
        let w = |s: &str| s.encode_utf16().chain(std::iter::once(0)).collect::<Vec<u16>>();
        let (t, m) = (w(title), w(text));
        unsafe {
            MessageBoxW(std::ptr::null_mut(), m.as_ptr(), t.as_ptr(), MB_OK | if error { MB_ICONERROR } else { MB_ICONINFORMATION });
        }
    }
    #[cfg(not(windows))]
    eprintln!("{title}: {text} (error: {error})");
}

#[cfg(windows)]
mod setup {
    use std::path::PathBuf;
    use winreg::enums::HKEY_CURRENT_USER;
    use winreg::RegKey;

    fn install_dir() -> Result<PathBuf, String> {
        let lad = std::env::var("LOCALAPPDATA").map_err(|_| "LOCALAPPDATA is not set")?;
        Ok(PathBuf::from(lad).join("ASRTX"))
    }

    /// Copies the exe to %LOCALAPPDATA%\ASRTX (so deleting the download does not
    /// break the link) and registers asrtx:// under HKCU, like BetterRTX's brtx://.
    pub fn install() -> Result<(), String> {
        let dir = install_dir()?;
        std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
        let target = dir.join("asrtx-helper.exe");
        let me = std::env::current_exe().map_err(|e| e.to_string())?;
        let same = std::fs::canonicalize(&me).ok() == std::fs::canonicalize(&target).ok();
        if !same {
            std::fs::copy(&me, &target).map_err(|e| format!("could not copy the helper to {target:?}: {e}"))?;
        }
        let classes = RegKey::predef(HKEY_CURRENT_USER).open_subkey_with_flags("Software\\Classes", winreg::enums::KEY_ALL_ACCESS).map_err(|e| e.to_string())?;
        let (key, _) = classes.create_subkey("asrtx").map_err(|e| e.to_string())?;
        key.set_value("", &"URL:A&S RTX Helper").map_err(|e| e.to_string())?;
        key.set_value("URL Protocol", &"").map_err(|e| e.to_string())?;
        let (icon, _) = key.create_subkey("DefaultIcon").map_err(|e| e.to_string())?;
        icon.set_value("", &format!("\"{}\",0", target.display())).map_err(|e| e.to_string())?;
        let (cmd, _) = key.create_subkey("shell\\open\\command").map_err(|e| e.to_string())?;
        cmd.set_value("", &format!("\"{}\" \"%1\"", target.display())).map_err(|e| e.to_string())?;
        Ok(())
    }

    pub fn uninstall() -> Result<(), String> {
        let classes = RegKey::predef(HKEY_CURRENT_USER).open_subkey_with_flags("Software\\Classes", winreg::enums::KEY_ALL_ACCESS).map_err(|e| e.to_string())?;
        let _ = classes.delete_subkey_all("asrtx");
        let dir = install_dir()?;
        let me = std::env::current_exe().ok().and_then(|p| std::fs::canonicalize(p).ok());
        let target = std::fs::canonicalize(dir.join("asrtx-helper.exe")).ok();
        if me.is_some() && me == target {
            // A running exe cannot delete itself; leave it, it is inert without the link.
            return Ok(());
        }
        let _ = std::fs::remove_dir_all(dir);
        Ok(())
    }
}

#[cfg(not(windows))]
mod setup {
    pub fn install() -> Result<(), String> {
        Err("the helper only works on Windows".into())
    }
    pub fn uninstall() -> Result<(), String> {
        Err("the helper only works on Windows".into())
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn parses_session_links() {
        assert_eq!(super::session_from_link("asrtx://start?s=abcdef0123456789abcd").as_deref(), Some("abcdef0123456789abcd"));
        assert_eq!(super::session_from_link("asrtx://start/?x=1&s=abcdef0123456789abcd").as_deref(), Some("abcdef0123456789abcd"));
        assert!(super::session_from_link("asrtx://start?s=short").is_none());
        assert!(super::session_from_link("asrtx://start?s=abcdef0123456789abcd%22").is_none());
        assert!(super::session_from_link("asrtx://start").is_none());
    }
}
