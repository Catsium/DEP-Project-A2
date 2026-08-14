//
// 03 June 2026
// Wong YC
// revision 1
//

#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <Arduino_Nesso_N1.h>
#include <Arduino_BMI270_BMM150.h>
#include <M5GFX.h>

M5GFX display;
NessoBattery battery;

// Sampling parameters
const int sampleRate = 10;
const unsigned long sampleTime = 1000 / sampleRate;

// Separate update intervals
const unsigned long displayTime = 500;
const unsigned long batteryTime = 10000;

// Timing variables
unsigned long lastSample = 0;
unsigned long lastDisplay = 0;
unsigned long lastBattery = 0;

uint16_t chargeLevel = 0;

bool deviceConnected = false;
bool previousDeviceConnected = false;
bool acclDataValid = false;
bool gyroDataValid = false;

// BLE server name
// IMPORTANT: Give each physical Nesso a different name before uploading.
// First Nesso:  "Catsium"
// Second Nesso: "Doggsium"
// Third Nesso:  "Birdsium"
const char* bleServerName = "Flowery";

// BLE service UUID
#define SERVICE_UUID "bdc766fc-7eee-417f-bbe0-2e71a8a2bf70"

// Sensor values
float accX, accY, accZ;
float gyrX, gyrY, gyrZ;

// BLE characteristics
BLECharacteristic BMI270_accelCharacteristics(
    "cba1d466-344c-4be3-ab3f-189f80dd7518",
    BLECharacteristic::PROPERTY_NOTIFY
);

BLEDescriptor BMI270_accelDescriptor(
    BLEUUID((uint16_t)0x2A58)
);

BLECharacteristic BMI270_gyroCharacteristics(
    "19a36902-0338-413f-90e5-b429fcd37164",
    BLECharacteristic::PROPERTY_NOTIFY
);

BLEDescriptor BMI270_gyroDescriptor(
    BLEUUID((uint16_t)0x2A58)
);

BLECharacteristic BMI270_accelngyroCharacteristics(
    "f509416c-3c4b-401e-a768-b25a9e621a91",
    BLECharacteristic::PROPERTY_NOTIFY
);

BLEDescriptor BMI270_accelngyroDescriptor(
    BLEUUID((uint16_t)0x2A58)
);


class MyServerCallbacks : public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) {
        deviceConnected = true;
        lastSample = millis();

        Serial.println("BLE connected");
    }

    void onDisconnect(BLEServer* pServer) {
        deviceConnected = false;

        Serial.println("BLE disconnected");

        pServer->getAdvertising()->start();

        Serial.println("BLE advertising restarted");
    }
};


void setup() {
    battery.begin();
    battery.enableCharge();

    Serial.begin(115200);

    while (!Serial) {
        ;
    }

    Serial.println("Loading Program");

    display.begin();
    display.setRotation(1);
    display.setTextColor(TFT_WHITE, TFT_BLACK);
    display.fillScreen(TFT_GREEN);
    display.setTextSize(1.5);
    display.setTextDatum(MC_DATUM);

    display.drawString(
        "- Initializing IMU...",
        display.width() / 2,
        display.height() / 2
    );

    if (!IMU.begin()) {
        Serial.println("Failed to initialize BMI270 IMU!");

        while (1) {
            ;
        }
    }

    Serial.println("BMI270 IMU initialized.");

    chargeLevel = battery.getChargeLevel();

    Serial.print("Charge Level %: ");
    Serial.println(chargeLevel);

    delay(3000);

    display.fillScreen(TFT_BLACK);
    display.setTextSize(1.5);
    display.setTextDatum(TL_DATUM);

    display.drawString("Battery ", 5, 95);
    display.setCursor(78, 95);
    display.printf("%d", chargeLevel);
    display.drawString("%", 110, 95);

    display.drawString(bleServerName, 130, 95);
    display.drawString("Waiting for BLE connection", 5, 110);

    display.drawString("- Accl Gyro Data:", 5, 5);
    display.drawString("- X:", 5, 30);
    display.drawString("- Y:", 5, 45);
    display.drawString("- Z:", 5, 60);

    display.drawString("g", 100, 30);
    display.drawString("g", 100, 45);
    display.drawString("g", 100, 60);

    display.drawString("d/s", 185, 30);
    display.drawString("d/s", 185, 45);
    display.drawString("d/s", 185, 60);

    BLEDevice::init(bleServerName);

    BLEServer* pServer = BLEDevice::createServer();

    pServer->setCallbacks(
        new MyServerCallbacks()
    );

    BLEService* bmiService = pServer->createService(
        SERVICE_UUID
    );

    bmiService->addCharacteristic(
        &BMI270_accelCharacteristics
    );

    BMI270_accelDescriptor.setValue(
        "Accelerometer"
    );

    BMI270_accelCharacteristics.addDescriptor(
        &BMI270_accelDescriptor
    );

    bmiService->addCharacteristic(
        &BMI270_gyroCharacteristics
    );

    BMI270_gyroDescriptor.setValue(
        "Gyroscope"
    );

    BMI270_gyroCharacteristics.addDescriptor(
        &BMI270_gyroDescriptor
    );

    bmiService->addCharacteristic(
        &BMI270_accelngyroCharacteristics
    );

    BMI270_accelngyroDescriptor.setValue(
        "AccelerometerAndGyroscope"
    );

    BMI270_accelngyroCharacteristics.addDescriptor(
        &BMI270_accelngyroDescriptor
    );

    bmiService->start();

    BLEAdvertising* pAdvertising =
        BLEDevice::getAdvertising();

    pAdvertising->addServiceUUID(
        SERVICE_UUID
    );

    pAdvertising->start();

    Serial.println(
        "Waiting a client connection to notify..."
    );

    lastBattery = millis();
}


void loop() {
    unsigned long currentTime = millis();

    if (deviceConnected != previousDeviceConnected) {
        display.fillRect(
            0,
            110,
            display.width(),
            20,
            TFT_BLACK
        );

        if (deviceConnected) {
            display.drawString(
                "BLE connected",
                5,
                110
            );
        } else {
            display.drawString(
                "Waiting for BLE connection",
                5,
                110
            );
        }

        previousDeviceConnected = deviceConnected;
    }

    if (IMU.accelerationAvailable()) {
        IMU.readAcceleration(
            accX,
            accY,
            accZ
        );

        acclDataValid = true;
    }

    if (IMU.gyroscopeAvailable()) {
        IMU.readGyroscope(
            gyrX,
            gyrY,
            gyrZ
        );

        gyroDataValid = true;
    }

    if (
        deviceConnected &&
        acclDataValid &&
        gyroDataValid &&
        currentTime - lastSample >= sampleTime
    ) {
        lastSample = currentTime;

        char allBuffer[64];

        snprintf(
            allBuffer,
            sizeof(allBuffer),
            "%.2f,%.2f,%.2f,%.2f,%.2f,%.2f",
            accX,
            accY,
            accZ,
            gyrX,
            gyrY,
            gyrZ
        );

        BMI270_accelngyroCharacteristics.setValue(
            allBuffer
        );

        BMI270_accelngyroCharacteristics.notify();

        acclDataValid = false;
        gyroDataValid = false;

        if (currentTime - lastDisplay >= displayTime) {
            lastDisplay = currentTime;

            display.fillRect(
                40,
                30,
                150,
                45,
                TFT_BLACK
            );

            display.setTextColor(
                TFT_GREEN,
                TFT_BLACK
            );

            display.setTextSize(1.5);

            display.setCursor(40, 30);
            display.printf("%+.3f", accX);

            display.setCursor(40, 45);
            display.printf("%+.3f", accY);

            display.setCursor(40, 60);
            display.printf("%+.3f", accZ);

            display.setCursor(120, 30);
            display.printf("%+.1f", gyrX);

            display.setCursor(120, 45);
            display.printf("%+.1f", gyrY);

            display.setCursor(120, 60);
            display.printf("%+.1f", gyrZ);
        }
    }

    if (currentTime - lastBattery >= batteryTime) {
        lastBattery = currentTime;

        chargeLevel = battery.getChargeLevel();

        Serial.print("Charge Level %: ");
        Serial.println(chargeLevel);

        display.fillRect(
            78,
            95,
            30,
            15,
            TFT_BLACK
        );

        display.setCursor(78, 95);
        display.printf("%d", chargeLevel);
    }
}