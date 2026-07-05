fn main() {
    println!("cargo:rerun-if-changed=../.env");
    if let Ok(content) = std::fs::read_to_string("../.env") {
        for line in content.lines() {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            if let Some((k, v)) = line.split_once('=') {
                let k = k.trim();
                let v = v.trim().trim_matches(|c| c == '"' || c == '\'');
                println!("cargo:rustc-env={}={}", k, v);
            }
        }
    }
    tauri_build::build()
}
