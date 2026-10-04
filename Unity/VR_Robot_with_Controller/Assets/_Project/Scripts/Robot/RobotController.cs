using UnityEngine;
using UnityEngine.InputSystem;

[RequireComponent(typeof(Rigidbody))]
public class RobotController : MonoBehaviour
{
    [Header("Robot Motion")]
    [SerializeField] private float maxLinearSpeed = 3.0f;
    [SerializeField] private float maxAngularSpeed = 120.0f;

    [Header("Test Input")]
    [SerializeField] private bool keyboardTestMode = true;

    [Header("Current Commands")]
    [SerializeField] private float linearCommand = 0.0f;
    [SerializeField] private float angularCommand = 0.0f;

    private Rigidbody rb;

    private void Awake()
    {
        rb = GetComponent<Rigidbody>();
    }

    private void Update()
    {
        if (keyboardTestMode)
        {
            ReadKeyboardInput();
        }
    }

    private void FixedUpdate()
    {
        ApplyRobotMotion();
    }

    // =========================================================
    // KEYBOARD TEST INPUT
    // =========================================================

    private void ReadKeyboardInput()
    {
        if (Keyboard.current == null)
        {
            ResetCommands();
            return;
        }

        bool forwardPressed =
            Keyboard.current.wKey.isPressed ||
            Keyboard.current.upArrowKey.isPressed;

        bool backwardPressed =
            Keyboard.current.sKey.isPressed ||
            Keyboard.current.downArrowKey.isPressed;

        bool leftPressed =
            Keyboard.current.aKey.isPressed ||
            Keyboard.current.leftArrowKey.isPressed;

        bool rightPressed =
            Keyboard.current.dKey.isPressed ||
            Keyboard.current.rightArrowKey.isPressed;

        // Reconstruct the commands from zero every frame.
        // This prevents old keyboard commands from remaining active.
        linearCommand = 0.0f;
        angularCommand = 0.0f;

        // Forward / reverse
        if (forwardPressed && !backwardPressed)
        {
            linearCommand = 1.0f;
        }
        else if (backwardPressed && !forwardPressed)
        {
            linearCommand = -1.0f;
        }

        // Left / right rotation
        if (rightPressed && !leftPressed)
        {
            angularCommand = 1.0f;
        }
        else if (leftPressed && !rightPressed)
        {
            angularCommand = -1.0f;
        }
    }

    // =========================================================
    // ROBOT PHYSICS
    // =========================================================

    private void ApplyRobotMotion()
    {
        // Linear movement along the robot's local Z axis.
        Vector3 forwardVelocity =
            transform.forward *
            linearCommand *
            maxLinearSpeed;

        rb.linearVelocity = new Vector3(
            forwardVelocity.x,
            rb.linearVelocity.y,
            forwardVelocity.z
        );

        // Rotation around the vertical Y axis.
        float angularVelocityRad =
            angularCommand *
            maxAngularSpeed *
            Mathf.Deg2Rad;

        rb.angularVelocity = new Vector3(
            0.0f,
            angularVelocityRad,
            0.0f
        );
    }

    // =========================================================
    // EXTERNAL CONTROL INTERFACE
    // =========================================================

    /// <summary>
    /// Receives normalized motion commands from an external source.
    ///
    /// linear:
    /// -1 = full reverse
    ///  0 = stop
    /// +1 = full forward
    ///
    /// angular:
    /// -1 = full left
    ///  0 = no rotation
    /// +1 = full right
    ///
    /// This method will later receive the commands generated
    /// from the MPU6050 Pitch and Roll values.
    /// </summary>
    public void SetControlCommands(float linear, float angular)
    {
        keyboardTestMode = false;

        linearCommand = Mathf.Clamp(linear, -1.0f, 1.0f);
        angularCommand = Mathf.Clamp(angular, -1.0f, 1.0f);
    }

    /// <summary>
    /// Stops all commanded robot motion.
    /// </summary>
    public void StopRobot()
    {
        ResetCommands();
    }

    /// <summary>
    /// Immediately clears linear and angular commands.
    /// </summary>
    public void ResetCommands()
    {
        linearCommand = 0.0f;
        angularCommand = 0.0f;

        // Also remove residual horizontal/angular velocity.
        if (rb != null)
        {
            rb.linearVelocity = new Vector3(
                0.0f,
                rb.linearVelocity.y,
                0.0f
            );

            rb.angularVelocity = Vector3.zero;
        }
    }

    /// <summary>
    /// Enables or disables temporary keyboard testing.
    /// </summary>
    public void SetKeyboardTestMode(bool enabled)
    {
        keyboardTestMode = enabled;
        ResetCommands();
    }
}