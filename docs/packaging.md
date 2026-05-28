# Packaging gh-desktop

Two formats supported out of the box: **.deb** for Debian/Ubuntu installs, and
**AppImage** for distro-agnostic single-file deployment. Both reuse the same
PyInstaller binary so the build is staged in two steps.

## 1. Add the build tool

```bash
uv add --dev pyinstaller
```

## 2. Build the binary

```bash
uv run pyinstaller packaging/gh-desktop.spec
```

Output goes to `dist/gh-desktop`. Test it standalone:

```bash
./dist/gh-desktop
```

## 3a. Build the .deb

```bash
./packaging/build-deb.sh 0.1.0
```

Produces `gh-desktop_0.1.0_amd64.deb`. Install with `sudo apt install ./gh-desktop_0.1.0_amd64.deb`.

## 3b. Build the AppImage

Download `appimagetool` from https://github.com/AppImage/AppImageKit/releases
and place it on `$PATH`, then:

```bash
./packaging/build-appimage.sh 0.1.0
```

Produces `gh-desktop-0.1.0-x86_64.AppImage`. Mark it executable and run.

## Icon

Both formats currently install a placeholder `gh-desktop.png` (empty file).
Replace `packaging/gh-desktop.png` with a real 256×256 PNG before publishing.

## Flatpak

Not included in this round. The Flatpak manifest would live at
`packaging/org.obsidianwatch.GhDesktop.yaml` and use the Freedesktop SDK
runtime with the same PyInstaller binary as input.
