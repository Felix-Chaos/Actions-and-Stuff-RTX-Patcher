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
                if k == "PATCHER_API_KEY" {
                    emit_obfuscated_key(v);
                } else {
                    println!("cargo:rustc-env={}={}", k, v);
                }
            }
        }
    }
    tauri_build::build()
}

// Keeps the raw API key out of the binary's plain-text strings table. A
// literal embedded via env!/option_env! sits verbatim in .rodata, so
// `strings patcher.exe | grep -i key` recovers it in seconds. XOR-ing it
// against a mask regenerated on every build (so a leaked mask+cipher pair
// from one release is useless against another) at least defeats that casual
// extraction. This is obfuscation, not real secrecy: a client-distributed
// secret can always be recovered by a determined reverse engineer with a
// debugger. Treat the server side as the actual trust boundary: rate-limit
// and validate there rather than relying on this key to gate anything.
fn emit_obfuscated_key(raw: &str) {
    let mask: Vec<u8> = (0..32u32).map(pseudo_random_byte).collect();
    let cipher: Vec<u8> = raw
        .bytes()
        .enumerate()
        .map(|(i, b)| b ^ mask[i % mask.len()])
        .collect();

    let join = |bytes: &[u8]| {
        bytes
            .iter()
            .map(|b| b.to_string())
            .collect::<Vec<_>>()
            .join(",")
    };

    println!("cargo:rustc-env=PATCHER_API_KEY_ENC={}", join(&cipher));
    println!("cargo:rustc-env=PATCHER_API_KEY_MASK={}", join(&mask));
}

// Deterministic-per-build PRNG seeded from build time, so the mask differs
// between builds without pulling in a `rand` build-dependency. Not
// cryptographically secure. It doesn't need to be for obfuscation purposes.
fn pseudo_random_byte(index: u32) -> u8 {
    use std::time::{SystemTime, UNIX_EPOCH};
    let seed = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let mixed = seed
        .wrapping_add(index as u128)
        .wrapping_mul(6364136223846793005)
        .wrapping_add(1442695040888963407);
    (mixed >> 33) as u8
}
