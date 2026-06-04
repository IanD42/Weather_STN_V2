#!/usr/bin/env python3
"""
main.py — Weather Station
Raspberry Pi Zero W2 · BME280 · ADS1115 · DS-15901 Wind & Rain Kit
Publishes to Home Assistant via MQTT.

Usage:
  python main.py

To run in simulation mode (no wind/rain hardware needed):
  Set SIMULATE = True in config.py
"""

import time
import logging
from datetime import datetime, timezone

import board
import busio
import RPi.GPIO as GPIO

from config import Config
from mqtt_publisher import MQTTPublisher
from sensors.bme280 import BME280Sensor
from sensors.anemometer import Anemometer, SimulatedAnemometer
from sensors.wind_vane import ADS1115ADC, WindVane, SimulatedWindVane
from sensors.rain_gauge import RainGauge, SimulatedRainGauge

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("weather_station.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# ─── Hardware factory ─────────────────────────────────────────────────────────

def build_sensors(cfg: Config, i2c):
    """Return (bme280, anemometer, wind_vane, rain_gauge) based on config."""

    bme280 = BME280Sensor(
        i2c,
        address=cfg.BME280_I2C_ADDRESS,
        sea_level_pressure=cfg.SEA_LEVEL_PRESSURE_HPA,
    )

    if cfg.SIMULATE:
        log.warning("SIMULATION MODE — wind and rain data is synthetic")
        anemometer = SimulatedAnemometer()
        wind_vane  = SimulatedWindVane()
        rain_gauge = SimulatedRainGauge(
            tips_per_minute=cfg.SIM_RAIN_TIPS_PER_MINUTE,
            daily_reset_hour=cfg.RAIN_GAUGE_DAILY_RESET_HOUR,
            daily_reset_minute=cfg.RAIN_GAUGE_DAILY_RESET_MINUTE,
        )
    else:
        adc        = ADS1115ADC(
            i2c,
            address=cfg.ADS1115_I2C_ADDRESS,
            gain=cfg.ADS1115_GAIN,
        )
        wind_vane  = WindVane(
            adc,
            channel=cfg.WIND_VANE_ADC_CHANNEL,
            vcc=cfg.ADC_VCC,
            r_pullup=cfg.WIND_VANE_PULLUP_OHM,
        )
        anemometer = Anemometer(
            cfg.ANEMOMETER_GPIO_PIN,
            sample_window=cfg.ANEMOMETER_SAMPLE_WINDOW,
        )
        rain_gauge = RainGauge(
            cfg.RAIN_GAUGE_GPIO_PIN,
            daily_reset_hour=cfg.RAIN_GAUGE_DAILY_RESET_HOUR,
            daily_reset_minute=cfg.RAIN_GAUGE_DAILY_RESET_MINUTE,
        )

    return bme280, anemometer, wind_vane, rain_gauge


# ─── Main loop ────────────────────────────────────────────────────────────────

def main():
    cfg = Config()

    log.info("Weather Station starting")
    log.info(f"  Mode     : {'SIMULATION' if cfg.SIMULATE else 'LIVE hardware'}")
    log.info(f"  Interval : {cfg.INTERVAL_SECONDS}s")
    log.info(f"  Broker   : {cfg.MQTT_HOST}:{cfg.MQTT_PORT}")

    GPIO.setmode(GPIO.BCM)
    i2c = busio.I2C(board.SCL, board.SDA)

    bme280, anemometer, wind_vane, rain_gauge = build_sensors(cfg, i2c)

    mqtt_pub = MQTTPublisher(cfg)
    mqtt_pub.connect()
    time.sleep(2)  # allow MQTT to establish connection

    try:
        while True:
            loop_start = time.monotonic()

            # ── Read all sensors ──────────────────────────────────────────────
            payload = {
                **bme280.read(),
                "wind_speed_kmh":      anemometer.read_speed_kmh(),
                "wind_speed_ms":       anemometer.read_speed_ms(),
                "wind_speed_mph":      anemometer.read_speed_mph(),
                "wind_direction_deg":  wind_vane.read_degrees(),
                "wind_direction_name": wind_vane.read_direction_name(),
                "rain_hourly_mm":      rain_gauge.read_hourly_mm(),
                "rain_daily_mm":       rain_gauge.read_daily_mm(),
                "rain_alltime_mm":     rain_gauge.read_alltime_mm(),
                "timestamp":           datetime.now(timezone.utc).isoformat(),
            }

            # ── Log summary ───────────────────────────────────────────────────
            log.info(
                f"T={payload['temperature_c']}°C  "
                f"H={payload['humidity_pct']}%  "
                f"P={payload['pressure_hpa']}hPa  "
                f"Wind={payload['wind_speed_kmh']}km/h "
                f"{payload['wind_direction_name']}  "
                f"Rain={payload['rain_hourly_mm']}mm/h  "
                f"Daily={payload['rain_daily_mm']}mm"
            )

            # ── Publish ───────────────────────────────────────────────────────
            mqtt_pub.publish(payload)

            # ── Sleep for remainder of interval ───────────────────────────────
            elapsed    = time.monotonic() - loop_start
            sleep_time = max(0.0, cfg.INTERVAL_SECONDS - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        log.info("Shutdown requested")
    finally:
        log.info("Cleaning up…")
        anemometer.cleanup()
        rain_gauge.cleanup()
        mqtt_pub.disconnect()
        GPIO.cleanup()
        log.info("Done")


if __name__ == "__main__":
    main()
