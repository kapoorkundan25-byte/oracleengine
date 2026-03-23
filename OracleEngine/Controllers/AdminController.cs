using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using OracleEngine.Helpers;
using OracleEngine.Models;
using OracleEngine.Services;

namespace OracleEngine.Controllers;

[Authorize(Policy = "AdminOnly")]
public class AdminController : Controller
{
    private readonly ISettingsService _settingsService;

    public AdminController(ISettingsService settingsService)
    {
        _settingsService = settingsService;
    }

    [HttpGet]
    public IActionResult Settings()
    {
        var settings = _settingsService.GetSettings();
        var model = new SiteSettingsViewModel
        {
            SiteTitle = settings.SiteTitle,
            SiteDescription = settings.SiteDescription,
            WelcomeMessage = settings.WelcomeMessage,
            ContactEmail = settings.ContactEmail
        };
        return View(model);
    }

    [HttpPost]
    [ValidateAntiForgeryToken]
    public IActionResult Settings(SiteSettingsViewModel model)
    {
        if (!ModelState.IsValid)
            return View(model);

        var settings = _settingsService.GetSettings();
        settings.SiteTitle = model.SiteTitle;
        settings.SiteDescription = model.SiteDescription;
        settings.WelcomeMessage = model.WelcomeMessage;
        settings.ContactEmail = model.ContactEmail;

        if (!string.IsNullOrWhiteSpace(model.NewAdminPassword))
        {
            settings.AdminPasswordHash = PasswordHelper.HashPassword(model.NewAdminPassword);
        }

        _settingsService.SaveSettings(settings);

        TempData["SuccessMessage"] = "Settings saved successfully.";
        return RedirectToAction(nameof(Settings));
    }
}
