using System;

[Serializable]
public class ControllerData
{
    // --------------------------------------------------------
    // IMU
    // --------------------------------------------------------

    public float pitch = 0.0f;
    public float roll = 0.0f;


    // --------------------------------------------------------
    // Normalized robot commands
    // --------------------------------------------------------

    public float linear = 0.0f;
    public float angular = 0.0f;


    // --------------------------------------------------------
    // Physical buttons
    // --------------------------------------------------------

    public bool grab = false;
    public bool forward = false;
    public bool backward = false;


    // --------------------------------------------------------
    // Packet counter
    // --------------------------------------------------------

    public uint packetNumber = 0;


    // --------------------------------------------------------
    // Debug representation
    // --------------------------------------------------------

    public override string ToString()
    {
        return
            $"P={pitch:F2}°, " +
            $"R={roll:F2}°, " +
            $"L={linear:F3}, " +
            $"A={angular:F3}, " +
            $"G={(grab ? 1 : 0)}, " +
            $"F={(forward ? 1 : 0)}, " +
            $"B={(backward ? 1 : 0)}, " +
            $"N={packetNumber}";
    }
}