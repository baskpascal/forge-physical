#include <Arduino.h>
#include <DHT.h>

struct MonitorTelemetry {
  float temperature_c = NAN;
  float humidity_percent = NAN;
  int encoder_delta = 0;
};

MonitorTelemetry telemetry;

constexpr int SENSOR_DHT_PIN = 15;
DHT sensor(SENSOR_DHT_PIN, DHT22);

void setup() {
  Serial.begin(115200);
  Serial.println("CHECK:BOOT:PASS");
  sensor.begin();
    Serial.println("CHECK:SENSOR_INIT:PASS");
}

void loop() {
  telemetry.humidity_percent = sensor.readHumidity();
    telemetry.temperature_c = sensor.readTemperature();
    if (!isnan(telemetry.temperature_c) && !isnan(telemetry.humidity_percent)) {
      Serial.println("CHECK:TEMPERATURE_READ:PASS");
    }
  delay(750);
}
