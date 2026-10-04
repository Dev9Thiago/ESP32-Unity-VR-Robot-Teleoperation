using UnityEngine;
using UnityEngine.InputSystem;

[RequireComponent(typeof(Rigidbody))]
public class RobotGrabber : MonoBehaviour
{
    [Header("References")]
    [SerializeField] private Transform grabPoint;

    [Header("Testing")]
    [SerializeField] private bool keyboardTestMode = true;

    [Header("Debug")]
    [SerializeField] private GameObject availableObject;
    [SerializeField] private GameObject grabbedObject;

    private Rigidbody robotRigidbody;
    private Rigidbody grabbedRigidbody;
    private FixedJoint grabJoint;

    public bool HasObject => grabbedObject != null;

    // =========================================================
    // INITIALIZATION
    // =========================================================

    private void Awake()
    {
        robotRigidbody = GetComponent<Rigidbody>();

        if (robotRigidbody == null)
        {
            Debug.LogError(
                "[GRAB] RobotGrabber requires a Rigidbody."
            );
        }

        if (grabPoint == null)
        {
            Debug.LogError(
                "[GRAB] GrabPoint has not been assigned."
            );
        }
    }

    // =========================================================
    // KEYBOARD TEST
    // =========================================================

    private void Update()
    {
        if (!keyboardTestMode)
            return;

        if (Keyboard.current == null)
            return;

        // Temporary desktop control:
        // SPACE = Grab / Release
        if (Keyboard.current.spaceKey.wasPressedThisFrame)
        {
            ToggleGrab();
        }
    }

    // =========================================================
    // PUBLIC GRAB COMMAND
    // =========================================================

    public void ToggleGrab()
    {
        if (grabbedObject != null)
        {
            ReleaseObject();
        }
        else if (availableObject != null)
        {
            GrabObject();
        }
        else
        {
            Debug.Log(
                "[GRAB] No interactable object available."
            );
        }
    }

    // =========================================================
    // GRAB
    // =========================================================

    private void GrabObject()
    {
        if (availableObject == null)
            return;

        if (grabPoint == null)
        {
            Debug.LogError(
                "[GRAB] Cannot grab because GrabPoint is missing."
            );

            return;
        }

        Rigidbody targetRigidbody =
            availableObject.GetComponent<Rigidbody>();

        if (targetRigidbody == null)
        {
            Debug.LogWarning(
                "[GRAB] Interactable object has no Rigidbody."
            );

            return;
        }

        grabbedObject = availableObject;
        grabbedRigidbody = targetRigidbody;

        // Stop previous object motion.
        grabbedRigidbody.linearVelocity = Vector3.zero;
        grabbedRigidbody.angularVelocity = Vector3.zero;

        // Keep object dynamic so collisions remain active.
        grabbedRigidbody.isKinematic = false;

        // Move object to the grabbing position.
        grabbedRigidbody.position = grabPoint.position;
        grabbedRigidbody.rotation = grabPoint.rotation;

        // Create physical connection.
        grabJoint = gameObject.AddComponent<FixedJoint>();

        grabJoint.connectedBody = grabbedRigidbody;

        grabJoint.autoConfigureConnectedAnchor = false;

        grabJoint.anchor =
            transform.InverseTransformPoint(
                grabPoint.position
            );

        grabJoint.connectedAnchor = Vector3.zero;

        // Do not let the held object collide with the robot
        // through the joint itself.
        grabJoint.enableCollision = false;

        grabJoint.breakForce = Mathf.Infinity;
        grabJoint.breakTorque = Mathf.Infinity;

        Debug.Log(
            "[GRAB] Object grabbed physically: " +
            grabbedObject.name
        );
    }

    // =========================================================
    // RELEASE
    // =========================================================

    private void ReleaseObject()
    {
        if (grabbedObject == null)
            return;

        GameObject releasedObject = grabbedObject;
        Rigidbody releasedRigidbody = grabbedRigidbody;

        // Remove physical connection.
        if (grabJoint != null)
        {
            Destroy(grabJoint);
            grabJoint = null;
        }

        // Restore normal dynamic physics.
        if (releasedRigidbody != null)
        {
            releasedRigidbody.isKinematic = false;

            // Preserve approximately the robot's velocity
            // at the instant of release.
            releasedRigidbody.linearVelocity =
                robotRigidbody.linearVelocity;

            releasedRigidbody.angularVelocity =
                Vector3.zero;
        }

        // Clear grabbed state.
        grabbedObject = null;
        grabbedRigidbody = null;

        // IMPORTANT:
        // Do NOT clear availableObject here.
        //
        // If the released object is still inside GrabZone,
        // it should remain immediately available for another grab.
        availableObject = releasedObject;

        Debug.Log(
            "[GRAB] Object released: " +
            releasedObject.name
        );

        Debug.Log(
            "[GRAB] Object remains available while inside grab zone: " +
            releasedObject.name
        );
    }

    // =========================================================
    // GRAB ZONE INTERFACE
    // =========================================================

    public void SetAvailableObject(GameObject obj)
    {
        // While carrying something, ignore other candidates.
        if (grabbedObject != null)
            return;

        availableObject = obj;
    }

    public void ClearAvailableObject(GameObject obj)
    {
        // If this is the currently grabbed object,
        // ignore trigger-exit messages caused while carrying it.
        if (grabbedObject == obj)
            return;

        if (availableObject == obj)
        {
            availableObject = null;

            Debug.Log(
                "[GRAB] Object no longer available: " +
                obj.name
            );
        }
    }

    // =========================================================
    // EXTERNAL CONTROL
    // =========================================================

    public void SetKeyboardTestMode(bool enabled)
    {
        keyboardTestMode = enabled;
    }
}