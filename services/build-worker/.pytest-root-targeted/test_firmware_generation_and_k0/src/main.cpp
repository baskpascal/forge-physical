#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <DHT.h>

struct MonitorTelemetry {
  float temperature_c = NAN;
  float humidity_percent = NAN;
  int encoder_delta = 0;
};

MonitorTelemetry telemetry;

constexpr int I2C_SDA = 8;
constexpr int I2C_SCL = 9;

constexpr int DISPLAY_SCREEN_WIDTH = 128;
constexpr int DISPLAY_SCREEN_HEIGHT = 64;
constexpr int DISPLAY_OLED_RESET = -1;
Adafruit_SSD1306 display(DISPLAY_SCREEN_WIDTH, DISPLAY_SCREEN_HEIGHT, &Wire, DISPLAY_OLED_RESET);

constexpr int SENSOR_DHT_PIN = 4;
DHT sensor(SENSOR_DHT_PIN, DHT22);

constexpr int ENCODER_ENCODER_CLK = 5;
constexpr int ENCODER_ENCODER_DT = 6;
constexpr int ENCODER_ENCODER_SW = 7;
int encoder_last_clk = HIGH;

void render_display(const MonitorTelemetry& telemetry) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println("FORGE / PHYSICAL");
  display.drawLine(0, 12, 127, 12, SSD1306_WHITE);
  display.setCursor(0, 20);
  display.print("Temp: ");
  if (isnan(telemetry.temperature_c)) display.println("--");
  else { display.print(telemetry.temperature_c, 1); display.println(" C"); }
  display.print("Humidity: ");
  if (isnan(telemetry.humidity_percent)) display.println("--");
  else { display.print(telemetry.humidity_percent, 1); display.println(" %"); }
  display.print("Knob: ");
  display.println(telemetry.encoder_delta);
  display.display();
}

void setup() {
  Serial.begin(115200);
  Serial.println("CHECK:BOOT:PASS");
  Wire.begin(I2C_SDA, I2C_SCL);
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
      Serial.println("CHECK:OLED_INIT:FAIL");
      return;
    }
    Serial.println("CHECK:OLED_INIT:PASS");
    render_display(telemetry);
  sensor.begin();
    Serial.println("CHECK:SENSOR_INIT:PASS");
  pinMode(ENCODER_ENCODER_CLK, INPUT_PULLUP);
    pinMode(ENCODER_ENCODER_DT, INPUT_PULLUP);
    pinMode(ENCODER_ENCODER_SW, INPUT_PULLUP);
    Serial.println("CHECK:ENCODER_INIT:PASS");
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
  render_display(telemetry);
  delay(750);
}
