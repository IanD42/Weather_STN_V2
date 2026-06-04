# Weather Station V2

A self-contained personal weather station built on a Raspberry Pi Zero 2W, publishing live sensor data to Home Assistant via MQTT.

## Hardware

| Component | Purpose |
|-----------|---------|
| Raspberry Pi Zero 2W | Main controller |
| BME280 (I2C, 0x77) | Temperature, humidity, barometric pressure |
| ADS1115 (I2C, 0x48) | 16-bit ADC for wind vane voltage |
| DS-15901 Wind & Rain Kit | Wind speed (anemometer), wind direction (vane), rainfall (tipping bucket) |

All sensors share a single I2C bus (GPIO 2/3) with the exception of the anemometer and rain gauge which use GPIO interrupt pins.

## Wiring Summary

```
BME280 / ADS1115
  VIN  → 3.3V  (Pin 1)
  GND  → GND   (Pin 6)
  SCL  → GPIO3 (Pin 5)
  SDA  → GPIO2 (Pin 3)

Wind Vane (via ADS1115 A0)
  3.3V ── 10kΩ ──┬── Vane ── GND
                 └── ADS1115 A0

Anemometer → GPIO (interrupt, configured in config.py)
Rain Gauge → GPIO (interrupt, configured in config.py)
```

## Software

- **Python 3.13** inside a virtual environment (`venv/`)
- **Adafruit CircuitPython** libraries for BME280 and ADS1115
- **paho-mqtt** for publishing to Home Assistant

### Key files

```
Weather_STN_V2/
├── main.py                  # Entry point — sensor loop and MQTT publish
├── config.py                # All hardware and MQTT settings
├── mqtt_publisher.py        # MQTT connection and Home Assistant discovery
├── requirements.txt         # Python dependencies
├── weather_station.service  # systemd unit for running at boot
└── sensors/
    ├── bme280.py            # Temperature, humidity, pressure
    ├── wind_vane.py         # Wind direction via ADS1115 ADC
    ├── anemometer.py        # Wind speed via reed switch interrupts
    └── rain_gauge.py        # Rainfall accumulation via tipping bucket
```

## Configuration

All settings are in `config.py`:

```python
SIMULATE        = False          # True = run without hardware (for testing)
MQTT_BROKER     = "192.168.1.x" # Your Home Assistant IP
MQTT_PORT       = 1883
BME280_ADDRESS  = 0x77           # 0x76 or 0x77 depending on breakout board
ADS1115_ADDRESS = 0x48
POLL_INTERVAL   = 60.0           # Seconds between readings
```

## Installation

```bash
# Clone the repo
git clone https://github.com/IanD42/Weather_STN_V2.git
cd Weather_STN_V2

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

### Run as a service (auto-start on boot)

```bash
sudo cp weather_station.service /etc/systemd/system/
sudo systemctl enable weather_station
sudo systemctl start weather_station
```

## Simulation Mode

To test the full MQTT and Home Assistant pipeline without any hardware connected, set `SIMULATE = True` in `config.py`. The simulated wind vane rotates slowly through all 16 compass points, completing one full revolution every 10 minutes.

## Home Assistant

The station uses MQTT Discovery — entities appear automatically in Home Assistant under the **Weather Station** device with the following sensors:

- Temperature (°C)
- Humidity (%)
- Pressure (hPa)
- Altitude (m)
- Wind Speed (km/h)
- Wind Direction (°)
- Wind Direction Name (N, NNE, NE … )
- Rain — Today (mm)
- Rain — Hourly (mm)
- Rain — All Time (mm)

## I2C Address Reference

| Device | Default | This build |
|--------|---------|------------|
| BME280 | 0x76 | **0x77** (SDO pulled high) |
| ADS1115 | 0x48 | 0x48 |

To scan the I2C bus on the Pi:
```python
import board, busio
i2c = busio.I2C(board.SCL, board.SDA)
print(i2c.scan())  # Should return [72, 119]
```

## License

MIT
