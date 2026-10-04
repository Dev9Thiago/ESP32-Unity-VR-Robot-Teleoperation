#include <Wire.h>
#include <math.h>
#include "BluetoothSerial.h"

// ============================================================
// ESP32 HAPTIC CONTROLLER
// INTEGRATED NON-BLOCKING FIRMWARE
// ============================================================
//
// ESP32 -> PC @ 50 Hz:
//
// CTRL,P:0.00,R:0.00,L:0.000,A:0.000,G:0,F:0,B:0,N:0
//
// PC -> ESP32:
//
// H0
// H1
// H2
// STATUS
// HELLO
// PING,<identifier>
//
// ============================================================


// ============================================================
// PIN CONFIGURATION
// ============================================================

const uint8_t SDA_PIN = 21;
const uint8_t SCL_PIN = 22;

const uint8_t PIN_GRAB = 25;
const uint8_t PIN_FORWARD = 26;
const uint8_t PIN_BACKWARD = 27;

const uint8_t PIN_MOTOR_1 = 32;
const uint8_t PIN_MOTOR_2 = 33;


// ============================================================
// BLUETOOTH
// ============================================================

BluetoothSerial SerialBT;

const char *BLUETOOTH_NAME =
  "ESP32_Haptic_Controller";

String bluetoothInput = "";


// ============================================================
// MPU6050
// ============================================================

#define MPU6050_ADDR       0x68

#define REG_SMPLRT_DIV     0x19
#define REG_CONFIG         0x1A
#define REG_GYRO_CONFIG    0x1B
#define REG_ACCEL_CONFIG   0x1C
#define REG_ACCEL_XOUT_H   0x3B
#define REG_PWR_MGMT_1     0x6B
#define REG_WHO_AM_I       0x75

const float ACCEL_SCALE = 16384.0f;
const float GYRO_SCALE = 131.0f;


// ============================================================
// FILTER / CALIBRATION
// ============================================================

const float COMPLEMENTARY_ALPHA = 0.98f;

const int CALIBRATION_SAMPLES = 1000;

float gyroOffsetX = 0.0f;
float gyroOffsetY = 0.0f;
float gyroOffsetZ = 0.0f;

float pitchZero = 0.0f;
float rollZero = 0.0f;


// ============================================================
// RAW SENSOR VALUES
// ============================================================

int16_t accelXRaw = 0;
int16_t accelYRaw = 0;
int16_t accelZRaw = 0;

int16_t gyroXRaw = 0;
int16_t gyroYRaw = 0;
int16_t gyroZRaw = 0;

int16_t temperatureRaw = 0;


// ============================================================
// PHYSICAL SENSOR VALUES
// ============================================================

float accelX = 0.0f;
float accelY = 0.0f;
float accelZ = 0.0f;

float gyroX = 0.0f;
float gyroY = 0.0f;
float gyroZ = 0.0f;


// ============================================================
// ORIENTATION
// ============================================================

float pitch = 0.0f;
float roll = 0.0f;

float pitchOutput = 0.0f;
float rollOutput = 0.0f;

unsigned long previousIMUTime = 0;


// ============================================================
// CONTROL MAPPING
// ============================================================

const float CONTROL_DEAD_ZONE = 3.0f;
const float CONTROL_MAX_ANGLE = 25.0f;

float linearCommand = 0.0f;
float angularCommand = 0.0f;


// ============================================================
// BUTTONS
// ============================================================

const unsigned long DEBOUNCE_TIME_MS = 30;

struct Button
{
  uint8_t pin;

  bool stableState;
  bool lastRawState;

  unsigned long lastChangeTime;
};

Button grabButton;
Button forwardButton;
Button backwardButton;


// ============================================================
// CONTROL PACKET
// ============================================================

const unsigned long CONTROL_PACKET_INTERVAL_MS = 20;

unsigned long previousControlPacketTime = 0;

uint32_t controlPacketCounter = 0;


// ============================================================
// HAPTIC MOTORS
// ============================================================

int motor1Percent = 0;
int motor2Percent = 0;


// ============================================================
// NON-BLOCKING HAPTIC STATE MACHINE
// ============================================================

enum HapticState
{
  HAPTIC_IDLE,

  H1_PULSE,

  H2_PULSE_1,
  H2_PAUSE,
  H2_PULSE_2
};

HapticState hapticState =
  HAPTIC_IDLE;

unsigned long hapticStateStart = 0;


// H1
const int H1_INTENSITY = 55;
const unsigned long H1_DURATION_MS = 180;


// H2
const int H2_INTENSITY = 85;

const unsigned long H2_PULSE_DURATION_MS = 180;
const unsigned long H2_PAUSE_DURATION_MS = 100;


// ============================================================
// MPU REGISTER WRITE
// ============================================================

bool writeMPURegister(
  uint8_t reg,
  uint8_t value
)
{
  Wire.beginTransmission(
    MPU6050_ADDR
  );

  Wire.write(reg);
  Wire.write(value);

  return (
    Wire.endTransmission() == 0
  );
}


// ============================================================
// MPU REGISTER READ
// ============================================================

uint8_t readMPURegister(
  uint8_t reg
)
{
  Wire.beginTransmission(
    MPU6050_ADDR
  );

  Wire.write(reg);

  if (
    Wire.endTransmission(false) != 0
  )
  {
    return 0xFF;
  }

  Wire.requestFrom(
    (uint8_t)MPU6050_ADDR,
    (uint8_t)1
  );

  if (Wire.available())
  {
    return Wire.read();
  }

  return 0xFF;
}


// ============================================================
// MPU DETECTION
// ============================================================

bool checkMPU6050()
{
  Wire.beginTransmission(
    MPU6050_ADDR
  );

  if (
    Wire.endTransmission() != 0
  )
  {
    return false;
  }

  uint8_t whoAmI =
    readMPURegister(
      REG_WHO_AM_I
    );

  Serial.print(
    "WHO_AM_I = 0x"
  );

  Serial.println(
    whoAmI,
    HEX
  );

  return (
    whoAmI == 0x68
  );
}


// ============================================================
// MPU INITIALIZATION
// ============================================================

bool initializeMPU6050()
{
  if (
    !writeMPURegister(
      REG_PWR_MGMT_1,
      0x00
    )
  )
  {
    return false;
  }

  delay(100);

  writeMPURegister(
    REG_SMPLRT_DIV,
    0x04
  );

  writeMPURegister(
    REG_CONFIG,
    0x03
  );

  writeMPURegister(
    REG_GYRO_CONFIG,
    0x00
  );

  writeMPURegister(
    REG_ACCEL_CONFIG,
    0x00
  );

  delay(100);

  return true;
}


// ============================================================
// READ MPU6050
// ============================================================

bool readMPU6050Raw()
{
  Wire.beginTransmission(
    MPU6050_ADDR
  );

  Wire.write(
    REG_ACCEL_XOUT_H
  );

  if (
    Wire.endTransmission(false) != 0
  )
  {
    return false;
  }

  uint8_t received =
    Wire.requestFrom(
      (uint8_t)MPU6050_ADDR,
      (uint8_t)14
    );

  if (received != 14)
  {
    return false;
  }


  accelXRaw =
    (int16_t)(
      (Wire.read() << 8)
      |
      Wire.read()
    );

  accelYRaw =
    (int16_t)(
      (Wire.read() << 8)
      |
      Wire.read()
    );

  accelZRaw =
    (int16_t)(
      (Wire.read() << 8)
      |
      Wire.read()
    );

  temperatureRaw =
    (int16_t)(
      (Wire.read() << 8)
      |
      Wire.read()
    );

  gyroXRaw =
    (int16_t)(
      (Wire.read() << 8)
      |
      Wire.read()
    );

  gyroYRaw =
    (int16_t)(
      (Wire.read() << 8)
      |
      Wire.read()
    );

  gyroZRaw =
    (int16_t)(
      (Wire.read() << 8)
      |
      Wire.read()
    );

  return true;
}


// ============================================================
// SENSOR CONVERSION
// ============================================================

void convertSensorValues()
{
  accelX =
    (float)accelXRaw /
    ACCEL_SCALE;

  accelY =
    (float)accelYRaw /
    ACCEL_SCALE;

  accelZ =
    (float)accelZRaw /
    ACCEL_SCALE;


  gyroX =
    (
      (float)gyroXRaw -
      gyroOffsetX
    )
    /
    GYRO_SCALE;

  gyroY =
    (
      (float)gyroYRaw -
      gyroOffsetY
    )
    /
    GYRO_SCALE;

  gyroZ =
    (
      (float)gyroZRaw -
      gyroOffsetZ
    )
    /
    GYRO_SCALE;
}


// ============================================================
// ACCELEROMETER ANGLES
// ============================================================

float calculateAccelRoll()
{
  return atan2(
    accelY,
    sqrt(
      accelX * accelX +
      accelZ * accelZ
    )
  )
  *
  180.0f / PI;
}


float calculateAccelPitch()
{
  return atan2(
    -accelX,
    sqrt(
      accelY * accelY +
      accelZ * accelZ
    )
  )
  *
  180.0f / PI;
}


// ============================================================
// GYROSCOPE CALIBRATION
// ============================================================

void calibrateGyroscope()
{
  Serial.println();
  Serial.println(
    "GYROSCOPE CALIBRATION"
  );

  Serial.println(
    "DO NOT MOVE CONTROLLER."
  );

  delay(2000);


  int64_t sumX = 0;
  int64_t sumY = 0;
  int64_t sumZ = 0;

  int validSamples = 0;


  for (
    int i = 0;
    i < CALIBRATION_SAMPLES;
    i++
  )
  {
    if (readMPU6050Raw())
    {
      sumX += gyroXRaw;
      sumY += gyroYRaw;
      sumZ += gyroZRaw;

      validSamples++;
    }

    delay(3);
  }


  if (validSamples == 0)
  {
    Serial.println(
      "ERROR: Gyro calibration failed."
    );

    while (true)
    {
      delay(1000);
    }
  }


  gyroOffsetX =
    (float)sumX /
    validSamples;

  gyroOffsetY =
    (float)sumY /
    validSamples;

  gyroOffsetZ =
    (float)sumZ /
    validSamples;


  Serial.print(
    "Gyro offsets: "
  );

  Serial.print(
    gyroOffsetX,
    2
  );

  Serial.print(", ");

  Serial.print(
    gyroOffsetY,
    2
  );

  Serial.print(", ");

  Serial.println(
    gyroOffsetZ,
    2
  );
}


// ============================================================
// INITIAL ORIENTATION
// ============================================================

void initializeOrientation()
{
  const int samples = 200;

  float rollSum = 0.0f;
  float pitchSum = 0.0f;

  int validSamples = 0;


  for (
    int i = 0;
    i < samples;
    i++
  )
  {
    if (readMPU6050Raw())
    {
      convertSensorValues();

      rollSum +=
        calculateAccelRoll();

      pitchSum +=
        calculateAccelPitch();

      validSamples++;
    }

    delay(5);
  }


  if (validSamples == 0)
  {
    Serial.println(
      "ERROR: Orientation calibration failed."
    );

    while (true)
    {
      delay(1000);
    }
  }


  rollZero =
    rollSum /
    validSamples;

  pitchZero =
    pitchSum /
    validSamples;

  roll = rollZero;
  pitch = pitchZero;


  Serial.print(
    "Pitch zero: "
  );

  Serial.println(
    pitchZero,
    2
  );

  Serial.print(
    "Roll zero: "
  );

  Serial.println(
    rollZero,
    2
  );


  previousIMUTime =
    micros();
}


// ============================================================
// UPDATE ORIENTATION
// ============================================================

void updateOrientation()
{
  unsigned long currentMicros =
    micros();

  float dt =
    (
      currentMicros -
      previousIMUTime
    )
    /
    1000000.0f;

  previousIMUTime =
    currentMicros;


  if (
    dt <= 0.0f ||
    dt > 0.1f
  )
  {
    dt = 0.01f;
  }


  if (!readMPU6050Raw())
  {
    return;
  }


  convertSensorValues();


  float accelRoll =
    calculateAccelRoll();

  float accelPitch =
    calculateAccelPitch();


  roll =
    COMPLEMENTARY_ALPHA *
    (
      roll +
      gyroX * dt
    )
    +
    (
      1.0f -
      COMPLEMENTARY_ALPHA
    )
    *
    accelRoll;


  pitch =
    COMPLEMENTARY_ALPHA *
    (
      pitch +
      gyroY * dt
    )
    +
    (
      1.0f -
      COMPLEMENTARY_ALPHA
    )
    *
    accelPitch;


  rollOutput =
    roll -
    rollZero;

  pitchOutput =
    pitch -
    pitchZero;
}


// ============================================================
// CONTROL MAPPING
// ============================================================

float angleToCommand(
  float angle
)
{
  float magnitude =
    fabs(angle);


  if (
    magnitude <=
    CONTROL_DEAD_ZONE
  )
  {
    return 0.0f;
  }


  if (
    magnitude >=
    CONTROL_MAX_ANGLE
  )
  {
    return (
      angle > 0.0f
    )
    ? 1.0f
    : -1.0f;
  }


  float command =
    (
      magnitude -
      CONTROL_DEAD_ZONE
    )
    /
    (
      CONTROL_MAX_ANGLE -
      CONTROL_DEAD_ZONE
    );


  if (angle < 0.0f)
  {
    command =
      -command;
  }


  return command;
}


void updateControlCommands()
{
  linearCommand =
    angleToCommand(
      pitchOutput
    );

  angularCommand =
    angleToCommand(
      rollOutput
    );
}


// ============================================================
// BUTTONS
// ============================================================

void initializeButton(
  Button &button,
  uint8_t pin
)
{
  button.pin =
    pin;

  pinMode(
    button.pin,
    INPUT_PULLUP
  );

  bool state =
    digitalRead(
      button.pin
    );

  button.stableState =
    state;

  button.lastRawState =
    state;

  button.lastChangeTime =
    millis();
}


void updateButton(
  Button &button
)
{
  bool rawState =
    digitalRead(
      button.pin
    );


  if (
    rawState !=
    button.lastRawState
  )
  {
    button.lastRawState =
      rawState;

    button.lastChangeTime =
      millis();
  }


  if (
    millis() -
    button.lastChangeTime
    >=
    DEBOUNCE_TIME_MS
  )
  {
    if (
      rawState !=
      button.stableState
    )
    {
      button.stableState =
        rawState;
    }
  }
}


bool isPressed(
  const Button &button
)
{
  return (
    button.stableState ==
    LOW
  );
}


// ============================================================
// MOTOR CONTROL
// ============================================================

uint8_t percentToPWM(
  int percent
)
{
  percent =
    constrain(
      percent,
      0,
      100
    );

  return (uint8_t)map(
    percent,
    0,
    100,
    0,
    255
  );
}


void setMotor1(
  int percent
)
{
  percent =
    constrain(
      percent,
      0,
      100
    );

  motor1Percent =
    percent;

  analogWrite(
    PIN_MOTOR_1,
    percentToPWM(
      percent
    )
  );
}


void setMotor2(
  int percent
)
{
  percent =
    constrain(
      percent,
      0,
      100
    );

  motor2Percent =
    percent;

  analogWrite(
    PIN_MOTOR_2,
    percentToPWM(
      percent
    )
  );
}


void setBothMotors(
  int percent
)
{
  setMotor1(percent);
  setMotor2(percent);
}


void stopMotors()
{
  setBothMotors(0);
}


// ============================================================
// HAPTIC STATE NAME
// ============================================================

String getHapticStateName()
{
  switch (hapticState)
  {
    case H1_PULSE:
      return "H1";

    case H2_PULSE_1:
    case H2_PAUSE:
    case H2_PULSE_2:
      return "H2";

    default:
      return "H0";
  }
}


// ============================================================
// START HAPTIC PATTERNS
// ============================================================

void startH1()
{
  setBothMotors(
    H1_INTENSITY
  );

  hapticState =
    H1_PULSE;

  hapticStateStart =
    millis();
}


void startH2()
{
  setBothMotors(
    H2_INTENSITY
  );

  hapticState =
    H2_PULSE_1;

  hapticStateStart =
    millis();
}


void cancelHaptic()
{
  stopMotors();

  hapticState =
    HAPTIC_IDLE;

  hapticStateStart =
    millis();
}


// ============================================================
// UPDATE HAPTIC STATE MACHINE
// ============================================================

void updateHaptic()
{
  unsigned long now =
    millis();


  switch (hapticState)
  {
    // --------------------------------------------------------
    // H0
    // --------------------------------------------------------

    case HAPTIC_IDLE:

      break;


    // --------------------------------------------------------
    // H1
    // --------------------------------------------------------

    case H1_PULSE:

      if (
        now -
        hapticStateStart
        >=
        H1_DURATION_MS
      )
      {
        stopMotors();

        hapticState =
          HAPTIC_IDLE;

        hapticStateStart =
          now;
      }

      break;


    // --------------------------------------------------------
    // H2 - Pulse 1
    // --------------------------------------------------------

    case H2_PULSE_1:

      if (
        now -
        hapticStateStart
        >=
        H2_PULSE_DURATION_MS
      )
      {
        stopMotors();

        hapticState =
          H2_PAUSE;

        hapticStateStart =
          now;
      }

      break;


    // --------------------------------------------------------
    // H2 - Pause
    // --------------------------------------------------------

    case H2_PAUSE:

      if (
        now -
        hapticStateStart
        >=
        H2_PAUSE_DURATION_MS
      )
      {
        setBothMotors(
          H2_INTENSITY
        );

        hapticState =
          H2_PULSE_2;

        hapticStateStart =
          now;
      }

      break;


    // --------------------------------------------------------
    // H2 - Pulse 2
    // --------------------------------------------------------

    case H2_PULSE_2:

      if (
        now -
        hapticStateStart
        >=
        H2_PULSE_DURATION_MS
      )
      {
        stopMotors();

        hapticState =
          HAPTIC_IDLE;

        hapticStateStart =
          now;
      }

      break;
  }
}


// ============================================================
// SEND CONTROL PACKET
// ============================================================

void sendControlPacket()
{
  if (!SerialBT.hasClient())
  {
    return;
  }


  SerialBT.print(
    "CTRL,P:"
  );

  SerialBT.print(
    pitchOutput,
    2
  );

  SerialBT.print(
    ",R:"
  );

  SerialBT.print(
    rollOutput,
    2
  );

  SerialBT.print(
    ",L:"
  );

  SerialBT.print(
    linearCommand,
    3
  );

  SerialBT.print(
    ",A:"
  );

  SerialBT.print(
    angularCommand,
    3
  );

  SerialBT.print(
    ",G:"
  );

  SerialBT.print(
    isPressed(grabButton)
    ? 1
    : 0
  );

  SerialBT.print(
    ",F:"
  );

  SerialBT.print(
    isPressed(forwardButton)
    ? 1
    : 0
  );

  SerialBT.print(
    ",B:"
  );

  SerialBT.print(
    isPressed(backwardButton)
    ? 1
    : 0
  );

  SerialBT.print(
    ",N:"
  );

  SerialBT.println(
    controlPacketCounter
  );


  controlPacketCounter++;
}


// ============================================================
// STATUS
// ============================================================

void sendStatus()
{
  if (!SerialBT.hasClient())
  {
    return;
  }


  SerialBT.print(
    "STATUS,H:"
  );

  SerialBT.print(
    getHapticStateName()
  );

  SerialBT.print(
    ",M1:"
  );

  SerialBT.print(
    motor1Percent
  );

  SerialBT.print(
    ",M2:"
  );

  SerialBT.print(
    motor2Percent
  );

  SerialBT.print(
    ",PACKETS:"
  );

  SerialBT.println(
    controlPacketCounter
  );
}


// ============================================================
// BLUETOOTH COMMANDS
// ============================================================

void processBluetoothCommand(
  String command
)
{
  command.trim();
  command.toUpperCase();


  if (
    command == "H0" ||
    command == "STOP"
  )
  {
    cancelHaptic();

    SerialBT.println(
      "EVENT,H0"
    );

    return;
  }


  if (command == "H1")
  {
    startH1();

    SerialBT.println(
      "EVENT,H1"
    );

    return;
  }


  if (command == "H2")
  {
    startH2();

    SerialBT.println(
      "EVENT,H2"
    );

    return;
  }


  if (command == "STATUS")
  {
    sendStatus();

    return;
  }


  if (command == "HELLO")
  {
    SerialBT.println(
      "HELLO,ESP32_HAPTIC_CONTROLLER"
    );

    return;
  }


  if (
    command.startsWith(
      "PING,"
    )
  )
  {
    String identifier =
      command.substring(5);

    SerialBT.print(
      "PONG,"
    );

    SerialBT.println(
      identifier
    );

    return;
  }


  SerialBT.println(
    "ERROR,UNKNOWN_COMMAND"
  );
}


// ============================================================
// READ BLUETOOTH
// ============================================================

void readBluetooth()
{
  while (
    SerialBT.available()
  )
  {
    char received =
      SerialBT.read();


    if (
      received == '\n'
    )
    {
      processBluetoothCommand(
        bluetoothInput
      );

      bluetoothInput = "";
    }

    else if (
      received != '\r'
    )
    {
      bluetoothInput +=
        received;


      if (
        bluetoothInput.length()
        > 100
      )
      {
        bluetoothInput = "";
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
    "========================================"
  );

  Serial.println(
    " ESP32 HAPTIC CONTROLLER"
  );

  Serial.println(
    " NON-BLOCKING INTEGRATED FIRMWARE"
  );

  Serial.println(
    "========================================"
  );


  // ----------------------------------------------------------
  // Motors
  // ----------------------------------------------------------

  pinMode(
    PIN_MOTOR_1,
    OUTPUT
  );

  pinMode(
    PIN_MOTOR_2,
    OUTPUT
  );

  cancelHaptic();


  // ----------------------------------------------------------
  // Buttons
  // ----------------------------------------------------------

  initializeButton(
    grabButton,
    PIN_GRAB
  );

  initializeButton(
    forwardButton,
    PIN_FORWARD
  );

  initializeButton(
    backwardButton,
    PIN_BACKWARD
  );


  // ----------------------------------------------------------
  // I2C
  // ----------------------------------------------------------

  Wire.begin(
    SDA_PIN,
    SCL_PIN
  );

  Wire.setClock(
    400000
  );


  // ----------------------------------------------------------
  // MPU6050
  // ----------------------------------------------------------

  if (!checkMPU6050())
  {
    Serial.println(
      "ERROR: MPU6050 not detected."
    );

    while (true)
    {
      cancelHaptic();
      delay(1000);
    }
  }


  if (!initializeMPU6050())
  {
    Serial.println(
      "ERROR: MPU6050 initialization failed."
    );

    while (true)
    {
      cancelHaptic();
      delay(1000);
    }
  }


  calibrateGyroscope();

  initializeOrientation();


  // ----------------------------------------------------------
  // Bluetooth
  // ----------------------------------------------------------

  Serial.println();
  Serial.println(
    "Starting Bluetooth..."
  );


  if (
    !SerialBT.begin(
      BLUETOOTH_NAME
    )
  )
  {
    Serial.println(
      "ERROR: Bluetooth failed."
    );

    while (true)
    {
      cancelHaptic();
      delay(1000);
    }
  }


  Serial.print(
    "Bluetooth device: "
  );

  Serial.println(
    BLUETOOTH_NAME
  );

  Serial.println();
  Serial.println(
    "CONTROLLER READY"
  );


  previousControlPacketTime =
    millis();
}


// ============================================================
// LOOP
// ============================================================

void loop()
{
  // ----------------------------------------------------------
  // Bluetooth RX
  // ----------------------------------------------------------

  readBluetooth();


  // ----------------------------------------------------------
  // Haptic state machine
  // ----------------------------------------------------------

  updateHaptic();


  // ----------------------------------------------------------
  // IMU
  // ----------------------------------------------------------

  updateOrientation();

  updateControlCommands();


  // ----------------------------------------------------------
  // Buttons
  // ----------------------------------------------------------

  updateButton(
    grabButton
  );

  updateButton(
    forwardButton
  );

  updateButton(
    backwardButton
  );


  // ----------------------------------------------------------
  // 50 Hz Bluetooth TX
  // ----------------------------------------------------------

  unsigned long currentTime =
    millis();


  if (
    currentTime -
    previousControlPacketTime
    >=
    CONTROL_PACKET_INTERVAL_MS
  )
  {
    previousControlPacketTime =
      currentTime;

    sendControlPacket();
  }


  delay(1);
}