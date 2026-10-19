// Do something every N milliseconds without delay(), so the board can do other things meanwhile.
//   Every readSoil(2000);              // every 2 seconds
//   if (readSoil.ready()) { ... }
#pragma once
class Every {
 public:
  explicit Every(unsigned long ms) : ms_(ms), last_(0), first_(true) {}
  bool ready() {
    unsigned long now = millis();
    if (first_ || now - last_ >= ms_) {   // subtraction keeps working when millis() wraps after 49 days
      first_ = false;
      last_ = now;
      return true;
    }
    return false;
  }
  void setInterval(unsigned long ms) { ms_ = ms; }
  void reset() { last_ = millis(); first_ = false; }
 private:
  unsigned long ms_, last_;
  bool first_;
};
