# FL Studio MIDI setup

DAWLoop installs one user-facing controller: **DAWLoop Controller**. It combines the bundled Community FL Studio MCP execution script with DAWLoop's read-only target identity query, using the same MIDI trigger and JSON request/response files. A separate Target Identity controller is not required.

## Install

Install the FL Studio dependencies, preview the detected environment, then install into the active FL Studio `Settings` directory:

```powershell
python -m pip install -e ".[flstudio]"
dawloop setup-fl --dry-run
dawloop setup-fl --settings-dir "<FL Studio Settings directory>"
dawloop doctor --settings-dir "<FL Studio Settings directory>"
```

`--dry-run` does not create directories, save configuration, or copy files. Installation preserves unrelated existing files. If a managed DAWLoop controller is being replaced, the installer saves a timestamped backup first. The selected Settings directory is stored in the current-user DAWLoop config so later diagnostics and RPC use the same location.

## Set up once

1. In loopMIDI, create two persistent virtual ports named `DAWLoop MCP IN` and `DAWLoop MCP OUT`. `IN` is the Python-to-FL Studio path. `OUT` is detected as the reverse MIDI device; the bundled MCP currently returns RPC results through JSON files rather than MIDI output. During migration, `FLSkill MCP IN` and `FLSkill MCP OUT` are recognized as legacy names.
2. Enable loopMIDI's own login-start option. DAWLoop only detects the current-user startup entry; it does not modify loopMIDI configuration. The ports exist only while loopMIDI is running.
3. Start loopMIDI before FL Studio so the same named devices are present when FL Studio enumerates MIDI hardware.
4. In FL Studio MIDI settings, select **DAWLoop Controller** for the `DAWLoop MCP IN` device if FL Studio does not bind it automatically. The script declares the supported device name using Image-Line's [`supportedDevices` metadata](https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/midi_scripting.htm). This official mechanism supports automatic association, but DAWLoop has not yet confirmed binding or persistence through a live restart test.
5. Keep the selected controller and port configuration. On later starts, loopMIDI should start before FL Studio; persistence across FL or loopMIDI restarts remains pending the explicit restart matrix.

The bundled backend uses named MIDI devices and does not require Port 42. Do not change a working host port setting solely to match that old development convention.

## Verify

### Release and Controller update awareness

`dawloop doctor` checks published GitHub Releases at most once every 24 hours,
including alpha/prerelease releases by default. Draft releases and newer main
commits are not update announcements. The check uses the latest 100 release
entries and compares recognized `major.minor.patch` versions, including
alpha, beta and rc suffixes in the project's SemVer or Python package format.
Unrecognized versions are not guessed.

```powershell
dawloop doctor --refresh-updates
dawloop doctor --update-channel stable
dawloop doctor --no-update-check
```

Set `DAWLOOP_NO_UPDATE_CHECK=1` to disable release network requests and update
cache access. Local Controller observations still run. The request sends no
token, project data, local paths or Controller state. It has a three-second
network timeout. Failed checks are also cached for 24 hours; manual refresh
bypasses that delay. An unavailable network or rate limit produces `UNKNOWN`
update availability, not an “up to date” claim, and never changes the local
doctor exit code. An unwritable cache is reported and may cause another attempt
on the next run. The report includes the check time and cache age.

The CLI version, installed Controller build, runtime build and protocol are
separate observations. The installed build's template digest is compared with
the packaged template; this is not a signature or proof that the running
Controller has reloaded. Missing or stale runtime state leaves runtime
protocol compatibility `UNKNOWN`. No MIDI or RPC request is sent by this check.

DAWLoop never automatically pulls Git, installs packages, replaces scripts,
or reloads FL Studio. Only a clean `main` checkout with the canonical origin,
a known upstream and no local commits receives a `git pull --ff-only` suggestion;
other checkouts require inspection first. A package installed from an unknown
index or a local wheel is not assumed to come from PyPI. Review the release and
your installation source before explicitly updating. Then run `dawloop setup-fl`,
reload the Controller through FL Studio's Script output window, and run
`dawloop doctor --probe-fl` again. Installing a script does not reload it.

For notifications while DAWLoop is not running, subscribe to the repository's
GitHub **Watch → Custom → Releases** option. No background notifier is installed.

`dawloop doctor` reports dependencies, loopMIDI process, port names, and installed scripts. `dawloop doctor --probe-fl` reads the Controller's local runtime status file only; it does not send MIDI, PING, or an identity request. The Controller writes this file during initialization and refreshes `last_seen_at` through a throttled `OnIdle` callback. Runtime build identity is compared with the build ID embedded in the installed script; the file SHA256 is reported separately and is not treated as proof of the loaded in-memory version. `supportedDevices` being present in the script means auto-binding is available in principle, not that FL has confirmed it in this installation.

## Troubleshooting

- `LOOPMIDI_NOT_INSTALLED`: install loopMIDI from its official distribution.
- `LOOPMIDI_NOT_RUNNING`: start loopMIDI; FL cannot see its virtual ports while it is closed.
- `DAWLOOP_MIDI_PORT_MISSING`: verify the exact names and that loopMIDI started before FL Studio. Legacy `FLSkill MCP IN/OUT` names are accepted during migration.
- `FL_USER_SCRIPT_MISSING`: rerun `dawloop setup-fl` with the active Settings directory.
- `RPC_NOT_RESPONDING`: confirm the selected device uses `DAWLoop Controller`, then run the read-only probe again. Do not use a note or Mixer write as a connection test.
- `LOOPMIDI_AUTOSTART_NOT_CONFIRMED`: check loopMIDI's own login-start option; DAWLoop does not edit undocumented configuration.

Restart checks are intentionally separate: FL close/reopen; loopMIDI close/reopen followed by FL device refresh; Windows logout/login or reboot. The Windows restart case must be performed by the maintainer. DAWLoop does not close FL Studio or reboot the machine.
