#include "BluetoothSerial.h"

// ============================================================
// ESP32 HAPTIC CONTROLLER
// BLUETOOTH CLASSIC SPP TEST
// ============================================================

#if !defined(CONFIG_BT_ENABLED) || \
    !defined(CONFIG_BLUEDROID_ENABLED)

#error Bluetooth is not enabled on this ESP32.

#endif

// ============================================================
// BLUETOOTH
// ============================================================

BluetoothSerial SerialBT;

const char *BLUETOOTH_NAME =
    "ESP32_Haptic_Controller";

// ============================================================
// TEST CONFIGURATION
// ============================================================

// 20 Hz diagnostic stream
const unsigned long PACKET_INTERVAL_MS = 50;

unsigned long previousPacketTime = 0;

uint32_t packetCounter = 0;

// ============================================================
// INPUT BUFFERS
// ============================================================

String bluetoothInput = "";
String usbInput = "";

// ============================================================
// SEND MESSAGE
// ============================================================

void sendBluetoothMessage(
    const String &message)
{
    SerialBT.println(message);

    // Mirror to USB for debugging.
    Serial.print("[BT TX] ");
    Serial.println(message);
}

// ============================================================
// SEND DATA PACKET
// ============================================================

void sendDataPacket()
{
    String packet =
        "DATA," +
        String(packetCounter) +
        "," +
        String(millis());

    sendBluetoothMessage(packet);

    packetCounter++;
}

// ============================================================
// PROCESS BLUETOOTH COMMAND
// ============================================================

void processBluetoothCommand(
    String command)
{
    command.trim();

    if (command.length() == 0)
    {
        return;
    }

    Serial.print("[BT RX] ");
    Serial.println(command);

    // ----------------------------------------------------------
    // PING
    //
    // Python sends:
    // PING,123456789
    //
    // ESP32 returns the exact identifier:
    // PONG,123456789
    // ----------------------------------------------------------

    if (command.startsWith("PING,"))
    {
        String identifier =
            command.substring(5);

        sendBluetoothMessage(
            "PONG," + identifier);

        return;
    }

    // ----------------------------------------------------------
    // STATUS
    // ----------------------------------------------------------

    if (command == "STATUS")
    {
        String status =
            "STATUS,UPTIME:" +
            String(millis()) +
            ",PACKETS:" +
            String(packetCounter);

        sendBluetoothMessage(status);

        return;
    }

    // ----------------------------------------------------------
    // HELLO
    // ----------------------------------------------------------

    if (command == "HELLO")
    {
        sendBluetoothMessage(
            "HELLO,ESP32_HAPTIC_CONTROLLER");

        return;
    }

    // ----------------------------------------------------------
    // Unknown
    // ----------------------------------------------------------

    sendBluetoothMessage(
        "ERROR,UNKNOWN_COMMAND");
}

// ============================================================
// PROCESS USB COMMAND
//
// Useful while debugging.
// ============================================================

void processUSBCommand(
    String command)
{
    command.trim();

    if (command == "BT_STATUS")
    {
        Serial.println();
        Serial.println(
            "Bluetooth device name:");

        Serial.println(
            BLUETOOTH_NAME);

        Serial.print(
            "Client connected: ");

        Serial.println(
            SerialBT.hasClient()
                ? "YES"
                : "NO");

        Serial.println();
    }
}

// ============================================================
// READ BLUETOOTH
// ============================================================

void readBluetooth()
{
    while (SerialBT.available())
    {
        char received =
            SerialBT.read();

        if (received == '\n')
        {
            processBluetoothCommand(
                bluetoothInput);

            bluetoothInput = "";
        }
        else if (received != '\r')
        {
            bluetoothInput += received;

            if (bluetoothInput.length() > 100)
            {
                bluetoothInput = "";
            }
        }
    }
}

// ============================================================
// READ USB SERIAL
// ============================================================

void readUSB()
{
    while (Serial.available())
    {
        char received =
            Serial.read();

        if (received == '\n')
        {
            processUSBCommand(
                usbInput);

            usbInput = "";
        }
        else if (received != '\r')
        {
            usbInput += received;

            if (usbInput.length() > 100)
            {
                usbInput = "";
            }
        }
    }
}

// ============================================================
// SETUP
// ============================================================

void setup()
{
    Serial.begin(115200);

    delay(1000);

    Serial.println();
    Serial.println(
        "========================================");

    Serial.println(
        " ESP32 HAPTIC CONTROLLER");

    Serial.println(
        " BLUETOOTH CLASSIC SPP TEST");

    Serial.println(
        "========================================");

    Serial.println();

    // ----------------------------------------------------------
    // Start Bluetooth
    // ----------------------------------------------------------

    if (!SerialBT.begin(BLUETOOTH_NAME))
    {
        Serial.println(
            "ERROR: Bluetooth initialization failed.");

        while (true)
        {
            delay(1000);
        }
    }

    Serial.print(
        "Bluetooth device: ");

    Serial.println(
        BLUETOOTH_NAME);

    Serial.println();

    Serial.println(
        "Pair this device with Windows.");

    Serial.println(
        "Waiting for Bluetooth client...");

    Serial.println();

    previousPacketTime =
        millis();
}

// ============================================================
// LOOP
// ============================================================

void loop()
{
    // ----------------------------------------------------------
    // Incoming communications
    // ----------------------------------------------------------

    readBluetooth();
    readUSB();

    // ----------------------------------------------------------
    // Periodic test stream
    // ----------------------------------------------------------

    unsigned long currentTime =
        millis();

    if (
        currentTime - previousPacketTime >= PACKET_INTERVAL_MS)
    {
        previousPacketTime =
            currentTime;

        // Only transmit test packets if a Bluetooth
        // client is actually connected.
        if (SerialBT.hasClient())
        {
            sendDataPacket();
        }
    }

    delay(1);
}