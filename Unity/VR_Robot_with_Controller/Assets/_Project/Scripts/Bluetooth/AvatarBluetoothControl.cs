using UnityEngine;

public class AvatarBluetoothControl : MonoBehaviour
{
    // ========================================================
    // REFERENCES
    // ========================================================

    [Header("References")]

    [SerializeField]
    private BluetoothManager bluetoothManager;

    [SerializeField]
    private AvatarController avatarController;


    // ========================================================
    // CONTROL
    // ========================================================

    [Header("Bluetooth Control")]

    [Tooltip(
        "When enabled, the Forward and Backward buttons on " +
        "the physical controller move the avatar."
    )]
    [SerializeField]
    private bool bluetoothControlEnabled = true;


    // ========================================================
    // SAFETY
    // ========================================================

    [Header("Safety")]

    [Tooltip(
        "Stop avatar movement if controller packets stop arriving."
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
    private bool forwardPressed = false;

    [SerializeField]
    private bool backwardPressed = false;

    [SerializeField]
    private float movementCommand = 0.0f;

    [SerializeField]
    private uint lastPacketNumber = 0;

    [SerializeField]
    private float timeSinceLastPacket = 0.0f;

    [SerializeField]
    private bool receivingFreshData = false;


    // ========================================================
    // INTERNAL STATE
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
                "[AvatarBluetoothControl] " +
                "BluetoothManager reference is missing."
            );
        }


        if (avatarController == null)
        {
            Debug.LogError(
                "[AvatarBluetoothControl] " +
                "AvatarController reference is missing."
            );
        }


        if (
            bluetoothControlEnabled &&
            avatarController != null
        )
        {
            avatarController.SetKeyboardTestMode(false);
        }
    }


    // ========================================================
    // UPDATE
    // ========================================================

    private void Update()
    {
        if (
            bluetoothManager == null ||
            avatarController == null
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

            movementCommand = 0.0f;

            avatarController.StopMovement();

            return;
        }


        ControllerData data =
            bluetoothManager.CurrentData;


        if (data == null)
        {
            receivingFreshData = false;

            movementCommand = 0.0f;

            avatarController.StopMovement();

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


            forwardPressed =
                data.forward;

            backwardPressed =
                data.backward;


            // ------------------------------------------------
            // Convert the two buttons into one movement command
            // ------------------------------------------------

            if (
                forwardPressed &&
                !backwardPressed
            )
            {
                movementCommand = 1.0f;
            }

            else if (
                backwardPressed &&
                !forwardPressed
            )
            {
                movementCommand = -1.0f;
            }

            else
            {
                // Neither button OR both buttons.
                movementCommand = 0.0f;
            }


            avatarController.SetMovementCommand(
                movementCommand
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

                forwardPressed =
                    false;

                backwardPressed =
                    false;

                movementCommand =
                    0.0f;


                avatarController.StopMovement();
            }
        }
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

        movementCommand =
            0.0f;


        if (avatarController != null)
        {
            avatarController.SetKeyboardTestMode(
                false
            );

            avatarController.StopMovement();
        }


        Debug.Log(
            "[AvatarBluetoothControl] " +
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

        movementCommand =
            0.0f;


        if (avatarController != null)
        {
            avatarController.SetKeyboardTestMode(
                true
            );
        }


        Debug.Log(
            "[AvatarBluetoothControl] " +
            "Keyboard test control ENABLED."
        );
    }


    // ========================================================
    // SAFETY
    // ========================================================

    private void OnDisable()
    {
        if (avatarController != null)
        {
            avatarController.StopMovement();
        }
    }


    private void OnDestroy()
    {
        if (avatarController != null)
        {
            avatarController.StopMovement();
        }
    }
}