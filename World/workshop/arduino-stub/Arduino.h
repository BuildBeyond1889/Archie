// A pretend Arduino for testing blocks on a normal computer. Not used on real boards.
// Tests set sim_analog[pin], sim_digital[pin], sim_pulse_us and move time with delay()/sim_advance().
#ifndef ARCHIE_FAKE_ARDUINO_H
#define ARCHIE_FAKE_ARDUINO_H
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <cmath>
typedef uint8_t byte;
typedef bool boolean;
#define HIGH 1
#define LOW 0
#define INPUT 0
#define OUTPUT 1
#define INPUT_PULLUP 2
#define A0 14
#define A1 15
#define A2 16
#define A3 17
#define A4 18
#define A5 19
#define LED_BUILTIN 13
inline int sim_analog[32];
inline int sim_digital[32];
inline int sim_written[32];
inline int sim_mode[32];
inline unsigned long sim_ms = 0;
inline unsigned long sim_pulse_us = 0;
inline int sim_tone_pin = -1;
inline void pinMode(int p, int m) { sim_mode[p] = m; if (m == INPUT_PULLUP && !sim_digital[p]) sim_digital[p] = HIGH; }
inline void digitalWrite(int p, int v) { sim_written[p] = v; }
inline int digitalRead(int p) { return sim_digital[p]; }
inline int analogRead(int p) { return sim_analog[p]; }
inline void analogWrite(int p, int v) { sim_written[p] = v; }
inline unsigned long millis() { return sim_ms; }
inline unsigned long micros() { return sim_ms * 1000UL; }
inline void delay(unsigned long ms) { sim_ms += ms; }
inline void delayMicroseconds(unsigned int) {}
inline void sim_advance(unsigned long ms) { sim_ms += ms; }
inline unsigned long pulseIn(int, int, unsigned long = 1000000UL) { return sim_pulse_us; }
inline void tone(int p, unsigned int, unsigned long = 0) { sim_tone_pin = p; }
inline void noTone(int) { sim_tone_pin = -1; }
inline long map(long x, long a, long b, long c, long d) { return (x - a) * (d - c) / (b - a) + c; }
template <class T> inline T constrain(T x, T a, T b) { return x < a ? a : (x > b ? b : x); }
class String : public std::string {
 public:
  String() {}
  String(const char* s) : std::string(s) {}
  String(const std::string& s) : std::string(s) {}
  String(int v) : std::string(std::to_string(v)) {}
  String(long v) : std::string(std::to_string(v)) {}
  String(unsigned long v) : std::string(std::to_string(v)) {}
  String(double v, int d = 2) { char b[32]; snprintf(b, sizeof b, "%.*f", d, v); assign(b); }
};
struct FakeSerial {
  std::string out;
  void begin(long) {}
  operator bool() const { return true; }
  void print(const char* s) { out += s; }
  void print(const std::string& s) { out += s; }
  void print(int v) { out += std::to_string(v); }
  void print(long v) { out += std::to_string(v); }
  void print(unsigned long v) { out += std::to_string(v); }
  void print(double v, int d = 2) { char b[32]; snprintf(b, sizeof b, "%.*f", d, v); out += b; }
  template <class T> void println(T v) { print(v); out += "\n"; }
  void println(double v, int d) { print(v, d); out += "\n"; }
  void println() { out += "\n"; }
};
inline FakeSerial Serial;
#endif
