#include "Arduino.h"
#include "sketch/soil.h"
#include <cassert>
int main() { SoilSensor s(A0, 520, 260); sim_analog[A0] = 520; assert(s.percent() == 0); sim_analog[A0] = 260; assert(s.percent() == 100);
  sim_analog[A0] = 390; assert(s.percent() == 50); sim_analog[A0] = 600; assert(s.percent() == 0 && s.isDry()); puts("soil ok"); }
