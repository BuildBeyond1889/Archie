#include "Arduino.h"
#include "sketch/ultrasonic.h"
#include <cassert>
int main() { Ultrasonic u(9, 10); u.begin(); sim_pulse_us = 5831; float c = u.cm(); assert(c > 99.9 && c < 100.1);
  TankLevel t(u, 120, 20); assert(t.percent() == 20); sim_pulse_us = 0; assert(u.cm() < 0 && t.percent() == -1);
  sim_pulse_us = 1000; assert(t.percent() == 100); puts("ultrasonic ok"); }
