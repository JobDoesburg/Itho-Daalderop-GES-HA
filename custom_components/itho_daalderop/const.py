"""Constants for the Itho Daalderop integration."""
from dataclasses import dataclass, field

DOMAIN = "itho_daalderop"

# API Configuration
SSO_INITIATE_URL = "https://itho-tussenlaag.bettywebblocks.com/sso/initiate"
API_BASE_URL = "https://wifi-api.id-c.net/api"
APPLICATION_ID = "2da3d256-ca0a-4041-84ba-93856efceef9"
REDIRECT_URI = "climateconnect://login"

# Config entry data keys
CONF_SERIAL_NUMBER = "serial_number"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"

# Update interval (API is slow: ~16s per call, 3 calls = ~50s total)
# 120s gives API breathing room between updates
UPDATE_INTERVAL = 120  # seconds

# Device modes
MODE_SMART_CONTROL = "SmartControl"
MODE_SCHEDULE = "Schedule"
MODE_CONTINUOUS = "Continuous"
MODE_HOLIDAY = "Holiday"

DEVICE_MODES = [
    MODE_SMART_CONTROL,
    MODE_SCHEDULE,
    MODE_CONTINUOUS,
    MODE_HOLIDAY,
]

# Display names matching the Climate Connect app. The app's "standby" is
# deviceMode=Holiday; its dated "holiday mode" is standby with a start/end
# date on top. Verified against a GRB Smartboiler: all four values are
# accepted ("Standby"/"AlwaysOn"/"Boost" are not valid API values).
MODE_LABELS = {
    MODE_SMART_CONTROL: "Smart",
    MODE_SCHEDULE: "Schedule",
    MODE_CONTINUOUS: "Always on",
    MODE_HOLIDAY: "Standby",
}
MODE_FROM_LABEL = {label: mode for mode, label in MODE_LABELS.items()}

# GetDeviceMode keeps returning the old mode for a while after an
# UpdateDeviceMode write (usually ~30s, sometimes much longer). A written
# mode is trusted over API reads until the API reports it back at least
# once; this is the safety timeout after which the API wins regardless,
# so HA can't mask a genuinely failed/overridden change forever.
MODE_CONFIRM_TIMEOUT_SECONDS = 600


@dataclass(frozen=True)
class DeviceProfile:
    """Capabilities of a boiler type, keyed on serial number prefix.

    The Climate Connect API serves multiple boiler types. They share the
    same endpoints, but not all fields/controls are supported by every type.
    """

    model: str
    # Measured water temperature reported in GetDeviceStatus
    supports_temperature: bool = True
    # Free setpoint control (written via the UpdateDeviceMode payload)
    supports_temperature_setpoint: bool = True
    # PV/solar function (GetDevicePVSettings / UpdateDevicePVSettings)
    supports_pv: bool = True
    # Boost function (both types have it; activating it via the API does
    # not work yet — the BoostBoiler request format is unknown)
    supports_boost: bool = True
    modes: list[str] = field(default_factory=lambda: list(DEVICE_MODES))


# Green Energy Smartboiler (GES): full feature set, PV function, setpoint control
PROFILE_GES = DeviceProfile(model="Green Energy Smartboiler")

# Smartboiler with Smart-upp module: self-learning boiler controlled via the
# same app/API, but without the PV function or free temperature setpoint.
# All four device modes are supported (verified live on a GRB device).
PROFILE_SMARTBOILER = DeviceProfile(
    model="Smartboiler (Smart-upp)",
    supports_temperature=False,
    supports_temperature_setpoint=False,
    supports_pv=False,
)

DEVICE_PROFILES = {
    "VPR": PROFILE_GES,
    "GRB": PROFILE_SMARTBOILER,
}


def get_device_profile(serial_number: str) -> DeviceProfile:
    """Return the device profile for a serial number.

    Unknown prefixes get the full GES profile so nothing is hidden;
    unsupported entities will simply report no data.
    """
    return DEVICE_PROFILES.get(serial_number[:3].upper(), PROFILE_GES)
