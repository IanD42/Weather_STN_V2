"""
config.py — Weather Station Configuration
Edit the non-secret values here directly.

SECRETS (MQTT host, username, password) are loaded from environment
variables so they are never stored in the code or pushed to GitHub.

How to set secrets on the Pi:
  1. Create a file called .env in the project folder:
       nano .env
  2. Add your values (no spaces around =):
       MQTT_HOST=192.168.1.x
       MQTT_USERNAME=mqtt_user
       MQTT_PASSWORD=mqtt_pass
  3. The .env file is listed in .gitignore so it will never be
     accidentally committed to GitHub.

The .env file is loaded automatically at startup via python-dotenv.
All GPIO pin numbers use BCM numbering.
"""

import os
from dotenv import load_dotenv

# Load .env file if present — silently ignored if it doesn't exist
load_dotenv()


def _require_env(key: str) -> str:
    """Return the value of an environment variable, or raise a clear
    error if it is missing — better than a cryptic auth failure later."""
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"\n\n  Missing required environment variable: {key}\n"
            f"  Add it to your .env file in the project folder.\n"
            f"  See config.py for instructions.\n"
        )
    return value


class Config:

    # ── Simulation mode ────────────────────────────────────────────────────────
    # Set SIMULATE = True to run without anemometer, wind vane or rain gauge
    # hardware connected. BME280 still reads real data. Wind and rain produce
    # realistic synthetic values. MQTT and Home Assistant work normally.
    SIMULATE: bool                  = True   # ← change to True to test
    SIM_RAIN_TIPS_PER_MINUTE: float = 2.0     # tip rate during simulated rain

    # ── Sampling interval ──────────────────────────────────────────────────────
    # How often (seconds) to read all sensors and publish to MQTT.
    INTERVAL_SECONDS: float         = 10.0    # e.g. 10, 30, 60, 300

    # ── MQTT secrets — loaded from .env file, never hard-coded ────────────────
    MQTT_HOST: str      = _require_env("MQTT_HOST")
    MQTT_PORT: int      = int(os.getenv("MQTT_PORT", "1883"))
    MQTT_USERNAME: str  = _require_env("MQTT_USERNAME")
    MQTT_PASSWORD: str  = _require_env("MQTT_PASSWORD")

    # ── MQTT non-secret settings — safe to commit ──────────────────────────────
    MQTT_CLIENT_ID: str  = "weather_station_pi"
    MQTT_BASE_TOPIC: str = "weather_station"  # state published to <base>/state

    # ── BME280 (I2C) ───────────────────────────────────────────────────────────
    # SDO → GND : 0x76 (default)   SDO → VCC : 0x77
    BME280_I2C_ADDRESS: int         = 0x77
    # Local sea-level pressure in hPa — used for altitude calculation.
    # Find your value at https://www.metoffice.gov.uk or https://openweathermap.org
    SEA_LEVEL_PRESSURE_HPA: float   = 1018.25

    # ── ADS1115 I2C ADC (Wind Vane) ───────────────────────────────────────────
    # ADDR → GND : 0x48 (default)   ADDR → VDD : 0x49
    # ADDR → SDA : 0x4A             ADDR → SCL : 0x4B
    ADS1115_I2C_ADDRESS: int        = 0x48
    # Gain: 1 = ±4.096V range (recommended for 3.3V supply)
    ADS1115_GAIN: int               = 1

    # ── Wind Vane ──────────────────────────────────────────────────────────────
    # ADS1115 channel the wind vane voltage divider is wired to (0–3)
    WIND_VANE_ADC_CHANNEL: int      = 0
    # Pull-up resistor value in the voltage divider (ohms) — use 10kΩ
    WIND_VANE_PULLUP_OHM: float     = 10000.0
    # Supply voltage for the wind vane circuit (match your logic level)
    ADC_VCC: float                  = 3.3

    # ── Anemometer ─────────────────────────────────────────────────────────────
    # BCM GPIO pin connected to the anemometer reed switch
    ANEMOMETER_GPIO_PIN: int        = 17
    # Rolling window in seconds for wind speed calculation (default 5s)
    # Larger value = smoother reading but slower to respond to gusts
    ANEMOMETER_SAMPLE_WINDOW: float = 5.0

    # ── Rain Gauge ─────────────────────────────────────────────────────────────
    # BCM GPIO pin connected to the rain gauge reed switch
    RAIN_GAUGE_GPIO_PIN: int        = 27
    # Time of day at which rain_daily_mm resets (24-hour clock)
    # e.g. 0, 0 = midnight   9, 0 = 9:00 AM
    RAIN_GAUGE_DAILY_RESET_HOUR: int   = 0
    RAIN_GAUGE_DAILY_RESET_MINUTE: int = 0
