### GitHub Changelog & Security Agent Rules

**1. Version Changelog Generation**
On every version change, you MUST update the `version_log.md` file located in the root of the workspace.

- **Scope:** Completely overwrite `version_log.md` so it contains _only_ the release notes for the most recent version. Do not retain past version history in this specific file.
- **Format:** Strictly use GitHub Markdown. Start with the version number as an `## [X.X.X]` header.
- **Categorization:** Group all changes under the following `###` headers as applicable: `Added`, `Changed`, `Fixed`, and `Removed`.
- **Language & Tone:** Write in simple, plain English targeted at end-users. Translate complex technical commits or backend restructuring into functional, user-facing benefits.
- **Concision:** Output _only_ the changelog content. Do not include introductory text, conversational filler, or explanations of your work.
- **Exclusions & Updater Noise:** Completely ignore and omit any internal system data, deployment hashes, auto-generated release keys, and **any dynamic keys that change automatically for updaters**. These technical artifacts must never appear in the changelog.

**2. Strict Security Protocol**

- **Zero-Disclosure:** You must never output, reference, or confirm the existence of any security keys, API tokens, or credentials in your responses or generated files.

### Rust Agent Rules: Structuring, Refactoring & Safety

## 1. Safety & Verification First (Mandatory Pre/Post Actions)

- **Local Backup Protocol:** Before modifying any file, you MUST ensure a local backup exists. If operating in a terminal-enabled environment, create a quick copy of the target file (e.g., `cp main.rs main.rs.bak`) or ensure the git working tree is clean.
- **The "Does it Compile?" Rule:** After ANY code modification, you must verify the changes by running `cargo check`. If tests exist, run `cargo test`.
- **No Blind Commits:** Never assume code works. If `cargo check` throws errors, you must fix the borrow checker, typing, or syntax issues before finalizing the task.

## 2. Incremental Refactoring (The "Boy Scout" Rule)

- **No Massive Overhauls:** The project is migrating away from 4 main files into a multi-module (`mod`) architecture. Do NOT attempt to refactor everything at once.
- **Opportunistic Extraction:** When asked to add a feature or fix a bug in a specific section of the code, extract _only that specific section_ into its own module (file/folder) as part of the update.
- **Module Structure:** Use idiomatic Rust module structuring. Create a new `.rs` file for the extracted `struct`s/`enum`s/`impl` blocks, and properly expose them using `pub` and `mod` declarations in the parent file.

## 3. Idiomatic Documentation & "Better Comments" Standardization

- **Doc Comments:** All new public functions, structs, and modules must be documented using idiomatic Rust doc comments (`///`). Explain _what_ it does and _why_, not just _how_.
- **Better Comments Integration:** You MUST format all internal line comments (`//`) to be strictly compatible with the "Better Comments" extension for visual categorization.
- **Highlights:** Start comments with `// *` for important information.
- **Alerts:** Start comments with `// !` for warnings, errors, or deprecated code.
- **Queries:** Start comments with `// ?` for questions or code that requires review.
- **TODOs:** Start comments with `// TODO:` for future tasks, tests, or refactoring.
- **Strikethrough:** Start comments with `////` to explicitly mark commented-out code that shouldn't be there permanently.
- **Standard Tooling:** Ensure all output code conforms to standard Rust formatting. Run `cargo fmt` and `cargo clippy` to ensure the code is idiomatic and clean.
- **Clean Imports:** When moving code to new files, ensure you clean up unused `use` statements in the original file.

## 4. Windows-Specific API & NTFS Commenting

- **Context-Aware Comments:** For logic that interacts with Windows APIs (Win32/NTFS), include the specific Win32 function names in the comments (e.g., `/// Uses NtCreateFile to open the directory`). This is crucial for maintainers.
- **ntdll.dll Functions:** If you use functions from `ntdll.dll` (like `NtCreateFile`, `NtQueryInformationFile`, etc.), you MUST import them using the `windows-sys` crate (e.g., `use windows_sys::Win32::System::LibraryLoader::GetProcAddress;`). Do not use `unsafe extern "system"` blocks without proper imports.
- **NTFS Streams for Attributes:** When using `NtQueryInformationFile` with `FileDispositionInformation` or `FileAttributeTagInformation`, you MUST use `windows-sys` imports. Do NOT invent import paths or use `windows` crate without explicit feature flags.
- **Windows Version Specifics:** If using version-specific APIs, include comments about minimum Windows versions (e.g., `/// Requires Windows 10 1607+`).
- **Error Handling:** When calling Windows APIs, always use `windows-sys` imports. Do NOT use `windows::Error` directly; instead, use `windows::Win32::Foundation::GetLastError()` after a failed call to convert the error code to a Rust `Result`.
- **Use `try_` Prefix:** For fallible Windows API calls that return a `Result` via `windows-sys`, use the `try_` prefix (e.g., `try_NtCreateFile`).
- **Proper Error Mapping:** When converting Win32 error codes to Rust `Result`, use `windows::Win32::Foundation::GetLastError()` to get the error code, then create a `Result` with the appropriate `windows-sys::Win32::Foundation::WIN32_ERROR` enum variant.
