// Soil-moisture irrigation. Calibrate the sensor first: note the reading in dry air and in a glass of water
// (open the Serial Monitor; the 'raw' column shows it) and put them in SOIL_DRY and SOIL_WET.
#include "every.h"
#include "soil.h"
#include "relay.h"
#include "button.h"
#include "csvlog.h"
// archie:includes

const int SOIL_DRY = 520, SOIL_WET = 260;   // your calibration
const int WATER_BELOW_PERCENT = 35;          // water when the soil is drier than this
const unsigned long WATER_FOR_MS = 20000;    // each watering: 20 seconds
const unsigned long SOAK_MS = 10UL * 60UL * 1000UL;   // then wait 10 minutes for water to soak in before deciding again

SoilSensor soil(A0, SOIL_DRY, SOIL_WET);
Relay pump(7, true, 60000UL);                // never more than 1 minute at a time
Button manual(2);                            // press to water now
CsvLog logger("seconds,soil_percent,raw,pump");
Every check(5000);
unsigned long lastWatered = 0;
bool everWatered = false;

void setup() {
  pump.begin();
  manual.begin();
  logger.begin(9600);
}

void loop() {
  pump.update();
  if (manual.pressed()) { pump.runFor(WATER_FOR_MS); lastWatered = millis(); everWatered = true; }
  if (!check.ready()) return;

  int pct = soil.percent();
  bool soaking = everWatered && millis() - lastWatered < SOAK_MS;
  if (pct < WATER_BELOW_PERCENT && !pump.isOn() && !soaking) {
    pump.runFor(WATER_FOR_MS);
    lastWatered = millis();
    everWatered = true;
  }
  logger.row(millis() / 1000, pct, soil.raw(), pump.isOn() ? 1 : 0);
}
