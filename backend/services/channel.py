"""Channel registry — tracks which messaging channel each phone is using."""

_active_channels: dict = {}


def set_channel(phone: str, channel: str):
    """Set the active channel for a phone number (whatsapp or telegram)."""
    _active_channels[phone] = channel


def get_channel(phone: str) -> str:
    """Get the active channel for a phone number. Default: whatsapp."""
    return _active_channels.get(phone, "whatsapp")
