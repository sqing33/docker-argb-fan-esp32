#include <FastLED.h>
#include <ArduinoJson.h>

// --- 配置 ---
#define NUM_LEDS 16      // 您的LED数量
#define DATA_PIN 2       // GPIO引脚
#define BAUD_RATE 115200 // 串口波特率
#define BRIGHTNESS 90    // 亮度 (0-255)

CRGB leds[NUM_LEDS];

// --- LED状态变量 ---
enum LedMode
{
  STATIC,
  GRADIENT
};
LedMode currentMode = STATIC;

CRGB staticColor = CRGB::Black;
CRGBPalette16 gradientPalette;
uint8_t gradientSpeed = 100; // 默认速度

void setup()
{
  Serial.begin(BAUD_RATE);

  FastLED.addLeds<NEOPIXEL, DATA_PIN>(leds, NUM_LEDS);
  FastLED.setBrightness(BRIGHTNESS);

  fill_solid(leds, NUM_LEDS, CRGB::Black);
  FastLED.show();

  Serial.println("ESP32 JSON Controller Ready.");
}

void processCommand(String cmd)
{
  StaticJsonDocument<1024> doc; // 增加JSON文档大小以容纳16种颜色
  DeserializationError error = deserializeJson(doc, cmd);

  if (error)
  {
    Serial.print("JSON Parse Error: ");
    Serial.println(error.c_str());
    return;
  }

  const char *mode = doc["mode"];

  if (strcmp(mode, "static") == 0)
  {
    currentMode = STATIC;
    const char *colorStr = doc["color"];
    if (colorStr) {
        long number = strtol(&colorStr[1], NULL, 16);
        staticColor = CRGB((number >> 16) & 0xFF, (number >> 8) & 0xFF, number & 0xFF);
    }
    Serial.println("Mode: Static. OK.");
  }
  else if (strcmp(mode, "gradient") == 0)
  {
    currentMode = GRADIENT;
    
    // 如果JSON中包含速度，则更新速度
    if(!doc["speed"].isNull()){
        gradientSpeed = doc["speed"]; 
    }

    JsonArray colors = doc["colors"];
    // 如果JSON中包含颜色数组，则更新调色板
    if (!colors.isNull()) {
        CRGB paletteArray[16];
        int count = 0;
        
        // **简化逻辑**: 直接读取16种颜色
        for (JsonVariant v : colors)
        {
          if (count >= 16) break; // 安全检查，防止数据超出16个
          const char *colorStr = v.as<const char *>();
          if(colorStr) {
            long number = strtol(&colorStr[1], NULL, 16);
            paletteArray[count++] = CRGB((number >> 16) & 0xFF, (number >> 8) & 0xFF, number & 0xFF);
          }
        }
        
        // 安全填充: 如果收到的颜色不足16个，用黑色填充剩余部分以避免显示垃圾数据
        for (int i = count; i < 16; ++i)
        {
          paletteArray[i] = CRGB::Black;
        }

        // 直接用16色数组创建调色板
        gradientPalette = CRGBPalette16(paletteArray);
        Serial.println("Mode: Gradient (16 colors received). OK.");
    } else {
        Serial.println("Mode: Gradient (speed updated only). OK.");
    }
  }
}

void loop()
{
  if (Serial.available() > 0)
  {
    String command = Serial.readStringUntil('\n');
    processCommand(command);
  }

  switch (currentMode)
  {
  case STATIC:
    fill_solid(leds, NUM_LEDS, staticColor);
    FastLED.show();
    delay(100);
    break;
  case GRADIENT:
    static uint8_t startIndex = 0;
    startIndex++; 
    
    fill_palette(leds, NUM_LEDS, startIndex, 255 / NUM_LEDS, gradientPalette, 255, LINEARBLEND);
    
    FastLED.show();
    delay(gradientSpeed); 
    break;
  }
}