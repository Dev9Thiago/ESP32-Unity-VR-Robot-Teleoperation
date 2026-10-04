// ============================================================
// ESP32 HAPTIC CONTROLLER
// BUTTON TEST
//
// Buttons:
//   GPIO25 -> Grab
//   GPIO26 -> Avatar Forward
//   GPIO27 -> Avatar Backward
//
// Wiring:
//   GPIO ---- Pushbutton ---- GND
//
// Internal pull-up resistors are enabled.
// ============================================================

// ============================================================
// PIN CONFIGURATION
// ============================================================

const uint8_t PIN_GRAB = 25;
const uint8_t PIN_FORWARD = 26;
const uint8_t PIN_BACKWARD = 27;

// ============================================================
// DEBOUNCE CONFIGURATION
// ============================================================

const unsigned long DEBOUNCE_TIME_MS = 30;

// ============================================================
// BUTTON STRUCTURE
// ============================================================

struct Button
{
    uint8_t pin;

    bool stableState;
    bool lastRawState;

    unsigned long lastChangeTime;
};

// ============================================================
// BUTTON OBJECTS
// ============================================================

Button grabButton;
Button forwardButton;
Button backwardButton;

// ============================================================
// INITIALIZE BUTTON
// ============================================================

void initializeButton(Button &button, uint8_t pin)
{
    button.pin = pin;

    pinMode(
        button.pin,
        INPUT_PULLUP);

    bool initialState =
        digitalRead(button.pin);

    button.stableState =
        initialState;

    button.lastRawState =
        initialState;

    button.lastChangeTime =
        millis();
}

// ============================================================
// UPDATE BUTTON WITH DEBOUNCING
// ============================================================

bool updateButton(Button &button)
{
    bool rawState =
        digitalRead(button.pin);

    // ----------------------------------------------------------
    // Raw input changed
    // ----------------------------------------------------------

    if (rawState != button.lastRawState)
    {
        button.lastChangeTime =
            millis();

        button.lastRawState =
            rawState;
    }

    // ----------------------------------------------------------
    // Input remained stable long enough
    // ----------------------------------------------------------

    if (
        (millis() - button.lastChangeTime) >= DEBOUNCE_TIME_MS)
    {
        if (rawState != button.stableState)
        {
            button.stableState =
                rawState;

            return true;
        }
    }

    return false;
}

// ============================================================
// IS BUTTON PRESSED?
// ============================================================

bool isPressed(const Button &button)
{
    // INPUT_PULLUP:
    //
    // LOW  = pressed
    // HIGH = released

    return button.stableState == LOW;
}

// ============================================================
// PRINT COMPLETE BUTTON STATE
// ============================================================

void printButtonStates()
{
    Serial.print("Grab:");
    Serial.print(
        isPressed(grabButton) ? 1 : 0);

    Serial.print(",Forward:");
    Serial.print(
        isPressed(forwardButton) ? 1 : 0);

    Serial.print(",Backward:");
    Serial.println(
        isPressed(backwardButton) ? 1 : 0);
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
        " ESP32 HAPTIC CONTROLLER - BUTTON TEST");

    Serial.println(
        "========================================");

    Serial.println();

    // ----------------------------------------------------------
    // Initialize buttons
    // ----------------------------------------------------------

    initializeButton(
        grabButton,
        PIN_GRAB);

    initializeButton(
        forwardButton,
        PIN_FORWARD);

    initializeButton(
        backwardButton,
        PIN_BACKWARD);

    Serial.println(
        "Buttons initialized.");

    Serial.println();

    Serial.println(
        "GPIO25 -> GRAB");

    Serial.println(
        "GPIO26 -> FORWARD");

    Serial.println(
        "GPIO27 -> BACKWARD");

    Serial.println();

    Serial.println(
        "Press and release each button.");

    Serial.println();

    // Print initial state
    printButtonStates();
}

// ============================================================
// LOOP
// ============================================================

void loop()
{
    bool stateChanged = false;

    // ----------------------------------------------------------
    // Update each button
    // ----------------------------------------------------------

    if (updateButton(grabButton))
    {
        stateChanged = true;
    }

    if (updateButton(forwardButton))
    {
        stateChanged = true;
    }

    if (updateButton(backwardButton))
    {
        stateChanged = true;
    }

    // ----------------------------------------------------------
    // Only transmit when something changes
    // ----------------------------------------------------------

    if (stateChanged)
    {
        printButtonStates();
    }

    delay(1);
}