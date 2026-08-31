#include <Arduino.h>

struct MonitorTelemetry {
  float temperature_c = NAN;
  float humidity_percent = NAN;
  int encoder_delta = 0;
};

MonitorTelemetry telemetry;

constexpr int ENCODER_ENCODER_CLK = 4;
constexpr int ENCODER_ENCODER_DT = 5;
constexpr int ENCODER_ENCODER_SW = 6;
int encoder_last_clk = HIGH;

void setup() {
  Serial.begin(115200);
  Serial.println("CHECK:BOOT:PASS");
  pinMode(ENCODER_ENCODER_CLK, INPUT_PULLUP);
    pinMode(ENCODER_ENCODER_DT, INPUT_PULLUP);
    pinMode(ENCODER_ENCODER_SW, INPUT_PULLUP);
    Serial.println("CHECK:ENCODER_INIT:PASS");
}

void loop() {
  int encoder_clk = digitalRead(ENCODER_ENCODER_CLK);
    if (encoder_clk != encoder_last_clk && encoder_clk == LOW) {
      telemetry.encoder_delta += digitalRead(ENCODER_ENCODER_DT) == encoder_clk ? -1 : 1;
      Serial.println("CHECK:ENCODER:PASS");
    }
    encoder_last_clk = encoder_clk;
  delay(750);
}
