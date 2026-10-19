#include "Arduino.h"
#include "sketch/battery.h"
#include <cassert>
int main() { Battery b(A2, 30000, 7500); sim_analog[A2] = 508; float v = b.volts(); assert(v > 12.3 && v < 12.5);
  int p = b.percent(); assert(p > 60 && p < 80); sim_analog[A2] = 400; assert(b.percent() == 0 && b.isLow()); sim_analog[A2] = 600; assert(b.percent() == 100);
  puts("battery ok"); }
