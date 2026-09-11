using RosMessageTypes.Sensor;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;
using UnityEngine.UI;

/// <summary>
/// Displays the S22 conveyor stop-line JPEG on a RawImage.
/// Attach this component to the RawImage (or assign target explicitly).
/// The texture size is taken from each JPEG; no 1280x720 assumption is made.
/// </summary>
public sealed class S22ConveyorOverlayView : MonoBehaviour
{
    [SerializeField] RawImage target;
    [SerializeField] string topic = "/vision/conveyor/stop_image/compressed";
    [SerializeField] bool updateAspectRatio = true;

    Texture2D texture;
    int receivedFrames;

    void Awake()
    {
        if (target == null)
            target = GetComponent<RawImage>();
    }

    void Start()
    {
        if (target == null)
        {
            Debug.LogError("S22ConveyorOverlayView needs a RawImage target.");
            enabled = false;
            return;
        }

        ROSConnection.GetOrCreateInstance().Subscribe<CompressedImageMsg>(
            topic, OnCompressedImage);
        Debug.Log($"S22 overlay subscribed: {topic}");
    }

    void OnCompressedImage(CompressedImageMsg message)
    {
        if (message == null || message.data == null || message.data.Length == 0)
        {
            Debug.LogWarning("S22 overlay received an empty CompressedImage.");
            return;
        }

        if (texture == null)
            texture = new Texture2D(2, 2, TextureFormat.RGB24, false);

        if (!texture.LoadImage(message.data, false))
        {
            Debug.LogWarning(
                $"S22 overlay JPEG decode failed (format={message.format}, bytes={message.data.Length}).");
            return;
        }

        target.texture = texture;
        if (updateAspectRatio)
        {
            var fitter = target.GetComponent<AspectRatioFitter>();
            if (fitter != null && texture.height > 0)
                fitter.aspectRatio = (float)texture.width / texture.height;
        }

        receivedFrames++;
        if (receivedFrames == 1 || receivedFrames % 60 == 0)
        {
            Debug.Log(
                $"S22 overlay frame {receivedFrames}: {texture.width}x{texture.height}, " +
                $"format={message.format}, bytes={message.data.Length}");
        }
    }

    void OnDestroy()
    {
        if (texture != null)
            Destroy(texture);
    }
}
