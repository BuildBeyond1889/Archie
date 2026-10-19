// Pretend DHT sensor library for tests.
#ifndef FAKE_DHT_H
#define FAKE_DHT_H
#define DHT11 11
#define DHT22 22
inline float sim_temp = 25.0f, sim_hum = 50.0f;
class DHT { public: DHT(int, int) {} void begin() {} float readTemperature() { return sim_temp; } float readHumidity() { return sim_hum; } };
#endif
