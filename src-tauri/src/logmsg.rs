//! Translatable backend log lines.
//!
//! The frontend shows log lines in the user's language but copies and exports
//! them in English. For that it needs the line's key and variables, not just
//! finished text, so backend log lines are sent as a [`LogMsg`] instead of a
//! formatted string.
//!
//! The English text is read from the frontend's own `dev/en.json`, embedded at
//! compile time, so there is exactly one copy of every English log string. Its
//! keys live under `log.backend.*`; `scripts/check-locales.mjs` fails if a key
//! used here is missing there.

use std::fmt;
use std::sync::OnceLock;
use tauri::Emitter;

/// The frontend's English dev bundle, the single source of English log text.
const DEV_EN_JSON: &str = include_str!("../../src/i18n/locales/dev/en.json");

fn dev_en() -> &'static serde_json::Value {
    static DICT: OnceLock<serde_json::Value> = OnceLock::new();
    // ! The file is ours and checked by CI, so a parse failure is a build bug;
    // ! an empty dictionary still logs the bare keys instead of panicking.
    DICT.get_or_init(|| serde_json::from_str(DEV_EN_JSON).unwrap_or(serde_json::Value::Null))
}

/// Looks up a dot-path key such as `log.backend.xdelta.done`.
fn english_template(key: &str) -> Option<&'static str> {
    key.split('.')
        .try_fold(dev_en(), |node, seg| node.get(seg))
        .and_then(|v| v.as_str())
}

/// A log line as a key plus named variables. `Display` renders it in English.
#[derive(Debug, Clone)]
pub struct LogMsg {
    pub key: &'static str,
    pub vars: Vec<(&'static str, String)>,
}

impl LogMsg {
    pub fn new(key: &'static str) -> Self {
        Self {
            key,
            vars: Vec::new(),
        }
    }

    /// Adds a `{name}` variable.
    pub fn var(mut self, name: &'static str, value: impl ToString) -> Self {
        self.vars.push((name, value.to_string()));
        self
    }
}

impl fmt::Display for LogMsg {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let mut text = english_template(self.key).unwrap_or(self.key).to_string();
        for (name, value) in &self.vars {
            text = text.replace(&format!("{{{}}}", name), value);
        }
        f.write_str(&text)
    }
}

/// Builds a [`LogMsg`]: `log_msg!("log.backend.zip.found", count = n)`.
#[macro_export]
macro_rules! log_msg {
    ($key:literal $(, $name:ident = $value:expr)* $(,)?) => {
        $crate::logmsg::LogMsg::new($key)$(.var(stringify!($name), $value))*
    };
}

#[derive(Clone, serde::Serialize)]
struct KeyedLogPayload {
    container: String,
    /// English text, shown as is by a frontend that does not know `key`.
    message: String,
    log_type: String,
    key: String,
    vars: serde_json::Map<String, serde_json::Value>,
}

/// Sends a translatable line to one of the frontend's log consoles.
/// `container` and `log_type` are the same as for `utils::emit_log`.
pub fn emit_msg(app: &tauri::AppHandle, container: &str, msg: &LogMsg, log_type: &str) {
    let vars = msg
        .vars
        .iter()
        .map(|(k, v)| (k.to_string(), serde_json::Value::String(v.clone())))
        .collect();
    let _ = app.emit(
        "app-log",
        KeyedLogPayload {
            container: container.to_string(),
            message: msg.to_string(),
            log_type: log_type.to_string(),
            key: msg.key.to_string(),
            vars,
        },
    );
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn renders_english_from_the_dev_bundle() {
        let m = crate::log_msg!("log.backend.zip.found", count = 3);
        assert_eq!(
            m.to_string(),
            "Found 3 files to compress deterministically."
        );
    }

    #[test]
    fn unknown_key_falls_back_to_the_key() {
        assert_eq!(LogMsg::new("log.missing").to_string(), "log.missing");
    }
}
