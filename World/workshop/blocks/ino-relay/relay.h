// A relay that switches a pump, valve, light or fan, with a safety limit so a pump can never run forever.
//   Relay pump(7, true, 60000UL);      // pin 7, module switches on LOW (most cheap modules), never more than 60 s at a time
//   pump.runFor(10000);                // 10 seconds
//   pump.update();                     // call every loop(): turns it off on time
// Mains voltage (220/240 V) can kill. Use 12 V pumps and valves, or have an electrician wire anything on mains.
#pragma once
class Relay {
 public:
  Relay(int pin, bool activeLow = true, unsigned long maxOnMs = 0) : pin_(pin), low_(activeLow), max_(maxOnMs), on_(false), since_(0), until_(0) {}
  void begin() { digitalWrite(pin_, low_ ? HIGH : LOW); pinMode(pin_, OUTPUT); off(); }
  void on() { if (!on_) since_ = millis(); on_ = true; until_ = 0; write(); }
  void off() { on_ = false; until_ = 0; write(); }
  void runFor(unsigned long ms) { on(); until_ = millis() + ms; if (until_ == 0) until_ = 1; }
  void update() {
    if (!on_) return;
    if (until_ && (long)(millis() - until_) >= 0) off();
    else if (max_ && millis() - since_ >= max_) { off(); tripped_ = true; }
  }
  bool isOn() const { return on_; }
  bool tripped() { bool t = tripped_; tripped_ = false; return t; }   // true once after the safety limit cut it off
 private:
  void write() { digitalWrite(pin_, (on_ ^ low_) ? HIGH : LOW); }
  int pin_;
  bool low_;
  unsigned long max_;
  bool on_;
  unsigned long since_, until_;
  bool tripped_ = false;
};
