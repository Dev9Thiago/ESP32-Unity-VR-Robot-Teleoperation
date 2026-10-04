using UnityEngine;
using UnityEngine.InputSystem;

[RequireComponent(typeof(CharacterController))]
public class AvatarController : MonoBehaviour
{
    [Header("References")]
    [Tooltip("XR Main Camera used to determine movement direction.")]
    [SerializeField] private Transform headCamera;

    [Header("Movement")]
    [SerializeField] private float movementSpeed = 2.0f;

    [Header("Gravity")]
    [SerializeField] private float gravity = -9.81f;
    [SerializeField] private float groundedVelocity = -2.0f;

    [Header("Test Input")]
    [SerializeField] private bool keyboardTestMode = true;

    [Header("Current Command")]
    [Range(-1.0f, 1.0f)]
    [SerializeField] private float movementCommand = 0.0f;

    private CharacterController characterController;
    private float verticalVelocity = 0.0f;

    // =========================================================
    // INITIALIZATION
    // =========================================================

    private void Awake()
    {
        characterController = GetComponent<CharacterController>();

        if (headCamera == null)
        {
            Debug.LogError(
                "[AVATAR] Main Camera has not been assigned."
            );
        }
    }

    // =========================================================
    // UPDATE
    // =========================================================

    private void Update()
    {
        if (keyboardTestMode)
        {
            ReadKeyboardInput();
        }

        ApplyMovement();
    }

    // =========================================================
    // TEMPORARY KEYBOARD INPUT
    // =========================================================

    private void ReadKeyboardInput()
    {
        if (Keyboard.current == null)
        {
            movementCommand = 0.0f;
            return;
        }

        bool forwardPressed =
            Keyboard.current.iKey.isPressed;

        bool backwardPressed =
            Keyboard.current.kKey.isPressed;

        movementCommand = 0.0f;

        if (forwardPressed && !backwardPressed)
        {
            movementCommand = 1.0f;
        }
        else if (backwardPressed && !forwardPressed)
        {
            movementCommand = -1.0f;
        }
    }

    // =========================================================
    // MOVEMENT
    // =========================================================

    private void ApplyMovement()
    {
        if (headCamera == null)
            return;

        // -----------------------------------------------------
        // Horizontal direction
        // -----------------------------------------------------

        Vector3 forward = headCamera.forward;

        // Ignore head pitch.
        forward.y = 0.0f;

        if (forward.sqrMagnitude > 0.001f)
        {
            forward.Normalize();
        }
        else
        {
            forward = transform.forward;
        }

        Vector3 horizontalMovement =
            forward *
            movementCommand *
            movementSpeed;

        // -----------------------------------------------------
        // Gravity
        // -----------------------------------------------------

        if (characterController.isGrounded)
        {
            if (verticalVelocity < 0.0f)
            {
                verticalVelocity = groundedVelocity;
            }
        }
        else
        {
            verticalVelocity +=
                gravity * Time.deltaTime;
        }

        Vector3 finalMovement =
            horizontalMovement +
            Vector3.up * verticalVelocity;

        // CharacterController handles collision response.
        characterController.Move(
            finalMovement * Time.deltaTime
        );
    }

    // =========================================================
    // EXTERNAL CONTROL INTERFACE
    // =========================================================

    public void SetMovementCommand(float command)
    {
        keyboardTestMode = false;

        movementCommand =
            Mathf.Clamp(command, -1.0f, 1.0f);
    }

    public void StopMovement()
    {
        movementCommand = 0.0f;
    }

    public void SetKeyboardTestMode(bool enabled)
    {
        keyboardTestMode = enabled;
        movementCommand = 0.0f;
    }
}