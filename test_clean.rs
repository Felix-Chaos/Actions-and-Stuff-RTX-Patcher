use std::path::{Path, PathBuf};

fn get_mojang_paths() -> Vec<PathBuf> {
    let mut paths = Vec::new();
    let local_app_data = std::env::var("LOCALAPPDATA").ok().map(PathBuf::from);
    let app_data = std::env::var("APPDATA").ok().map(PathBuf::from);

    if let Some(ref lad) = local_app_data {
        paths.push(
            lad.join(r"Packages\Microsoft.MinecraftUWP_8wekyb3d8bbwe\LocalState\games\com.mojang"),
        );
        paths.push(lad.join(
            r"Packages\Microsoft.MinecraftWindowsBeta_8wekyb3d8bbwe\LocalState\games\com.mojang",
        ));
    }

    if let Some(ref ad) = app_data {
        paths.push(ad.join(r"Minecraft Bedrock\games\com.mojang"));
        paths.push(ad.join(r"Minecraft Bedrock Preview\games\com.mojang"));

        let users_dir = ad.join(r"Minecraft Bedrock\Users");
        if users_dir.exists() {
            if let Ok(entries) = std::fs::read_dir(users_dir) {
                for entry in entries.flatten() {
                    if entry.path().is_dir() {
                        paths.push(entry.path().join(r"games\com.mojang"));
                    }
                }
            }
        }
    }

    paths.retain(|p| p.exists());
    paths
}

fn scan_cleanable_packs_in_mojang(mojang_path: &Path) -> Vec<PathBuf> {
    let mut results = Vec::new();
    let prefixes = vec![
        "a&s",
        "actions & st",
        "actions&st",
        "a&sforrtx",
        "actions & stuff enhanced",
        "actions & stuff rtx",
    ];

    let check_dir_and_collect = |dir_path: &Path, results: &mut Vec<PathBuf>| {
        if let Ok(entries) = std::fs::read_dir(dir_path) {
            for entry in entries.flatten() {
                if entry.path().is_dir() {
                    if let Some(name) = entry.file_name().to_str() {
                        let lower_name = name.to_lowercase();
                        if prefixes.iter().any(|prefix| lower_name.starts_with(prefix)) {
                            results.push(entry.path());
                        }
                    }
                }
            }
        }
    };

    check_dir_and_collect(&mojang_path.join("resource_packs"), &mut results);
    check_dir_and_collect(
        &mojang_path.join("development_resource_packs"),
        &mut results,
    );

    results
}

fn main() {
    let mut results = Vec::new();
    for path in get_mojang_paths() {
        println!("Scanning: {:?}", path);
        for p in scan_cleanable_packs_in_mojang(&path) {
            results.push(p.to_string_lossy().into_owned());
        }
    }
    println!("Found: {:?}", results);
}
