using UnityEngine;

public class GrabBluetoothControl : MonoBehaviour
{
    // ========================================================
    // REFERENCES
    // ========================================================

    [Header("References")]

    [SerializeField]
    private BluetoothManager bluetoothManager;

    [SerializeField]
    private RobotGrabber robotGrabber;


    // ========================================================
    // CONTROL
    // ========================================================

    [Header("Bluetooth Control")]

    [Tooltip(
        "When enabled, the physical Grab button toggles " +
        "the robot grab/release system."
    )]
    [SerializeField]
    private bool bluetoothControlEnabled = true;


    // ========================================================
    // SAFETY
    // ========================================================

    [Header("Safety")]

    [Tooltip(
        "Ignore grab input if controller packets stop arriving."
    )]
    [SerializeField]
    private bool enableCommunicationTimeout = true;

    [SerializeField]
    private float communicationTimeout = 0.25f;


    // ========================================================
    // LIVE DEBUG
    // ========================================================

    [Header("Live Debug")]

    [SerializeField]
    private bool grabPressed = false;

    [SerializeField]
    private bool previousGrabPressed = false;

    [SerializeField]
    private bool risingEdgeDetected = false;

    [SerializeField]
    private bool robotHasObject = false;

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
                "[GrabBluetoothControl] " +
                "BluetoothManager reference is missing."
            );
        }


        if (robotGrabber == null)
        {
            Debug.LogError(
                "[GrabBluetoothControl] " +
                "RobotGrabber reference is missing."
            );
        }


        if (
            bluetoothControlEnabled &&
            robotGrabber != null
        )
        {
            robotGrabber.SetKeyboardTestMode(false);
        }
    }


    // ========================================================
    // UPDATE
    // ========================================================

    private void Update()
    {
        if (
            bluetoothManager == null ||
            robotGrabber == null
        )
        {
            return;
        }


        robotHasObject =
            robotGrabber.HasObject;


        // Rising-edge indicator is only true for the
        // frame in which the event occurs.
        risingEdgeDetected =
            false;


        // ----------------------------------------------------
        // Bluetooth control disabled
        // ----------------------------------------------------

        if (!bluetoothControlEnabled)
        {
            receivingFreshData =
                false;

            return;
        }


        // ----------------------------------------------------
        // Bluetooth disconnected
        // ----------------------------------------------------

        if (!bluetoothManager.IsConnected)
        {
            receivingFreshData =
                false;

            ResetButtonState();

            return;
        }


        ControllerData data =
            bluetoothManager.CurrentData;


        if (data == null)
        {
            receivingFreshData =
                false;

            ResetButtonState();

            return;
        }


        // ----------------------------------------------------
        // Process only NEW packets
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

            receivingFreshData =
                true;


            grabPressed =
                data.grab;


            // ================================================
            // RISING EDGE
            //
            // Previous = 0
            // Current  = 1
            //
            // Only this transition generates ToggleGrab().
            // ================================================

            if (
                grabPressed &&
                !previousGrabPressed
            )
            {
                risingEdgeDetected =
                    true;


                robotGrabber.ToggleGrab();


                Debug.Log(
                    "[GrabBluetoothControl] " +
                    "Physical Grab button rising edge."
                );
            }


            // Store current state for the next packet.
            previousGrabPressed =
                grabPressed;


            robotHasObject =
                robotGrabber.HasObject;
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


                // IMPORTANT:
                //
                // We reset the BUTTON state,
                // but we do NOT automatically release an
                // object that is already being carried.
                //
                // The physical FixedJoint remains intact.
                ResetButtonState();
            }
        }
    }


    // ========================================================
    // RESET BUTTON STATE
    // ========================================================

    private void ResetButtonState()
    {
        grabPressed =
            false;

        previousGrabPressed =
            false;

        risingEdgeDetected =
            false;
    }


    // ========================================================
    // BLUETOOTH CONTROL
    // ========================================================

    public void EnableBluetoothControl()
    {
        bluetoothControlEnabled =
            true;

        hasReceivedPacket =
            false;

        receivingFreshData =
            false;

        ResetButtonState();


        if (robotGrabber != null)
        {
            robotGrabber.SetKeyboardTestMode(
                false
            );
        }


        Debug.Log(
            "[GrabBluetoothControl] " +
            "Bluetooth control ENABLED."
        );
    }


    // ========================================================
    // KEYBOARD TEST CONTROL
    // ========================================================

    public void EnableKeyboardControl()
    {
        bluetoothControlEnabled =
            false;

        hasReceivedPacket =
            false;

        receivingFreshData =
            false;

        ResetButtonState();


        if (robotGrabber != null)
        {
            robotGrabber.SetKeyboardTestMode(
                true
            );
        }


        Debug.Log(
            "[GrabBluetoothControl] " +
            "Keyboard test control ENABLED."
        );
    }


    // ========================================================
    // DISABLE
    // ========================================================

    private void OnDisable()
    {
        ResetButtonState();
    }
}