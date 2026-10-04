#include <Wire.h>
#include <math.h>

// ============================================================
// I2C CONFIGURATION
// ============================================================

#define SDA_PIN 21
#define SCL_PIN 22

#define MPU6050_ADDR 0x68

// MPU6050 registers
#define REG_PWR_MGMT_1    0x6B
#define REG_SMPLRT_DIV    0x19
#define REG_CONFIG        0x1A
#define REG_GYRO_CONFIG   0x1B
#define REG_ACCEL_CONFIG  0x1C
#define REG_ACCEL_XOUT_H  0x3B
#define REG_WHO_AM_I      0x75

// ============================================================
// SENSOR SCALE
// ============================================================

// Accelerometer configured for +/- 2 g
#define ACCEL_SCALE 16384.0f

// Gyroscope configured for +/- 250 deg/s
#define GYRO_SCALE 131.0f

// ============================================================
// FILTER CONFIGURATION
// ============================================================

const float COMPLEMENTARY_ALPHA = 0.98f;

// ============================================================
// CALIBRATION CONFIGURATION
// ============================================================

const int CALIBRATION_SAMPLES = 1000;
const int CALIBRATION_DELAY_MS = 3;

// ============================================================
// CONTROL MAPPING CONFIGURATION
// ============================================================

// Hand movement inside +/-3 degrees produces no command.
const float CONTROL_DEAD_ZONE = 3.0f;

// At +/-25 degrees the command reaches maximum magnitude.
const float CONTROL_MAX_ANGLE = 25.0f;

// Normalized robot commands
float linearCommand = 0.0f;
float angularCommand = 0.0f;

// ============================================================
// RAW SENSOR DATA
// ============================================================

int16_t accelXRaw = 0;
int16_t accelYRaw = 0;
int16_t accelZRaw = 0;

int16_t gyroXRaw = 0;
int16_t gyroYRaw = 0;
int16_t gyroZRaw = 0;

int16_t temperatureRaw = 0;

// ============================================================
// PHYSICAL VALUES
// ============================================================

float accelX = 0.0f;
float accelY = 0.0f;
float accelZ = 0.0f;

float gyroX = 0.0f;
float gyroY = 0.0f;
float gyroZ = 0.0f;

// ============================================================
// GYROSCOPE OFFSETS
// ============================================================

float gyroOffsetX = 0.0f;
float gyroOffsetY = 0.0f;
float gyroOffsetZ = 0.0f;

// ============================================================
// ANGLES
// ============================================================

float pitch = 0.0f;
float roll = 0.0f;

float pitchZero = 0.0f;
float rollZero = 0.0f;

float pitchOutput = 0.0f;
float rollOutput = 0.0f;

// ============================================================
// TIMING
// ============================================================

unsigned long previousMicros = 0;

// ============================================================
// REGISTER WRITE
// ============================================================

bool writeRegister(uint8_t reg, uint8_t value)
{
  Wire.beginTransmission(MPU6050_ADDR);

  Wire.write(reg);
  Wire.write(value);

  return (Wire.endTransmission() == 0);
}

// ============================================================
// REGISTER READ
// ============================================================

uint8_t readRegister(uint8_t reg)
{
  Wire.beginTransmission(MPU6050_ADDR);

  Wire.write(reg);

  if (Wire.endTransmission(false) != 0)
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
// MPU6050 DETECTION
// ============================================================

bool checkMPU6050()
{
  Wire.beginTransmission(MPU6050_ADDR);

  if (Wire.endTransmission() != 0)
  {
    return false;
  }

  uint8_t whoAmI = readRegister(REG_WHO_AM_I);

  Serial.print("WHO_AM_I = 0x");

  if (whoAmI < 0x10)
  {
    Serial.print("0");
  }

  Serial.println(whoAmI, HEX);

  return (whoAmI == 0x68);
}

// ============================================================
// MPU6050 INITIALIZATION
// ============================================================

bool initializeMPU6050()
{
  // Wake sensor and select internal clock initially
  if (!writeRegister(REG_PWR_MGMT_1, 0x00))
    return false;

  delay(100);

  // Sample rate divider
  writeRegister(REG_SMPLRT_DIV, 0x04);

  // Digital low-pass filter
  // CONFIG = 0x03
  writeRegister(REG_CONFIG, 0x03);

  // Gyroscope +/-250 deg/s
  writeRegister(REG_GYRO_CONFIG, 0x00);

  // Accelerometer +/-2 g
  writeRegister(REG_ACCEL_CONFIG, 0x00);

  delay(100);

  return true;
}

// ============================================================
// READ RAW MPU6050
// ============================================================

bool readMPU6050Raw()
{
  Wire.beginTransmission(MPU6050_ADDR);

  Wire.write(REG_ACCEL_XOUT_H);

  if (Wire.endTransmission(false) != 0)
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
    (int16_t)((Wire.read() << 8) | Wire.read());

  accelYRaw =
    (int16_t)((Wire.read() << 8) | Wire.read());

  accelZRaw =
    (int16_t)((Wire.read() << 8) | Wire.read());

  temperatureRaw =
    (int16_t)((Wire.read() << 8) | Wire.read());

  gyroXRaw =
    (int16_t)((Wire.read() << 8) | Wire.read());

  gyroYRaw =
    (int16_t)((Wire.read() << 8) | Wire.read());

  gyroZRaw =
    (int16_t)((Wire.read() << 8) | Wire.read());

  return true;
}

// ============================================================
// CONVERT RAW VALUES
// ============================================================

void convertSensorValues()
{
  accelX =
    (float)accelXRaw / ACCEL_SCALE;

  accelY =
    (float)accelYRaw / ACCEL_SCALE;

  accelZ =
    (float)accelZRaw / ACCEL_SCALE;

  gyroX =
    ((float)gyroXRaw - gyroOffsetX) /
    GYRO_SCALE;

  gyroY =
    ((float)gyroYRaw - gyroOffsetY) /
    GYRO_SCALE;

  gyroZ =
    ((float)gyroZRaw - gyroOffsetZ) /
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
         ) * 180.0f / PI;
}

float calculateAccelPitch()
{
  return atan2(
           -accelX,
           sqrt(
             accelY * accelY +
             accelZ * accelZ
           )
         ) * 180.0f / PI;
}

// ============================================================
// GYROSCOPE CALIBRATION
// ============================================================

void calibrateGyroscope()
{
  Serial.println();
  Serial.println("======================================");
  Serial.println(" GYROSCOPE CALIBRATION");
  Serial.println("======================================");
  Serial.println();
  Serial.println("Keep the controller COMPLETELY STILL.");
  Serial.println();

  delay(2000);

  long sumX = 0;
  long sumY = 0;
  long sumZ = 0;

  int validSamples = 0;

  for (int i = 0; i < CALIBRATION_SAMPLES; i++)
  {
    if (readMPU6050Raw())
    {
      sumX += gyroXRaw;
      sumY += gyroYRaw;
      sumZ += gyroZRaw;

      validSamples++;
    }

    if (i % 100 == 0)
    {
      Serial.print("Calibration: ");
      Serial.print(
        (i * 100) /
        CALIBRATION_SAMPLES
      );
      Serial.println("%");
    }

    delay(CALIBRATION_DELAY_MS);
  }

  if (validSamples == 0)
  {
    Serial.println(
      "ERROR: No valid calibration samples."
    );

    while (true)
    {
      delay(1000);
    }
  }

  gyroOffsetX =
    (float)sumX / validSamples;

  gyroOffsetY =
    (float)sumY / validSamples;

  gyroOffsetZ =
    (float)sumZ / validSamples;

  Serial.println();
  Serial.println("Calibration complete.");

  Serial.print("Gyro X offset: ");
  Serial.println(gyroOffsetX, 2);

  Serial.print("Gyro Y offset: ");
  Serial.println(gyroOffsetY, 2);

  Serial.print("Gyro Z offset: ");
  Serial.println(gyroOffsetZ, 2);
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

  Serial.println();
  Serial.println(
    "Measuring neutral controller orientation..."
  );

  for (int i = 0; i < samples; i++)
  {
    if (readMPU6050Raw())
    {
      convertSensorValues();

      rollSum += calculateAccelRoll();
      pitchSum += calculateAccelPitch();

      validSamples++;
    }

    delay(5);
  }

  if (validSamples == 0)
  {
    Serial.println(
      "ERROR: Could not determine initial orientation."
    );

    while (true)
    {
      delay(1000);
    }
  }

  rollZero =
    rollSum / validSamples;

  pitchZero =
    pitchSum / validSamples;

  // Start complementary filter from accelerometer estimate.
  roll = rollZero;
  pitch = pitchZero;

  Serial.println();
  Serial.println("Neutral orientation stored.");

  Serial.print("Pitch zero: ");
  Serial.print(pitchZero, 2);
  Serial.println(" deg");

  Serial.print("Roll zero: ");
  Serial.print(rollZero, 2);
  Serial.println(" deg");

  Serial.println();
  Serial.println(
    "Filtered Pitch/Roll measurements starting..."
  );

  Serial.println();

  previousMicros = micros();
}

// ============================================================
// UPDATE COMPLEMENTARY FILTER
// ============================================================

void updateOrientation()
{
  unsigned long currentMicros = micros();

  float dt =
    (currentMicros - previousMicros) /
    1000000.0f;

  previousMicros = currentMicros;

  // Protect against abnormal dt after pauses/resets.
  if (dt <= 0.0f || dt > 0.1f)
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

  // ----------------------------------------------------------
  // Complementary filter
  // ----------------------------------------------------------

  roll =
    COMPLEMENTARY_ALPHA *
    (roll + gyroX * dt)
    +
    (1.0f - COMPLEMENTARY_ALPHA) *
    accelRoll;

  pitch =
    COMPLEMENTARY_ALPHA *
    (pitch + gyroY * dt)
    +
    (1.0f - COMPLEMENTARY_ALPHA) *
    accelPitch;

  // ----------------------------------------------------------
  // Neutral-relative output
  // ----------------------------------------------------------

  rollOutput =
    roll - rollZero;

  pitchOutput =
    pitch - pitchZero;
}

// ============================================================
// ANGLE -> NORMALIZED CONTROL COMMAND
// ============================================================

float angleToCommand(float angle)
{
  float magnitude = fabs(angle);

  // ----------------------------------------------------------
  // Dead zone
  // ----------------------------------------------------------

  if (magnitude <= CONTROL_DEAD_ZONE)
  {
    return 0.0f;
  }

  // ----------------------------------------------------------
  // Saturation
  // ----------------------------------------------------------

  if (magnitude >= CONTROL_MAX_ANGLE)
  {
    return (angle > 0.0f) ? 1.0f : -1.0f;
  }

  // ----------------------------------------------------------
  // Linear mapping outside dead zone
  //
  // 3 deg  -> 0
  // 25 deg -> 1
  // ----------------------------------------------------------

  float command =
    (magnitude - CONTROL_DEAD_ZONE) /
    (CONTROL_MAX_ANGLE - CONTROL_DEAD_ZONE);

  // Restore original sign
  if (angle < 0.0f)
  {
    command = -command;
  }

  return command;
}


// ============================================================
// UPDATE ROBOT COMMANDS
// ============================================================

void updateControlCommands()
{
  // Pitch:
  // + = forward
  // - = backward
  linearCommand =
    angleToCommand(pitchOutput);

  // Roll:
  // + = right
  // - = left
  angularCommand =
    angleToCommand(rollOutput);
}

// ============================================================
// SETUP
// ============================================================

void setup()
{
  Serial.begin(115200);

  delay(1500);

  Serial.println();
  Serial.println("======================================");
  Serial.println(" ESP32 + MPU6050 ORIENTATION TEST");
  Serial.println("======================================");

  Wire.begin(
    SDA_PIN,
    SCL_PIN
  );

  Wire.setClock(400000);

  Serial.println();
  Serial.println("Checking MPU6050...");

  if (!checkMPU6050())
  {
    Serial.println(
      "ERROR: MPU6050 not detected."
    );

    while (true)
    {
      delay(1000);
    }
  }

  Serial.println(
    "MPU6050 detected successfully."
  );

  if (!initializeMPU6050())
  {
    Serial.println(
      "ERROR: MPU6050 initialization failed."
    );

    while (true)
    {
      delay(1000);
    }
  }

  Serial.println(
    "MPU6050 initialized successfully."
  );

  // ----------------------------------------------------------
  // Calibration
  // ----------------------------------------------------------

  calibrateGyroscope();

  // ----------------------------------------------------------
  // Establish controller neutral orientation
  // ----------------------------------------------------------

  initializeOrientation();
}

// ============================================================
// LOOP
// ============================================================

void loop()
{
  // ----------------------------------------------------------
  // Update filtered Pitch and Roll
  // ----------------------------------------------------------

  updateOrientation();

  // ----------------------------------------------------------
  // Convert orientation into normalized robot commands
  // ----------------------------------------------------------

  updateControlCommands();

  // ----------------------------------------------------------
  // Diagnostic serial output
  // ----------------------------------------------------------

  Serial.print("Pitch:");
  Serial.print(pitchOutput, 2);

  Serial.print(",Roll:");
  Serial.print(rollOutput, 2);

  Serial.print(",Linear:");
  Serial.print(linearCommand, 3);

  Serial.print(",Angular:");
  Serial.println(angularCommand, 3);

  delay(10);
}