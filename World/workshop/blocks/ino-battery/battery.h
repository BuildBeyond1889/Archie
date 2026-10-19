// Battery voltage through a resistor divider, and a rough charge % for 12 V batteries (solar systems).
//   Battery bat(A2, 30000.0, 7500.0);     // R1 from battery+ to A2 = 30k, R2 from A2 to GND = 7.5k (reads up to 25 V)
//   float v = bat.volts();  int pct = bat.percent();
// The divider keeps the pin under 5 V. Check the 5 V rail with a multimeter and set vref to it for accuracy.
// Charge % from voltage is only right when the battery has rested (no charging or big load for a while).
#pragma once
class Battery {
 public:
  enum Kind { LEAD_ACID_12V = 0, LIFEPO4_12V = 1 };
  Battery(int pin, float r1, float r2, float vref = 5.0f, Kind kind = LEAD_ACID_12V) : pin_(pin), r1_(r1), r2_(r2), vref_(vref), kind_(kind) {}
  float volts() {
    long sum = 0;
    for (int i = 0; i < 8; i++) sum += analogRead(pin_);
    float pinV = (sum / 8.0f) * vref_ / 1023.0f;
    return pinV * (r1_ + r2_) / r2_;
  }
  int percent() {
    static const float lead[] = {11.8f, 12.0f, 12.2f, 12.4f, 12.7f};     // 0, 25, 50, 75, 100 %
    static const float lfp[] = {12.0f, 13.0f, 13.1f, 13.2f, 13.4f};
    const float* t = kind_ == LIFEPO4_12V ? lfp : lead;
    float v = volts();
    if (v <= t[0]) return 0;
    if (v >= t[4]) return 100;
    for (int i = 0; i < 4; i++)
      if (v < t[i + 1]) return (int)(25 * i + 25 * (v - t[i]) / (t[i + 1] - t[i]) + 0.5f);
    return 100;
  }
  bool isLow(int belowPercent = 30) { return percent() < belowPercent; }
 private:
  int pin_;
  float r1_, r2_, vref_;
  Kind kind_;
};
