#include "Arduino.h"
#include "sketch/climate.h"
#include <cassert>
int main() { Climate c(4, DHT22); c.begin(); sim_temp = 32; sim_hum = 70; assert(c.read() && c.tempC == 32);
  float hi = c.heatIndexC(); assert(hi > 39 && hi < 42); sim_temp = NAN; assert(!c.read()); puts("climate ok"); }
