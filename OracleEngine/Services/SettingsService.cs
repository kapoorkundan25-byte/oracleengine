using System.Text.Json;

namespace OracleEngine.Services;

public class SettingsService : ISettingsService
{
    private readonly string _settingsFilePath;
    private readonly IConfiguration _configuration;
    private readonly object _lock = new();
    private SiteSettings? _cached;

    public SettingsService(IWebHostEnvironment env, IConfiguration configuration)
    {
        _settingsFilePath = Path.Combine(env.ContentRootPath, "site-settings.json");
        _configuration = configuration;
    }

    public SiteSettings GetSettings()
    {
        lock (_lock)
        {
            if (_cached is not null)
                return _cached;

            if (File.Exists(_settingsFilePath))
            {
                var json = File.ReadAllText(_settingsFilePath);
                _cached = JsonSerializer.Deserialize<SiteSettings>(json) ?? CreateDefaults();
            }
            else
            {
                _cached = CreateDefaults();
            }

            return _cached;
        }
    }

    public void SaveSettings(SiteSettings settings)
    {
        lock (_lock)
        {
            var json = JsonSerializer.Serialize(settings, new JsonSerializerOptions { WriteIndented = true });
            File.WriteAllText(_settingsFilePath, json);
            _cached = settings;
        }
    }

    private SiteSettings CreateDefaults()
    {
        // Seed the admin password hash from appsettings.json on first run
        var hash = _configuration["AdminCredentials:PasswordHash"] ?? string.Empty;
        return new SiteSettings { AdminPasswordHash = hash };
    }
}
