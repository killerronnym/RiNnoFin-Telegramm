using System;
using System.Collections.Generic;
using System.IO;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Classes
{
    public static class PluginLog
    {
        private static readonly List<string> _inMemoryLogs = new();
        private static readonly object _lock = new();
        private static string _logFilePath = null;

        private static string LogFilePath
        {
            get
            {
                if (_logFilePath == null)
                {
                    try
                    {
                        var plugin = RiNnoFinPlugin.Instance;
                        if (plugin != null)
                        {
                            var logDir = plugin.ApplicationPaths.LogDirectoryPath;
                            if (!Directory.Exists(logDir))
                            {
                                Directory.CreateDirectory(logDir);
                            }
                            _logFilePath = Path.Combine(logDir, "rinnofin_telegramm.log");
                        }
                    }
                    catch
                    {
                        // Fallback
                    }
                }
                return _logFilePath;
            }
        }

        public static void Info(string message) => Log("INFO", message);
        public static void Warn(string message) => Log("WARN", message);
        public static void Error(string message) => Log("ERROR", message);
        public static void Error(Exception ex, string message) => Log("ERROR", $"{message} | Exception: {ex.Message}\n{ex.StackTrace}");

        private static void Log(string level, string message)
        {
            var formatted = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [{level}] {message}";
            lock (_lock)
            {
                _inMemoryLogs.Add(formatted);
                if (_inMemoryLogs.Count > 300)
                {
                    _inMemoryLogs.RemoveAt(0);
                }

                try
                {
                    var path = LogFilePath;
                    if (path != null)
                    {
                        File.AppendAllText(path, formatted + Environment.NewLine);
                    }
                }
                catch
                {
                    // Ignored
                }
            }
        }

        public static List<string> GetLogs()
        {
            lock (_lock)
            {
                return new List<string>(_inMemoryLogs);
            }
        }
    }
}
