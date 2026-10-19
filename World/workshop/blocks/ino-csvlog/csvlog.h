// Send readings to the computer as CSV lines over USB. Archie (or any serial monitor) can save them
// straight into a spreadsheet file.
//   CsvLog log("seconds,soil,tank");     // in setup(): log.begin();
//   log.row(millis() / 1000, soil.percent(), tank.percent());
#pragma once
class CsvLog {
 public:
  explicit CsvLog(const char* header) : header_(header) {}
  void begin(long baud = 9600) { Serial.begin(baud); Serial.println(header_); }
  template <typename A> void row(A a) { Serial.println(a); }
  template <typename A, typename B> void row(A a, B b) { Serial.print(a); Serial.print(","); Serial.println(b); }
  template <typename A, typename B, typename C> void row(A a, B b, C c) { Serial.print(a); Serial.print(","); row(b, c); }
  template <typename A, typename B, typename C, typename D> void row(A a, B b, C c, D d) { Serial.print(a); Serial.print(","); row(b, c, d); }
  template <typename A, typename B, typename C, typename D, typename E> void row(A a, B b, C c, D d, E e) { Serial.print(a); Serial.print(","); row(b, c, d, e); }
 private:
  const char* header_;
};
