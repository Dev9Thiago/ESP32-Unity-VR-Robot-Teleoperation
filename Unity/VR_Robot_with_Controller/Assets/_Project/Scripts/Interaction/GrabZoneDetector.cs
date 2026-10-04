using UnityEngine;

public class GrabZoneDetector : MonoBehaviour
{
    [SerializeField] private RobotGrabber robotGrabber;

    private int interactableLayer;

    private void Awake()
    {
        interactableLayer = LayerMask.NameToLayer("Interactable");

        if (interactableLayer == -1)
        {
            Debug.LogError(
                "Layer 'Interactable' does not exist."
            );
        }
    }

    private void OnTriggerEnter(Collider other)
    {
        if (other.gameObject.layer != interactableLayer)
            return;

        robotGrabber.SetAvailableObject(other.gameObject);

        Debug.Log(
            "[GRAB ZONE] Object available: " +
            other.gameObject.name
        );
    }

    private void OnTriggerExit(Collider other)
    {
        if (other.gameObject.layer != interactableLayer)
            return;

        robotGrabber.ClearAvailableObject(other.gameObject);

        Debug.Log(
            "[GRAB ZONE] Object left zone: " +
            other.gameObject.name
        );
    }
}