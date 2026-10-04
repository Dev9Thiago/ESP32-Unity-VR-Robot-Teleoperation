using UnityEngine;

public class RobotCollisionDetector : MonoBehaviour
{
    private int environmentLayer;
    private int interactableLayer;

    private void Awake()
    {
        environmentLayer = LayerMask.NameToLayer("Environment");
        interactableLayer = LayerMask.NameToLayer("Interactable");

        if (environmentLayer == -1)
            Debug.LogError("Layer 'Environment' does not exist.");

        if (interactableLayer == -1)
            Debug.LogError("Layer 'Interactable' does not exist.");
    }

    private void OnCollisionEnter(Collision collision)
    {
        int collisionLayer = collision.gameObject.layer;

        if (collisionLayer == environmentLayer)
        {
            HapticEventManager.Instance?.TriggerEvent(
                HapticEventManager.HapticEvent.Environment
            );
        }
        else if (collisionLayer == interactableLayer)
        {
            HapticEventManager.Instance?.TriggerEvent(
                HapticEventManager.HapticEvent.Interactable
            );
        }
    }

    private void OnCollisionExit(Collision collision)
    {
        int collisionLayer = collision.gameObject.layer;

        if (collisionLayer == environmentLayer ||
            collisionLayer == interactableLayer)
        {
            HapticEventManager.Instance?.StopHaptics();
        }
    }
}