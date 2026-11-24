# Spotify Desktop Lyrics

A lightweight always-on-top lyrics overlay for the Spotify desktop app. It reads what Spotify is currently playing from the local system (no Spotify login or API key needed) and shows time-synced lyrics from [LRCLIB](https://lrclib.net).

## Install (Windows)

Download `SpotifyLyrics-Setup-x.y.z.exe` from the [Releases](../../releases) page and run it. You can optionally create a desktop shortcut and start it with Windows. A portable `SpotifyLyrics.exe` is also attached if you'd rather not install.

Because the exe isn't code-signed, Windows SmartScreen may warn on first run: click **More info → Run anyway**.

## Usage

- Drag the overlay to move it.
- Right-click the overlay to hide it or quit.
- Use the tray icon (bottom-right) to show/hide or quit.
- The Spotify **desktop app** must be running; the web player isn't supported.

## Run from source

```bash
pip install -r requirements.txt
python spotify_lyrics.py
```

On macOS only `requests` is needed. Allow Terminal to control Spotify when prompted.

## Build a release

Push a version tag and GitHub Actions builds the exe and the installer, then attaches both to a new Release:

```bash
git tag v1.0.0
git push origin v1.0.0
```

## Tuning

Edit `OFFSET` at the top of `spotify_lyrics.py` if lyrics run early or late.
