// A push button that counts one press per press (no flicker), wired between the pin and GND.
//   Button btn(2);  in setup(): btn.begin();   in loop(): if (btn.pressed()) { ... }
#pragma once
class Button {
 public:
  explicit Button(int pin, unsigned long debounceMs = 30) : pin_(pin), ms_(debounceMs), stable_(HIGH), last_(HIGH), changed_(0) {}
  void begin() { pinMode(pin_, INPUT_PULLUP); stable_ = last_ = digitalRead(pin_); }
  bool pressed() {                           // true once, when the button goes down
    int r = digitalRead(pin_);
    if (r != last_) { last_ = r; changed_ = millis(); }
    if (millis() - changed_ >= ms_ && r != stable_) {
      stable_ = r;
      return stable_ == LOW;
    }
    return false;
  }
  bool isDown() const { return stable_ == LOW; }
 private:
  int pin_;
  unsigned long ms_;
  int stable_, last_;
  unsigned long changed_;
};
