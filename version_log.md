## [2.2.9]

### Added
- Optional, anonymous hardware diagnostics to help us track down rare RTX rendering bugs that only affect specific graphics cards and drivers. You choose whether to enable this on first launch, and can turn it off anytime in Settings.
- A "View Last Sent Data" button so you can always see exactly what information was sent.
- A "Delete My Data" button in Settings to permanently erase your diagnostic data on request.
- Bug reports can now include your Minecraft content log automatically. If logging isn't turned on yet, or the log is too old, too small, or too large, the Patcher now tells you exactly what to do (restart Minecraft, reproduce the issue, and try again).
- Bug reports can now optionally include recent GPU driver activity, helping us spot graphics driver crashes tied to the bug.
- A new "Bug Category" selector lets you tag your report with one or more categories (Texture Messup, Texture Purple, DeltaX Problem, No Dynamic Light, Wrong Model for Mob) so issues get triaged faster.
- Bug reports now include more of your system's specs (CPU, RAM, Windows version, RTX/graphics settings) so our team can reproduce issues more reliably.

### Changed
- Updated our Privacy Policy with a new section explaining exactly what the optional hardware diagnostics feature collects, why, and how to opt out or delete your data.

### Fixed
- Removed a leftover debug message that printed internal connection details to the console on startup.
