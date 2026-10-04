// ============================================================
// ESP32 HAPTIC CONTROLLER - HAPTIC TEST
//
// GPIO32 -> Motor 1 MOSFET gate
// GPIO33 -> Motor 2 MOSFET gate
//
// Serial commands:
// M1,<0-100>
// M2,<0-100>
// BOTH,<0-100>
// H0
// H1
// H2
// STOP
// STATUS
// ============================================================

const uint8_t PIN_MOTOR_1 = 32;
const uint8_t PIN_MOTOR_2 = 33;

// PWM range used internally: 0-255
int motor1Percent = 0;
int motor2Percent = 0;

String inputCommand = "";

// ============================================================
// PERCENT -> PWM
// ============================================================

uint8_t percentToPWM(int percent)
{
    percent = constrain(percent, 0, 100);

    return (uint8_t)map(
        percent,
        0,
        100,
        0,
        255);
}

// ============================================================
// MOTOR CONTROL
// ============================================================

void setMotor1(int percent)
{
    percent = constrain(percent, 0, 100);

    motor1Percent = percent;

    analogWrite(
        PIN_MOTOR_1,
        percentToPWM(percent));
}

void setMotor2(int percent)
{
    percent = constrain(percent, 0, 100);

    motor2Percent = percent;

    analogWrite(
        PIN_MOTOR_2,
        percentToPWM(percent));
}

void setBothMotors(int percent)
{
    setMotor1(percent);
    setMotor2(percent);
}

void stopMotors()
{
    setMotor1(0);
    setMotor2(0);
}

// ============================================================
// STATUS
// ============================================================

void sendStatus()
{
    Serial.print("STATUS,M1:");
    Serial.print(motor1Percent);

    Serial.print(",M2:");
    Serial.println(motor2Percent);
}

// ============================================================
// HAPTIC PATTERNS
// ============================================================

// H0 = no haptic feedback
void patternH0()
{
    stopMotors();

    Serial.println("EVENT,H0");
}

// H1 = manipulable object
//
// Short, softer pulse.
// This should feel clearly different from a wall collision.
void patternH1()
{
    Serial.println("EVENT,H1");

    setBothMotors(55);

    delay(180);

    stopMotors();

    sendStatus();
}

// H2 = wall / boundary
//
// Two stronger pulses.
void patternH2()
{
    Serial.println("EVENT,H2");

    setBothMotors(85);

    delay(180);

    stopMotors();

    delay(100);

    setBothMotors(85);

    delay(180);

    stopMotors();

    sendStatus();
}

// ============================================================
// COMMAND PROCESSING
// ============================================================

void processCommand(String command)
{
    command.trim();
    command.toUpperCase();

    // ----------------------------------------------------------
    // Emergency stop
    // ----------------------------------------------------------

    if (
        command == "STOP" ||
        command == "H0")
    {
        stopMotors();

        Serial.println("OK,STOP");

        sendStatus();

        return;
    }

    // ----------------------------------------------------------
    // Haptic patterns
    // ----------------------------------------------------------

    if (command == "H1")
    {
        patternH1();
        return;
    }

    if (command == "H2")
    {
        patternH2();
        return;
    }

    // ----------------------------------------------------------
    // Status
    // ----------------------------------------------------------

    if (command == "STATUS")
    {
        sendStatus();
        return;
    }

    // ----------------------------------------------------------
    // Motor 1
    // ----------------------------------------------------------

    if (command.startsWith("M1,"))
    {
        int percent =
            command.substring(3).toInt();

        percent =
            constrain(percent, 0, 100);

        setMotor1(percent);

        Serial.print("OK,M1:");
        Serial.println(percent);

        sendStatus();

        return;
    }

    // ----------------------------------------------------------
    // Motor 2
    // ----------------------------------------------------------

    if (command.startsWith("M2,"))
    {
        int percent =
            command.substring(3).toInt();

        percent =
            constrain(percent, 0, 100);

        setMotor2(percent);

        Serial.print("OK,M2:");
        Serial.println(percent);

        sendStatus();

        return;
    }

    // ----------------------------------------------------------
    // Both
    // ----------------------------------------------------------

    if (command.startsWith("BOTH,"))
    {
        int percent =
            command.substring(5).toInt();

        percent =
            constrain(percent, 0, 100);

        setBothMotors(percent);

        Serial.print("OK,BOTH:");
        Serial.println(percent);

        sendStatus();

        return;
    }

    // ----------------------------------------------------------
    // Unknown command
    // ----------------------------------------------------------

    Serial.print("ERROR,UNKNOWN_COMMAND:");
    Serial.println(command);
}

// ============================================================
// SETUP
// ============================================================

void setup()
{
    Serial.begin(115200);

    pinMode(
        PIN_MOTOR_1,
        OUTPUT);

    pinMode(
        PIN_MOTOR_2,
        OUTPUT);

    stopMotors();

    delay(1000);

    Serial.println();
    Serial.println(
        "========================================");

    Serial.println(
        " ESP32 HAPTIC CONTROLLER - HAPTIC TEST");

    Serial.println(
        "========================================");

    Serial.println();

    Serial.println("GPIO32 -> MOTOR 1");
    Serial.println("GPIO33 -> MOTOR 2");

    Serial.println();

    Serial.println("READY");

    sendStatus();
}

// ============================================================
// LOOP
// ============================================================

void loop()
{
    while (Serial.available())
    {
        char received =
            Serial.read();

        if (received == '\n')
        {
            processCommand(
                inputCommand);

            inputCommand = "";
        }
        else if (received != '\r')
        {
            inputCommand += received;

            // Prevent malformed data from filling memory.
            if (inputCommand.length() > 50)
            {
                inputCommand = "";
            }
        }
    }
}