#include "Arduino.h"
#include "sketch/csvlog.h"
#include <cassert>
int main() { CsvLog l("t,soil,tank"); l.begin(); l.row(1, 40, 75); l.row(2L, 41); assert(Serial.out == "t,soil,tank\n1,40,75\n2,41\n"); puts("csvlog ok"); }
