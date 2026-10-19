// Temperature and humidity from a DHT11 or DHT22 sensor (needs the "DHT sensor library" by Adafruit:
// arduino-cli lib install "DHT sensor library").
//   Climate air(4, DHT22);   setup: air.begin();   loop: if (air.read()) { air.tempC; air.humidity; }
// The DHT22 is more accurate; either should be read at most every 2 seconds.
#pragma once
#include <DHT.h>
class Climate {
 public:
  Climate(int pin, int type) : dht_(pin, type) {}
  void begin() { dht_.begin(); }
  bool read() {                            // false if the sensor didn't answer (check the wires)
    float t = dht_.readTemperature(), h = dht_.readHumidity();
    if (t != t || h != h) return false;    // NaN check: NaN is never equal to itself
    tempC = t; humidity = h;
    return true;
  }
  float heatIndexC() const {               // "feels like" temperature (Steadman / NOAA formula)
    float T = tempC * 9.0f / 5.0f + 32.0f, R = humidity;
    float hi = 0.5f * (T + 61.0f + (T - 68.0f) * 1.2f + R * 0.094f);
    if (hi > 79.0f)
      hi = -42.379f + 2.04901523f * T + 10.14333127f * R - 0.22475541f * T * R - 0.00683783f * T * T - 0.05481717f * R * R +
           0.00122874f * T * T * R + 0.00085282f * T * R * R - 0.00000199f * T * T * R * R;
    return (hi - 32.0f) * 5.0f / 9.0f;
  }
  float tempC = 0, humidity = 0;
 private:
  DHT dht_;
};
