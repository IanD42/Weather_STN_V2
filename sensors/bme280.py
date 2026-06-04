"""
sensors/bme280.py
BME280 temperature, humidity and pressure sensor over I2C.
"""

import board
import busio
import adafruit_bme280.advanced as adafruit_bme280


class BME280Sensor:
    """Read temperature, humidity, and pressure from BME280 via I2C.

    Shares the I2C bus with the ADS1115 ADC — no extra wiring needed.

    I2C address is set by the SDO pin:
      SDO → GND : 0x76 (default)
      SDO → VCC : 0x77
    """

    def __init__(self, i2c, address: int = 0x77,
                 sea_level_pressure: float = 1013.25):
        """
        i2c               : shared busio.I2C instance
        address           : I2C address (0x76 or 0x77)
        sea_level_pressure: local reference pressure in hPa for altitude calc.
                            Find your local value at: https://www.metoffice.gov.uk
        """
        self.sensor = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=address)
        self.sensor.sea_level_pressure = sea_level_pressure

    def read(self) -> dict:
        """Return all BME280 readings as a dict."""
        temp_c = self.sensor.temperature
        return {
            "temperature_c": round(temp_c, 2),
            "temperature_f": round(temp_c * 9 / 5 + 32, 2),
            "humidity_pct":  round(self.sensor.relative_humidity, 2),
            "pressure_hpa":  round(self.sensor.pressure, 2),
            "altitude_m":    round(self.sensor.altitude, 1),
        }
