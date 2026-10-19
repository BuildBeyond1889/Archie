// Arduino sketch. Upload with the Arduino app or: arduino-cli upload
// archie:includes

const int STATUS_LED = LED_BUILTIN;
unsigned long lastBlink = 0;

void setup() {
  Serial.begin(9600);                 // open the Serial Monitor at 9600 to see messages
  pinMode(STATUS_LED, OUTPUT);
  Serial.println("Started");
}

void loop() {
  // Blink the built-in LED once a second without stopping everything else (no delay()).
  if (millis() - lastBlink >= 1000) {
    lastBlink = millis();
    digitalWrite(STATUS_LED, !digitalRead(STATUS_LED));
  }
  // Your code here.
}
