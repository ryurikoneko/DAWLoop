from __future__ import annotations

from dawloop.midi_setup import select_midi_output
from dawloop.setup import default_settings_dir


def _configure_bundled_transport() -> None:
    import mido
    from fl_studio_mcp.utils import midi_connection

    settings_dir = default_settings_dir()
    hardware_dir = settings_dir / "Hardware" / "DAWLoopMCP"
    midi_connection._get_fl_hardware_dir = lambda: hardware_dir

    def connect_exact(self) -> bool:
        if self.is_connected:
            return True
        port_name = select_midi_output(mido.get_output_names())
        if port_name is None:
            self._error = "DAWLOOP_MIDI_PORT_MISSING"
            return False
        try:
            self._port = mido.open_output(port_name)
            self._port_name = port_name
            self._connected = True
            self._error = None
            return True
        except Exception as error:
            self._error = f"MIDI_PORT_UNAVAILABLE: {type(error).__name__}"
            return False

    midi_connection.MIDIConnection.connect = connect_exact


def main() -> None:
    _configure_bundled_transport()
    from fl_studio_mcp.server import main as upstream_main
    upstream_main()


if __name__ == "__main__":
    main()
