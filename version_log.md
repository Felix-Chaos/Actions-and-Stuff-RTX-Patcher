## [2.2.10]

### Changed
- Hardware/RTX diagnostics (for users who opted in) are now checked fresh every time you open the Patcher instead of once per version — so changes like switching your BetterRTX preset show up sooner. We still only actually upload something if it's different from what we last sent, so nothing extra is sent on every launch.
- Diagnostics now include a one-way, anonymous hash derived from your PC so re-installing the Patcher doesn't create a second, duplicate hardware entry on our end. The original identifying value never leaves your machine, only its hash.

### Fixed
- Fixed the default folder suggested when picking your patched pack folder in the Patch Generator utility — it could point to the wrong location on some installs.
