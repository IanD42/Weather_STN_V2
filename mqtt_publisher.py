"""
mqtt_publisher.py
MQTT publisher with Home Assistant auto-discovery support.

On connect, publishes discovery configs so all sensors automatically
appear in Home Assistant under a single 'Weather Station' device —
no manual HA configuration required.
"""

import json
import logging

import paho.mqtt.client as mqtt

log = logging.getLogger(__name__)


class MQTTPublisher:
    """Publish weather data to an MQTT broker for Home Assistant.

    Uses MQTT Discovery so all sensors appear in HA automatically.
    All 10 sensors are registered as a single device.
    """

    # Sensor definitions: (id, display_name, unit, device_class, icon, json_key)
    HA_SENSORS = [
        ("temperature",         "Temperature",          "°C",  "temperature",   "mdi:thermometer",     "temperature_c"),
        ("humidity",            "Humidity",             "%",   "humidity",      "mdi:water-percent",   "humidity_pct"),
        ("pressure",            "Pressure",             "hPa", "pressure",      "mdi:gauge",           "pressure_hpa"),
        ("altitude",            "Altitude",             "m",   None,            "mdi:altimeter",       "altitude_m"),
        ("wind_speed",          "Wind Speed",           "km/h","wind_speed",    "mdi:weather-windy",   "wind_speed_kmh"),
        ("wind_direction",      "Wind Direction",       "°",   None,            "mdi:compass",         "wind_direction_deg"),
        ("wind_direction_name", "Wind Direction Name",  None,  None,            "mdi:compass-rose",    "wind_direction_name"),
        ("rain_hourly",         "Rain (Hourly)",        "mm",  "precipitation", "mdi:weather-rainy",   "rain_hourly_mm"),
        ("rain_daily",          "Rain (Today)",         "mm",  "precipitation", "mdi:calendar-today",  "rain_daily_mm"),
        ("rain_alltime",        "Rain (All Time)",      "mm",  "precipitation", "mdi:cup-water",       "rain_alltime_mm"),
    ]

    def __init__(self, cfg):
        """cfg : Config instance"""
        self.cfg    = cfg
        self.client = mqtt.Client(client_id=cfg.MQTT_CLIENT_ID)
        self._connected = False

        if cfg.MQTT_USERNAME:
            self.client.username_pw_set(cfg.MQTT_USERNAME, cfg.MQTT_PASSWORD)

        self.client.on_connect    = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_publish    = self._on_publish

    # ── MQTT callbacks ────────────────────────────────────────────────────────

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            log.info(f"MQTT connected to {self.cfg.MQTT_HOST}:{self.cfg.MQTT_PORT}")
            self._publish_ha_discovery()
        else:
            log.error(f"MQTT connection failed (rc={rc})")

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        log.warning("MQTT disconnected")

    def _on_publish(self, client, userdata, mid):
        log.debug(f"MQTT published (mid={mid})")

    # ── Public API ────────────────────────────────────────────────────────────

    def connect(self):
        """Connect to the broker and start the background network loop."""
        self.client.connect(self.cfg.MQTT_HOST, self.cfg.MQTT_PORT, keepalive=60)
        self.client.loop_start()

    def disconnect(self):
        """Stop the network loop and disconnect cleanly."""
        self.client.loop_stop()
        self.client.disconnect()

    def publish(self, data: dict):
        """Publish a weather data dict as JSON to the state topic."""
        if not self._connected:
            log.warning("MQTT not connected — skipping publish")
            return
        topic   = f"{self.cfg.MQTT_BASE_TOPIC}/state"
        payload = json.dumps(data)
        result  = self.client.publish(topic, payload, qos=1, retain=True)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            log.error(f"MQTT publish error: {mqtt.error_string(result.rc)}")

    # ── Home Assistant Discovery ──────────────────────────────────────────────

    def _publish_ha_discovery(self):
        """Publish MQTT discovery configs so all sensors appear in HA
        automatically under a single 'Weather Station' device."""

        device = {
            "identifiers":  [self.cfg.MQTT_CLIENT_ID],
            "name":         "Weather Station",
            "model":        "Pi Zero W2 Weather Station",
            "manufacturer": "DIY",
        }
        state_topic = f"{self.cfg.MQTT_BASE_TOPIC}/state"

        for sensor_id, name, unit, dev_class, icon, value_key in self.HA_SENSORS:
            config = {
                "name":           name,
                "state_topic":    state_topic,
                "value_template": f"{{{{ value_json.{value_key} }}}}",
                "unique_id":      f"{self.cfg.MQTT_CLIENT_ID}_{sensor_id}",
                "device":         device,
                "icon":           icon,
            }
            if unit:
                config["unit_of_measurement"] = unit
            if dev_class:
                config["device_class"] = dev_class

            discovery_topic = (
                f"homeassistant/sensor/{self.cfg.MQTT_CLIENT_ID}"
                f"/{sensor_id}/config"
            )
            self.client.publish(discovery_topic, json.dumps(config),
                                qos=1, retain=True)

        log.info("Home Assistant MQTT discovery configs published")
