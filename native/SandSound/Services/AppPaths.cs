namespace SandSound.Services;

public static class AppPaths
{
    public static string ExecutableDirectory
    {
        get
        {
            var processPath = Environment.ProcessPath;
            return !string.IsNullOrWhiteSpace(processPath)
                ? Path.GetDirectoryName(processPath)!
                : AppContext.BaseDirectory;
        }
    }

    public static string DataDirectory => Ensure(Path.Combine(ExecutableDirectory, "Data"));
    public static string ToolsDirectory => Path.Combine(ExecutableDirectory, "Tools");
    public static string DefaultDownloadDirectory => Ensure(Path.Combine(ExecutableDirectory, "Downloads"));
    public static string SettingsFile => Path.Combine(DataDirectory, "settings.json");
    public static string HistoryFile => Path.Combine(DataDirectory, "history.json");
    public static string LogFile => Path.Combine(DataDirectory, "sandsound.log");

    public static string FindTool(string fileName, string pathFallback)
    {
        var portable = Path.Combine(ToolsDirectory, fileName);
        return File.Exists(portable) ? portable : pathFallback;
    }

    public static string ToStoredPath(string path)
    {
        if (string.IsNullOrWhiteSpace(path)) return string.Empty;
        var fullPath = Path.GetFullPath(path);
        var root = Path.GetFullPath(ExecutableDirectory).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        return fullPath.StartsWith(root, StringComparison.OrdinalIgnoreCase)
            ? "." + Path.DirectorySeparatorChar + Path.GetRelativePath(ExecutableDirectory, fullPath)
            : fullPath;
    }

    public static string FromStoredPath(string path)
    {
        if (string.IsNullOrWhiteSpace(path)) return string.Empty;
        return path.StartsWith("." + Path.DirectorySeparatorChar, StringComparison.Ordinal)
            ? Path.GetFullPath(Path.Combine(ExecutableDirectory, path[2..]))
            : Path.GetFullPath(path);
    }

    private static string Ensure(string path)
    {
        Directory.CreateDirectory(path);
        return path;
    }
}
