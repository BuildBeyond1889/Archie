#include "Arduino.h"
#include "sketch/light.h"
#include <cassert>
int main() { LightSensor l(A1); sim_analog[A1] = 950; assert(l.percent() == 100 && !l.isDark());
  sim_analog[A1] = 200; assert(l.isDark(20)); sim_analog[A1] = 270; assert(l.isDark(20)); sim_analog[A1] = 320; assert(!l.isDark(20)); puts("light ok"); }
