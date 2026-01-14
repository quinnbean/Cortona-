# Cortona Desktop App

Native macOS app for Cortona Voice Assistant.

## Features

- 🎤 **Global Shortcut**: Press `⌘+Shift+J` from anywhere to activate Jarvis
- 📍 **Menubar App**: Always accessible from your menubar
- 🚀 **Auto-Launch**: Starts with your Mac
- 🔔 **Native Notifications**: macOS notifications for alerts
- 🎨 **Native Look**: Vibrancy, traffic lights, dark mode support

## Development

### Prerequisites

- Node.js 18+ 
- npm or yarn

### Setup

```bash
cd cortona-desktop
npm install
```

### Run in Development

```bash
npm run dev
```

This connects to `http://localhost:5050` - make sure your Flask server is running.

### Run with Production Server

```bash
npm start
```

This connects to `https://cortona.onrender.com`.

## Building

### Build for macOS

```bash
# Build for current architecture
npm run build:mac

# Build for Apple Silicon (M1/M2/M3)
npm run build:mac:arm64

# Build for Intel
npm run build:mac:x64

# Build both architectures
npm run dist
```

The built app will be in `cortona-desktop/dist/`.

## App Structure

```
cortona-desktop/
├── main.js          # Main process (tray, shortcuts, window)
├── preload.js       # Bridge to renderer (secure IPC)
├── package.json     # Cortona desktop dependencies
├── entitlements.mac.plist  # macOS permissions
└── assets/
    ├── icon.png     # App icon (1024x1024)
    ├── icon.icns    # macOS icon bundle
    └── trayTemplate.png  # Menubar icon (18x18, template)
```

## Icons

You need to create the following icons:

1. **icon.png** (1024x1024) - Main app icon
2. **icon.icns** - macOS icon bundle (use `iconutil` to create)
3. **trayTemplate.png** (18x18) - Menubar icon (black on transparent, macOS will handle dark/light mode)

### Creating icon.icns

```bash
# Create iconset folder
mkdir icon.iconset

# Add required sizes (you need to create these)
# icon_16x16.png, icon_16x16@2x.png, icon_32x32.png, etc.

# Convert to icns
iconutil -c icns icon.iconset -o assets/icon.icns
```

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `⌘+Shift+J` | Toggle Cortona window & activate mic |
| `⌘+Shift+V` | Quick voice recording |
| `⌘+Q` | Quit Cortona |

## Settings

Settings are stored in:
```
~/Library/Application Support/cortona/config.json
```

Available settings:
- `autoLaunch` - Start at login
- `alwaysOnTop` - Keep window on top
- `showInDock` - Show in dock (vs menubar-only)
- `startMinimized` - Start hidden

## Code Signing (for Distribution)

With your Apple Developer account:

```bash
# Sign the app
codesign --deep --force --verify --verbose \
  --sign "Developer ID Application: Your Name (TEAM_ID)" \
  dist/mac-arm64/Cortona.app

# Notarize for Gatekeeper
xcrun notarytool submit dist/Cortona-1.0.0-arm64.dmg \
  --apple-id "your@email.com" \
  --team-id "TEAM_ID" \
  --password "app-specific-password" \
  --wait

# Staple the notarization
xcrun stapler staple dist/Cortona-1.0.0-arm64.dmg
```

## Troubleshooting

### "App is damaged" error
The app needs to be signed and notarized. For development, you can:
```bash
xattr -cr /Applications/Cortona.app
```

### Microphone not working
Make sure you've granted microphone access in System Preferences > Privacy & Security > Microphone.

### Global shortcut not working
Check System Preferences > Privacy & Security > Accessibility and add Cortona.

