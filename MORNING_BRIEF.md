# Morning Brief — 2026-05-09

**State as of 22:00 EST 2026-05-08:**

## What's working

- ✅ Charles agent: healthy, all 4 LaunchAgents on, ticking goals overnight
- ✅ War Room server: running as LaunchAgent, `0.0.0.0:8765` accepting Tailscale + localhost
- ✅ Server secret = `GreenPondMafia817` (your pick, in `~/charles/workspace/warroom_secret.txt`)
- ✅ WarRoom Mac app: built once, currently running on screen (probably hung — see below)
- ✅ Tailscale: both Mac (100.95.100.65) and iPhone (100.77.38.67) on `tail09ce02.ts.net`

## The one fix you need to do — should take 30 seconds

The WarRoom Mac app errored with **"Operation not permitted"** when trying to fetch from the server. Root cause: the new Xcode project enabled **App Sandbox** (correct) but never granted **Network Client** capability (so all outgoing HTTP is blocked).

I fixed it at the project-file level overnight:
- Created `Sources/WarRoom/WarRoom/WarRoom.entitlements` with the right plist:
  - `com.apple.security.app-sandbox` = true
  - `com.apple.security.network.client` = true ← the fix
  - `com.apple.security.files.user-selected.read-only` = true
- Wired it into the build settings (`CODE_SIGN_ENTITLEMENTS = WarRoom/WarRoom.entitlements;` for both Debug and Release configs)

**To activate the fix:**
1. Bring Xcode forward (it should still be open)
2. **Product menu → Stop** (or click the ■ stop button — kills the currently running session)
3. **Product menu → Clean Build Folder** (Shift+Cmd+K) — important so it re-signs with the new entitlements
4. **Product menu → Run** (or Cmd+R) — fresh build picks up the entitlements

App should launch with all 6 tabs working — Approvals will show "All clear", System tab will show real Mac stats, Goals will show all 3 active goals (#8, #9, #11) with live progress.

## If something goes wrong

**"App Sandbox" capability missing in Xcode UI:** doesn't matter — the entitlements file works regardless of whether the UI shows the capability. If you're paranoid, manually add it: Project root → WarRoom target → Signing & Capabilities → + Capability → App Sandbox → check Network → Outgoing Connections (Client).

**Build error returns:** check Issue Navigator (Cmd+5) — paste first error to me. Backup of the original `project.pbxproj` is at `Sources/WarRoom/WarRoom.xcodeproj/project.pbxproj.bak` if you need to revert.

**App launches but blank:** the secret in the app might not match `GreenPondMafia817`. Open Settings (Cmd+,) → re-paste the secret → Save.

## What I touched overnight

- `Sources/WarRoom/WarRoom/WarRoom.entitlements` (new file)
- `Sources/WarRoom/WarRoom.xcodeproj/project.pbxproj` (added CODE_SIGN_ENTITLEMENTS to 2 places; backup at `.bak`)
- `workspace/warroom_secret.txt` (changed to `GreenPondMafia817`)
- LaunchAgent restart for `com.charles.warroom`

## Charles's autonomous overnight work (already happening)

- Goal #8 (training corpus ingest): scraping URLs, last count was 149 DONE / 76 FAILED
- Goal #9 (doctrine synthesis): writing `workspace/knowledge-base/*.md` files
- Goal #11 (business URLs ingest): 5 DONE / 1 FAILED at last check, ticking every 15 min
- Hallucination guard active — zero Tesla/Bugatti regressions since the patch

## POC #1 status (unchanged from yesterday)

Still waiting on you for:
- Buy `thepromptdesk.com` on Namecheap (~$12, ~3 min)
- Stripe Payment Link for "$39 Custom AI Prompt Suite — delivered in 24h via email"
- Carrd OR Cloudflare Pages OR Netlify for the landing page (Charles wrote HTML at `workspace/poc1/index.html`)
- $20 promo budget approval

Whenever you've got a free 30 minutes between life and the WarRoom build.
