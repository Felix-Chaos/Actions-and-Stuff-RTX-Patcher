## [2.2.11]

### Security
- Enabled a strict content security policy for the app window (previously disabled), restricted the "open link" command to http(s) URLs only, and fixed a path-traversal edge case when unpacking `.brarchive` files.

### Fixed
- Turned off the Create Patch tool's "Replace Unchanged" option by default. It could ship patches where some assets stayed DRM-encrypted with no way for Minecraft to decrypt them, causing textures/models/sounds to silently fail to load. It's now clearly labeled as experimental if you re-enable it.
- Settings and diagnostics files (`settings.json`, `telemetry.json`) now save to your Windows user profile instead of next to the app, so they're no longer shared or overwritten between different installs.

### Added
- Added a full Wiki guide (`docs/WIKI.md`) covering every tab and tool, including when you actually need Extract Brarchives and how the Create Patch workflow works.
- Dependabot now actually watches for dependency updates across npm, Cargo, and GitHub Actions (its config was previously misconfigured and silently doing nothing).

## [2.2.10]

### Changed
- Hardware/RTX diagnostics (for users who opted in) are now checked fresh every time you open the Patcher instead of once per version — so changes like switching your BetterRTX preset show up sooner. We still only actually upload something if it's different from what we last sent, so nothing extra is sent on every launch.
- Diagnostics now include a one-way, anonymous hash derived from your PC so re-installing the Patcher doesn't create a second, duplicate hardware entry on our end. The original identifying value never leaves your machine, only its hash.

### Fixed
- Fixed the default folder suggested when picking your patched pack folder in the Patch Generator utility — it could point to the wrong location on some installs.
