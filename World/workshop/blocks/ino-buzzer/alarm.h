// A buzzer alarm that beeps in a pattern without stopping the rest of the program.
//   Alarm alarm(8);       alarm.start(Alarm::FAST);    alarm.update() every loop();   alarm.stop();
// Works with a passive buzzer (tone) or an active one (set active=true: just on/off).
#pragma once
class Alarm {
 public:
  enum Pattern { SLOW = 0, FAST = 1, SOS = 2 };
  Alarm(int pin, bool active = false, unsigned int hz = 2000) : pin_(pin), active_(active), hz_(hz) {}
  void begin() { pinMode(pin_, OUTPUT); quiet(); }
  void start(Pattern p) { pat_ = p; step_ = 0; running_ = true; at_ = millis(); sound(true); }
  void stop() { running_ = false; quiet(); }
  bool running() const { return running_; }
  void update() {
    if (!running_) return;
    static const unsigned int slow[] = {400, 1600}, fast[] = {150, 150}, sos[] = {150, 150, 150, 150, 150, 450, 450, 150, 450, 150, 450, 450, 150, 150, 150, 150, 150, 1500};
    const unsigned int* seq = pat_ == SLOW ? slow : pat_ == FAST ? fast : sos;
    int n = pat_ == SOS ? 18 : 2;
    if (millis() - at_ >= seq[step_]) {
      at_ = millis();
      step_ = (step_ + 1) % n;
      sound(step_ % 2 == 0);
    }
  }
 private:
  void sound(bool on) { if (!on) { quiet(); return; } if (active_) digitalWrite(pin_, HIGH); else tone(pin_, hz_); }
  void quiet() { if (active_) digitalWrite(pin_, LOW); else noTone(pin_); }
  int pin_;
  bool active_;
  unsigned int hz_;
  Pattern pat_ = SLOW;
  int step_ = 0;
  bool running_ = false;
  unsigned long at_ = 0;
};
