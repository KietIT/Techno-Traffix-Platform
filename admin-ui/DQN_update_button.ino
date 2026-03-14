#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <TM1637Display.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 oled(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

#define R_MAIN 25
#define Y_MAIN 26
#define G_MAIN 27
#define R_SUB 14
#define Y_SUB 12
#define G_SUB 13

#define CLK_MAIN 18
#define DIO_MAIN 19
TM1637Display displayMain(CLK_MAIN, DIO_MAIN);

#define CLK_SUB 4
#define DIO_SUB 5
TM1637Display displaySub(CLK_SUB, DIO_SUB);

const uint8_t SEG_SOS[]   = { 0x6d, 0x3f, 0x6d, 0 };
const uint8_t SEG_DASH[]  = { 0x40, 0x40, 0x40, 0x40 };

const char* ssid = "Anh Minh";
const char* password = "171970023";
const char* mqttServer = "broker.emqx.io";
const char* topicControl = "KHKT_DQN/traffic_control_node2";

WiFiClient espClient;
PubSubClient client(espClient);

// --- MODE CONSTANTS ---
enum Mode { MODE_AI, MODE_AUTO, MODE_MANUAL };

// --- STATE VARIABLES ---
Mode current_mode = MODE_AUTO;
int current_action = 0;   // 0 = Green Main (N-S), 1 = Green Sub (E-W)
int target_action = 0;
bool is_transitioning = false;
int transition_timer = 0;

int accident_timer = 0;
bool has_ambulance = false;
bool has_accident = false;
int timer_main = 30;
int timer_sub = 33;

unsigned long lastBlink = 0;
bool blinkState = false;

unsigned long lastTick = 0;
unsigned long lastMsgTime = 0;
bool timeout_active = false;

unsigned long lastReconnectAttempt = 0;

// ================= OLED =================
void updateOLED(String msg1, String msg2 = "") {
  oled.clearDisplay();
  oled.setTextSize(2);
  oled.setTextColor(SSD1306_WHITE);
  oled.setCursor(0, 10);
  oled.print(msg1);
  if(msg2 != "") {
    oled.setCursor(0, 40);
    oled.print(msg2);
  }
  oled.display();
}

// ================= 7-SEGMENT =================
void handle7Seg() {
  if (has_ambulance) {
    displayMain.setSegments(SEG_SOS);
    displaySub.setSegments(SEG_SOS);
  } else if (accident_timer > 0) {
    displayMain.showNumberDec(accident_timer, false);
    displaySub.showNumberDec(accident_timer, false);
  } else if (is_transitioning) {
    // Show yellow countdown
    displayMain.showNumberDec(transition_timer, false);
    displaySub.showNumberDec(transition_timer, false);
  } else if (current_mode == MODE_MANUAL && !timeout_active) {
    displayMain.setSegments(SEG_DASH);
    displaySub.setSegments(SEG_DASH);
  } else {
    displayMain.showNumberDec(timer_main > 0 ? timer_main : 0, false);
    displaySub.showNumberDec(timer_sub > 0 ? timer_sub : 0, false);
  }
}

// ================= SET LIGHTS DIRECTLY =================
void setLights(bool rM, bool yM, bool gM, bool rS, bool yS, bool gS) {
  digitalWrite(R_MAIN, rM); digitalWrite(Y_MAIN, yM); digitalWrite(G_MAIN, gM);
  digitalWrite(R_SUB, rS);  digitalWrite(Y_SUB, yS);  digitalWrite(G_SUB, gS);
}

// ================= UNIFIED OUTPUT LEDS =================
void updateLEDs() {
  if (is_transitioning) {
    if (current_action == 0) {
      setLights(LOW, HIGH, LOW, HIGH, LOW, LOW); // Main Yellow, Sub Red
    } else {
      setLights(HIGH, LOW, LOW, LOW, HIGH, LOW); // Main Red, Sub Yellow
    }
  } else {
    if (current_action == 0) {
      setLights(LOW, LOW, HIGH, HIGH, LOW, LOW); // Main Green, Sub Red
    } else if (current_action == 1) {
      setLights(HIGH, LOW, LOW, LOW, LOW, HIGH); // Main Red, Sub Green
    } else {
      setLights(HIGH, LOW, LOW, HIGH, LOW, LOW); // Action 2: All Red
    }
  }
}

// ================= APPLY MANUAL ACTION INSTANTLY =================
void applyManualAction(int action) {
  current_action = action;
  is_transitioning = false;
  transition_timer = 0;
  updateLEDs();
  handle7Seg();
}

// ================= START YELLOW TRANSITION =================
void startTransition(int target) {
  if (is_transitioning || current_action == target) return;
  
  Serial.println(">>> STARTING 3S YELLOW TRANSITION!");
  target_action = target;
  is_transitioning = true;
  transition_timer = 3;
  
  // Force displays to update immediately (fixes perceived delay)
  lastTick = millis(); 
  updateLEDs();
  handle7Seg();
}

// ================= RESET TO AUTO CYCLE =================
void resetToAutoCycle() {
  is_transitioning = false;
  transition_timer = 0;
  current_action = 0;
  timer_main = 30;
  timer_sub = 33;
  accident_timer = 0;
  has_ambulance = false;
  has_accident = false;
  updateLEDs();
}

// ================= MQTT CALLBACK =================
void callback(char* topic, byte* payload, unsigned int len) {
  String message;
  for (unsigned int i = 0; i < len; i++) {
    message += (char)payload[i];
  }

  StaticJsonDocument<512> doc;
  DeserializationError error = deserializeJson(doc, message);
  if (error) {
    Serial.println(">>> ERROR: Cannot parse JSON!");
    return;
  }

  String mode_str = doc["mode"].as<String>();
  int action = doc["action"].as<int>();
  bool new_amb = doc["has_ambulance"].as<bool>();
  bool new_acc = doc["has_accident"].as<bool>();

  Serial.println("====================================");
  Serial.print(">>> RECEIVED: Mode = "); Serial.print(mode_str);
  Serial.print(" | Action = "); Serial.print(action);
  Serial.print(" | Ambulance = "); Serial.print(new_amb);
  Serial.print(" | Accident = "); Serial.println(new_acc);
  Serial.println("====================================");

  // Reset timeout
  lastMsgTime = millis();
  timeout_active = false;

  Mode new_mode = MODE_AUTO;
  if (mode_str == "ai") new_mode = MODE_AI;
  else if (mode_str == "manual") new_mode = MODE_MANUAL;

  // Handle mode change
  if (new_mode != current_mode) {
    Serial.print(">>> MODE CHANGED TO: "); Serial.println(mode_str);
    if (new_mode == MODE_AUTO) {
      resetToAutoCycle();
    } else if (new_mode == MODE_AI) {
      is_transitioning = false;
      current_action = 0;
      timer_main = 10;
      timer_sub = 13;
      updateLEDs();
    }
    current_mode = new_mode;
  }

  // Update ambulance & accident
  has_ambulance = new_amb;
  if (new_acc && accident_timer <= 0 && !has_ambulance) {
    accident_timer = 10;
  }
  if (!new_acc) {
    has_accident = false;
  }

  // Action handling per mode
  if (!has_ambulance && accident_timer <= 0) {
    if (current_mode == MODE_MANUAL) {
      if (action != current_action && !is_transitioning) {
        startTransition(action);
      }
    } else if (current_mode == MODE_AI) {
      if (action != current_action && !is_transitioning) {
         startTransition(action);
      } else if (action == current_action && !is_transitioning) {
         // Extend timer if running low
         if (current_action == 0 && timer_main <= 3) { timer_main = 10; timer_sub = 13; }
         else if (current_action == 1 && timer_sub <= 3) { timer_sub = 10; timer_main = 13; }
      }
    }
  }
}

// ================= RECONNECT =================
boolean reconnect() {
  String clientId = "ESP32_AI_";
  clientId += String(random(0xffff), HEX);

  if (client.connect(clientId.c_str())) {
    client.subscribe(topicControl);
    Serial.println(">>> MQTT Connected!");
    return true;
  }
  return false;
}

// ================= SETUP =================
void setup() {
  Serial.begin(115200);

  pinMode(R_MAIN, OUTPUT); pinMode(Y_MAIN, OUTPUT); pinMode(G_MAIN, OUTPUT);
  pinMode(R_SUB, OUTPUT); pinMode(Y_SUB, OUTPUT); pinMode(G_SUB, OUTPUT);

  setLights(LOW, LOW, LOW, LOW, LOW, LOW);

  displayMain.setBrightness(7);
  displaySub.setBrightness(7);
  displayMain.setSegments(SEG_DASH);
  displaySub.setSegments(SEG_DASH);

  oled.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  updateOLED("WIFI WAIT...");

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) { delay(500); }

  randomSeed(micros());
  client.setServer(mqttServer, 1883);
  client.setCallback(callback);

  lastTick = millis();
  lastMsgTime = millis();
  timeout_active = true; 
}

// ================= MAIN LOOP =================
void loop() {
  unsigned long currentMillis = millis();

  // --- MQTT RECONNECT ---
  if (!client.connected()) {
    if (WiFi.status() == WL_CONNECTED) {
      if (currentMillis - lastReconnectAttempt > 5000) {
        lastReconnectAttempt = currentMillis;
        if (reconnect()) lastReconnectAttempt = 0;
      }
    }
  } else {
    client.loop();
  }

  // --- TIMEOUT CHECK ---
  unsigned long now = millis();
  if (!timeout_active && (now >= lastMsgTime) && (now - lastMsgTime > 30000)) {
    timeout_active = true;
    resetToAutoCycle();
    Serial.println(">>> TIMEOUT 30s - SWITCHING TO AUTO MODE!");
  }

  Mode effective_mode = timeout_active ? MODE_AUTO : current_mode;

  // ================= HIGHEST PRIORITY: AMBULANCE =================
  if (has_ambulance) {
    if (current_action == 0) setLights(LOW, LOW, HIGH, HIGH, LOW, LOW);
    else setLights(HIGH, LOW, LOW, LOW, LOW, HIGH);
    
    handle7Seg();
    updateOLED("AMBULANCE!", "OPEN ROAD");

    if (currentMillis - lastTick >= 1000) {
      lastTick = currentMillis;
      handle7Seg();
    }
    return; 
  }

  // ================= HIGHEST PRIORITY: ACCIDENT =================
  if (accident_timer > 0) {
    if (currentMillis - lastBlink >= 500) {
      lastBlink = currentMillis;
      blinkState = !blinkState;
    }
    setLights(LOW, blinkState, LOW, LOW, blinkState, LOW);

    if (currentMillis - lastTick >= 1000) {
      lastTick = currentMillis;
      accident_timer--;
      if (accident_timer <= 0) {
        if (effective_mode == MODE_AI) {
          timer_main = (current_action == 0) ? 10 : 13;
          timer_sub = (current_action == 1) ? 10 : 13;
        } else if (effective_mode == MODE_AUTO) {
          timer_main = (current_action == 0) ? 30 : 33;
          timer_sub = (current_action == 1) ? 30 : 33;
        }
        updateLEDs(); // Restore lights
      }
      handle7Seg();
    }
    updateOLED("ACCIDENT!", "CAUTION");
    return;
  }

  // ================= COMMON 1-SECOND TICK FOR ALL MODES =================
  if (currentMillis - lastTick >= 1000) {
    lastTick = currentMillis;

    if (is_transitioning) {
      // 1. Xử lý đếm ngược đèn vàng
      transition_timer--;
      if (transition_timer <= 0) {
        is_transitioning = false;
        current_action = target_action; // Hoàn tất đổi đèn
        
        // Reset thời gian tùy theo mode
        if (effective_mode == MODE_AUTO) {
          timer_main = (current_action == 0) ? 30 : 33;
          timer_sub  = (current_action == 1) ? 30 : 33;
        } else if (effective_mode == MODE_AI) {
          timer_main = (current_action == 0) ? 10 : 13;
          timer_sub  = (current_action == 1) ? 10 : 13;
        }
      }
    } else {
      // 2. Xử lý đếm ngược bình thường
      if (effective_mode == MODE_AUTO || effective_mode == MODE_AI) {
        timer_main--;
        timer_sub--;

        // Hết giờ đèn xanh -> Tự động kích hoạt chuyển đèn
        if (current_action == 0 && timer_main <= 0) {
          startTransition(1);
        } else if (current_action == 1 && timer_sub <= 0) {
          startTransition(0);
        }
      }
    }
    
    updateLEDs();
    handle7Seg();
  }

  // ================= CẬP NHẬT OLED =================
  if (is_transitioning) {
    updateOLED(effective_mode == MODE_MANUAL ? "MANUAL" : (effective_mode == MODE_AI ? "AI MODE" : "AUTO MODE"), "YELLOW 3S");
  } else {
    String stateStr = (current_action == 0) ? "NS: GREEN" : "EW: GREEN";
    if (timeout_active) updateOLED("AUTO MODE", "TIMEOUT");
    else if (effective_mode == MODE_MANUAL) updateOLED("MANUAL", stateStr);
    else if (effective_mode == MODE_AI) updateOLED("AI MODE", stateStr);
    else updateOLED("AUTO MODE", stateStr);
  }
}