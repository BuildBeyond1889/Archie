#include "Arduino.h"
#include "sketch/alarm.h"
#include <cassert>
int main() { Alarm a(8); a.begin(); a.start(Alarm::FAST); assert(sim_tone_pin == 8); sim_advance(150); a.update(); assert(sim_tone_pin == -1);
  sim_advance(150); a.update(); assert(sim_tone_pin == 8); a.stop(); assert(sim_tone_pin == -1 && !a.running());
  Alarm b(9, true); b.begin(); b.start(Alarm::SOS); assert(sim_written[9] == HIGH); puts("alarm ok"); }
