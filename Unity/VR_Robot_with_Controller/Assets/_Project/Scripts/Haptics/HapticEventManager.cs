using UnityEngine;

public class HapticEventManager : MonoBehaviour
{
    // ========================================================
    // HAPTIC EVENT TYPES
    // ========================================================

    public enum HapticEvent
    {
        None,
        Interactable,
        Environment
    }


    // ========================================================
    // SINGLETON
    // ========================================================

    public static HapticEventManager Instance { get; private set; }


    // ========================================================
    // REFERENCES
    // ========================================================

    [Header("References")]

    [Tooltip(
        "Bluetooth communication manager used to send " +
        "H0, H1 and H2 commands to the ESP32."
    )]
    [SerializeField]
    private BluetoothManager bluetoothManager;


    // ========================================================
    // HAPTIC CONFIGURATION
    // ========================================================

    [Header("Haptic Configuration")]

    [Tooltip(
        "Minimum time between repeated haptic events. " +
        "Prevents physics collisions from continuously " +
        "restarting the vibration pattern."
    )]
    [SerializeField]
    private float eventCooldown = 0.50f;


    // ========================================================
    // DEBUG
    // ========================================================

    [Header("Debug")]

    [SerializeField]
    private HapticEvent lastEvent = HapticEvent.None;

    [SerializeField]
    private string lastCommand = "H0";

    [SerializeField]
    private float timeSinceLastEvent = 0.0f;

    [SerializeField]
    private uint totalHapticEvents = 0;

    [SerializeField]
    private bool bluetoothAvailable = false;


    // ========================================================
    // INTERNAL STATE
    // ========================================================

    private float lastEventTime = -1000.0f;


    // ========================================================
    // INITIALIZATION
    // ========================================================

    private void Awake()
    {
        if (
            Instance != null &&
            Instance != this
        )
        {
            Destroy(gameObject);
            return;
        }

        Instance = this;
    }


    private void Start()
    {
        if (bluetoothManager == null)
        {
            Debug.LogWarning(
                "[HAPTIC] BluetoothManager has not been assigned."
            );
        }
    }


    // ========================================================
    // UPDATE DEBUG INFORMATION
    // ========================================================

    private void Update()
    {
        timeSinceLastEvent =
            Time.unscaledTime -
            lastEventTime;


        bluetoothAvailable =
            bluetoothManager != null &&
            bluetoothManager.IsConnected;
    }


    // ========================================================
    // TRIGGER HAPTIC EVENT
    // ========================================================

    public void TriggerEvent(
        HapticEvent hapticEvent
    )
    {
        if (hapticEvent == HapticEvent.None)
        {
            StopHaptics();
            return;
        }


        // ----------------------------------------------------
        // Event cooldown
        // ----------------------------------------------------

        float elapsed =
            Time.unscaledTime -
            lastEventTime;


        if (elapsed < eventCooldown)
        {
            return;
        }


        lastEventTime =
            Time.unscaledTime;

        lastEvent =
            hapticEvent;

        totalHapticEvents++;


        // ----------------------------------------------------
        // H1 - Interactable object
        // ----------------------------------------------------

        if (
            hapticEvent ==
            HapticEvent.Interactable
        )
        {
            lastCommand = "H1";


            Debug.Log(
                "[HAPTIC] H1 - Interactable object"
            );


            if (
                bluetoothManager != null &&
                bluetoothManager.IsConnected
            )
            {
                bluetoothManager.SendH1();
            }


            return;
        }


        // ----------------------------------------------------
        // H2 - Environment / wall / obstacle
        // ----------------------------------------------------

        if (
            hapticEvent ==
            HapticEvent.Environment
        )
        {
            lastCommand = "H2";


            Debug.Log(
                "[HAPTIC] H2 - Wall / obstacle"
            );


            if (
                bluetoothManager != null &&
                bluetoothManager.IsConnected
            )
            {
                bluetoothManager.SendH2();
            }


            return;
        }
    }


    // ========================================================
    // STOP HAPTICS
    // ========================================================

    public void StopHaptics()
    {
        lastEvent =
            HapticEvent.None;

        lastCommand =
            "H0";


        Debug.Log(
            "[HAPTIC] H0 - Stop"
        );


        if (
            bluetoothManager != null &&
            bluetoothManager.IsConnected
        )
        {
            bluetoothManager.SendH0();
        }
    }


    // ========================================================
    // MANUAL DEBUG COMMANDS
    // ========================================================

    public void TestH1()
    {
        TriggerEvent(
            HapticEvent.Interactable
        );
    }


    public void TestH2()
    {
        TriggerEvent(
            HapticEvent.Environment
        );
    }


    public void TestH0()
    {
        StopHaptics();
    }


    // ========================================================
    // SHUTDOWN
    // ========================================================

    private void OnDisable()
    {
        if (
            bluetoothManager != null &&
            bluetoothManager.IsConnected
        )
        {
            bluetoothManager.SendH0();
        }
    }
}