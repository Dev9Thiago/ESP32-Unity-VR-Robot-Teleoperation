# ESP32–Unity VR Robot Teleoperation

Immersive virtual-reality teleoperation system that integrates a custom ESP32-based haptic controller with a mobile robot simulated in Unity.

The project was developed for the **Virtual Reality** course of the **Mechatronics Engineering** program at **Universidad Militar Nueva Granada**, academic period **2026-2**.

## Project Overview

The system allows a user to teleoperate a virtual mobile robot by physically tilting a handheld controller. An **MPU6050** measures controller orientation, an **ESP32** processes Pitch and Roll, and normalized motion commands are transmitted to Unity through **Bluetooth Classic SPP**.

The controller also includes physical buttons for avatar navigation and object grabbing. Unity detects robot interactions and sends differentiated commands back to the ESP32, where two vibrotactile motors provide haptic feedback.

The final immersive visualization uses **Unity + OpenXR**, with the tested VR chain using **SteamVR + VRidge + a smartphone VR viewer**.

## Implemented Architecture

```text
                         USER
                          |
              +-----------+-----------+
              |                       |
              v                       v
      Handheld Controller          VR Headset
      ESP32 + MPU6050              Head tracking
      Buttons + Haptics                 |
              |                         |
              | Bluetooth Classic SPP   |
              v                         v
        +------------------------------------+
        |                UNITY               |
        |                                    |
        |  Virtual Robot     Avatar          |
        |  Grab System       Physics         |
        |  Collision / Haptic Event Manager  |
        +------------------------------------+
```

Two bidirectional information paths are implemented:

```text
CONTROL
Pitch / Roll + Buttons
        ↓
      ESP32
        ↓
 Bluetooth Classic SPP
        ↓
      Unity
        ↓
Robot / Avatar / Grab System
```

```text
HAPTIC FEEDBACK
Virtual Collision / Interaction
        ↓
      Unity
        ↓
   H0 / H1 / H2
        ↓
 Bluetooth Classic SPP
        ↓
      ESP32
        ↓
 Vibrotactile Motors
```

## Controller Mapping

The final controller uses proportional orientation mapping:

| Physical input | Function |
|---|---|
| Pitch + | Robot forward |
| Pitch − | Robot reverse |
| Roll + | Robot right rotation |
| Roll − | Robot left rotation |
| Forward button | Avatar forward |
| Backward button | Avatar backward |
| Grab button | Grab / release object |

Orientation commands use:

- Complementary filter: `alpha = 0.98`
- Dead zone: `±3°`
- Saturation angle: `±25°`
- Normalized output range: `[-1, 1]`
- Controller packet target rate: `50 Hz`

The mapping is:

```text
|angle| <= 3°      -> 0

3° < |angle| < 25°
-> sign(angle) * (|angle| - 3) / (25 - 3)

|angle| >= 25°     -> sign(angle)
```

## Haptic Feedback

Unity classifies relevant interactions and sends a high-level haptic command to the controller.

| Command | Meaning | Pattern |
|---|---|---|
| `H0` | Stop / no haptic event | Motors off |
| `H1` | Manipulable-object interaction | 55%, 180 ms |
| `H2` | Wall / environment collision | 85%, 180 ms → 100 ms pause → 85%, 180 ms |

The haptic firmware uses a **non-blocking state machine**, allowing sensor acquisition, button processing and Bluetooth transmission to continue while a vibration pattern is executing.

Unity applies a `0.50 s` haptic-event cooldown so a persistent physics contact does not continuously restart the `H2` sequence.

## ESP32 Hardware

Final controller pin assignment:

| Function | ESP32 GPIO |
|---|---:|
| MPU6050 SDA | 21 |
| MPU6050 SCL | 22 |
| Grab button | 25 |
| Forward button | 26 |
| Backward button | 27 |
| Haptic motor 1 PWM | 32 |
| Haptic motor 2 PWM | 33 |

Main hardware:

- ESP32 DevKit
- MPU6050 IMU
- 3 push buttons
- 2 vibrotactile DC motors
- 2 IRLZ44N MOSFET driver stages
- Flyback protection and motor-noise suppression
- 3D-printed handheld enclosure

### Power-supply note

The original design included a **3.7 V Li-ion battery**, charging/protection stage and regulated supply. During complete-system integration, the battery-powered configuration exhibited a voltage drop under the combined load and could not reliably sustain all controller components.

For the **final validated configuration**, the controller electronics were powered through the ESP32 using a standard USB power bank. Bluetooth remained the communication link between the controller and the PC; the USB cable was used only for power.

A future hardware revision should use a properly dimensioned regulated/buffered power stage capable of sustaining the complete load, including haptic-motor current transients, before returning to the internal 3.7 V battery architecture.

## Bluetooth Protocol

Bluetooth device name:

```text
ESP32_Haptic_Controller
```

Main ESP32 → PC packet:

```text
CTRL,P:12.34,R:-5.67,L:0.425,A:-0.121,G:0,F:1,B:0,N:123
```

Fields:

- `P`: Pitch [deg]
- `R`: Roll [deg]
- `L`: normalized linear command
- `A`: normalized angular command
- `G`: Grab button
- `F`: Forward button
- `B`: Backward button
- `N`: sequence number

Main PC → ESP32 commands include:

```text
H0
H1
H2
STATUS
HELLO
PING
```

The Unity `BluetoothManager` communicates through the Bluetooth virtual serial port at **115200 baud**. The current Unity project contains `COM4` as the development-machine default; this must be changed in the Inspector or script configuration when Windows assigns another COM port.

## Unity Implementation

The final Unity project is located at:

```text
Unity/VR_Robot_with_Controller/
```

Tested editor version:

```text
Unity 6000.6.2f1
```

Relevant packages include:

- Universal Render Pipeline 17.6.0
- Input System 1.20.0
- XR Interaction Toolkit 3.6.1
- XR Management 4.7.0
- OpenXR Plugin 1.18.0

Main scene:

```text
Assets/_Project/Scenes/TeleoperationLab.unity
```

Main project scripts:

```text
Assets/_Project/Scripts/
├── Avatar/
│   ├── AvatarController.cs
│   └── DesktopLookController.cs
├── Bluetooth/
│   ├── AvatarBluetoothControl.cs
│   ├── BluetoothManager.cs
│   ├── ControllerData.cs
│   ├── GrabBluetoothControl.cs
│   └── RobotBluetoothControl.cs
├── Haptics/
│   └── HapticEventManager.cs
├── Interaction/
│   ├── GrabZoneDetector.cs
│   └── RobotGrabber.cs
└── Robot/
    ├── RobotCollisionDetector.cs
    └── RobotController.cs
```

Implemented functions include:

- Proportional robot translation and yaw control
- Independent avatar navigation
- Independent VR head tracking
- Object detection, grab and release
- `FixedJoint`-based object attachment
- Environment and interactable collision classification
- Bidirectional Bluetooth communication
- `0.25 s` communication watchdog for continuous motion commands
- Differentiated haptic-event transmission

## Repository Structure

```text
ESP32-Unity-VR-Robot-Teleoperation/
├── ESP32/
│   ├── Tests/
│   │   ├── IMU_Test/
│   │   ├── Bluetooth_Test/
│   │   ├── Buttons_Test/
│   │   └── Haptic_Test/
│   └── Haptic_Controller/
├── Unity/
│   └── VR_Robot_with_Controller/
├── CAD/
│   └── Controller/
├── Experimental_Data/
│   ├── IMU/
│   ├── Buttons/
│   ├── Haptic/
│   ├── Bluetooth/
│   ├── Controller/
│   └── analyze_tests.py
├── .gitignore
└── README.md
```

## Subsystem Tests

Each physical subsystem was validated independently before complete integration.

### IMU Test

```text
ESP32/Tests/IMU_Test/
├── IMU_Test.ino
└── imu_data_logger.py
```

Validates:

- MPU6050 communication
- Calibration
- Pitch and Roll estimation
- Complementary filtering
- Dead zone and saturation behavior
- Normalized linear/angular commands
- CSV acquisition

### Buttons Test

```text
ESP32/Tests/Buttons_Test/
├── Buttons_Test.ino
└── buttons_test_gui.py
```

Validates the Grab, Forward and Backward inputs, including simultaneous button states and debouncing.

### Haptic Test

```text
ESP32/Tests/Haptic_Test/
├── Haptic_Test.ino
└── haptic_test_gui.py
```

Validates both vibration motors, manual PWM intensity commands and the `H0`, `H1` and `H2` patterns.

### Bluetooth Test

```text
ESP32/Tests/Bluetooth_Test/
├── Bluetooth_Test.ino
└── bluetooth_test_gui.py
```

Validates Bluetooth Classic SPP communication, sequence continuity, receive rate and RTT measurements.

### Complete Controller

```text
ESP32/Haptic_Controller/
├── Haptic_Controller.ino
└── haptic_controller_gui.py
```

Integrates:

- IMU
- Buttons
- Control mapping
- Bluetooth
- Bidirectional commands
- Vibrotactile feedback

## Experimental Data

Raw CSV recordings and generated analysis outputs are stored under:

```text
Experimental_Data/
```

The repository includes the analysis utility:

```text
Experimental_Data/analyze_tests.py
```

It supports the five experimental datasets used during validation:

1. IMU
2. Buttons
3. Haptic
4. Bluetooth
5. Complete controller

The generated folders contain plots, summary CSV files and text analyses while preserving the original raw recordings.

### Main Recorded Results

| Test | Main result |
|---|---|
| IMU stationary condition | Pitch mean ≈ +0.032°, Roll mean ≈ −0.041°, σ ≈ 0.008° |
| Bluetooth long-duration test | 54,333 DATA packets over ≈ 48.21 min |
| Bluetooth average receive rate | ≈ 18.78 packets/s for the 20 Hz test configuration |
| Sequence discontinuities | 146 absent sequence numbers |
| Bluetooth RTT | 31.86 ms average, 12.37–47.96 ms measured range |
| Integrated controller | 2,783 CTRL packets over ≈ 55.56 s |
| Integrated receive rate | ≈ 50.07 packets/s |
| Integrated Pitch range | −25.48° to +44.86° |
| Integrated Roll range | −21.69° to +24.57° |
| Integrated linear command | −1 to +1 |
| Integrated angular command | −0.849 to +0.981 |

Sequence discontinuities are reported as missing sequence numbers in the recorded acquisition and should not be interpreted automatically as isolated Bluetooth radio packet loss. Likewise, RTT is a round-trip measurement and is not equivalent to measured one-way control latency.

## CAD and Manufacturing

Controller CAD files are located under:

```text
CAD/Controller/SteamController-main/
```

The enclosure uses the **Steam Controller as a dimensional and ergonomic reference** for the general handheld form factor. The electronics layout, openings, component integration and haptic-controller implementation were adapted for this project.

The repository includes STL files for reproducible 3D printing. Native CAD and exchange formats are excluded by `.gitignore` unless intentionally tracked.

## Running the Project

### 1. ESP32

Open:

```text
ESP32/Haptic_Controller/Haptic_Controller.ino
```

Compile and upload it to an ESP32 with Bluetooth Classic support.

Pair the PC with:

```text
ESP32_Haptic_Controller
```

### 2. Python tools

Recommended Python packages:

```text
pyserial
numpy
pandas
matplotlib
```

Tkinter is also required for the graphical test/analysis tools and is included with many standard Python installations.

Example:

```bash
pip install pyserial numpy pandas matplotlib
```

### 3. Unity

Open:

```text
Unity/VR_Robot_with_Controller/
```

using Unity `6000.6.2f1`.

Before running the scene:

1. Pair the ESP32 with Windows.
2. Identify the Bluetooth serial COM port.
3. Set the corresponding port in `BluetoothManager`.
4. Open `TeleoperationLab`.
5. Verify that OpenXR is configured for the intended XR runtime.
6. Enter Play Mode.

For the tested smartphone VR configuration, SteamVR and VRidge must also be configured externally.

## Known Limitations

- The final controller used a USB power bank because the original 3.7 V battery supply exhibited voltage drop under complete load.
- Bluetooth timing measurements include the complete PC acquisition chain and do not isolate radio-only latency.
- RTT measurements do not represent one-way latency.
- Haptic patterns were functionally validated but were not characterized with an external vibration/force sensor or formal perceptual user study.
- The `FixedJoint` grab mechanism is a functional approximation rather than a detailed physical gripper model.
- The smartphone → VRidge → SteamVR → OpenXR chain introduces additional processing and perceptible visual latency compared with a native OpenXR headset.
- No controlled multi-user study was performed for task-completion time, collision count, ergonomics or cybersickness.

## Future Improvements

- Redesign and validate the battery power stage under maximum simultaneous load.
- Characterize one-way and end-to-end communication latency.
- Quantify haptic vibration at the enclosure and perform user discrimination tests.
- Evaluate the controller with multiple users and different hand sizes.
- Measure task completion time, collisions and manipulation errors.
- Use a native OpenXR headset or lower-latency VR link.
- Improve the virtual grab model if higher physical fidelity is required.

## Academic Context

**Universidad Militar Nueva Granada**  
**Mechatronics Engineering**  
**Virtual Reality**  
**Academic Period:** 2026-2

## Repository Purpose

This repository acts as the technical annex of the project report and preserves the firmware, Unity implementation, CAD resources, raw experimental data and analysis tools used during development and validation.
