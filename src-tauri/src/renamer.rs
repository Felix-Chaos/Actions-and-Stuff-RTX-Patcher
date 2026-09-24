//! Experimental geometry renamer for extracted Actions & Stuff resource packs.
//!
//! Actions & Stuff ships every custom model as `geometry.oreville_ans.<6 random letters>`.
//! This module gives each one a readable, version-stable name and rewrites every
//! reference in the pack, then re-validates the result:
//!
//! * referenced geometries are named after the entity / attachable that uses them plus the
//!   role key they are bound to (`creeper.baby_snowy`); role keys are decoded from a static
//!   table and from the pack's own render-controller Molang (`v.x = q.is_name_any('snowy')`);
//! * unreferenced ("orphan") geometries are named from the atlas texels they sample, 16-member
//!   dye series, same-shape referenced siblings, or their decoded bone names;
//! * minified bone names are decoded (each letter is shifted -8 in the base-36 alphabet);
//! * names that would collide get a short content-hash suffix so the same model keeps the same
//!   name across pack versions.
//!
//! Vanilla geometry IDs (`geometry.boat`, `geometry.humanoid.*`, ...) are never renamed.
//! Results the user should double-check are written to a plain-text report.

use regex::Regex;
use serde::Serialize;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};
use std::path::{Path, PathBuf};
use std::sync::OnceLock;
use walkdir::WalkDir;

const PREFIX: &str = "geometry.oreville_ans.";

fn obf_re() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"^geometry\.oreville_ans\.[a-z]{6}$").unwrap())
}

fn is_obfuscated(gid: &str) -> bool {
    obf_re().is_match(gid)
}

// --------------------------------------------------------------------------- role table

/// Role keys decoded by hand from render controllers (carried over from the original
/// descrambler so names stay compatible). The pack's own Molang overrides it on conflict.
const BASE_ROLE_SEMANTICS: &[(&str, &str)] = &[
    ("default", "default"),
    ("rcvngv", "3d"),
    ("dfhqgk", "glint_1st_person"),
    ("tptvei", "overlay_glow_1"),
    ("kiqicb", "overlay_glow_2"),
    ("ospxor", "overlay_glow_3"),
    ("imnsla", "overlay_glow_4"),
    ("znbejo", "enchanted_mesh"),
    ("sumltu", "overlay_glow_5"),
    ("zuwklr", "overlay_glow_6"),
    ("kvxvid", "overlay_glow_7"),
    ("karenl", "outline"),
    ("wvhqfq", "enchanted_1st_person"),
    ("ckwnyv", "enchanted_3rd_person"),
    ("rgutwk", "hand_pose_1"),
    ("wnborj", "hand_pose_2"),
    ("ksowfn", "hand_pose_1"),
    ("rmoulm", "hand_pose_2"),
    ("thgzsf", "hand_pose_1"),
    ("vfcojb", "hand_pose_2"),
    ("sjseco", "hand_pose_1"),
    ("ukihsz", "hand_pose_2"),
    ("oltrej", "baby"),
    ("rnvtrq", "baby_snowy"),
    ("vgdfde", "baby_sulfur"),
    ("vaznlz", "baby_cherry"),
    ("zqykjy", "snowy"),
    ("htgktc", "sulfur"),
    ("jevhhw", "cherry"),
    ("gjhrgi", "eyes"),
    ("cqvkuv", "powered"),
    ("meratx", "swelling_stage1"),
    ("sofmpb", "baby"),
    ("tblaea", "baby_powered"),
    ("uibrhs", "swelling_stage2"),
    ("hkyjlq", "baby_swelling_stage1"),
    ("tlyzdy", "baby_swelling_stage2"),
    ("qrkrcz", "swelling_stage3"),
    ("bsitgo", "baby_swelling_stage3"),
    ("qddgxu", "swelling_stage4"),
    ("xcyaru", "baby_swelling_stage4"),
    ("vpbaiq", "swelling_stage5"),
    ("hxbtht", "baby_swelling_stage5"),
    ("giazhl", "swelling_stage6"),
    ("mnpxpx", "baby_swelling_stage6"),
    ("pyscvg", "snowy"),
    ("hbdelw", "snowy_baby"),
    ("tunagv", "baby"),
    ("dwvyiq", "baby_drowned"),
    ("cfsfem", "drowned"),
    ("bizcge", "head_item"),
    ("xbxrgg", "baby_head_item"),
    ("ufzxyk", "eyes"),
    ("nfcspr", "baby_eyes"),
    ("cxnlin", "baby"),
    ("efdwmo", "baby"),
    ("raszyg", "baby"),
    ("nmaiou", "baby"),
    ("yklrin", "baby"),
    ("fnzlax", "baby_snowy"),
    ("smhkos", "baby_sulfur"),
    ("afrgqm", "baby_cherry"),
    ("kpacwn", "baby"),
    ("wziosx", "cold"),
    ("lokszx", "warm"),
    ("xjjhzp", "baby_cold"),
    ("zvtryp", "baby_warm"),
    ("bgbxrm", "baby"),
    ("gtjjer", "sleep"),
    ("bpylml", "cracked_high"),
    ("zywjwc", "cracked_medium"),
    ("sfhcsy", "cracked_low"),
    ("oauppz", "eyes"),
    ("swezok", "armor_iron"),
    ("yhsorx", "armor_gold"),
    ("rnnsyu", "armor_diamond"),
    ("qjyuja", "armor_leather"),
    ("gusrqk", "saddle"),
    ("gmvben", "chest"),
    ("cpizre", "baby"),
    ("gxffsv", "markings"),
    ("rgzdhy", "reins"),
    ("oyxmae", "armor_netherite"),
    ("lunuox", "mule_saddle"),
];

const CONDITION_KEYWORDS: &[(&str, &str)] = &[
    ("v.cdrzno", "baby"),
    ("q.is_baby", "baby"),
    ("v.aybhly", "snowy"),
    ("v.ifqpks", "cherry"),
    ("v.uunhwi", "sulfur"),
    ("q.is_powered", "powered"),
    ("q.is_sheared", "sheared"),
    ("q.is_sleeping", "sleep"),
    ("c.is_first_person", "1st_person"),
    ("!c.is_first_person", "3rd_person"),
    ("jlfjfs", "3d"),
    ("q.swell_amount", "swelling"),
    ("is_enchanted", "enchanted"),
];

const DYES: &[&str] = &[
    "black",
    "blue",
    "brown",
    "cyan",
    "gray",
    "green",
    "light_blue",
    "light_gray",
    "lime",
    "magenta",
    "orange",
    "pink",
    "purple",
    "red",
    "white",
    "yellow",
];

// --------------------------------------------------------------------------- pack model

#[derive(Clone)]
struct Usage {
    category: String, // "entity", "attachable" or "subpack:SPx"
    ident: String,
    role: String,
}

struct GeoDef {
    rel: String,
    index: usize,
    geo: Value,
}

struct Pack {
    defs: BTreeMap<String, GeoDef>,
    uses: BTreeMap<String, Vec<Usage>>,
    clients: Vec<(String, Value)>,
    render_controllers: BTreeMap<String, Value>,
    /// raw text of animation/entity scripts, for Molang variable definitions
    scripts: Vec<String>,
    vocab: HashSet<String>,
    json_failures: Vec<String>,
}

fn json_files(root: &Path) -> Vec<(String, PathBuf)> {
    let mut out: Vec<(String, PathBuf)> = WalkDir::new(root)
        .into_iter()
        .filter_map(|e| e.ok())
        .filter(|e| e.file_type().is_file())
        .filter(|e| e.path().extension().and_then(|x| x.to_str()) == Some("json"))
        .map(|e| {
            let rel = e
                .path()
                .strip_prefix(root)
                .unwrap_or(e.path())
                .to_string_lossy()
                .replace('\\', "/");
            (rel, e.path().to_path_buf())
        })
        .collect();
    out.sort();
    out
}

fn split_words(s: &str, re: &Regex, into: &mut HashSet<String>) {
    for w in re.split(s) {
        if !w.is_empty() {
            into.insert(w.to_lowercase());
        }
    }
}

impl Pack {
    fn load(root: &Path) -> Pack {
        let mut p = Pack {
            defs: BTreeMap::new(),
            uses: BTreeMap::new(),
            clients: Vec::new(),
            render_controllers: BTreeMap::new(),
            scripts: Vec::new(),
            vocab: HashSet::new(),
            json_failures: Vec::new(),
        };
        let id_split = Regex::new(r"[_:.]").unwrap();
        let sub_re = Regex::new(r"^subpacks/([^/]+)/").unwrap();
        for (rel, path) in json_files(root) {
            let Ok(bytes) = std::fs::read(&path) else {
                continue;
            };
            let text = String::from_utf8_lossy(&bytes).to_string();
            let data: Value = match serde_json::from_str(text.trim_start_matches('\u{feff}')) {
                Ok(v) => v,
                Err(_) => {
                    p.json_failures.push(rel);
                    continue;
                }
            };
            let Some(obj) = data.as_object() else {
                continue;
            };
            if [
                "entity/",
                "attachables/",
                "animations/",
                "animation_controllers/",
            ]
            .iter()
            .any(|d| rel.starts_with(d))
            {
                p.scripts.push(text.clone());
            }
            if let Some(geos) = obj.get("minecraft:geometry").and_then(|g| g.as_array()) {
                if rel.contains("models") {
                    for (i, g) in geos.iter().enumerate() {
                        if let Some(id) = g
                            .pointer("/description/identifier")
                            .and_then(|x| x.as_str())
                        {
                            p.defs.insert(
                                id.to_string(),
                                GeoDef {
                                    rel: rel.clone(),
                                    index: i,
                                    geo: g.clone(),
                                },
                            );
                        }
                    }
                }
            }
            let client = obj
                .get("minecraft:client_entity")
                .or_else(|| obj.get("minecraft:attachable"));
            if let Some(desc) = client.and_then(|c| c.get("description")) {
                let ident = desc
                    .get("identifier")
                    .and_then(|x| x.as_str())
                    .unwrap_or("")
                    .to_string();
                split_words(&ident, &id_split, &mut p.vocab);
                if let (false, Some(geos)) = (
                    ident.is_empty(),
                    desc.get("geometry").and_then(|g| g.as_object()),
                ) {
                    let category = if let Some(c) = sub_re.captures(&rel) {
                        format!("subpack:{}", &c[1])
                    } else if rel.contains("entity") {
                        "entity".to_string()
                    } else {
                        "attachable".to_string()
                    };
                    for (role, gid) in geos {
                        if let Some(gid) = gid.as_str() {
                            p.uses.entry(gid.to_string()).or_default().push(Usage {
                                category: category.clone(),
                                ident: ident.clone(),
                                role: role.clone(),
                            });
                        }
                    }
                }
                p.clients.push((rel.clone(), desc.clone()));
            }
            if let Some(rcs) = obj.get("render_controllers").and_then(|r| r.as_object()) {
                let sp = sub_re.captures(&rel).map(|c| c[1].to_string());
                for (name, rc) in rcs {
                    let key = match &sp {
                        Some(s) => format!("{}:{}", s, name),
                        None => name.clone(),
                    };
                    p.render_controllers.insert(key, rc.clone());
                }
            }
        }
        if let Ok(lang) = std::fs::read_to_string(root.join("texts").join("en_US.lang")) {
            let w = Regex::new(r"[A-Za-z]{2,}").unwrap();
            for m in w.find_iter(&lang) {
                p.vocab.insert(m.as_str().to_lowercase());
            }
        }
        let plain = Regex::new(r"[s-z]").unwrap();
        let bone_split = Regex::new(r"[_\d]+").unwrap();
        let mut bone_words = HashSet::new();
        for d in p.defs.values() {
            for b in bones(&d.geo) {
                let n = bone_name(b);
                if plain.is_match(n) {
                    split_words(n, &bone_split, &mut bone_words);
                }
            }
        }
        p.vocab.extend(bone_words);
        p
    }

    fn orphans(&self) -> Vec<String> {
        self.defs
            .keys()
            .filter(|g| !self.uses.contains_key(*g))
            .cloned()
            .collect()
    }
}

fn bones(g: &Value) -> &[Value] {
    g.get("bones")
        .and_then(|b| b.as_array())
        .map(|v| v.as_slice())
        .unwrap_or(&[])
}

fn bone_name(b: &Value) -> &str {
    b.get("name").and_then(|n| n.as_str()).unwrap_or("")
}

fn cubes(b: &Value) -> &[Value] {
    b.get("cubes")
        .and_then(|c| c.as_array())
        .map(|v| v.as_slice())
        .unwrap_or(&[])
}

fn tex_size(g: &Value) -> (i64, i64) {
    let d = g.get("description");
    let f = |k: &str| {
        d.and_then(|d| d.get(k))
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0) as i64
    };
    (f("texture_width"), f("texture_height"))
}

fn strip_ns(ident: &str) -> &str {
    ident.strip_prefix("minecraft:").unwrap_or(ident)
}

fn short_ident(ident: &str) -> &str {
    ident.rsplit(':').next().unwrap_or(ident)
}

// --------------------------------------------------------------------------- bone cipher

const B36: &str = "0123456789abcdefghijklmnopqrstuvwxyz";
const SHIFT: usize = 8;

const BUILTIN_WORDS: &str = "a an and at back bar base bit bits block body book bottom brd bl2 center \
centroid chest cloth collar core counter cube dummy ear east emissive eye eyes face fin flag floor \
flame front glow hand head held inner item layer left leg lid light main mouth nose north oar offset \
outline overlay part pivot plush pole post posts right ring rotate side south spin stem tail top \
trail west wing wall wick node nodes extras anchor elements frame portal sensor tendril active";

fn decode_char(c: char) -> char {
    let i = B36.find(c).unwrap();
    B36.as_bytes()[i + SHIFT] as char
}

struct BoneDecoder {
    vocab: HashSet<String>,
    cache: std::cell::RefCell<HashMap<String, String>>,
}

impl BoneDecoder {
    fn new(vocab: &HashSet<String>) -> Self {
        let v: HashSet<String> = vocab
            .iter()
            .map(String::as_str)
            .chain(BUILTIN_WORDS.split_whitespace())
            .filter(|w| (2..=24).contains(&w.len()))
            .map(String::from)
            .collect();
        BoneDecoder {
            vocab: v,
            cache: Default::default(),
        }
    }

    fn is_encoded_segment(seg: &str) -> bool {
        !seg.is_empty()
            && seg
                .chars()
                .all(|c| c.is_ascii_digit() || ('a'..='r').contains(&c))
            && !seg.chars().all(|c| c.is_ascii_digit())
    }

    /// Best word-segmentation score (higher is better).
    fn score(&self, s: &str) -> f64 {
        let n = s.len();
        let mut best = vec![-1e9f64; n + 1];
        best[0] = 0.0;
        for i in 1..=n {
            for j in i.saturating_sub(24)..i {
                if best[j] <= -1e9 {
                    continue;
                }
                let w = &s[j..i];
                let val = if self.vocab.contains(w) {
                    (w.len() * w.len()) as f64
                } else if w.chars().all(|c| c.is_ascii_digit()) {
                    if i == n {
                        0.5
                    } else {
                        -3.5
                    } // literal digits are plausible only as a suffix
                } else if w.len() == 1 {
                    -3.0
                } else {
                    continue;
                };
                best[i] = best[i].max(best[j] + val);
            }
        }
        best[n]
    }

    fn decode_segment(&self, seg: &str) -> String {
        if !Self::is_encoded_segment(seg) {
            return seg.to_string();
        }
        let mut cands = vec![String::new()];
        for c in seg.chars() {
            let opts: Vec<char> = if c.is_ascii_alphabetic() {
                vec![decode_char(c)]
            } else if ('2'..='9').contains(&c) {
                vec![decode_char(c), c]
            } else {
                vec![c]
            };
            cands = cands
                .iter()
                .flat_map(|p| opts.iter().map(move |o| format!("{}{}", p, o)))
                .collect();
            if cands.len() > 4096 {
                cands.sort_by(|a, b| self.score(b).partial_cmp(&self.score(a)).unwrap());
                cands.truncate(512);
            }
        }
        let key = |s: &String| {
            let body = s.trim_end_matches(|c: char| c.is_ascii_digit());
            let digits = body.chars().filter(|c| c.is_ascii_digit()).count() as i64;
            (self.score(s), -digits, (s.len() - body.len()) as i64)
        };
        let mut best = cands[0].clone();
        let mut best_key = key(&best);
        for c in &cands[1..] {
            let k = key(c);
            if k.partial_cmp(&best_key) == Some(std::cmp::Ordering::Greater) {
                best_key = k;
                best = c.clone();
            }
        }
        best
    }

    fn decode(&self, name: &str) -> String {
        if let Some(v) = self.cache.borrow().get(name) {
            return v.clone();
        }
        let out = name
            .split('_')
            .map(|p| self.decode_segment(p))
            .collect::<Vec<_>>()
            .join("_");
        self.cache
            .borrow_mut()
            .insert(name.to_string(), out.clone());
        out
    }
}

fn decoded_bone_label(dec: &BoneDecoder, g: &Value) -> String {
    const SKIP: &[&str] = &[
        "root",
        "item",
        "body",
        "head",
        "waist",
        "itemglow",
        "emissiveadditivealphabilinear",
    ];
    for b in bones(g) {
        let d = dec.decode(bone_name(b));
        if !cubes(b).is_empty() && !SKIP.contains(&d.as_str()) && !d.starts_with("root_") {
            return d
                .chars()
                .filter(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || *c == '_')
                .collect();
        }
    }
    "model".to_string()
}

// --------------------------------------------------------------------------- fingerprints

/// JSON with object keys sorted, so equal content always serialises the same way.
fn canonical(v: &Value) -> String {
    match v {
        Value::Object(m) => {
            let mut keys: Vec<&String> = m.keys().collect();
            keys.sort();
            let parts: Vec<String> = keys
                .iter()
                .map(|k| format!("{:?}:{}", k, canonical(&m[*k])))
                .collect();
            format!("{{{}}}", parts.join(","))
        }
        Value::Array(a) => format!(
            "[{}]",
            a.iter().map(canonical).collect::<Vec<_>>().join(",")
        ),
        other => other.to_string(),
    }
}

fn fingerprint(g: &Value, loose: bool) -> String {
    let f = |v: Option<&Value>, dflt: &str| v.map(canonical).unwrap_or_else(|| dflt.to_string());
    let mut bone_keys: Vec<String> = bones(g)
        .iter()
        .map(|b| {
            let mut cs: Vec<String> = cubes(b)
                .iter()
                .map(|c| {
                    let uv = if loose {
                        String::new()
                    } else {
                        f(c.get("uv"), "null")
                    };
                    format!(
                        "{}|{}|{}|{}",
                        f(c.get("origin"), "[]"),
                        f(c.get("size"), "[]"),
                        f(c.get("inflate"), "0"),
                        uv
                    )
                })
                .collect();
            cs.sort();
            if loose {
                format!("{}#{}", bone_name(b), cs.join(";"))
            } else {
                format!(
                    "{}#{}#{}#{}#{}",
                    bone_name(b),
                    f(b.get("parent"), "null"),
                    f(b.get("pivot"), "[]"),
                    f(b.get("rotation"), "[0,0,0]"),
                    cs.join(";")
                )
            }
        })
        .collect();
    bone_keys.sort();
    let key = if loose {
        bone_keys.join("/")
    } else {
        let (w, h) = tex_size(g);
        format!("{}x{}/{}", w, h, bone_keys.join("/"))
    };
    let digest = Sha256::digest(key.as_bytes());
    digest
        .iter()
        .take(8)
        .map(|b| format!("{:02x}", b))
        .collect()
}

type Rect = (f64, f64, f64, f64);

fn uv_rects(g: &Value) -> Vec<Rect> {
    let mut out = Vec::new();
    let num = |v: Option<&Value>, i: usize| {
        v.and_then(|a| a.get(i))
            .and_then(|x| x.as_f64())
            .unwrap_or(0.0)
    };
    for b in bones(g) {
        for c in cubes(b) {
            match c.get("uv") {
                Some(Value::Object(faces)) => {
                    for f in faces.values() {
                        let (u, v) = (num(f.get("uv"), 0), num(f.get("uv"), 1));
                        let (w, h) = (num(f.get("uv_size"), 0), num(f.get("uv_size"), 1));
                        out.push((u.min(u + w), v.min(v + h), u.max(u + w), v.max(v + h)));
                    }
                }
                Some(Value::Array(a)) if a.len() == 2 => {
                    let size = c.get("size");
                    let (sx, sy, sz) = (num(size, 0), num(size, 1), num(size, 2));
                    let (u, v) = (a[0].as_f64().unwrap_or(0.0), a[1].as_f64().unwrap_or(0.0));
                    out.push((u, v, u + 2.0 * sz + 2.0 * sx, v + sz + sy));
                }
                _ => {}
            }
        }
    }
    out
}

/// The atlas texels a geometry samples: in shared atlases they identify the texture.
fn texel_mask(g: &Value) -> HashSet<(i64, i64)> {
    let mut m = HashSet::new();
    for (x0, y0, x1, y1) in uv_rects(g) {
        let (xa, xb) = (x0.trunc() as i64, x1.max(x0 + 1.0).trunc() as i64);
        let (ya, yb) = (y0.trunc() as i64, y1.max(y0 + 1.0).trunc() as i64);
        for x in xa..xb {
            for y in ya..yb {
                m.insert((x, y));
            }
        }
    }
    m
}

struct Mask {
    set: HashSet<(i64, i64)>,
    bbox: (i64, i64, i64, i64),
}

impl Mask {
    fn of(g: &Value) -> Mask {
        let set = texel_mask(g);
        let mut bbox = (i64::MAX, i64::MAX, i64::MIN, i64::MIN);
        for &(x, y) in &set {
            bbox = (bbox.0.min(x), bbox.1.min(y), bbox.2.max(x), bbox.3.max(y));
        }
        Mask { set, bbox }
    }
    fn overlaps(&self, o: &Mask) -> bool {
        !(self.bbox.2 < o.bbox.0
            || o.bbox.2 < self.bbox.0
            || self.bbox.3 < o.bbox.1
            || o.bbox.3 < self.bbox.1)
    }
    fn inter(&self, o: &Mask) -> usize {
        if !self.overlaps(o) {
            return 0;
        }
        let (a, b) = if self.set.len() < o.set.len() {
            (&self.set, &o.set)
        } else {
            (&o.set, &self.set)
        };
        a.iter().filter(|p| b.contains(p)).count()
    }
}

// --------------------------------------------------------------------------- Molang

fn token_re() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| {
        Regex::new(
            r"\?\?|&&|\|\||[?:()\[\]!]|'[^']*'|[A-Za-z_][\w.]*|\d+(?:\.\d+)?|->|[<>=]=?|==|!=|\S",
        )
        .unwrap()
    })
}

#[derive(Debug, Clone)]
enum Node {
    Tern(Box<Node>, Box<Node>, Box<Node>),
    Bin(String, Box<Node>, Box<Node>),
    Not(Box<Node>),
    Array(String, Box<Node>),
    Call(String, Vec<Node>),
    Atom(String),
}

struct Parser {
    t: Vec<String>,
    i: usize,
}

impl Parser {
    fn parse(expr: &str) -> Result<Node, String> {
        let mut p = Parser {
            t: token_re()
                .find_iter(expr)
                .map(|m| m.as_str().to_string())
                .collect(),
            i: 0,
        };
        p.ternary()
    }
    fn peek(&self) -> Option<&str> {
        self.t.get(self.i).map(|s| s.as_str())
    }
    fn take(&mut self, want: Option<&str>) -> Result<String, String> {
        let tok = self.peek().map(String::from);
        if let Some(w) = want {
            if tok.as_deref() != Some(w) {
                return Err(format!(
                    "expected '{}', got {:?} in {}",
                    w,
                    tok,
                    self.t.join(" ")
                ));
            }
        }
        self.i += 1;
        tok.ok_or_else(|| "unexpected end of expression".to_string())
    }
    fn ternary(&mut self) -> Result<Node, String> {
        let cond = self.logic_or()?;
        if self.peek() == Some("?") {
            self.take(Some("?"))?;
            let a = self.ternary()?;
            let b = if self.peek() == Some(":") {
                self.take(Some(":"))?;
                self.ternary()?
            } else {
                Node::Atom("0".into()) // Molang 'a ? b' yields 0 when false
            };
            return Ok(Node::Tern(Box::new(cond), Box::new(a), Box::new(b)));
        }
        Ok(cond)
    }
    fn logic_or(&mut self) -> Result<Node, String> {
        let mut n = self.logic_and()?;
        while self.peek() == Some("||") {
            self.take(None)?;
            n = Node::Bin("||".into(), Box::new(n), Box::new(self.logic_and()?));
        }
        Ok(n)
    }
    fn logic_and(&mut self) -> Result<Node, String> {
        let mut n = self.compare()?;
        while self.peek() == Some("&&") {
            self.take(None)?;
            n = Node::Bin("&&".into(), Box::new(n), Box::new(self.compare()?));
        }
        Ok(n)
    }
    fn compare(&mut self) -> Result<Node, String> {
        let mut n = self.unary()?;
        while matches!(
            self.peek(),
            Some("==" | "!=" | "<" | ">" | "<=" | ">=" | "+" | "-" | "*" | "/")
        ) {
            let op = self.take(None)?;
            n = Node::Bin(op, Box::new(n), Box::new(self.unary()?));
        }
        Ok(n)
    }
    fn unary(&mut self) -> Result<Node, String> {
        if self.peek() == Some("!") {
            self.take(None)?;
            return Ok(Node::Not(Box::new(self.unary()?)));
        }
        self.primary()
    }
    fn primary(&mut self) -> Result<Node, String> {
        let tok = self.take(None)?;
        if tok == "(" {
            let n = self.ternary()?;
            self.take(Some(")"))?;
            return Ok(n);
        }
        if tok.to_lowercase().starts_with("array.") && self.peek() == Some("[") {
            self.take(Some("["))?;
            let idx = self.ternary()?;
            self.take(Some("]"))?;
            return Ok(Node::Array(tok, Box::new(idx)));
        }
        if self.peek() == Some("(") {
            self.take(Some("("))?;
            let mut args = Vec::new();
            while self.peek().is_some() && self.peek() != Some(")") {
                args.push(self.ternary()?);
                if self.peek() == Some(",") {
                    self.take(None)?;
                }
            }
            self.take(Some(")"))?;
            return Ok(Node::Call(tok, args));
        }
        Ok(Node::Atom(tok))
    }
}

fn describe(n: &Node, labels: &HashMap<String, String>) -> String {
    match n {
        Node::Atom(tok) => {
            let low = tok.to_lowercase();
            if low.starts_with("v.") || low.starts_with("variable.") {
                let var = tok.splitn(2, '.').nth(1).unwrap_or("");
                labels.get(var).cloned().unwrap_or_else(|| tok.clone())
            } else if low.starts_with("q.") || low.starts_with("query.") {
                let q = tok.splitn(2, '.').nth(1).unwrap_or("");
                q.strip_prefix("is_").unwrap_or(q).to_string()
            } else {
                tok.clone()
            }
        }
        Node::Not(x) => format!("not_{}", describe(x, labels)),
        Node::Bin(op, a, b) => {
            let j = match op.as_str() {
                "&&" => "_and_".to_string(),
                "||" => "_or_".to_string(),
                "==" => "_eq_".to_string(),
                "!=" => "_ne_".to_string(),
                o => o.to_string(),
            };
            format!("{}{}{}", describe(a, labels), j, describe(b, labels))
        }
        Node::Call(name, args) => {
            for a in args {
                if let Node::Atom(t) = a {
                    if t.starts_with('\'') {
                        return t.trim_matches('\'').to_lowercase();
                    }
                }
            }
            name.splitn(2, '.').last().unwrap_or(name).to_string()
        }
        _ => "?".to_string(),
    }
}

fn enumerate_branches(
    n: &Node,
    arrays: &serde_json::Map<String, Value>,
    labels: &HashMap<String, String>,
    path: Vec<String>,
    out: &mut Vec<(Vec<String>, String)>,
    depth: usize,
) {
    if depth > 64 {
        return;
    }
    match n {
        Node::Tern(c, a, b) => {
            let lab = describe(c, labels);
            let mut pa = path.clone();
            pa.push(lab.clone());
            enumerate_branches(a, arrays, labels, pa, out, depth + 1);
            let mut pb = path;
            pb.push(format!("not_{}", lab));
            enumerate_branches(b, arrays, labels, pb, out, depth + 1);
        }
        Node::Array(name, idx) => {
            let idx_lab = describe(idx, labels);
            if let Some(items) = arrays.get(name).and_then(|a| a.as_array()) {
                for (i, item) in items.iter().enumerate() {
                    if let Some(Ok(sub)) = item.as_str().map(Parser::parse) {
                        let mut p = path.clone();
                        p.push(format!("{}_{}", idx_lab, i));
                        enumerate_branches(&sub, arrays, labels, p, out, depth + 1);
                    }
                }
            }
        }
        Node::Atom(tok) if tok.to_lowercase().starts_with("geometry.") => {
            out.push((path, tok.splitn(2, '.').nth(1).unwrap_or("").to_string()));
        }
        _ => {}
    }
}

/// v.xxx -> meaning, recovered from how each variable is assigned in the pack's scripts.
fn infer_variable_labels(pack: &Pack) -> HashMap<String, String> {
    let assign = Regex::new(r"\bv(?:ariable)?\.(\w+)\s*=\s*([^;]+)").unwrap();
    let lit = Regex::new(r"is_name_any\('([^']+)'").unwrap();
    let query = Regex::new(r"\bq(?:uery)?\.(\w+)").unwrap();
    let mut counts: HashMap<String, Vec<(String, i64)>> = HashMap::new();
    let mut bump = |var: &str, label: String, by: i64| {
        let e = counts.entry(var.to_string()).or_default();
        match e.iter_mut().find(|(l, _)| *l == label) {
            Some(x) => x.1 += by,
            None => e.push((label, by)),
        }
    };
    for text in &pack.scripts {
        for c in assign.captures_iter(text) {
            let (var, rhs) = (&c[1], &c[2]);
            if let Some(l) = lit.captures(rhs) {
                bump(var, l[1].to_lowercase(), 3);
            }
            for q in query.captures_iter(rhs) {
                let q = &q[1];
                if ![
                    "is_in_ui",
                    "is_name_any",
                    "is_attached",
                    "is_pack_setting_selected",
                ]
                .contains(&q)
                {
                    bump(var, q.strip_prefix("is_").unwrap_or(q).to_string(), 1);
                }
            }
        }
    }
    counts
        .into_iter()
        .filter_map(|(var, c)| {
            let mut best: Option<&(String, i64)> = None;
            for x in &c {
                if best.map_or(true, |b| x.1 > b.1) {
                    best = Some(x);
                }
            }
            best.map(|b| (var, b.0.clone()))
        })
        .collect()
}

fn index_label_re() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"_\d+$").unwrap())
}

/// controller name -> {geometry role key -> label}; parse errors are counted.
fn resolve_render_controllers(pack: &Pack) -> (BTreeMap<String, HashMap<String, String>>, usize) {
    let labels = infer_variable_labels(pack);
    let empty = serde_json::Map::new();
    let mut out = BTreeMap::new();
    let mut errors = 0;
    for (name, rc) in &pack.render_controllers {
        let Some(expr) = rc.get("geometry").and_then(|g| g.as_str()) else {
            continue;
        };
        let low = expr.to_lowercase();
        if !low.contains("geometry.") && !low.contains("array.") {
            continue;
        }
        let arrays = rc
            .pointer("/arrays/geometries")
            .and_then(|a| a.as_object())
            .unwrap_or(&empty);
        let tree = match Parser::parse(expr) {
            Ok(t) => t,
            Err(_) => {
                errors += 1;
                continue;
            }
        };
        let mut leaves = Vec::new();
        enumerate_branches(&tree, arrays, &labels, Vec::new(), &mut leaves, 0);
        let mut branches: HashMap<String, ((bool, usize), String)> = HashMap::new();
        for (path, key) in leaves {
            let positive: Vec<&String> = path.iter().filter(|p| !p.starts_with("not_")).collect();
            let label = if positive.is_empty() {
                "default".to_string()
            } else {
                positive
                    .iter()
                    .map(|s| s.as_str())
                    .collect::<Vec<_>>()
                    .join(".")
            };
            let rank = (index_label_re().is_match(&label), label.len()); // prefer semantic labels
            if branches.get(&key).map_or(true, |(r, _)| rank < *r) {
                branches.insert(key, (rank, label));
            }
        }
        out.insert(
            name.clone(),
            branches.into_iter().map(|(k, (_, l))| (k, l)).collect(),
        );
    }
    (out, errors)
}

/// Positive terms of a controller's activation condition, e.g.
/// `q.swell_amount&&!v.cdrzno` -> ["swell_amount"], `q.is_powered` -> ["powered"].
fn positive_terms(n: &Node, labels: &HashMap<String, String>, out: &mut Vec<String>) {
    match n {
        Node::Bin(op, a, b) if op == "&&" => {
            positive_terms(a, labels, out);
            positive_terms(b, labels, out);
        }
        Node::Not(_) => {}
        Node::Atom(t) if t.parse::<f64>().is_ok() => {}
        other => {
            let d = describe(other, labels);
            if !d.starts_with("v.") && !out.contains(&d) {
                out.push(d);
            }
        }
    }
}

/// entity identifier -> {role -> label from that entity's own render controllers}.
/// The controller's own activation condition (entity file: `{"controller": "q.is_powered"}`)
/// is prefixed, so e.g. swelling / powered overlays keep that context.
fn controller_labels_per_entity(
    pack: &Pack,
    branches: &BTreeMap<String, HashMap<String, String>>,
) -> HashMap<String, HashMap<String, String>> {
    let sub_re = Regex::new(r"^subpacks/([^/]+)/").unwrap();
    let var_labels = infer_variable_labels(pack);
    let mut per: HashMap<String, HashMap<String, (usize, String)>> = HashMap::new();
    for (rel, desc) in &pack.clients {
        let ident = desc
            .get("identifier")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string();
        let sp = sub_re.captures(rel).map(|c| c[1].to_string());
        let Some(rcs) = desc.get("render_controllers").and_then(|r| r.as_array()) else {
            continue;
        };
        for rc in rcs {
            let (name, cond) = match rc {
                Value::String(s) => (s.clone(), String::new()),
                Value::Object(m) => match m.iter().next() {
                    Some((k, v)) => (k.clone(), v.as_str().unwrap_or("").to_string()),
                    None => continue,
                },
                _ => continue,
            };
            let mut prefix = Vec::new();
            if !cond.is_empty() {
                if let Ok(node) = Parser::parse(&cond) {
                    positive_terms(&node, &var_labels, &mut prefix);
                }
            }
            let table = sp
                .as_ref()
                .and_then(|s| branches.get(&format!("{}:{}", s, name)))
                .or_else(|| branches.get(&name));
            let Some(t) = table else { continue };
            let e = per.entry(ident.clone()).or_default();
            for (role, label) in t {
                if index_label_re().is_match(label) {
                    continue;
                }
                let mut parts = prefix.clone();
                if label != "default" {
                    parts.push(label.clone());
                }
                if parts.is_empty() {
                    continue;
                }
                // prefer the controller that needs the fewest extra conditions
                let cand = (prefix.len(), parts.join("."));
                if e.get(role).map_or(true, |cur| cand.0 < cur.0) {
                    e.insert(role.clone(), cand);
                }
            }
        }
    }
    per.into_iter()
        .map(|(k, m)| (k, m.into_iter().map(|(r, (_, l))| (r, l)).collect()))
        .collect()
}

fn label_conflicts(table_value: &str, molang_label: &str) -> bool {
    let words: HashSet<&str> = table_value.split(|c| c == '_' || c == '.').collect();
    let compact = table_value.replace('_', "");
    molang_label.split('.').any(|part| {
        !part
            .split("_or_")
            .any(|o| words.contains(o) || compact.contains(&o.replace('_', "")))
    })
}

// --------------------------------------------------------------------------- naming

fn role_dictionary(pack: &Pack) -> HashMap<String, String> {
    let mut d: HashMap<String, String> = BASE_ROLE_SEMANTICS
        .iter()
        .map(|(k, v)| (k.to_string(), v.to_string()))
        .collect();
    for (name, rc) in &pack.render_controllers {
        if name.contains(':') {
            continue; // the original descrambler only reads the main pack's controllers
        }
        let expr = match rc.get("geometry") {
            Some(Value::String(s)) => s.clone(),
            Some(other) => other.to_string(),
            None => String::new(),
        };
        for (cond, meaning) in CONDITION_KEYWORDS {
            if !expr.contains(cond) {
                continue;
            }
            let re = Regex::new(&format!(
                r"{}[^?]*\?[^:]*Geometry\.([a-zA-Z0-9_]+)",
                regex::escape(cond)
            ))
            .unwrap();
            if let Some(c) = re.captures(&expr) {
                let role = c[1].to_string();
                if d.get(&role).map_or(true, |v| *v == role) {
                    d.insert(role, meaning.to_string());
                }
            }
        }
    }
    d
}

/// Name for a referenced geometry, from the entity/attachable that uses it and its role key.
fn canonical_name(
    gid: &str,
    usages: &[Usage],
    roles: &HashMap<String, String>,
    def_rel: Option<&str>,
) -> String {
    if !gid.starts_with(PREFIX) {
        return gid.to_string();
    }
    if usages.is_empty() {
        let stem = def_rel
            .and_then(|r| Path::new(r).file_stem())
            .map(|s| s.to_string_lossy().to_string())
            .unwrap_or_else(|| "unref".into());
        return format!("{}model.{}", PREFIX, stem);
    }
    let cat_score = |c: &str| {
        if c == "entity" {
            0
        } else if c == "attachable" {
            1
        } else if c.contains("SP2") {
            2
        } else if c.contains("SP1") {
            3
        } else {
            4
        }
    };
    let mut sorted: Vec<&Usage> = usages.iter().collect();
    sorted.sort_by(|a, b| {
        (
            cat_score(&a.category),
            a.role != "default",
            &a.ident,
            &a.role,
        )
            .cmp(&(
                cat_score(&b.category),
                b.role != "default",
                &b.ident,
                &b.role,
            ))
    });
    let first = sorted[0];
    if usages.len() > 15 {
        let all_roles: HashSet<&str> = usages.iter().map(|u| u.role.as_str()).collect();
        if all_roles.contains("dfhqgk") {
            return format!("{}item_glint_1st_person", PREFIX);
        }
        if all_roles.contains("rcvngv") {
            return format!("{}tool_3d_base", PREFIX);
        }
        if usages.iter().all(|u| u.ident.contains("shulker_box")) {
            return format!("{}shulker_box", PREFIX);
        }
        if usages.iter().all(|u| u.ident.contains("candle")) {
            return format!("{}candle", PREFIX);
        }
        if usages
            .iter()
            .any(|u| u.ident.contains("allium") || u.ident.contains("tulip"))
        {
            return format!("{}plant_cross", PREFIX);
        }
    }
    let suffix = roles
        .get(&first.role)
        .cloned()
        .unwrap_or_else(|| first.role.clone());
    let sp2 = if first.category.contains("subpack:SP2") {
        "sp2."
    } else {
        ""
    };
    let id = strip_ns(&first.ident);
    if first.role == "default" || suffix == "default" {
        format!("{}{}{}", PREFIX, sp2, id)
    } else {
        format!("{}{}{}.{}", PREFIX, sp2, id, suffix)
    }
}

struct OrphanName {
    name: String,
    method: &'static str,
    confidence: &'static str,
    note: String,
}

fn family_from_uses(pack: &Pack, gids: &[String]) -> String {
    let names: Vec<String> = gids
        .iter()
        .filter_map(|g| pack.uses.get(g).and_then(|u| u.first()))
        .map(|u| {
            short_ident(&u.ident)
                .split('.')
                .next()
                .unwrap_or("")
                .to_string()
        })
        .collect();
    if names.is_empty() {
        return "model".into();
    }
    let toks: Vec<Vec<&str>> = names.iter().map(|n| n.split('_').rev().collect()).collect();
    let mut common: Vec<&str> = Vec::new();
    let min_len = toks.iter().map(|t| t.len()).min().unwrap_or(0);
    for i in 0..min_len {
        let t0 = toks[0][i];
        if toks.iter().all(|t| t[i] == t0) {
            common.insert(0, t0);
        } else {
            break;
        }
    }
    if !common.is_empty() {
        return common.join("_");
    }
    let mut counts: Vec<(&String, usize)> = Vec::new();
    for n in &names {
        match counts.iter_mut().find(|(k, _)| *k == n) {
            Some(x) => x.1 += 1,
            None => counts.push((n, 1)),
        }
    }
    let mut best = counts[0];
    for c in &counts {
        if c.1 > best.1 {
            best = *c;
        }
    }
    best.0.clone()
}

fn resolve_orphans(pack: &Pack, dec: &BoneDecoder) -> BTreeMap<String, OrphanName> {
    let orphans = pack.orphans();
    let mut result: BTreeMap<String, OrphanName> = BTreeMap::new();

    let mut loose_used: HashMap<String, Vec<String>> = HashMap::new();
    for (gid, d) in &pack.defs {
        if pack.uses.contains_key(gid) {
            loose_used
                .entry(fingerprint(&d.geo, true))
                .or_default()
                .push(gid.clone());
        }
    }

    // --- dye series: 16 structurally identical orphans in one file
    let mut series: BTreeMap<(String, String), Vec<String>> = BTreeMap::new();
    for gid in &orphans {
        let d = &pack.defs[gid];
        series
            .entry((d.rel.clone(), fingerprint(&d.geo, true)))
            .or_default()
            .push(gid.clone());
    }
    let mut dye_masks: HashMap<&str, Mask> = HashMap::new();
    for (gid, d) in &pack.defs {
        for u in pack.uses.get(gid).into_iter().flatten() {
            let short = short_ident(&u.ident);
            if let Some(col) = short.strip_suffix("_dye") {
                if let Some(dye) = DYES.iter().find(|d| **d == col) {
                    let m = Mask::of(&d.geo);
                    let e = dye_masks.entry(dye).or_insert(Mask {
                        set: HashSet::new(),
                        bbox: (i64::MAX, i64::MAX, i64::MIN, i64::MIN),
                    });
                    e.set.extend(m.set);
                    e.bbox = (
                        e.bbox.0.min(m.bbox.0),
                        e.bbox.1.min(m.bbox.1),
                        e.bbox.2.max(m.bbox.2),
                        e.bbox.3.max(m.bbox.3),
                    );
                }
            }
        }
    }
    for members in series.values() {
        if members.len() != 16 {
            continue;
        }
        let family = decoded_bone_label(dec, &pack.defs[&members[0]].geo);
        let mut order = members.clone();
        order.sort_by_key(|m| pack.defs[m].index);
        // strongest signal: each member shares atlas texels with exactly one '<colour>_dye' item
        let mut by_texture: HashMap<&String, &str> = HashMap::new();
        for gid in members {
            let mine = Mask::of(&pack.defs[gid].geo);
            let mut hits: Vec<(usize, &str)> =
                dye_masks.iter().map(|(c, m)| (mine.inter(m), *c)).collect();
            hits.sort_by(|a, b| b.cmp(a));
            if let Some(h) = hits.first() {
                if h.0 > 0 && (hits.len() == 1 || h.0 > hits[1].0) {
                    by_texture.insert(gid, h.1);
                }
            }
        }
        let distinct: HashSet<&&str> = by_texture.values().collect();
        let use_texture = by_texture.len() == 16 && distinct.len() == 16;
        for (rank, gid) in order.iter().enumerate() {
            // fallback: the generator emits dye series in alphabetical dye order
            let dye = if use_texture {
                by_texture[gid]
            } else {
                DYES[rank]
            };
            result.insert(
                gid.clone(),
                OrphanName {
                    name: format!("{}.{}", family, dye),
                    method: if use_texture {
                        "dye_series_dye_texture"
                    } else {
                        "dye_series_file_order"
                    },
                    confidence: if use_texture { "high" } else { "medium" },
                    note: String::new(),
                },
            );
        }
    }

    // --- atlas-region overlap (shared atlases >= 256px): the sampled texels identify the item
    let mut atlas_used: HashMap<(i64, i64), Vec<(Mask, String)>> = HashMap::new();
    for (gid, d) in &pack.defs {
        let (w, h) = tex_size(&d.geo);
        if w >= 256 {
            if let Some(u) = pack.uses.get(gid).and_then(|u| u.first()) {
                atlas_used
                    .entry((w, h))
                    .or_default()
                    .push((Mask::of(&d.geo), u.ident.clone()));
            }
        }
    }
    for gid in &orphans {
        if result.contains_key(gid) {
            continue;
        }
        let g = &pack.defs[gid].geo;
        let Some(cands) = atlas_used.get(&tex_size(g)) else {
            continue;
        };
        let mine = Mask::of(g);
        if mine.set.is_empty() {
            continue;
        }
        let mut iou: HashMap<&str, f64> = HashMap::new();
        let mut cov: HashMap<&str, f64> = HashMap::new();
        for (mask, ident) in cands {
            let i = mine.inter(mask);
            if i > 0 {
                let v = i as f64 / (mine.set.len() + mask.set.len() - i) as f64;
                let c = i as f64 / mine.set.len() as f64;
                let e = iou.entry(ident).or_insert(0.0);
                *e = e.max(v);
                let e = cov.entry(ident).or_insert(0.0);
                *e = e.max(c);
            }
        }
        let mut ranked: Vec<(&str, f64)> = iou.into_iter().collect();
        ranked.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap().then(a.0.cmp(b.0)));
        let Some(&(ident, best)) = ranked.first() else {
            continue;
        };
        let runner = ranked.get(1).map(|r| r.1).unwrap_or(0.0);
        if best >= 0.3 && best - runner >= 0.1 && cov[ident] >= 0.5 {
            result.insert(
                gid.clone(),
                OrphanName {
                    name: format!("{}.alt_{}", short_ident(ident), decoded_bone_label(dec, g)),
                    method: "atlas_uv_overlap",
                    confidence: if best >= 0.6 { "high" } else { "medium" },
                    note: format!(
                        "texel IoU {:.2}{}",
                        best,
                        ranked
                            .get(1)
                            .map(|r| format!(", runner-up {} ({:.2})", short_ident(r.0), r.1))
                            .unwrap_or_default()
                    ),
                },
            );
        }
    }

    // --- family-level fallbacks
    for gid in &orphans {
        if result.contains_key(gid) {
            continue;
        }
        let g = &pack.defs[gid].geo;
        let (w, h) = tex_size(g);
        let tex = format!("tex{}x{}", w, h);
        let entry = match loose_used.get(&fingerprint(g, true)) {
            Some(sib) => OrphanName {
                name: format!("{}.unused_{}", family_from_uses(pack, sib), tex),
                method: "same_shape_as_referenced",
                confidence: "family",
                note: format!(
                    "same shape as {} referenced model(s), different UV/texture size",
                    sib.len()
                ),
            },
            None => OrphanName {
                name: format!("{}.unused_{}", decoded_bone_label(dec, g), tex),
                method: "decoded_bone_names",
                confidence: "family",
                note: "named from decoded bone names only".into(),
            },
        };
        result.insert(gid.clone(), entry);
    }
    result
}

// --------------------------------------------------------------------------- report

#[derive(Serialize, Clone, Default)]
pub struct PackReport {
    pub pack: String,
    pub geometries: usize,
    pub renamed: usize,
    pub files_changed: usize,
    pub tiers: BTreeMap<String, usize>,
    pub orphan_methods: BTreeMap<String, usize>,
    pub molang_parse_errors: usize,
    pub needs_manual_check: usize,
    pub errors: Vec<String>,
    pub already_renamed: bool,
    pub report_path: String,
    pub checklist_path: String,
    pub mapping_path: String,
}

struct Entry {
    old: String,
    new: String,
    tier: &'static str,
    method: String,
    note: String,
}

const TIER_HELP: &[(&str, &str)] = &[
    ("referenced_role_conflict", "The old role table and the entity's own Molang disagree; the Molang label was used. Check that the variant name fits the model."),
    ("orphan_medium", "Unused model matched to an item with medium confidence. Check the item name."),
    ("orphan_family_only", "Unused model: only its family is known (e.g. slab, glow_berries), not the exact item."),
    ("referenced_role_unresolved", "Used by the right entity/item, but the variant suffix is still the minifier's raw 6-letter token."),
];

fn write_outputs(root: &Path, entries: &[Entry], report: &mut PackReport) -> Result<(), String> {
    let name = root
        .file_name()
        .map(|n| n.to_string_lossy().to_string())
        .unwrap_or_else(|| "pack".into());
    // Written next to the pack (not inside it), so the files never end up in a packaged .mcpack.
    let dir = root
        .parent()
        .filter(|p| p.as_os_str().len() > 0)
        .unwrap_or(root);
    let mapping_path = dir.join(format!("{} - geometry mapping.json", name));
    let report_path = dir.join(format!("{} - geometry rename report.json", name));
    let check_path = dir.join(format!("{} - geometry manual check.txt", name));

    let mapping: BTreeMap<&str, &str> = entries
        .iter()
        .map(|e| (e.old.as_str(), e.new.as_str()))
        .collect();
    std::fs::write(
        &mapping_path,
        serde_json::to_string_pretty(&mapping).unwrap(),
    )
    .map_err(|e| format!("Could not write {}: {}", mapping_path.display(), e))?;

    let per: BTreeMap<&str, Value> = entries
        .iter()
        .map(|e| {
            (
                e.old.as_str(),
                json!({"new": e.new, "tier": e.tier, "method": e.method, "note": e.note}),
            )
        })
        .collect();
    report.report_path = report_path.to_string_lossy().to_string();
    report.checklist_path = check_path.to_string_lossy().to_string();
    report.mapping_path = mapping_path.to_string_lossy().to_string();
    let full = json!({"summary": report, "geometries": per});
    std::fs::write(&report_path, serde_json::to_string_pretty(&full).unwrap())
        .map_err(|e| format!("Could not write {}: {}", report_path.display(), e))?;

    let mut txt = String::new();
    txt.push_str(&format!(
        "Geometry renamer - manual check list\nPack: {}\n\n",
        root.display()
    ));
    if report.errors.is_empty() {
        txt.push_str("ERRORS: none. Validation passed.\n\n");
    } else {
        txt.push_str(&format!("ERRORS ({}):\n", report.errors.len()));
        for e in &report.errors {
            txt.push_str(&format!("  ! {}\n", e));
        }
        txt.push('\n');
    }
    for (tier, help) in TIER_HELP {
        let rows: Vec<&Entry> = entries.iter().filter(|e| e.tier == *tier).collect();
        if rows.is_empty() {
            continue;
        }
        txt.push_str(&format!("== {} ({}) ==\n{}\n", tier, rows.len(), help));
        for e in rows {
            let short = e.new.strip_prefix(PREFIX).unwrap_or(&e.new);
            let old = e.old.strip_prefix(PREFIX).unwrap_or(&e.old);
            if e.note.is_empty() {
                txt.push_str(&format!("  {}  ->  {}\n", old, short));
            } else {
                txt.push_str(&format!("  {}  ->  {}   [{}]\n", old, short, e.note));
            }
        }
        txt.push('\n');
    }
    std::fs::write(&check_path, txt)
        .map_err(|e| format!("Could not write {}: {}", check_path.display(), e))?;
    Ok(())
}

// --------------------------------------------------------------------------- driver

/// Finds extracted resource packs (folder with manifest.json + models/) in a workspace.
pub fn find_pack_roots(workspace: &Path) -> Vec<PathBuf> {
    let mut out = Vec::new();
    for e in WalkDir::new(workspace).into_iter().filter_map(|e| e.ok()) {
        if e.file_type().is_file() && e.file_name() == "manifest.json" {
            let dir = e.path().parent().unwrap_or(workspace).to_path_buf();
            let in_subpack = dir
                .strip_prefix(workspace)
                .map(|r| r.components().any(|c| c.as_os_str() == "subpacks"))
                .unwrap_or(false);
            if !in_subpack && dir.join("models").is_dir() {
                out.push(dir);
            }
        }
    }
    out.sort();
    out
}

pub fn has_packed_brarchives(workspace: &Path) -> bool {
    WalkDir::new(workspace)
        .into_iter()
        .filter_map(|e| e.ok())
        .any(|e| e.file_type().is_dir() && e.file_name() == "__brarchive")
}

/// Renames every obfuscated geometry in one extracted pack, in place.
/// `log(message, level)` receives progress lines (levels: info, success, warning, error).
pub fn rename_pack(root: &Path, log: &dyn Fn(&str, &str)) -> Result<PackReport, String> {
    let mut report = PackReport {
        pack: root.to_string_lossy().to_string(),
        ..Default::default()
    };
    log(
        "Reading models, entities, attachables and render controllers...",
        "info",
    );
    let pack = Pack::load(root);
    if !pack.json_failures.is_empty() {
        log(
            &format!(
                "{} JSON file(s) could not be parsed and were skipped (they are left untouched).",
                pack.json_failures.len()
            ),
            "warning",
        );
    }
    let obf_defs = pack.defs.keys().filter(|g| is_obfuscated(g)).count();
    let obf_uses = pack.uses.keys().filter(|g| is_obfuscated(g)).count();
    if obf_defs == 0 && obf_uses == 0 {
        let already = pack.defs.keys().any(|g| g.starts_with(PREFIX));
        report.already_renamed = already;
        report.geometries = pack.defs.len();
        log(
            if already {
                "No obfuscated geometry IDs left - this pack looks already renamed. Skipping."
            } else {
                "No Actions & Stuff geometries found in this pack. Skipping."
            },
            "warning",
        );
        return Ok(report);
    }
    log(
        &format!(
            "Found {} geometry definitions ({} obfuscated), {} referenced.",
            pack.defs.len(),
            obf_defs,
            pack.uses.len()
        ),
        "info",
    );

    let roles = role_dictionary(&pack);
    let dec = BoneDecoder::new(&pack.vocab);
    log("Resolving render-controller Molang...", "info");
    let (branches, molang_errors) = resolve_render_controllers(&pack);
    report.molang_parse_errors = molang_errors;
    let per_entity = controller_labels_per_entity(&pack, &branches);

    log(
        "Identifying unreferenced geometries (atlas overlap, dye series, shapes, bone names)...",
        "info",
    );
    let orphans = resolve_orphans(&pack, &dec);

    // 1. base names
    let all: BTreeSet<String> = pack.defs.keys().chain(pack.uses.keys()).cloned().collect();
    let mut base: HashMap<String, String> = HashMap::new();
    let mut tier: HashMap<String, &'static str> = HashMap::new();
    let mut method: HashMap<String, String> = HashMap::new();
    let mut note: HashMap<String, String> = HashMap::new();
    let empty = Vec::new();
    for g in &all {
        base.insert(
            g.clone(),
            canonical_name(
                g,
                pack.uses.get(g).unwrap_or(&empty),
                &roles,
                pack.defs.get(g).map(|d| d.rel.as_str()),
            ),
        );
    }
    for (g, o) in &orphans {
        if !is_obfuscated(g) {
            continue; // vanilla overrides (geometry.boat, geometry.humanoid.*) keep their IDs
        }
        base.insert(g.clone(), format!("{}unused.{}", PREFIX, o.name));
        tier.insert(
            g.clone(),
            match o.confidence {
                "high" => "orphan_high",
                "medium" => "orphan_medium",
                _ => "orphan_family_only",
            },
        );
        method.insert(g.clone(), o.method.to_string());
        note.insert(g.clone(), o.note.clone());
    }

    // 2. referenced: grade (and fix) the role part of the name using the entity's own Molang
    let raw_role = Regex::new(r"^[a-z]{6}$").unwrap();
    let is_raw = |r: &str| raw_role.is_match(r) && !pack.vocab.contains(r);
    for g in &all {
        if tier.contains_key(g) {
            continue;
        }
        if !is_obfuscated(g) {
            tier.insert(g.clone(), "vanilla_untouched");
            continue;
        }
        let Some(u) = pack.uses.get(g) else {
            tier.insert(g.clone(), "orphan_family_only");
            continue;
        };
        let mut sorted: Vec<&Usage> = u.iter().collect();
        sorted.sort_by(|a, b| {
            (
                a.category != "entity",
                a.category != "attachable",
                &a.category,
                &a.ident,
                &a.role,
            )
                .cmp(&(
                    b.category != "entity",
                    b.category != "attachable",
                    &b.category,
                    &b.ident,
                    &b.role,
                ))
        });
        let role = sorted[0].role.clone();
        let tv = roles.get(&role).cloned().unwrap_or_else(|| role.clone());
        let lab = sorted
            .iter()
            .filter(|x| x.role == role)
            .find_map(|x| per_entity.get(&x.ident).and_then(|m| m.get(&role)).cloned())
            .filter(|l| !l.starts_with("v."));
        let mut t = "referenced_ok";
        method.insert(g.clone(), "entity_or_attachable_binding".into());
        if role != "default" {
            match &lab {
                Some(l) => {
                    let use_molang = if tv == role && is_raw(&role) {
                        t = "referenced_named_by_molang";
                        true
                    } else if label_conflicts(&tv, l) {
                        t = "referenced_role_conflict";
                        note.insert(
                            g.clone(),
                            format!("role table said '{}', Molang says '{}'", tv, l),
                        );
                        true
                    } else {
                        false
                    };
                    let b = base[g].clone();
                    if use_molang && b.ends_with(&format!(".{}", tv)) {
                        base.insert(
                            g.clone(),
                            format!("{}{}", &b[..b.len() - tv.len()], l.replace('.', "_")),
                        );
                    }
                }
                None if tv == role && is_raw(&role) => t = "referenced_role_unresolved",
                None => {}
            }
        }
        tier.insert(g.clone(), t);
    }

    // 3. de-duplicate with content-hash suffixes (stable across pack versions)
    let fp: HashMap<&String, String> = all
        .iter()
        .map(|g| {
            (
                g,
                pack.defs
                    .get(g)
                    .map(|d| fingerprint(&d.geo, false))
                    .unwrap_or_else(|| g.clone()),
            )
        })
        .collect();
    let mut groups: BTreeMap<String, Vec<&String>> = BTreeMap::new();
    for g in &all {
        let mut b = base[g].clone();
        // A new name must never look like an obfuscated ID (prefix + exactly 6 letters),
        // otherwise it could collide with one and re-runs could not tell renamed packs apart.
        if is_obfuscated(&b) && b != *g {
            b.push_str("_model");
        }
        groups.entry(b).or_default().push(g);
    }
    let mut rename: BTreeMap<String, String> = BTreeMap::new();
    let mut taken: HashSet<String> = HashSet::new();
    for (stem, members) in &groups {
        let mut members = members.clone();
        members.sort_by(|a, b| fp[a].cmp(&fp[b]).then(a.cmp(b)));
        for g in &members {
            let tag = &fp[g][..4.min(fp[g].len())];
            let mut n = if members.len() == 1 {
                stem.clone()
            } else {
                format!("{}_{}", stem, tag)
            };
            let mut k = 1;
            while taken.contains(&n) || (groups.contains_key(&n) && n != *stem) {
                k += 1;
                n = format!("{}_{}_{}", stem, tag, k);
            }
            taken.insert(n.clone());
            rename.insert((*g).clone(), n);
        }
    }

    // 4. apply: rewrite every exact old ID in every JSON file of the pack (subpacks included)
    let active: HashMap<&str, &str> = rename
        .iter()
        .filter(|(o, n)| o != n && is_obfuscated(o))
        .map(|(o, n)| (o.as_str(), n.as_str()))
        .collect();
    log(
        &format!("Rewriting {} geometry IDs across the pack...", active.len()),
        "info",
    );
    let id_re = Regex::new(r"geometry\.oreville_ans\.[a-z0-9_]+").unwrap();
    let mut changed = 0;
    for (rel, path) in json_files(root) {
        let Ok(bytes) = std::fs::read(&path) else {
            continue;
        };
        let Ok(text) = String::from_utf8(bytes) else {
            continue;
        }; // leave non-UTF-8 files untouched
        let new_text = id_re.replace_all(&text, |c: &regex::Captures| {
            active
                .get(&c[0])
                .map(|s| s.to_string())
                .unwrap_or_else(|| c[0].to_string())
        });
        if new_text != text {
            std::fs::write(&path, new_text.as_bytes())
                .map_err(|e| format!("Could not write {}: {}", rel, e))?;
            changed += 1;
        }
    }
    report.files_changed = changed;
    report.renamed = active.len();

    // 5. validate the rewritten pack
    log("Validating renamed pack...", "info");
    let after = Pack::load(root);
    let broken_before: HashSet<&String> = pack
        .uses
        .keys()
        .filter(|g| g.starts_with(PREFIX) && !pack.defs.contains_key(*g))
        .collect();
    let broken_after: Vec<&String> = after
        .uses
        .keys()
        .filter(|g| g.starts_with(PREFIX) && !after.defs.contains_key(*g))
        .collect();
    if broken_after.len() > broken_before.len() {
        report.errors.push(format!(
            "{} geometry reference(s) point to IDs that no longer exist, e.g. {}",
            broken_after.len() - broken_before.len(),
            broken_after
                .iter()
                .take(5)
                .map(|s| s.as_str())
                .collect::<Vec<_>>()
                .join(", ")
        ));
    }
    let leftovers: Vec<&String> = after
        .defs
        .keys()
        .chain(after.uses.keys())
        .filter(|g| active.contains_key(g.as_str()))
        .collect();
    if !leftovers.is_empty() {
        report.errors.push(format!(
            "{} obfuscated ID(s) were not replaced",
            leftovers.len()
        ));
    }
    if after.defs.len() != pack.defs.len() {
        report.errors.push(format!(
            "Geometry count changed: {} before, {} after",
            pack.defs.len(),
            after.defs.len()
        ));
    }
    if after.json_failures.len() > pack.json_failures.len() {
        report.errors.push(format!(
            "{} JSON file(s) no longer parse after renaming",
            after.json_failures.len() - pack.json_failures.len()
        ));
    }
    if molang_errors > 0 {
        log(&format!("{} render-controller expression(s) could not be parsed; their roles fall back to the static table.", molang_errors), "warning");
    }

    // 6. outputs
    let entries: Vec<Entry> = rename
        .iter()
        .map(|(o, n)| Entry {
            old: o.clone(),
            new: n.clone(),
            tier: tier.get(o).copied().unwrap_or("referenced_ok"),
            method: method.get(o).cloned().unwrap_or_default(),
            note: note.get(o).cloned().unwrap_or_default(),
        })
        .collect();
    report.geometries = entries.len();
    for e in &entries {
        *report.tiers.entry(e.tier.to_string()).or_default() += 1;
        if e.tier.starts_with("orphan") {
            *report.orphan_methods.entry(e.method.clone()).or_default() += 1;
        }
    }
    report.needs_manual_check = entries
        .iter()
        .filter(|e| TIER_HELP.iter().any(|(t, _)| *t == e.tier))
        .count()
        + report.errors.len();
    write_outputs(root, &entries, &mut report)?;
    Ok(report)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bone_cipher_decodes_known_names() {
        let vocab: HashSet<String> = [
            "dorsal", "person", "banner", "post", "bar", "bite", "ribbon",
        ]
        .iter()
        .map(|s| s.to_string())
        .collect();
        let d = BoneDecoder::new(&vocab);
        assert_eq!(d.decode("d67l"), "left");
        assert_eq!(d.decode("ja89l"), "right");
        assert_eq!(d.decode("8dgo2"), "glow2");
        assert_eq!(d.decode("32ff6jhgkl32j"), "bannerpostbar");
        assert_eq!(d.decode("5gjk2d7af_3"), "dorsalfin_3");
        assert_eq!(d.decode("rightleg"), "rightleg"); // plaintext untouched
    }

    #[test]
    fn molang_nested_ternary_branches() {
        let e = "v.cdrzno?(v.aybhly?Geometry.a:Geometry.b):Array.x[v.i]";
        let tree = Parser::parse(e).unwrap();
        let mut arrays = serde_json::Map::new();
        arrays.insert("Array.x".into(), json!(["Geometry.default", "Geometry.c"]));
        let labels: HashMap<String, String> = [("cdrzno", "baby"), ("aybhly", "snowy")]
            .iter()
            .map(|(a, b)| (a.to_string(), b.to_string()))
            .collect();
        let mut out = Vec::new();
        enumerate_branches(&tree, &arrays, &labels, vec![], &mut out, 0);
        let find = |k: &str| out.iter().find(|(_, g)| g == k).map(|(p, _)| p.join("."));
        assert_eq!(find("a").unwrap(), "baby.snowy");
        assert_eq!(find("c").unwrap(), "not_baby.v.i_1");
        assert!(Parser::parse("Array.a[q.life_time*24]").is_ok());
        assert!(Parser::parse("Array.a[!v.b?v.c]").is_ok());
    }

    /// Full run on a real pack copy: RENAMER_TEST_PACK=<extracted pack> cargo test -- --ignored
    #[test]
    #[ignore]
    fn rename_real_pack() {
        let Ok(p) = std::env::var("RENAMER_TEST_PACK") else {
            return;
        };
        let r = rename_pack(Path::new(&p), &|m, l| println!("[{}] {}", l, m)).unwrap();
        println!("{}", serde_json::to_string_pretty(&r).unwrap());
        assert!(r.errors.is_empty(), "{:?}", r.errors);
    }

    /// Extract + rename, like the app does: RENAMER_TEST_WORKSPACE=<folder with __brarchive packs>
    #[test]
    #[ignore]
    fn extract_then_rename_workspace() {
        let Ok(p) = std::env::var("RENAMER_TEST_WORKSPACE") else {
            return;
        };
        let ws = Path::new(&p);
        let extracted =
            crate::utils::extract_brarchives_in_workspace_impl(None, ws, "test").unwrap();
        println!("extracted: {}", extracted);
        let roots = find_pack_roots(ws);
        assert!(!roots.is_empty(), "no extracted pack found");
        for root in roots {
            let r = rename_pack(&root, &|m, l| println!("[{}] {}", l, m)).unwrap();
            println!(
                "{} -> renamed {}, tiers {:?}, errors {:?}",
                r.pack, r.renamed, r.tiers, r.errors
            );
            assert!(r.errors.is_empty(), "{:?}", r.errors);
        }
    }
}
