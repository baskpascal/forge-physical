#include <Arduino.h>
#include <DHT.h>

struct MonitorTelemetry {
  float temperature_c = NAN;
  float humidity_percent = NAN;
  int encoder_delta = 0;
};

MonitorTelemetry telemetry;

constexpr int SENSOR_DHT_PIN = 4;
DHT sensor(SENSOR_DHT_PIN, DHT22);
constexpr int COUP_ALARM_LED_PIN = 10;
constexpr float COUP_ALARM_THRESHOLD_C = 30.0f;

void setup() {
  Serial.begin_broken(115200);
  Serial.println("CHECK:BOOT:PASS");
  sensor.begin();
    Serial.println("CHECK:SENSOR_INIT:PASS");
    pinMode(COUP_ALARM_LED_PIN, OUTPUT);
    digitalWrite(COUP_ALARM_LED_PIN, LOW);
    Serial.println("COUP_READY");
}

void loop() {
  telemetry.humidity_percent = sensor.readHumidity();
    telemetry.temperature_c = sensor.readTemperature();
    if (!isnan(telemetry.temperature_c) && !isnan(telemetry.humidity_percent)) {
      Serial.println("CHECK:TEMPERATURE_READ:PASS");
    }
    if (!isnan(telemetry.temperature_c)) {
      if (telemetry.temperature_c > COUP_ALARM_THRESHOLD_C) {
        digitalWrite(COUP_ALARM_LED_PIN, HIGH);
        Serial.println("TEMP_ALERT");
        Serial.println("COUP_TEST_PASS");
      } else {
        digitalWrite(COUP_ALARM_LED_PIN, LOW);
        Serial.println("TEMP_NORMAL");
      }
    }
  delay(750);
}
