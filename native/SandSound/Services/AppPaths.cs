namespace SandSound.Services;

public static class AppPaths
{
    private static readonly StringComparison PathComparison = OperatingSystem.IsWindows()
        ? StringComparison.OrdinalIgnoreCase
        : StringComparison.Ordinal;

    private static string ProcessDirectory
    {
        get
        {
            var processPath = Environment.ProcessPath;
            return Path.GetFullPath(!string.IsNullOrWhiteSpace(processPath)
                ? Path.GetDirectoryName(processPath)!
                : AppContext.BaseDirectory);
        }
    }

    private static bool IsMacAppBundleDirectory(string directory) =>
        OperatingSystem.IsMacOS() &&
        string.Equals(Path.GetFileName(directory), "MacOS", StringComparison.Ordinal) &&
        string.Equals(Path.GetFileName(Path.GetDirectoryName(directory)), "Contents", StringComparison.Ordinal);

    public static string ExecutableDirectory
    {
        get
        {
            var executableDirectory = ProcessDirectory;

            // A portable macOS release keeps mutable data beside SandSound.app,
            // rather than inside its Contents directory.
            if (IsMacAppBundleDirectory(executableDirectory))
            {
                var appBundle = Directory.GetParent(executableDirectory)?.Parent;
                if (appBundle?.Parent is { } portableRoot) return portableRoot.FullName;
            }

            return Path.GetFullPath(executableDirectory);
        }
    }

    public static string DataDirectory => Ensure(Path.Combine(ExecutableDirectory, "Data"));
    public static string ToolsDirectory => IsMacAppBundleDirectory(ProcessDirectory)
        ? Path.Combine(ProcessDirectory, "Tools")
        : Path.Combine(ExecutableDirectory, "Tools");
    public static string DefaultDownloadDirectory => Ensure(Path.Combine(ExecutableDirectory, "Downloads"));
    public static string SettingsFile => Path.Combine(DataDirectory, "settings.json");
    public static string HistoryFile => Path.Combine(DataDirectory, "history.json");
    public static string LogFile => Path.Combine(DataDirectory, "sandsound.log");

    public static string ToolFileName(string baseName) => OperatingSystem.IsWindows() ? baseName + ".exe" : baseName;

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
        return fullPath.StartsWith(root, PathComparison)
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
