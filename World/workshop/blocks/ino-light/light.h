// Light level from a photoresistor (LDR) as 0-100 %, e.g. to switch lights on at dusk.
//   LightSensor light(A1);   // LDR from 5V to A1, 10k resistor from A1 to GND
//   if (light.isDark(20)) ...
#pragma once
class LightSensor {
 public:
  explicit LightSensor(int pin, int darkReading = 50, int brightReading = 950) : pin_(pin), d_(darkReading), b_(brightReading) {}
  int percent() {
    long sum = 0;
    for (int i = 0; i < 4; i++) sum += analogRead(pin_);
    long p = (sum / 4 - d_) * 100L / (b_ - d_);
    return (int)(p < 0 ? 0 : (p > 100 ? 100 : p));
  }
  bool isDark(int belowPercent = 20) {      // a little gap (hysteresis) so it doesn't flicker at dusk
    int p = percent();
    if (dark_ && p > belowPercent + 5) dark_ = false;
    else if (!dark_ && p < belowPercent) dark_ = true;
    return dark_;
  }
 private:
  int pin_, d_, b_;
  bool dark_ = false;
};
