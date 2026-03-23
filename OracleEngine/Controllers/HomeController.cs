using System.Diagnostics;
using Microsoft.AspNetCore.Mvc;
using OracleEngine.Models;
using OracleEngine.Services;

namespace OracleEngine.Controllers;

public class HomeController : Controller
{
    private readonly ISettingsService _settingsService;

    public HomeController(ISettingsService settingsService)
    {
        _settingsService = settingsService;
    }

    public IActionResult Index()
    {
        var settings = _settingsService.GetSettings();
        ViewData["SiteTitle"] = settings.SiteTitle;
        ViewData["SiteDescription"] = settings.SiteDescription;
        ViewData["WelcomeMessage"] = settings.WelcomeMessage;
        ViewData["ContactEmail"] = settings.ContactEmail;
        return View();
    }

    public IActionResult Privacy()
    {
        return View();
    }

    [ResponseCache(Duration = 0, Location = ResponseCacheLocation.None, NoStore = true)]
    public IActionResult Error()
    {
        return View(new ErrorViewModel { RequestId = Activity.Current?.Id ?? HttpContext.TraceIdentifier });
    }
}
