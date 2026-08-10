using System.Net.Http.Headers;
using System.Text.Json;

namespace SandSound.Services;

public sealed record UpdateInfo(Version Version, string Tag, string PageUrl, string Notes);

public sealed class UpdateService
{
    public static readonly Version CurrentVersion = new(2, 0, 1);
    private const string LatestReleaseApi = "https://api.github.com/repos/Nasapan23/sandsound/releases/latest";

    public async Task<UpdateInfo?> CheckAsync(CancellationToken cancellationToken = default)
    {
        using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(10) };
        client.DefaultRequestHeaders.UserAgent.Add(new ProductInfoHeaderValue("SandSound", CurrentVersion.ToString()));
        client.DefaultRequestHeaders.Accept.Add(new MediaTypeWithQualityHeaderValue("application/vnd.github+json"));
        await using var stream = await client.GetStreamAsync(LatestReleaseApi, cancellationToken);
        using var payload = await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken);
        var root = payload.RootElement;
        var tag = root.GetProperty("tag_name").GetString() ?? string.Empty;
        if (!Version.TryParse(tag.TrimStart('v', 'V').Split('-', 2)[0], out var version) || version <= CurrentVersion)
            return null;
        return new UpdateInfo(
            version,
            tag,
            root.GetProperty("html_url").GetString() ?? "https://github.com/Nasapan23/sandsound/releases/latest",
            root.TryGetProperty("body", out var body) ? body.GetString() ?? string.Empty : string.Empty);
    }
}
