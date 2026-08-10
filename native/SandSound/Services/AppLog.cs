namespace SandSound.Services;

public static class AppLog
{
    private static readonly object Sync = new();

    public static void Write(string message, Exception? exception = null)
    {
        try
        {
            lock (Sync)
            {
                File.AppendAllText(
                    AppPaths.LogFile,
                    $"[{DateTimeOffset.Now:O}] {message}{(exception is null ? string.Empty : Environment.NewLine + exception)}{Environment.NewLine}");
            }
        }
        catch
        {
            // Logging must never take down the application.
        }
    }
}
