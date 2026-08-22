## [2.2.13]

### Fixed
- Fixed the Torch texture (and potentially other untouched assets) rendering as missing/purple in-game, caused by the "Replace Unchanged" feature shipping raw DRM-encrypted files that Minecraft could no longer decrypt.

### Removed
- Removed "Replace Unchanged" entirely from the Create Patch tool. Every patch now ships fully decrypted assets instead of relying on DRM decryption that can no longer be guaranteed to work.
- Removed "Extract Brarchives" from the normal patching flow and from the Create Patch tool, since it only existed to support the now-removed "Replace Unchanged" feature. The standalone Extract Brarchives utility is unaffected.

## [2.2.11]

### Security
- Improved app security with a strict content security policy and secure link restrictions.
- Fixed a potential path-traversal vulnerability when unpacking `.brarchive` files.

### Fixed
- Fixed missing or purple textures in-game (often on mobs) caused by the "Replace Unchanged" feature.
- Fixed "checksum mismatch" errors when applying patches created with the Create Patch tool.
- Fixed crashes and data loss during patch creation when handling encrypted or unreadable `.brarchive` containers.
- Fixed Marketplace-mode patching failures caused by improper archive extraction attempts.
- Improved Marketplace auto-detect to consistently pick the correct Actions & Stuff pack.
- Disabled "Replace Unchanged" by default in the Create Patch tool as it is experimental.
- Fixed app settings being overwritten between installs by moving them to your Windows user profile.

### Added
- "Replace Unchanged" now restores whole untouched `.brarchive` containers instead of loose files.
- Added a one-click anonymous reporting tool for the NVIDIA mob texture corruption bug.
- Added a comprehensive Wiki guide (`docs/WIKI.md`) explaining all tools and features.
- Fixed Dependabot configuration to correctly monitor and update dependencies.

