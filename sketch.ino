const int PIN_FAN = 6;
const int PIN_LED = 7;

void setup() {
  Serial.begin(9600);
  pinMode(PIN_FAN, OUTPUT);
  pinMode(PIN_LED, OUTPUT);
  Serial.println("Arduino ready.");
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = Serial.read();

    if (cmd == 'T') {
      digitalWrite(PIN_LED, HIGH);
      digitalWrite(PIN_FAN, HIGH);
      Serial.println("Trigger: ON");
    }

    if (cmd == 'R') {
      digitalWrite(PIN_LED, LOW);
      digitalWrite(PIN_FAN, LOW);
      Serial.println("Reset: OFF");
    }

    if (cmd == 'F') {
      digitalWrite(PIN_FAN, HIGH);
      Serial.println("Fan ON");
    }

    if (cmd == 'f') {
      digitalWrite(PIN_FAN, LOW);
      Serial.println("Fan OFF");
    }

    if (cmd == 'L') {
      digitalWrite(PIN_LED, HIGH);
      Serial.println("LED ON");
    }

    if (cmd == 'l') {
      digitalWrite(PIN_LED, LOW);
      Serial.println("LED OFF");
    }
  }
}
