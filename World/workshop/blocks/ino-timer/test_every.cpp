#include "Arduino.h"
#include "sketch/every.h"
#include <cassert>
int main() { Every e(1000); assert(e.ready()); assert(!e.ready()); sim_advance(999); assert(!e.ready()); sim_advance(1); assert(e.ready());
  sim_ms = 4294967000UL; e.reset(); sim_ms += 1200; assert(e.ready()); puts("every ok"); }
