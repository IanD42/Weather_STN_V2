"""
sensors/wind_vane.py
Wind direction sensor using the DS-15901 wind vane and ADS1115 I2C ADC.

Wiring:
  3.3V ── 10kΩ ──┬── Wind Vane ── GND
                 └── ADS1115 A0

The vane contains 8 reed switches each connected to a different resistor.
The voltage at A0 changes with direction — converted to degrees via the
resistance lookup table from the DS-15901 datasheet.
"""

import math
import time
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

# ─── Datasheet resistance → degrees table ─────────────────────────────────────
# Source: DS-15901 datasheet. Values in ohms.
WIND_VANE_RESISTANCES = {
    33000:  0.0,
    6570:   22.5,
    8200:   45.0,
    891:    67.5,
    1000:   90.0,
    688:    112.5,
    2200:   135.0,
    1410:   157.5,
    3900:   180.0,
    3140:   202.5,
    16000:  225.0,
    14120:  247.5,
    120000: 270.0,
    42120:  292.5,
    64900:  315.0,
    21880:  337.5,
}

DIRECTION_NAMES = {
    0.0:   "N",   22.5:  "NNE", 45.0:  "NE",  67.5:  "ENE",
    90.0:  "E",   112.5: "ESE", 135.0: "SE",  157.5: "SSE",
    180.0: "S",   202.5: "SSW", 225.0: "SW",  247.5: "WSW",
    270.0: "W",   292.5: "WNW", 315.0: "NW",  337.5: "NNW",
}


class ADS1115ADC:
    """Read analog voltage from ADS1115 via I2C.

    The ADS1115 is a 16-bit ADC with 4 single-ended channels (A0–A3).
    It shares the I2C bus with the BME280 — no extra wiring needed.

    I2C address is set by the ADDR pin:
      ADDR → GND : 0x48 (default)
      ADDR → VDD : 0x49
      ADDR → SDA : 0x4A
      ADDR → SCL : 0x4B

    Gain setting controls full-scale voltage range:
      1  → ±4.096V  (recommended for 3.3V supply, ~0.125mV resolution)
      2  → ±2.048V
      4  → ±1.024V
    """

    _CHANNEL_MAP = {0: 0, 1: 1, 2: 2, 3: 3}

    def __init__(self, i2c, address: int = 0x48, gain: int = 1):
        self._ads      = ADS.ADS1115(i2c, address=address, gain=gain)
        self._channels = {}

    def _get_channel(self, channel: int) -> AnalogIn:
        if channel not in self._channels:
            if channel not in self._CHANNEL_MAP:
                raise ValueError(f"Invalid channel {channel}. Must be 0–3.")
            self._channels[channel] = AnalogIn(
                self._ads, self._CHANNEL_MAP[channel])
        return self._channels[channel]

    def read_voltage(self, channel: int) -> float:
        """Return voltage in volts for the given channel (0–3)."""
        return self._get_channel(channel).voltage

    def read_raw(self, channel: int) -> int:
        """Return raw 16-bit ADC value for the given channel."""
        return self._get_channel(channel).value

    def close(self):
        pass  # I2C bus is shared — nothing to explicitly close


class WindVane:
    """Decode wind direction from ADS1115 ADC reading.

    Reads the voltage from the resistor voltage divider, converts it to
    the vane's internal resistance, then looks up the closest match in
    the datasheet table to determine compass direction.
    """

    def __init__(self, adc: ADS1115ADC, channel: int = 0,
                 vcc: float = 3.3, r_pullup: float = 10000.0):
        """
        adc       : ADS1115ADC instance
        channel   : ADC channel the vane output is wired to (0–3)
        vcc       : supply voltage of the voltage divider (V)
        r_pullup  : pull-up resistor value in ohms (default 10kΩ)
        """
        self.adc      = adc
        self.channel  = channel
        self.vcc      = vcc
        self.r_pullup = r_pullup

    def _voltage_to_resistance(self, v_out: float) -> float | None:
        """Voltage divider formula rearranged for R_sensor.
        Vout = Vcc * R_sensor / (R_pullup + R_sensor)
        R_sensor = R_pullup * Vout / (Vcc - Vout)
        """
        if v_out >= self.vcc or v_out <= 0:
            return None
        return self.r_pullup * v_out / (self.vcc - v_out)

    def read_degrees(self) -> float | None:
        """Return wind direction in degrees (0–337.5), or None on error."""
        voltage    = self.adc.read_voltage(self.channel)
        resistance = self._voltage_to_resistance(voltage)
        if resistance is None:
            return None
        closest = min(WIND_VANE_RESISTANCES.keys(),
                      key=lambda r: abs(r - resistance))
        return WIND_VANE_RESISTANCES[closest]

    def read_direction_name(self) -> str:
        """Return compass point name e.g. 'NNE', 'SW'."""
        degrees = self.read_degrees()
        if degrees is None:
            return "Unknown"
        return DIRECTION_NAMES.get(degrees, f"{degrees}°")


class SimulatedWindVane:
    """Simulates wind direction rotating slowly through all 16 compass points.

    Completes one full 360° rotation every 10 minutes, snapping to valid
    compass points. Useful for testing MQTT and Home Assistant pipelines
    without hardware connected.
    """

    _DIRECTIONS = sorted(DIRECTION_NAMES.keys())

    def __init__(self):
        self._start = time.monotonic()

    def read_degrees(self) -> float:
        t     = time.monotonic() - self._start
        angle = (t / 600 * 360) % 360
        return min(self._DIRECTIONS, key=lambda d: abs(d - angle))

    def read_direction_name(self) -> str:
        return DIRECTION_NAMES.get(self.read_degrees(), "N")
