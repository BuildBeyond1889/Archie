// Water tank level alarm. Set the four numbers under "YOUR TANK" first.
#include "every.h"
#include "ultrasonic.h"
#include "alarm.h"
#include "relay.h"
#include "csvlog.h"
// archie:includes

// ---- YOUR TANK (measure with a tape) ----
const float SENSOR_TO_BOTTOM_CM = 150;   // from the sensor down to the empty tank floor
const float SENSOR_TO_FULL_CM = 20;      // from the sensor down to the water when the tank is full
const int FULL_ALARM_PERCENT = 95;       // beep and stop the pump at this level
const int EMPTY_ALARM_PERCENT = 10;      // warn when this low

Ultrasonic sonar(9, 10);                 // trig on pin 9, echo on pin 10
TankLevel tank(sonar, SENSOR_TO_BOTTOM_CM, SENSOR_TO_FULL_CM);
Alarm alarm(8);                          // buzzer on pin 8
Relay pump(7, true, 30UL * 60UL * 1000UL);   // filling pump relay on pin 7; never more than 30 minutes in one go
CsvLog logger("seconds,level_percent,pump");
Every measure(5000);                     // check the tank every 5 seconds
int sensorFails = 0;

void setup() {
  sonar.begin();
  alarm.begin();
  pump.begin();
  logger.begin(9600);
  pinMode(LED_BUILTIN, OUTPUT);
}

void loop() {
  alarm.update();
  pump.update();
  if (!measure.ready()) return;

  int level = tank.percent();
  if (level < 0) {                       // no echo: the sensor is loose, wet or blocked
    if (++sensorFails >= 3) alarm.start(Alarm::SOS);
    logger.row(millis() / 1000, -1, pump.isOn() ? 1 : 0);
    return;
  }
  sensorFails = 0;

  if (level >= FULL_ALARM_PERCENT) {
    pump.off();
    if (!alarm.running()) alarm.start(Alarm::FAST);
  } else if (level <= EMPTY_ALARM_PERCENT) {
    if (!alarm.running()) alarm.start(Alarm::SLOW);
  } else {
    alarm.stop();
  }
  digitalWrite(LED_BUILTIN, level <= EMPTY_ALARM_PERCENT ? HIGH : LOW);
  if (pump.tripped()) alarm.start(Alarm::SOS);     // pump ran too long: maybe the tank leaks or the pipe broke
  logger.row(millis() / 1000, level, pump.isOn() ? 1 : 0);
}
