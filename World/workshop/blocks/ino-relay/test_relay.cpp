#include "Arduino.h"
#include "sketch/relay.h"
#include <cassert>
int main() { Relay p(7, true, 60000UL); p.begin(); assert(sim_written[7] == HIGH && !p.isOn());
  p.runFor(10000); assert(p.isOn() && sim_written[7] == LOW); sim_advance(9999); p.update(); assert(p.isOn()); sim_advance(1); p.update(); assert(!p.isOn() && sim_written[7] == HIGH);
  p.on(); sim_advance(60000); p.update(); assert(!p.isOn() && p.tripped() && !p.tripped());
  Relay q(8, false); q.begin(); q.on(); assert(sim_written[8] == HIGH); puts("relay ok"); }
