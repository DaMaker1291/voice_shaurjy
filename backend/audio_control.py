"""Windows audio control via pycaw — direct CoreAudio API, no PowerShell needed."""

from pycaw.pycaw import AudioUtilities


def get_volume() -> float:
    """Get current volume as percentage (0-100)."""
    dev = AudioUtilities.GetSpeakers()
    scalar = dev.EndpointVolume.GetMasterVolumeLevelScalar()
    return round(scalar * 100, 1)


def set_volume(level: int):
    """Set volume to percentage (0-100)."""
    dev = AudioUtilities.GetSpeakers()
    dev.EndpointVolume.SetMasterVolumeLevelScalar(max(0, min(1, level / 100.0)), None)


def get_mute() -> bool:
    """Check if audio is muted."""
    dev = AudioUtilities.GetSpeakers()
    return bool(dev.EndpointVolume.GetMute())


def set_mute(muted: bool):
    """Mute or unmute."""
    dev = AudioUtilities.GetSpeakers()
    dev.EndpointVolume.SetMute(int(muted), None)


def toggle_mute() -> bool:
    """Toggle mute state. Returns new mute state."""
    muted = get_mute()
    set_mute(not muted)
    return not muted


def volume_up(step: int = 10) -> int:
    """Increase volume by step percentage. Returns new volume."""
    current = get_volume()
    new_level = min(100, int(current) + step)
    set_volume(new_level)
    return new_level


def volume_down(step: int = 10) -> int:
    """Decrease volume by step percentage. Returns new volume."""
    current = get_volume()
    new_level = max(0, int(current) - step)
    set_volume(new_level)
    return new_level
