//! Local HTTP API the Web Patcher polls (127.0.0.1 only).
//!
//! - `GET  /status?s=<session>`                      state, found packs, progress
//! - `POST /patch?s=<session>&pack=<id>&slug=<slug>` start patching
//! - `POST /takeover?s=<session>`                    a second `asrtx://` launch hands
//!   its session to the running helper (no browser can send this: it carries no Origin)
//!
//! Browsers always send `Origin` on these cross-origin requests, so only the
//! Web Patcher's own origin (and localhost for testing) gets an answer. The
//! page never passes a URL or path: the helper looks the slug up in its own
//! catalogue and works only on packs it found itself.

use crate::{pack, patch};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tiny_http::{Header, Method, Request, Response, Server};

pub const PORT: u16 = 47613;
/// Quit this long after a finished or failed run…
const LINGER_AFTER_END: Duration = Duration::from_secs(120);
/// …or after this long without the page asking (while not patching).
const IDLE_TIMEOUT: Duration = Duration::from_secs(15 * 60);

#[derive(Clone, Copy, PartialEq, serde::Serialize)]
#[serde(rename_all = "lowercase")]
enum State {
    Scanning,
    Ready,
    Running,
    Done,
    Error,
}

#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]
struct Job {
    helper_version: &'static str,
    #[serde(skip)]
    session: String,
    state: State,
    packs: Vec<pack::PackInfo>,
    step: Option<&'static str>,
    done: u64,
    total: u64,
    message: Option<String>,
    installed: Vec<String>,
    #[serde(skip)]
    last_seen: Instant,
    #[serde(skip)]
    ended_at: Option<Instant>,
}

type Shared = Arc<Mutex<Job>>;

impl Job {
    fn new(session: String) -> Job {
        Job {
            helper_version: env!("CARGO_PKG_VERSION"),
            session,
            state: State::Scanning,
            packs: Vec::new(),
            step: None,
            done: 0,
            total: 0,
            message: None,
            installed: Vec::new(),
            last_seen: Instant::now(),
            ended_at: None,
        }
    }
}

fn start_scan(job: &Shared) {
    let job = job.clone();
    std::thread::spawn(move || {
        let packs = pack::scan_packs();
        let mut j = job.lock().unwrap();
        j.packs = packs;
        j.state = State::Ready;
    });
}

pub fn run(session: String) {
    let server = match Server::http(("127.0.0.1", PORT)) {
        Ok(s) => s,
        Err(_) => {
            // Another helper is running: hand it the new session and quit.
            let url = format!("http://127.0.0.1:{PORT}/takeover?s={session}");
            if ureq::post(&url).timeout(Duration::from_secs(5)).call().is_err() {
                crate::message(
                    "A&S RTX Helper",
                    &format!("Port {PORT} is in use by another program, so the Web Patcher cannot talk to the helper."),
                    true,
                );
            }
            return;
        }
    };

    let job: Shared = Arc::new(Mutex::new(Job::new(session)));
    start_scan(&job);

    loop {
        if let Ok(Some(req)) = server.recv_timeout(Duration::from_secs(1)) {
            handle(req, &job);
        }
        let j = job.lock().unwrap();
        let over = j.ended_at.is_some_and(|t| t.elapsed() > LINGER_AFTER_END);
        let idle = j.state != State::Running && j.last_seen.elapsed() > IDLE_TIMEOUT;
        if over || idle {
            break;
        }
    }
}

fn allowed_origin(origin: &str) -> bool {
    origin == "https://rtx.chaosdev.dev"
        || ["http://localhost", "http://127.0.0.1"].iter().any(|base| {
            origin == *base || origin.strip_prefix(base).and_then(|r| r.strip_prefix(':')).is_some_and(|p| !p.is_empty() && p.bytes().all(|b| b.is_ascii_digit()))
        })
}

fn header(name: &str, value: &str) -> Header {
    Header::from_bytes(name.as_bytes(), value.as_bytes()).unwrap()
}

fn query(url: &str) -> Vec<(String, String)> {
    url.split_once('?')
        .map(|(_, q)| q.split('&').filter_map(|kv| kv.split_once('=')).map(|(k, v)| (k.to_string(), v.to_string())).collect())
        .unwrap_or_default()
}

fn handle(req: Request, job: &Shared) {
    let origin = req.headers().iter().find(|h| h.field.equiv("Origin")).map(|h| h.value.as_str().to_string());
    if let Some(o) = &origin {
        if !allowed_origin(o) {
            let _ = req.respond(Response::from_string("forbidden").with_status_code(403));
            return;
        }
    }
    let cors = |r: Response<std::io::Cursor<Vec<u8>>>| match &origin {
        Some(o) => r.with_header(header("Access-Control-Allow-Origin", o)).with_header(header("Vary", "Origin")),
        None => r,
    };
    let json = |code: u16, body: String| cors(Response::from_string(body).with_status_code(code).with_header(header("Content-Type", "application/json")).with_header(header("Cache-Control", "no-store")));
    let err = |code: u16, msg: &str| json(code, serde_json::json!({ "error": msg }).to_string());

    if *req.method() == Method::Options {
        let r = cors(Response::from_string("").with_status_code(204))
            .with_header(header("Access-Control-Allow-Methods", "GET, POST"))
            .with_header(header("Access-Control-Allow-Headers", "Content-Type"))
            .with_header(header("Access-Control-Allow-Private-Network", "true"))
            .with_header(header("Access-Control-Max-Age", "600"));
        let _ = req.respond(r);
        return;
    }

    let url = req.url().to_string();
    let path = url.split('?').next().unwrap_or("");
    let q = query(&url);
    let get = |k: &str| q.iter().find(|(key, _)| key == k).map(|(_, v)| v.as_str());
    let session = get("s").unwrap_or("");

    let resp = match (req.method(), path) {
        (Method::Post, "/takeover") if origin.is_none() => {
            let mut j = job.lock().unwrap();
            if j.state == State::Running {
                err(409, "busy")
            } else if session.len() < 16 || !session.bytes().all(|b| b.is_ascii_alphanumeric()) {
                err(400, "bad session")
            } else {
                *j = Job::new(session.to_string());
                drop(j);
                start_scan(job);
                json(200, "{}".into())
            }
        }
        (Method::Get, "/status") => {
            let mut j = job.lock().unwrap();
            if session != j.session {
                err(409, if j.state == State::Running { "busy" } else { "session" })
            } else {
                j.last_seen = Instant::now();
                json(200, serde_json::to_string(&*j).unwrap())
            }
        }
        (Method::Post, "/patch") => {
            let mut j = job.lock().unwrap();
            let slug = get("slug").unwrap_or("");
            let pack = get("pack").and_then(|id| j.packs.iter().find(|p| p.id == id).cloned());
            if session != j.session {
                err(409, "session")
            } else if j.state != State::Ready && j.state != State::Error && j.state != State::Done {
                err(409, "busy")
            } else if slug.is_empty() || !slug.bytes().all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'-') {
                err(400, "bad slug")
            } else if let Some(pack) = pack {
                j.state = State::Running;
                j.message = None;
                j.installed.clear();
                j.ended_at = None;
                j.last_seen = Instant::now();
                let (job2, slug, session) = (job.clone(), slug.to_string(), j.session.clone());
                std::thread::spawn(move || run_patch(job2, pack, slug, session));
                json(202, "{}".into())
            } else {
                err(400, "unknown pack")
            }
        }
        _ => err(404, "not found"),
    };
    let _ = req.respond(resp);
}

fn set_progress(job: &Shared, step: &'static str, done: u64, total: u64) {
    let mut j = job.lock().unwrap();
    j.step = Some(step);
    j.done = done;
    j.total = total;
}

fn run_patch(job: Shared, pack: pack::PackInfo, slug: String, session: String) {
    let base = std::env::temp_dir().join("asrtx-helper");
    let work = base.join(&session);
    let result = (|| -> Result<Vec<String>, String> {
        std::fs::create_dir_all(&work).map_err(|e| format!("Could not create a temp folder: {e}"))?;

        set_progress(&job, "download", 0, 0);
        let entry = patch::find_entry(&slug)?;
        let patch_file = work.join("patch.vcdiff");
        patch::download(&entry, &patch_file, |d, t| set_progress(&job, "download", d, t))?;
        set_progress(&job, "verify", 1, 1);

        let source = work.join("source.zip");
        pack::zip_folder(&pack.path, &source, |d, t| set_progress(&job, "zip", d as u64, t as u64))?;

        set_progress(&job, "apply", 0, 0);
        let output = work.join("patched.zip");
        patch::apply(&base, &source, &patch_file, &output)?;
        let _ = std::fs::remove_file(&source);
        let _ = std::fs::remove_file(&patch_file);

        let folder = format!(
            "Actions & Stuff RTX {} P{}",
            pack::normalize_version(&entry.pack_version),
            entry.patch_version.as_deref().unwrap_or("1.0")
        );
        set_progress(&job, "install", 0, 0);
        let dirs = pack::install_zip(&output, &folder, |d, t| set_progress(&job, "install", d as u64, t as u64))?;
        Ok(dirs.iter().map(|d| d.to_string_lossy().into_owned()).collect())
    })();
    let _ = std::fs::remove_dir_all(&work);

    let mut j = job.lock().unwrap();
    j.ended_at = Some(Instant::now());
    match result {
        Ok(dirs) => {
            j.state = State::Done;
            j.installed = dirs;
        }
        Err(e) => {
            j.state = State::Error;
            j.message = Some(e);
        }
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn origins() {
        assert!(super::allowed_origin("https://rtx.chaosdev.dev"));
        assert!(super::allowed_origin("http://localhost:8765"));
        assert!(super::allowed_origin("http://127.0.0.1"));
        assert!(!super::allowed_origin("https://rtx.chaosdev.dev.evil.com"));
        assert!(!super::allowed_origin("http://localhost.evil.com"));
        assert!(!super::allowed_origin("http://localhost:80@evil"));
        assert!(!super::allowed_origin("https://evil.com"));
    }
}
