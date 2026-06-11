namespace FirmwareSentinelExposure;

public class ExposureParser
{
    public string Classify(int score)
    {
        if (score < 25) return "Routine";
        if (score < 50) return "Anomalous";
        if (score < 75) return "Exposure";
        return "Critical";
    }
}
