using UnityEngine;

using System;
using System.IO.Ports;
using System.Globalization;
using System.Threading;
using System.Collections.Concurrent;


public class BluetoothManager : MonoBehaviour
{
    // ========================================================
    // SERIAL CONFIGURATION
    // ========================================================

    [Header("Bluetooth Serial")]

    [Tooltip("Windows Bluetooth SPP COM port.")]
    public string portName = "COM4";

    public int baudRate = 115200;

    [Tooltip("Automatically connect when Play Mode starts.")]
    public bool connectOnStart = true;


    // ========================================================
    // DEBUG
    // ========================================================

    [Header("Debug")]

    [Tooltip("Print parsed controller packets periodically.")]
    public bool showPacketsInConsole = true;

    [Tooltip(
        "How often Unity prints a packet. " +
        "Reception itself still occurs at full rate."
    )]
    public float consolePrintInterval = 0.25f;


    // ========================================================
    // LIVE DATA - INSPECTOR
    // ========================================================

    [Header("Live Controller Data")]

    [SerializeField]
    private float pitch;

    [SerializeField]
    private float roll;

    [SerializeField]
    private float linear;

    [SerializeField]
    private float angular;

    [SerializeField]
    private bool grab;

    [SerializeField]
    private bool forward;

    [SerializeField]
    private bool backward;

    [SerializeField]
    private uint packetNumber;


    // ========================================================
    // COMMUNICATION STATUS
    // ========================================================

    [Header("Communication Status")]

    [SerializeField]
    private bool connected = false;

    [SerializeField]
    private long receivedPackets = 0;

    [SerializeField]
    private long invalidPackets = 0;

    [SerializeField]
    private long missingPackets = 0;

    [SerializeField]
    private float receiveRate = 0.0f;


    // ========================================================
    // PUBLIC CURRENT DATA
    // ========================================================

    public ControllerData CurrentData { get; private set; }
        = new ControllerData();


    public bool IsConnected
    {
        get
        {
            return connected;
        }
    }


    // ========================================================
    // INTERNAL SERIAL OBJECTS
    // ========================================================

    private SerialPort serialPort;

    private Thread serialThread;

    private volatile bool keepReading = false;


    // Thread-safe queue:
    //
    // Serial thread
    //      ↓
    // incomingLines
    //      ↓
    // Unity main thread

    private readonly ConcurrentQueue<string> incomingLines
        = new ConcurrentQueue<string>();


    // ========================================================
    // PACKET STATISTICS
    // ========================================================

    private bool hasPreviousPacket = false;

    private uint previousPacketNumber = 0;

    private long packetsDuringRateWindow = 0;

    private float rateTimer = 0.0f;

    private float consoleTimer = 0.0f;


    // ========================================================
    // UNITY START
    // ========================================================

    private void Start()
    {
        if (connectOnStart)
        {
            Connect();
        }
    }


    // ========================================================
    // UNITY UPDATE
    // ========================================================

    private void Update()
    {
        // ----------------------------------------------------
        // Process everything received by the background thread
        // ----------------------------------------------------

        while (incomingLines.TryDequeue(out string line))
        {
            ProcessReceivedLine(line);
        }


        // ----------------------------------------------------
        // Receive-rate measurement
        // ----------------------------------------------------

        rateTimer += Time.unscaledDeltaTime;


        if (rateTimer >= 1.0f)
        {
            receiveRate =
                packetsDuringRateWindow /
                rateTimer;

            packetsDuringRateWindow = 0;

            rateTimer = 0.0f;
        }


        // ----------------------------------------------------
        // Console output
        // ----------------------------------------------------

        if (showPacketsInConsole && connected)
        {
            consoleTimer += Time.unscaledDeltaTime;


            if (consoleTimer >= consolePrintInterval)
            {
                consoleTimer = 0.0f;

                Debug.Log(
                    "[ESP32] " +
                    CurrentData.ToString() +
                    $" | RX={receiveRate:F1} Hz"
                );
            }
        }
    }


    // ========================================================
    // CONNECT
    // ========================================================

    public void Connect()
    {
        if (connected)
        {
            return;
        }


        try
        {
            Debug.Log(
                $"[Bluetooth] Opening {portName}..."
            );


            serialPort = new SerialPort(
                portName,
                baudRate
            );


            serialPort.NewLine = "\n";

            serialPort.ReadTimeout = 200;

            serialPort.WriteTimeout = 200;

            serialPort.DtrEnable = false;

            serialPort.RtsEnable = false;


            serialPort.Open();


            keepReading = true;


            serialThread = new Thread(
                SerialReadLoop
            );


            serialThread.IsBackground = true;

            serialThread.Start();


            connected = true;


            ResetStatistics();


            Debug.Log(
                $"[Bluetooth] CONNECTED to {portName}"
            );


            SendCommand(
                "HELLO"
            );
        }

        catch (Exception exception)
        {
            connected = false;

            Debug.LogError(
                "[Bluetooth] Connection failed: " +
                exception.Message
            );
        }
    }


    // ========================================================
    // BACKGROUND SERIAL READER
    // ========================================================

    private void SerialReadLoop()
    {
        while (keepReading)
        {
            try
            {
                if (
                    serialPort != null &&
                    serialPort.IsOpen
                )
                {
                    string line =
                        serialPort.ReadLine();

                    if (
                        !string.IsNullOrWhiteSpace(line)
                    )
                    {
                        incomingLines.Enqueue(
                            line.Trim()
                        );
                    }
                }
            }

            catch (TimeoutException)
            {
                // Normal.
                // Allows the thread to periodically check
                // keepReading.
            }

            catch (Exception exception)
            {
                if (keepReading)
                {
                    Debug.LogWarning(
                        "[Bluetooth] Serial reader stopped: " +
                        exception.Message
                    );
                }

                break;
            }
        }
    }


    // ========================================================
    // PROCESS RECEIVED LINE
    // ========================================================

    private void ProcessReceivedLine(
        string line
    )
    {
        // Controller packet
        if (line.StartsWith("CTRL,"))
        {
            ParseControlPacket(line);

            return;
        }


        // ESP32 handshake
        if (line.StartsWith("HELLO,"))
        {
            Debug.Log(
                "[Bluetooth] ESP32 replied: " +
                line
            );

            return;
        }


        // Ping response
        if (line.StartsWith("PONG,"))
        {
            Debug.Log(
                "[Bluetooth] " +
                line
            );

            return;
        }


        // Haptic event acknowledgement
        if (line.StartsWith("EVENT,"))
        {
            Debug.Log(
                "[Bluetooth] " +
                line
            );

            return;
        }


        // Status
        if (line.StartsWith("STATUS,"))
        {
            Debug.Log(
                "[Bluetooth] " +
                line
            );

            return;
        }


        // Error generated by ESP32
        if (line.StartsWith("ERROR,"))
        {
            Debug.LogWarning(
                "[ESP32] " +
                line
            );

            return;
        }


        Debug.Log(
            "[Bluetooth RX] " +
            line
        );
    }


    // ========================================================
    // PARSE CTRL PACKET
    // ========================================================

    private void ParseControlPacket(
        string packet
    )
    {
        try
        {
            string[] fields =
                packet.Split(',');


            // Expected:
            //
            // CTRL
            // P:x
            // R:x
            // L:x
            // A:x
            // G:x
            // F:x
            // B:x
            // N:x

            if (fields.Length != 9)
            {
                invalidPackets++;

                return;
            }


            ControllerData newData =
                new ControllerData();


            bool gotP = false;
            bool gotR = false;
            bool gotL = false;
            bool gotA = false;

            bool gotG = false;
            bool gotF = false;
            bool gotB = false;

            bool gotN = false;


            for (
                int i = 1;
                i < fields.Length;
                i++
            )
            {
                string[] pair =
                    fields[i].Split(':');


                if (pair.Length != 2)
                {
                    invalidPackets++;

                    return;
                }


                string key =
                    pair[0];

                string value =
                    pair[1];


                switch (key)
                {
                    case "P":

                        newData.pitch =
                            ParseFloat(value);

                        gotP = true;

                        break;


                    case "R":

                        newData.roll =
                            ParseFloat(value);

                        gotR = true;

                        break;


                    case "L":

                        newData.linear =
                            ParseFloat(value);

                        gotL = true;

                        break;


                    case "A":

                        newData.angular =
                            ParseFloat(value);

                        gotA = true;

                        break;


                    case "G":

                        newData.grab =
                            ParseButton(value);

                        gotG = true;

                        break;


                    case "F":

                        newData.forward =
                            ParseButton(value);

                        gotF = true;

                        break;


                    case "B":

                        newData.backward =
                            ParseButton(value);

                        gotB = true;

                        break;


                    case "N":

                        newData.packetNumber =
                            uint.Parse(
                                value,
                                CultureInfo.InvariantCulture
                            );

                        gotN = true;

                        break;


                    default:

                        invalidPackets++;

                        return;
                }
            }


            if (
                !gotP ||
                !gotR ||
                !gotL ||
                !gotA ||
                !gotG ||
                !gotF ||
                !gotB ||
                !gotN
            )
            {
                invalidPackets++;

                return;
            }


            // ------------------------------------------------
            // Packet sequence
            // ------------------------------------------------

            if (hasPreviousPacket)
            {
                uint expected =
                    previousPacketNumber + 1;


                if (
                    newData.packetNumber >
                    expected
                )
                {
                    missingPackets +=
                        newData.packetNumber -
                        expected;
                }
            }


            previousPacketNumber =
                newData.packetNumber;

            hasPreviousPacket = true;


            // ------------------------------------------------
            // Publish latest data
            // ------------------------------------------------

            CurrentData =
                newData;


            pitch =
                newData.pitch;

            roll =
                newData.roll;

            linear =
                newData.linear;

            angular =
                newData.angular;

            grab =
                newData.grab;

            forward =
                newData.forward;

            backward =
                newData.backward;

            packetNumber =
                newData.packetNumber;


            receivedPackets++;

            packetsDuringRateWindow++;
        }

        catch
        {
            invalidPackets++;
        }
    }


    // ========================================================
    // PARSE FLOAT
    // ========================================================

    private float ParseFloat(
        string value
    )
    {
        return float.Parse(
            value,
            NumberStyles.Float,
            CultureInfo.InvariantCulture
        );
    }


    // ========================================================
    // PARSE BUTTON
    // ========================================================

    private bool ParseButton(
        string value
    )
    {
        if (value == "1")
        {
            return true;
        }


        if (value == "0")
        {
            return false;
        }


        throw new FormatException(
            "Button value must be 0 or 1."
        );
    }


    // ========================================================
    // SEND COMMAND
    // ========================================================

    public void SendCommand(
        string command
    )
    {
        if (
            serialPort == null ||
            !serialPort.IsOpen
        )
        {
            Debug.LogWarning(
                "[Bluetooth] Cannot send command: port is closed."
            );

            return;
        }


        try
        {
            serialPort.WriteLine(
                command
            );
        }

        catch (Exception exception)
        {
            Debug.LogWarning(
                "[Bluetooth] TX failed: " +
                exception.Message
            );
        }
    }


    // ========================================================
    // FUTURE HAPTIC METHODS
    // ========================================================

    public void SendH0()
    {
        SendCommand("H0");
    }


    public void SendH1()
    {
        SendCommand("H1");
    }


    public void SendH2()
    {
        SendCommand("H2");
    }


    // ========================================================
    // RESET STATISTICS
    // ========================================================

    public void ResetStatistics()
    {
        receivedPackets = 0;

        invalidPackets = 0;

        missingPackets = 0;

        packetsDuringRateWindow = 0;

        receiveRate = 0.0f;

        rateTimer = 0.0f;

        hasPreviousPacket = false;

        previousPacketNumber = 0;
    }


    // ========================================================
    // DISCONNECT
    // ========================================================

    public void Disconnect()
    {
        keepReading = false;


        if (
            serialThread != null &&
            serialThread.IsAlive
        )
        {
            serialThread.Join(500);
        }


        serialThread = null;


        if (serialPort != null)
        {
            try
            {
                if (serialPort.IsOpen)
                {
                    serialPort.Close();
                }
            }

            catch
            {
                // Ignore shutdown errors.
            }


            serialPort.Dispose();

            serialPort = null;
        }


        connected = false;


        Debug.Log(
            "[Bluetooth] DISCONNECTED"
        );
    }


    // ========================================================
    // UNITY SHUTDOWN
    // ========================================================

    private void OnApplicationQuit()
    {
        Disconnect();
    }


    private void OnDestroy()
    {
        Disconnect();
    }
}