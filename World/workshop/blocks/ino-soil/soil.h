// Soil moisture sensor (the cheap two-prong or capacitive kind) on an analog pin, as 0-100 %.
//   SoilSensor soil(A0, 520, 260);   // reading in dry air, reading in a glass of water: measure yours!
//   int wet = soil.percent();
// Capacitive sensors last much longer; the bare two-prong ones corrode in weeks.
#pragma once
class SoilSensor {
 public:
  SoilSensor(int pin, int dryReading, int wetReading, int samples = 8) : pin_(pin), dry_(dryReading), wet_(wetReading), n_(samples) {}
  int raw() {                                   // average a few readings to calm the noise
    long sum = 0;
    for (int i = 0; i < n_; i++) sum += analogRead(pin_);
    return (int)(sum / n_);
  }
  int percent() {
    long p = (long)(raw() - dry_) * 100 / (wet_ - dry_);
    return (int)(p < 0 ? 0 : (p > 100 ? 100 : p));
  }
  bool isDry(int belowPercent = 30) { return percent() < belowPercent; }
 private:
  int pin_, dry_, wet_, n_;
};
