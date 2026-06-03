# Setting Up GitHub Auto-Updater for Tauri V3 Patcher

Tauri v2 includes a built-in auto-updater. To enable updates for users, you need to sign your releases with a private key, compile the installer binaries, and host an update metadata file (`updater.json`) in your GitHub repository.

Follow these step-by-step instructions to set it up:

---

## Step 1: Generate Signature Keys
Tauri uses public-key cryptography to verify that update files have not been tampered with.

1. Open your terminal in the `A-S-Minecraft-RTX-Community-PatcherV3` directory.
2. Run the following command to generate a key pair:
   ```bash
   npx tauri signature generate-key
   ```
3. This command will output two things:
   - **Public Key**: A short base64 string.
   - **Private Key / Secret**: A longer base64 string.
4. **Copy the Public Key** and paste it into `src-tauri/tauri.conf.json` under `plugins.updater.pubkey`:
   ```json
   "plugins": {
     "updater": {
       "active": true,
       "pubkey": "YOUR_GENERATED_PUBLIC_KEY",
       "endpoints": [
         "https://raw.githubusercontent.com/Felix-Chaos/Actions-and-Stuff-RTX-Patcher/main/updater.json"
      ]
     }
   }
   ```
5. **Keep the Private Key secure**. Do not commit it to git.

---

## Step 2: Set Up GitHub Secrets
When you build your application using GitHub Actions, the builder needs access to the private key to sign the installer.

1. Navigate to your GitHub repository: `Felix-Chaos/Actions-and-Stuff-RTX-Patcher`.
2. Go to **Settings** > **Secrets and variables** > **Actions**.
3. Click **New repository secret**.
4. Add the following secrets:
   - **Name**: `TAURI_SIGNING_PRIVATE_KEY`
   - **Value**: *Paste your base64 private key here.*
   - **Name**: `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` (Optional: If you set a password when generating the key).

---

## Step 3: Create a GitHub Actions Release Workflow
To build signed releases automatically when you push a new tag, create a workflow file at `.github/workflows/release.yml` in your repo:

```yaml
name: Release
on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    permissions:
      contents: write
    strategy:
      fail-fast: false
      matrix:
        platform: [windows-latest]
    runs-on: ${{ matrix.platform }}
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 20

      - name: Set up Rust
        uses: dtolnay/rust-toolchain@stable

      - name: Install dependencies
        run: npm install

      - name: Build Tauri App
        uses: tauri-apps/tauri-action@v0
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          TAURI_SIGNING_PRIVATE_KEY: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY }}
          TAURI_SIGNING_PRIVATE_KEY_PASSWORD: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY_PASSWORD }}
        with:
          tagName: v__VERSION__
          releaseName: 'Actions & Stuff RTX Patcher v__VERSION__'
          releaseBody: 'See changelog for updates.'
          releaseDraft: true
          prerelease: false
```

---

## Step 4: Structuring the `updater.json` Metadata
Tauri will request the `updater.json` from the repository root (e.g. via `raw.githubusercontent.com`).

Whenever you release a new version (e.g., `3.1.0`), update the file `updater.json` in the root of your `main` branch.

```json
{
  "version": "3.1.0",
  "notes": "Added deterministic pack compression optimization and cleaner speed improvements.",
  "pub_date": "2026-06-01T19:00:00Z",
  "platforms": {
    "windows-x86_64": {
      "signature": "CONTENT_OF_YOUR_MSI_ZIP_SIG_FILE",
      "url": "https://github.com/Felix-Chaos/Actions-and-Stuff-RTX-Patcher/releases/download/v3.1.0/Actions_and_Stuff_RTX_Patcher_3.1.0_x64_en-US.msi.zip"
    }
  }
}
```

### How to get the `signature` value:
When GitHub Actions finishes the release build, it attaches a signature file next to the installer (e.g. `Actions_and_Stuff_RTX_Patcher_3.1.0_x64_en-US.msi.zip.sig`).
Open that `.sig` file, copy its text content, and paste it into the `signature` field in `updater.json`.

Now, when users launch the app, Tauri will detect the update, verify the signature against the public key, and prompt them to upgrade automatically!
