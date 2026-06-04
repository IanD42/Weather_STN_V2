"""
sensors/anemometer.py
Cup anemometer wind speed sensor using GPIO interrupt counting.

DS-15901 datasheet spec:
  A wind speed of 2.4 km/h causes the reed switch to close once per second.
  Speed (km/h) = pulse_frequency_hz * 2.4

Wiring:
  Reed switch wire 1 → GPIO pin (BCM numbering)
  Reed switch wire 2 → GND
  Internal pull-up enabled in software.
  RJ11 inner pair (pins 2 & 3).
"""

import time
import math
import threading
from collections import deque

import RPi.GPIO as GPIO


class Anemometer:
    """Measure wind speed via GPIO interrupt from the anemometer reed switch.

    Uses a rolling time window of recent pulse timestamps to calculate
    a responsive, continuously-updated wind speed reading.
    """

    KMH_PER_HZ = 2.4  # from DS-15901 datasheet

    def __init__(self, gpio_pin: int, sample_window: float = 5.0):
        """
        gpio_pin      : BCM GPIO pin number
        sample_window : rolling window in seconds for speed calculation (default 5s)
                        Larger = smoother but slower to respond to changes.
        """
        self.gpio_pin      = gpio_pin
        self.sample_window = sample_window
        self._pulse_times  = deque()
        self._lock         = threading.Lock()

        GPIO.setup(gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(gpio_pin, GPIO.FALLING,
                              callback=self._pulse_callback,
                              bouncetime=10)

    def _pulse_callback(self, channel):
        """Called on each falling edge — records pulse timestamp."""
        now    = time.monotonic()
        cutoff = now - self.sample_window
        with self._lock:
            self._pulse_times.append(now)
            # Discard pulses older than the sample window
            while self._pulse_times and self._pulse_times[0] < cutoff:
                self._pulse_times.popleft()

    def _speed_kmh(self) -> float:
        now    = time.monotonic()
        cutoff = now - self.sample_window
        with self._lock:
            recent = sum(1 for t in self._pulse_times if t >= cutoff)
        return (recent / self.sample_window) * self.KMH_PER_HZ

    def read_speed_kmh(self) -> float:
        return round(self._speed_kmh(), 2)

    def read_speed_ms(self) -> float:
        return round(self._speed_kmh() / 3.6, 2)

    def read_speed_mph(self) -> float:
        return round(self._speed_kmh() * 0.621371, 2)

    def cleanup(self):
        GPIO.remove_event_detect(self.gpio_pin)


class SimulatedAnemometer:
    """Simulates wind speed with a slow base cycle and realistic gusts.

    Speed follows a sine wave between ~1–29 km/h over a 5-minute cycle,
    with a shorter gust pattern layered on top.
    Useful for testing MQTT and Home Assistant without hardware connected.
    """

    def __init__(self):
        self._start = time.monotonic()

    def _speed_kmh(self) -> float:
        t    = time.monotonic() - self._start
        base = 15 + 14 * math.sin(t / 300)               # 5-min slow cycle
        gust =  4 * math.sin(t / 17) * abs(math.sin(t / 5))  # rapid gusts
        return max(0.0, base + gust)

    def read_speed_kmh(self) -> float:
        return round(self._speed_kmh(), 2)

    def read_speed_ms(self) -> float:
        return round(self._speed_kmh() / 3.6, 2)

    def read_speed_mph(self) -> float:
        return round(self._speed_kmh() * 0.621371, 2)

    def cleanup(self):
        pass  # nothing to release
