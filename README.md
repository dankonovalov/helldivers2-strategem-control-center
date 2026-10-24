# Helldivers 2 Stratagem Control Center

Helldivers 2 Stratagem Control Center is an open-source macro application
configured for the official Elgato Stream Deck and Stream Deck Mobile software.
It recognizes the four stratagems selected on the Helldivers 2 loadout screen,
displays their recognition status, and assigns the confirmed stratagems to
Stream Deck buttons.

When a button is pressed, the plugin holds `Left Ctrl` and enters the stratagem
sequence using the default `W/A/S/D` controls.

> [!NOTE]
> This is an unofficial, community-made open-source project. It is not
> affiliated with or endorsed by Arrowhead Game Studios, PlayStation, Sony, or
> Elgato.

## Features

- Local screen recognition powered by OpenCV; no cloud processing is required.
- Four dynamic loadout slots for Stream Deck and Stream Deck Mobile.
- Fixed `Reinforce`, `Resupply`, and `Hellbomb` actions.
- Automatic recognition with confidence scoring and stable-frame confirmation.
- Manual selection from the best candidates when recognition is uncertain.
- Native Windows macro input through `SendInput`.
- English and Ukrainian GUI localization.
- Portable Windows build and an installable Stream Deck plugin.

## How It Works

The application uses two independent processes:

1. **Control Center GUI** captures only the configured screen region, divides it
   into four horizontal slots, and compares each slot with the local PNG icon
   library.
2. **Stream Deck plugin** is launched by the Elgato application, reads the last
   confirmed state, updates the button images, and sends the corresponding
   keyboard sequence to the game.

Confirmed slots are written atomically to:

```text
%LOCALAPPDATA%\HelldiversStratagems\last_state.json
```

Shared GUI and plugin settings are stored in:

```text
%LOCALAPPDATA%\HelldiversStratagems\config.json
```

An empty screen or a temporary low-confidence match does not clear the Stream
Deck buttons. A new icon is accepted only after several stable frames and a
sufficient number of confident slots.

## Installation

### Portable Release

1. Extract the complete portable ZIP archive into a regular folder.
2. Run `Helldivers2-Stratagems-Control.exe` from the extracted folder.
3. Install `com.super-earth.helldivers2.streamDeckPlugin`.
4. Open the Elgato Stream Deck application and add the required actions to a
   profile.
5. Keep the official Stream Deck application open while using Stream Deck
   Mobile.

Do not run the executable directly from the ZIP archive or move it away from
the `_internal`, `locales`, and `stratagem_library` folders.

### Run from Source

Python 3.11 or newer is required.

```powershell
py -m pip install -r requirements-build.txt
py app_ui.py
```

## Calibration

1. Open the **Control** tab and select **Select the 4-icon area**.
2. Draw one rectangle around all four loadout icons in the game.
3. Open the **Stream Deck** tab and select the monitor index and match threshold.
4. Save the settings.
5. Start the parser.

Slot cards use four states:

- **Green** — the stratagem was recognized with sufficient confidence.
- **Orange** — a candidate was found, but its score is below the threshold.
- **Yellow** — a candidate was selected manually and pinned to the slot.
- **Gray** — no candidate is visible or the parser is waiting for an image.

Each card contains a list of the best candidates. A manual choice is written to
the Stream Deck state immediately and is not replaced by the parser. Select
**Automatic selection** to resume automatic recognition for that slot.

## Stream Deck Actions

The plugin manifest provides:

- `Stratagem Slot 1` through `Stratagem Slot 4` — dynamic loadout slots.
- `Reinforce`.
- `Resupply`.
- `Hellbomb`.

On a six-button Stream Deck Mobile page, the four loadout slots can be placed on
the first page and the fixed actions on another page. The physical position of
a button does not change its assigned slot number.

## Default Game Controls

- Stratagem menu — `Left Ctrl`.
- Up — `W`.
- Down — `S`.
- Left — `A`.
- Right — `D`.

The plugin holds `Left Ctrl` for the full sequence and releases every injected
key even if an error occurs.

## Interface Languages

The GUI supports English and Ukrainian. Use the `EN` / `UA` switch in the top
bar to change the language. The selection is stored in `ui.language`.

Translations are stored in:

```text
locales/en.json
locales/uk.json
```

## Build Commands

Build the Stream Deck plugin:

```powershell
.\build_streamdeck_plugin.ps1
```

Build the portable GUI, plugin, and ZIP archive:

```powershell
.\build_portable.ps1
```

Update the plugin in both the root `dist` folder and the portable package:

```powershell
.\build_plugin_everywhere.ps1
```

## Project Structure

- `app_ui.py` — GUI, screen capture, and parser worker management.
- `parser.py` — OpenCV template matching.
- `stratagem_catalog.py` — stratagem names and keyboard sequences from JSON.
- `main.py` — lightweight Stream Deck plugin process.
- `input_sender.py` — Windows `SendInput` sequence execution.
- `config_store.py` — shared configuration and confirmed-state storage.
- `i18n.py` and `locales/` — interface localization.
- `plugin/com.super-earth.helldivers2.sdPlugin/manifest.json` — Elgato plugin
  manifest.
- `stratagem_library/` — PNG icons and `stratagems.json`.

## Icon Credits

The stratagem icons used by this project are sourced from
[nvigneux/Helldivers-2-Stratagems-icons-svg](https://github.com/nvigneux/Helldivers-2-Stratagems-icons-svg),
created and maintained by [nvigneux](https://github.com/nvigneux).

The original repository provides the Helldivers 2 stratagem icon collection in
SVG format and also includes a
[Figma file and contribution workflow](https://github.com/nvigneux/Helldivers-2-Stratagems-icons-svg#figma-file-available-for-contributors)
for creating and updating icons consistently. Please visit the original project
for the latest assets, contribution information, and to support its author.

## Feedback and Contributions

Improvements, bug reports, recognition problems, missing stratagems, and pull
requests are welcome. If you encounter a problem or have an idea that could
improve the application, please open an issue in the project repository or
contact me using the email address below.

When reporting a recognition problem, include a screenshot of the icon, the
detected candidate and confidence score, and the expected stratagem name.

## Contact

[![Email](https://img.shields.io/badge/Email-konovalovbogdan21%40gmail.com-EA4335?style=flat-square&logo=gmail&logoColor=white)](mailto:konovalovbogdan21@gmail.com)

## License

This project is open source. Add the repository's license file before public
distribution so that contribution and reuse terms are explicit.
