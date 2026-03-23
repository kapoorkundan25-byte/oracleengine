using System.Security.Claims;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Mvc;
using OracleEngine.Helpers;
using OracleEngine.Models;
using OracleEngine.Services;

namespace OracleEngine.Controllers;

public class AccountController : Controller
{
    private readonly ISettingsService _settingsService;
    private readonly IConfiguration _configuration;

    public AccountController(ISettingsService settingsService, IConfiguration configuration)
    {
        _settingsService = settingsService;
        _configuration = configuration;
    }

    [HttpGet]
    public IActionResult Login(string? returnUrl = null)
    {
        if (User.Identity?.IsAuthenticated == true)
            return RedirectToAction("Settings", "Admin");

        return View(new LoginViewModel { ReturnUrl = returnUrl });
    }

    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Login(LoginViewModel model)
    {
        if (!ModelState.IsValid)
            return View(model);

        var adminUsername = _configuration["AdminCredentials:Username"] ?? "admin";
        var settings = _settingsService.GetSettings();
        var storedHash = settings.AdminPasswordHash;

        if (!string.Equals(model.Username, adminUsername, StringComparison.OrdinalIgnoreCase)
            || !PasswordHelper.VerifyPassword(model.Password, storedHash))
        {
            ModelState.AddModelError(string.Empty, "Invalid username or password.");
            return View(model);
        }

        var claims = new List<Claim>
        {
            new Claim(ClaimTypes.Name, adminUsername),
            new Claim("Role", "Admin")
        };

        var identity = new ClaimsIdentity(claims, "AdminCookie");
        var principal = new ClaimsPrincipal(identity);

        await HttpContext.SignInAsync("AdminCookie", principal);

        if (!string.IsNullOrEmpty(model.ReturnUrl) && Url.IsLocalUrl(model.ReturnUrl))
            return Redirect(model.ReturnUrl);

        return RedirectToAction("Settings", "Admin");
    }

    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Logout()
    {
        await HttpContext.SignOutAsync("AdminCookie");
        return RedirectToAction("Index", "Home");
    }
}
