#include <Arduino.h>
#include <Wire.h>
#include <DHT.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_MPU6050.h>

struct MonitorTelemetry {
  float temperature_c = NAN;
  float humidity_percent = NAN;
  int encoder_delta = 0;
};

MonitorTelemetry telemetry;

constexpr int I2C_SDA = 11;
constexpr int I2C_SCL = 12;

constexpr int SENSOR_DHT_PIN = 15;
DHT sensor(SENSOR_DHT_PIN, DHT22);

constexpr int ENCODER_ENCODER_CLK = 4;
constexpr int ENCODER_ENCODER_DT = 5;
constexpr int ENCODER_ENCODER_SW = 6;
int encoder_last_clk = HIGH;

Adafruit_MPU6050 imu;

void setup() {
  Serial.begin(115200);
  Serial.println("CHECK:BOOT:PASS");
  Wire.begin(I2C_SDA, I2C_SCL);
  sensor.begin();
    Serial.println("CHECK:SENSOR_INIT:PASS");
  pinMode(ENCODER_ENCODER_CLK, INPUT_PULLUP);
    pinMode(ENCODER_ENCODER_DT, INPUT_PULLUP);
    pinMode(ENCODER_ENCODER_SW, INPUT_PULLUP);
    Serial.println("CHECK:ENCODER_INIT:PASS");
  if (!imu.begin(0x68, &Wire)) {
      Serial.println("CHECK:MOTION_INIT:FAIL");
      return;
    }
    Serial.println("CHECK:MOTION_INIT:PASS");
}

void loop() {
  telemetry.humidity_percent = sensor.readHumidity();
    telemetry.temperature_c = sensor.readTemperature();
    if (!isnan(telemetry.temperature_c) && !isnan(telemetry.humidity_percent)) {
      Serial.println("CHECK:TEMPERATURE_READ:PASS");
    }
  int encoder_clk = digitalRead(ENCODER_ENCODER_CLK);
    if (encoder_clk != encoder_last_clk && encoder_clk == LOW) {
      telemetry.encoder_delta += digitalRead(ENCODER_ENCODER_DT) == encoder_clk ? -1 : 1;
      Serial.println("CHECK:ENCODER:PASS");
    }
    encoder_last_clk = encoder_clk;
  sensors_event_t imu_acceleration, imu_gyro, imu_temperature;
    imu.getEvent(&imu_acceleration, &imu_gyro, &imu_temperature);
    Serial.println("CHECK:MOTION_READ:PASS");
  delay(750);
}
