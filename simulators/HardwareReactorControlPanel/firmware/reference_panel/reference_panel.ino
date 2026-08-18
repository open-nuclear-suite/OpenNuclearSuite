/*
  Open Nuclear Suite teaching-panel reference firmware.
  Target: Arduino Mega 2560. This is an educational mockup, not a safety system.
*/

const unsigned long BAUD = 115200;
const unsigned long DEBOUNCE_MS = 35;
const unsigned long ANALOG_PERIOD_MS = 100;
const unsigned long LINK_TIMEOUT_MS = 2000;

struct Button { const char *name; byte pin; bool stable; bool sample; unsigned long changed; };
Button buttons[] = {
  {"start", 22, HIGH, HIGH, 0}, {"pause", 23, HIGH, HIGH, 0},
  {"scram", 24, HIGH, HIGH, 0}, {"reset", 25, HIGH, HIGH, 0},
  {"step", 26, HIGH, HIGH, 0}, {"trim_minus", 27, HIGH, HIGH, 0},
  {"trim_plus", 28, HIGH, HIGH, 0}
};

struct AnalogInput { const char *name; byte pin; float low; float high; int lastSent; };
AnalogInput analogs[] = {
  {"rod_insertion_pct", A0, 0, 100, -100},
  {"coolant_flow_pct", A1, 20, 120, -100},
  {"heat_sink_pct", A2, 30, 120, -100},
  {"power_setpoint_pct", A3, 30, 120, -100},
  {"boron_ppm", A4, 0, 1000, -100},
  {"fault_severity_pct", A5, 0, 100, -100}
};

const byte MODE_MANUAL_PIN = 29;
const byte MODE_AUTO_PIN = 30;
const byte MODE_LOAD_PIN = 31;
const byte LAMP_HIGH_POWER = 40;
const byte LAMP_HIGH_TEMP = 41;
const byte LAMP_LOW_FLOW = 42;
const byte LAMP_TRIP = 43;
const byte LAMP_LINK = 44;

unsigned long sequenceNumber = 0;
unsigned long lastAnalogScan = 0;
unsigned long lastSimulatorMessage = 0;
String receiveLine;
String lastMode = "";

void emitPrefix(const char *type, const char *name) {
  Serial.print(F("{\"v\":1,\"type\":\"")); Serial.print(type);
  Serial.print(F("\",\"name\":\"")); Serial.print(name);
  Serial.print(F("\",\"seq\":")); Serial.print(sequenceNumber++);
}

void emitButton(const char *name) {
  emitPrefix("button", name); Serial.println(F(",\"value\":\"pressed\"}"));
}

void emitAnalog(AnalogInput &input, int raw) {
  float value = input.low + (input.high - input.low) * raw / 1023.0;
  emitPrefix("analog", input.name); Serial.print(F(",\"value\":"));
  Serial.print(value, 2); Serial.println('}');
}

void emitMode(const String &mode) {
  emitPrefix("mode", "control_mode"); Serial.print(F(",\"value\":\""));
  Serial.print(mode); Serial.println(F("\"}"));
}

bool jsonTrue(const String &line, const char *key) {
  String pattern = String("\"") + key + "\":true";
  return line.indexOf(pattern) >= 0;
}

void acceptSimulatorState(const String &line) {
  if (line.indexOf(F("\"type\":\"state\"")) < 0 &&
      line.indexOf(F("\"type\":\"hello\"")) < 0) return;
  lastSimulatorMessage = millis();
  digitalWrite(LAMP_LINK, HIGH);
  if (line.indexOf(F("\"type\":\"state\"")) >= 0) {
    digitalWrite(LAMP_HIGH_POWER, jsonTrue(line, "lamp_high_power"));
    digitalWrite(LAMP_HIGH_TEMP, jsonTrue(line, "lamp_high_temp"));
    digitalWrite(LAMP_LOW_FLOW, jsonTrue(line, "lamp_low_flow"));
    digitalWrite(LAMP_TRIP, jsonTrue(line, "lamp_trip"));
  }
}

void setup() {
  Serial.begin(BAUD);
  for (Button &button : buttons) pinMode(button.pin, INPUT_PULLUP);
  pinMode(MODE_MANUAL_PIN, INPUT_PULLUP); pinMode(MODE_AUTO_PIN, INPUT_PULLUP);
  pinMode(MODE_LOAD_PIN, INPUT_PULLUP);
  for (byte pin = LAMP_HIGH_POWER; pin <= LAMP_LINK; ++pin) {
    pinMode(pin, OUTPUT); digitalWrite(pin, LOW);
  }
  Serial.println(F("{\"v\":1,\"type\":\"hello\",\"name\":\"panel\",\"value\":\"mega-reference\"}"));
}

void loop() {
  unsigned long now = millis();
  for (Button &button : buttons) {
    bool sample = digitalRead(button.pin);
    if (sample != button.sample) { button.sample = sample; button.changed = now; }
    if (now - button.changed >= DEBOUNCE_MS && sample != button.stable) {
      button.stable = sample;
      if (sample == LOW) emitButton(button.name);
    }
  }

  String mode = digitalRead(MODE_MANUAL_PIN) == LOW ? "manual" :
                digitalRead(MODE_AUTO_PIN) == LOW ? "auto" :
                digitalRead(MODE_LOAD_PIN) == LOW ? "load_follow" : "";
  if (mode.length() && mode != lastMode) { lastMode = mode; emitMode(mode); }

  if (now - lastAnalogScan >= ANALOG_PERIOD_MS) {
    lastAnalogScan = now;
    for (AnalogInput &input : analogs) {
      int raw = analogRead(input.pin);
      if (abs(raw - input.lastSent) >= 3) { input.lastSent = raw; emitAnalog(input, raw); }
    }
  }

  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') { acceptSimulatorState(receiveLine); receiveLine = ""; }
    else if (c != '\r' && receiveLine.length() < 1000) receiveLine += c;
  }

  if (now - lastSimulatorMessage > LINK_TIMEOUT_MS) {
    for (byte pin = LAMP_HIGH_POWER; pin <= LAMP_LINK; ++pin) digitalWrite(pin, LOW);
  }
}
