using UnityEngine;

public class RobotBluetoothControl : MonoBehaviour
{
    // ========================================================
    // REFERENCES
    // ========================================================

    [Header("References")]

    [SerializeField]
    private BluetoothManager bluetoothManager;

    [SerializeField]
    private RobotController robotController;


    // ========================================================
    // CONTROL
    // ========================================================

    [Header("Bluetooth Control")]

    [Tooltip(
        "When enabled, the robot receives Linear and Angular " +
        "commands from the ESP32 controller."
    )]
    [SerializeField]
    private bool bluetoothControlEnabled = true;


    // ========================================================
    // SAFETY
    // ========================================================

    [Header("Safety")]

    [Tooltip(
        "Stop the robot if Bluetooth data stops updating."
    )]
    [SerializeField]
    private bool enableCommunicationTimeout = true;

    [Tooltip(
        "Maximum allowed time without a new controller packet."
    )]
    [SerializeField]
    private float communicationTimeout = 0.25f;


    // ========================================================
    // DEBUG
    // ========================================================

    [Header("Live Debug")]

    [SerializeField]
    private float receivedLinear = 0.0f;

    [SerializeField]
    private float receivedAngular = 0.0f;

    [SerializeField]
    private uint lastPacketNumber = 0;

    [SerializeField]
    private float timeSinceLastPacket = 0.0f;

    [SerializeField]
    private bool receivingFreshData = false;


    // ========================================================
    // INTERNAL
    // ========================================================

    private bool hasReceivedPacket = false;

    private float lastPacketTime = 0.0f;


    // ========================================================
    // START
    // ========================================================

    private void Start()
    {
        if (bluetoothManager == null)
        {
            Debug.LogError(
                "[RobotBluetoothControl] " +
                "BluetoothManager reference is missing."
            );
        }


        if (robotController == null)
        {
            Debug.LogError(
                "[RobotBluetoothControl] " +
                "RobotController reference is missing."
            );
        }


        if (
            bluetoothControlEnabled &&
            robotController != null
        )
        {
            // Disable keyboard commands once the physical
            // controller takes ownership of the robot.
            robotController.SetKeyboardTestMode(false);
        }
    }


    // ========================================================
    // UPDATE
    // ========================================================

    private void Update()
    {
        if (
            bluetoothManager == null ||
            robotController == null
        )
        {
            return;
        }


        // ----------------------------------------------------
        // Bluetooth mode disabled
        // ----------------------------------------------------

        if (!bluetoothControlEnabled)
        {
            receivingFreshData = false;

            return;
        }


        // ----------------------------------------------------
        // Bluetooth disconnected
        // ----------------------------------------------------

        if (!bluetoothManager.IsConnected)
        {
            receivingFreshData = false;

            robotController.StopRobot();

            return;
        }


        ControllerData data =
            bluetoothManager.CurrentData;


        if (data == null)
        {
            receivingFreshData = false;

            robotController.StopRobot();

            return;
        }


        // ----------------------------------------------------
        // Detect a NEW packet
        // ----------------------------------------------------

        if (
            !hasReceivedPacket ||
            data.packetNumber != lastPacketNumber
        )
        {
            lastPacketNumber =
                data.packetNumber;

            lastPacketTime =
                Time.unscaledTime;

            hasReceivedPacket =
                true;


            receivedLinear =
                data.linear;

            receivedAngular =
                data.angular;


            receivingFreshData =
                true;


            // Send normalized ESP32 commands directly
            // to the already-working RobotController.
            robotController.SetControlCommands(
                receivedLinear,
                receivedAngular
            );
        }


        // ----------------------------------------------------
        // Communication watchdog
        // ----------------------------------------------------

        if (hasReceivedPacket)
        {
            timeSinceLastPacket =
                Time.unscaledTime -
                lastPacketTime;


            if (
                enableCommunicationTimeout &&
                timeSinceLastPacket >
                communicationTimeout
            )
            {
                receivingFreshData =
                    false;

                receivedLinear =
                    0.0f;

                receivedAngular =
                    0.0f;


                robotController.StopRobot();
            }
        }
    }


    // ========================================================
    // ENABLE BLUETOOTH CONTROL
    // ========================================================

    public void EnableBluetoothControl()
    {
        bluetoothControlEnabled =
            true;

        hasReceivedPacket =
            false;

        receivingFreshData =
            false;


        if (robotController != null)
        {
            robotController.SetKeyboardTestMode(
                false
            );
        }


        Debug.Log(
            "[RobotBluetoothControl] " +
            "Bluetooth control ENABLED."
        );
    }


    // ========================================================
    // ENABLE KEYBOARD TEST CONTROL
    // ========================================================

    public void EnableKeyboardControl()
    {
        bluetoothControlEnabled =
            false;

        hasReceivedPacket =
            false;

        receivingFreshData =
            false;


        if (robotController != null)
        {
            robotController.SetKeyboardTestMode(
                true
            );
        }


        Debug.Log(
            "[RobotBluetoothControl] " +
            "Keyboard test control ENABLED."
        );
    }


    // ========================================================
    // DISABLE / DESTROY SAFETY
    // ========================================================

    private void OnDisable()
    {
        if (robotController != null)
        {
            robotController.StopRobot();
        }
    }


    private void OnDestroy()
    {
        if (robotController != null)
        {
            robotController.StopRobot();
        }
    }
}