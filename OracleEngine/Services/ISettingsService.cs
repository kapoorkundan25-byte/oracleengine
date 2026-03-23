namespace OracleEngine.Services;

public interface ISettingsService
{
    SiteSettings GetSettings();
    void SaveSettings(SiteSettings settings);
}

public class SiteSettings
{
    public string SiteTitle { get; set; } = "OracleEngine";
    public string SiteDescription { get; set; } = "Your trusted Oracle Engine platform.";
    public string WelcomeMessage { get; set; } = "Welcome to OracleEngine. Explore and discover.";
    public string? ContactEmail { get; set; }
    public string AdminPasswordHash { get; set; } = string.Empty;
}
