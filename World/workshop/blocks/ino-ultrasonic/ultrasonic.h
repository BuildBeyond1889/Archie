// HC-SR04 ultrasonic distance sensor, and a water tank level made from it.
//   Ultrasonic sonar(9, 10);                 // trig pin, echo pin
//   float cm = sonar.cm();                   // -1 if nothing came back
//   TankLevel tank(sonar, 120, 15);          // sensor is 120 cm above the empty bottom; full water is 15 cm below it
//   int pct = tank.percent();
// Mount it pointing straight down, out of splashes. In a closed tank, use the waterproof JSN-SR04T.
#pragma once
class Ultrasonic {
 public:
  Ultrasonic(int trig, int echo) : trig_(trig), echo_(echo) {}
  void begin() { pinMode(trig_, OUTPUT); pinMode(echo_, INPUT); digitalWrite(trig_, LOW); }
  float cmOnce() {
    digitalWrite(trig_, LOW); delayMicroseconds(2);
    digitalWrite(trig_, HIGH); delayMicroseconds(10);
    digitalWrite(trig_, LOW);
    unsigned long us = pulseIn(echo_, HIGH, 30000UL);     // give up after 30 ms (about 5 m)
    if (us == 0) return -1;
    return us * 0.0343f / 2.0f;                         // sound travels 0.0343 cm per microsecond, there and back
  }
  float cm(int samples = 5) {                           // the middle of a few readings ignores odd echoes
    float v[9];
    int n = 0;
    if (samples > 9) samples = 9;
    for (int i = 0; i < samples; i++) { float c = cmOnce(); if (c > 0) v[n++] = c; delay(30); }
    if (n == 0) return -1;
    for (int i = 1; i < n; i++) for (int j = i; j > 0 && v[j - 1] > v[j]; j--) { float t = v[j]; v[j] = v[j - 1]; v[j - 1] = t; }
    return v[n / 2];
  }
 private:
  int trig_, echo_;
};

class TankLevel {
 public:
  TankLevel(Ultrasonic& s, float emptyCm, float fullCm) : s_(s), empty_(emptyCm), full_(fullCm) {}
  int percent() {
    float d = s_.cm();
    if (d < 0) return -1;                               // sensor problem: say so instead of guessing
    float p = (empty_ - d) * 100.0f / (empty_ - full_);
    return (int)(p < 0 ? 0 : (p > 100 ? 100 : p + 0.5f));
  }
 private:
  Ultrasonic& s_;
  float empty_, full_;
};
