#include "Arduino.h"
#include "sketch/button.h"
#include <cassert>
int main() { Button b(2); b.begin(); assert(!b.pressed());
  sim_digital[2] = LOW; assert(!b.pressed()); sim_advance(10); sim_digital[2] = HIGH; b.pressed(); sim_advance(5); sim_digital[2] = LOW; b.pressed();
  sim_advance(31); assert(b.pressed()); assert(!b.pressed()); assert(b.isDown());
  sim_digital[2] = HIGH; b.pressed(); sim_advance(31); assert(!b.pressed()); assert(!b.isDown()); puts("button ok"); }
