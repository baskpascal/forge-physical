#include <Arduino.h>
#include <Adafruit_GFX.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_SSD1306.h>
#include <DHT.h>

Adafruit_MPU6050 motion;
Adafruit_SSD1306 display(128, 64, &Wire, -1);
DHT sensor(4, DHT22);

void setup() {
  Wire.begin(8, 9);
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  motion.begin();
  sensor.begin();
}

void loop() {
  delay(750);
}
