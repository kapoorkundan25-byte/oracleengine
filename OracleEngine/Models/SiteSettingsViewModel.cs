using System.ComponentModel.DataAnnotations;

namespace OracleEngine.Models;

public class SiteSettingsViewModel
{
    [Required(ErrorMessage = "Site title is required.")]
    [StringLength(100, ErrorMessage = "Title cannot exceed 100 characters.")]
    [Display(Name = "Site Title")]
    public string SiteTitle { get; set; } = string.Empty;

    [Required(ErrorMessage = "Site description is required.")]
    [StringLength(500, ErrorMessage = "Description cannot exceed 500 characters.")]
    [Display(Name = "Site Description")]
    public string SiteDescription { get; set; } = string.Empty;

    [Required(ErrorMessage = "Welcome message is required.")]
    [StringLength(1000, ErrorMessage = "Welcome message cannot exceed 1000 characters.")]
    [Display(Name = "Welcome Message")]
    public string WelcomeMessage { get; set; } = string.Empty;

    [EmailAddress(ErrorMessage = "Enter a valid email address.")]
    [StringLength(200)]
    [Display(Name = "Contact Email")]
    public string? ContactEmail { get; set; }

    [Display(Name = "New Admin Password")]
    [StringLength(100, MinimumLength = 8, ErrorMessage = "Password must be at least 8 characters.")]
    [DataType(DataType.Password)]
    public string? NewAdminPassword { get; set; }

    [DataType(DataType.Password)]
    [Display(Name = "Confirm New Password")]
    [Compare(nameof(NewAdminPassword), ErrorMessage = "Passwords do not match.")]
    public string? ConfirmNewPassword { get; set; }
}
