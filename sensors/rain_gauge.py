"""
sensors/rain_gauge.py
Tipping bucket rain gauge using GPIO interrupt counting.

DS-15901 datasheet spec:
  Each tip of the bucket = 0.2794mm of rainfall.
  Reed switch connects the two centre conductors of the RJ11 cable.

Wiring:
  Reed switch wire 1 → GPIO pin (BCM numbering)
  Reed switch wire 2 → GND
  100kΩ pull-up resistor: 3.3V → GPIO pin
  100nF capacitor: GPIO pin → GND  (hardware debounce per datasheet)
  RJ11 centre conductors.

Three rainfall accumulators are maintained:
  rain_hourly_mm  — rolling 1-hour window, resets every 60 minutes
  rain_daily_mm   — resets at the configured time each day (default midnight)
  rain_alltime_mm — never resets; lifetime total since script started
"""

import time
import threading
from datetime import datetime, timedelta

import RPi.GPIO as GPIO

import logging
log = logging.getLogger(__name__)


class RainGauge:
    """Count rainfall via GPIO interrupt from the tipping bucket reed switch."""

    MM_PER_TIP = 0.2794  # DS-15901 datasheet

    def __init__(self, gpio_pin: int,
                 daily_reset_hour: int = 0,
                 daily_reset_minute: int = 0):
        """
        gpio_pin           : BCM GPIO pin number
        daily_reset_hour   : hour of day to reset rain_daily_mm (0–23)
        daily_reset_minute : minute of hour to reset rain_daily_mm (0–59)
        """
        self.gpio_pin           = gpio_pin
        self.daily_reset_hour   = daily_reset_hour
        self.daily_reset_minute = daily_reset_minute

        self._daily_tips   = 0
        self._hourly_tips  = 0
        self._alltime_tips = 0
        self._lock              = threading.Lock()
        self._last_hour_reset   = time.monotonic()
        self._last_daily_reset  = datetime.now()

        GPIO.setup(gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(gpio_pin, GPIO.FALLING,
                              callback=self._tip_callback,
                              bouncetime=300)

        self._stop_event   = threading.Event()
        self._reset_thread = threading.Thread(
            target=self._daily_reset_loop, daemon=True)
        self._reset_thread.start()

    def _tip_callback(self, channel):
        """Called on each bucket tip — increments all accumulators."""
        with self._lock:
            self._daily_tips   += 1
            self._hourly_tips  += 1
            self._alltime_tips += 1

    def _daily_reset_loop(self):
        """Background thread: sleeps until daily reset time, then resets."""
        while not self._stop_event.is_set():
            now        = datetime.now()
            next_reset = now.replace(
                hour=self.daily_reset_hour,
                minute=self.daily_reset_minute,
                second=0, microsecond=0)
            if next_reset <= now:
                next_reset += timedelta(days=1)

            sleep_secs = (next_reset - now).total_seconds()
            while sleep_secs > 0 and not self._stop_event.is_set():
                time.sleep(min(30, sleep_secs))
                sleep_secs -= 30

            if not self._stop_event.is_set():
                self.reset_daily()
                log.info(
                    f"Rain gauge daily reset at "
                    f"{self.daily_reset_hour:02d}:{self.daily_reset_minute:02d}"
                )

    def read_daily_mm(self) -> float:
        with self._lock:
            return round(self._daily_tips * self.MM_PER_TIP, 2)

    def read_hourly_mm(self) -> float:
        now = time.monotonic()
        with self._lock:
            if now - self._last_hour_reset >= 3600:
                self._hourly_tips    = 0
                self._last_hour_reset = now
            return round(self._hourly_tips * self.MM_PER_TIP, 2)

    def read_alltime_mm(self) -> float:
        with self._lock:
            return round(self._alltime_tips * self.MM_PER_TIP, 2)

    def reset_daily(self):
        with self._lock:
            self._daily_tips       = 0
            self._last_daily_reset = datetime.now()

    def cleanup(self):
        self._stop_event.set()
        GPIO.remove_event_detect(self.gpio_pin)


class SimulatedRainGauge:
    """Simulates rainfall accumulation for testing without hardware.

    Simulates rain in bursts: raining for the first 3 minutes of every
    10-minute cycle. Tip rate during rain is configurable.
    All three accumulators behave identically to the real RainGauge.
    """

    MM_PER_TIP = 0.2794

    def __init__(self, tips_per_minute: float = 2.0,
                 daily_reset_hour: int = 0,
                 daily_reset_minute: int = 0):
        """
        tips_per_minute  : bucket tip rate during simulated rain bursts
        daily_reset_hour / daily_reset_minute : same as real RainGauge
        """
        self._tips_per_minute   = tips_per_minute
        self._daily_tips        = 0.0
        self._hourly_tips       = 0.0
        self._alltime_tips      = 0.0
        self._last_hour_reset   = time.monotonic()
        self._last_read         = time.monotonic()
        self.daily_reset_hour   = daily_reset_hour
        self.daily_reset_minute = daily_reset_minute

        self._stop_event   = threading.Event()
        self._reset_thread = threading.Thread(
            target=self._daily_reset_loop, daemon=True)
        self._reset_thread.start()

    def _is_raining(self) -> bool:
        """Rain for first 3 min of every 10-min cycle."""
        return (time.monotonic() % 600) < 180

    def _accumulate(self):
        """Calculate tips accrued since last call and add to accumulators."""
        now  = time.monotonic()
        dt   = now - self._last_read
        self._last_read = now

        if self._is_raining():
            tips = (self._tips_per_minute / 60.0) * dt
            self._daily_tips   += tips
            self._hourly_tips  += tips
            self._alltime_tips += tips

        if now - self._last_hour_reset >= 3600:
            self._hourly_tips     = 0.0
            self._last_hour_reset = now

    def read_daily_mm(self) -> float:
        self._accumulate()
        return round(self._daily_tips * self.MM_PER_TIP, 2)

    def read_hourly_mm(self) -> float:
        self._accumulate()
        return round(self._hourly_tips * self.MM_PER_TIP, 2)

    def read_alltime_mm(self) -> float:
        self._accumulate()
        return round(self._alltime_tips * self.MM_PER_TIP, 2)

    def reset_daily(self):
        self._daily_tips = 0.0

    def _daily_reset_loop(self):
        while not self._stop_event.is_set():
            now        = datetime.now()
            next_reset = now.replace(
                hour=self.daily_reset_hour,
                minute=self.daily_reset_minute,
                second=0, microsecond=0)
            if next_reset <= now:
                next_reset += timedelta(days=1)
            sleep_secs = (next_reset - now).total_seconds()
            while sleep_secs > 0 and not self._stop_event.is_set():
                time.sleep(min(30, sleep_secs))
                sleep_secs -= 30
            if not self._stop_event.is_set():
                self.reset_daily()
                log.info("Simulated rain gauge daily reset")

    def cleanup(self):
        self._stop_event.set()
