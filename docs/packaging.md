# Packaging gitget

Two formats supported out of the box: **.deb** for Debian/Ubuntu installs, and
**AppImage** for distro-agnostic single-file deployment. Both reuse the same
PyInstaller binary so the build is staged in two steps.

## 1. Add the build tool

```bash
uv add --dev pyinstaller
```

## 2. Build the binary

```bash
uv run pyinstaller packaging/gitget.spec
```

Output goes to `dist/gitget`. Test it standalone:

```bash
./dist/gitget
```

## 3a. Build the .deb

```bash
./packaging/build-deb.sh 0.1.0
```

Produces `gitget_0.1.0_amd64.deb`. Install with `sudo apt install ./gitget_0.1.0_amd64.deb`.

## 3b. Build the AppImage

Download `appimagetool` from https://github.com/AppImage/AppImageKit/releases
and place it on `$PATH`, then:

```bash
./packaging/build-appimage.sh 0.1.0
```

Produces `gitget-0.1.0-x86_64.AppImage`. Mark it executable and run.

## Icon

Both formats currently install a placeholder `gitget.png` (empty file).
Replace `packaging/gitget.png` with a real 256×256 PNG before publishing.

## Flatpak

Manifest lives at `packaging/org.obsidianwatch.GitGet.yaml`. It bundles the
PyInstaller-built binary plus desktop entry and icons.

Prereqs:

```bash
sudo apt install flatpak flatpak-builder
flatpak install -y flathub org.freedesktop.Sdk//23.08 org.freedesktop.Platform//23.08
```

Build + install for the current user:

```bash
flatpak-builder --user --install --force-clean build packaging/org.obsidianwatch.GitGet.yaml
```

Run:

```bash
flatpak run org.obsidianwatch.GitGet
```

The manifest grants secret-service, notifications, network, and the three
`xdg-{config,data,cache}/gitget` paths so the app behaves the same as a native
install (token storage, polling cache, etc).
