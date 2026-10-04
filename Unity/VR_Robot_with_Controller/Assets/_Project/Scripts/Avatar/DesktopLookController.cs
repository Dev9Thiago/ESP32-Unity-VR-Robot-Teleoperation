using UnityEngine;
using UnityEngine.InputSystem;

public class DesktopLookController : MonoBehaviour
{
    [Header("References")]
    [SerializeField] private Transform cameraTransform;

    [Header("Mouse Look")]
    [SerializeField] private float sensitivity = 0.12f;

    [SerializeField] private float minimumPitch = -80.0f;
    [SerializeField] private float maximumPitch = 80.0f;

    [Header("Testing")]
    [SerializeField] private bool desktopLookEnabled = true;

    private float yaw = 0.0f;
    private float pitch = 0.0f;

    private bool mouseCaptured = false;

    private void Start()
    {
        yaw = transform.eulerAngles.y;

        if (cameraTransform != null)
        {
            pitch = cameraTransform.localEulerAngles.x;

            if (pitch > 180.0f)
            {
                pitch -= 360.0f;
            }
        }
    }

    private void Update()
    {
        if (!desktopLookEnabled)
            return;

        if (Mouse.current == null)
            return;

        HandleMouseCapture();

        if (!mouseCaptured)
            return;

        HandleMouseLook();
    }

    // =========================================================
    // MOUSE CAPTURE
    // =========================================================

    private void HandleMouseCapture()
    {
        // Left click captures mouse.
        if (Mouse.current.leftButton.wasPressedThisFrame)
        {
            mouseCaptured = true;

            Cursor.lockState = CursorLockMode.Locked;
            Cursor.visible = false;
        }

        // ESC releases mouse.
        if (Keyboard.current != null &&
            Keyboard.current.escapeKey.wasPressedThisFrame)
        {
            mouseCaptured = false;

            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
        }
    }

    // =========================================================
    // LOOK
    // =========================================================

    private void HandleMouseLook()
    {
        Vector2 mouseDelta =
            Mouse.current.delta.ReadValue();

        yaw +=
            mouseDelta.x *
            sensitivity;

        pitch -=
            mouseDelta.y *
            sensitivity;

        pitch = Mathf.Clamp(
            pitch,
            minimumPitch,
            maximumPitch
        );

        // Horizontal rotation:
        // rotate entire Avatar.
        transform.rotation =
            Quaternion.Euler(
                0.0f,
                yaw,
                0.0f
            );

        // Vertical rotation:
        // rotate only camera.
        if (cameraTransform != null)
        {
            cameraTransform.localRotation =
                Quaternion.Euler(
                    pitch,
                    0.0f,
                    0.0f
                );
        }
    }

    // =========================================================
    // EXTERNAL MODE CONTROL
    // =========================================================

    public void SetDesktopLookEnabled(bool enabled)
    {
        desktopLookEnabled = enabled;

        if (!enabled)
        {
            mouseCaptured = false;

            Cursor.lockState =
                CursorLockMode.None;

            Cursor.visible = true;
        }
    }
}