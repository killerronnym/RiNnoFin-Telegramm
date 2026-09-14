using System;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Http;

namespace Jellyfin.Plugin.RiNnoFinTelegramm.Classes;

internal static class ControllerExtensions
{
    public static string GetRequestBase(this HttpRequest request, PluginConfiguration configuration)
    {
        if (request == null)
        {
            throw new ArgumentNullException(nameof(request), "Request ist null.");
        }

        if (!string.IsNullOrWhiteSpace(configuration.LoginBaseUrl))
        {
            return configuration.LoginBaseUrl.TrimEnd('/');
        }

        var configSchema = configuration.ForcedUrlScheme;
        var requestPort = request.Host.Port ?? -1;
        var requestScheme =
            string.Equals(configSchema, "http", StringComparison.OrdinalIgnoreCase)
            || string.Equals(configSchema, "https", StringComparison.OrdinalIgnoreCase)
                ? configSchema
                : request.Scheme;

        if ((requestPort == 80 && string.Equals(requestScheme, "http", StringComparison.OrdinalIgnoreCase))
            || (requestPort == 443 && string.Equals(requestScheme, "https", StringComparison.OrdinalIgnoreCase)))
        {
            requestPort = -1;
        }

        return new UriBuilder { Scheme = requestScheme, Host = request.Host.Host, Port = requestPort, Path = request.PathBase }.ToString().TrimEnd('/');
    }

    public static System.Collections.IEnumerable GetUsersSafe(this object? userManager)
    {
        if (userManager == null) return System.Array.Empty<object>();

        try
        {
            var type = userManager.GetType();
            PluginLog.Info($"[GetUsersSafe] UserManager type: {type.FullName}");

            // 1. Try GetUsers(UserQuery) or GetUsers()
            foreach (var m in type.GetMethods())
            {
                if (m.Name.Equals("GetUsers", StringComparison.OrdinalIgnoreCase))
                {
                    var paramsList = m.GetParameters();
                    if (paramsList.Length == 0)
                    {
                        var res = m.Invoke(userManager, null) as System.Collections.IEnumerable;
                        if (res != null) return res;
                    }
                    else if (paramsList.Length == 1)
                    {
                        var paramType = paramsList[0].ParameterType;
                        object? query = null;
                        try { query = System.Activator.CreateInstance(paramType); } catch { }
                        var res = m.Invoke(userManager, new[] { query }) as System.Collections.IEnumerable;
                        if (res != null) return res;
                    }
                }
            }

            // 2. Try Users property safely
            var usersProp = type.GetProperty("Users");
            if (usersProp != null)
            {
                var res = usersProp.GetValue(userManager, null) as System.Collections.IEnumerable;
                if (res != null) return res;
            }

            // 3. Fallback: try GetUserIds / UserIds
            var getUserIdsMethod = type.GetMethod("GetUserIds");
            if (getUserIdsMethod != null)
            {
                var ids = getUserIdsMethod.Invoke(userManager, null) as System.Collections.IEnumerable;
                if (ids != null)
                {
                    var userList = new System.Collections.ArrayList();
                    var getUserByIdMethod = type.GetMethod("GetUserById", new[] { typeof(System.Guid) });
                    foreach (var idObj in ids)
                    {
                        if (idObj is System.Guid g && getUserByIdMethod != null)
                        {
                            var u = getUserByIdMethod.Invoke(userManager, new object[] { g });
                            if (u != null) userList.Add(u);
                        }
                    }
                    if (userList.Count > 0) return userList;
                }
            }

            // 4. Log methods for diagnosis if empty
            PluginLog.Warn("[GetUsersSafe] Could not retrieve users. Available methods:");
            foreach (var m in type.GetMethods())
            {
                if (m.Name.Contains("User", StringComparison.OrdinalIgnoreCase))
                {
                    PluginLog.Warn($"[GetUsersSafe] Method: {m.Name}({string.Join(", ", m.GetParameters().Select(p => p.ParameterType.Name))}) -> {m.ReturnType.Name}");
                }
            }
        }
        catch (System.Exception ex)
        {
            PluginLog.Error(ex, "[GetUsersSafe] Exception during reflection user discovery");
        }

        return System.Array.Empty<object>();
    }

    public static dynamic? GetUserByIdSafe(this object? userManager, Guid id)
    {
        if (userManager == null || id == Guid.Empty) return null;
        try
        {
            var method = userManager.GetType().GetMethod("GetUserById", new[] { typeof(Guid) });
            if (method != null)
            {
                return method.Invoke(userManager, new object[] { id });
            }
        }
        catch { }
        return null;
    }

    public static dynamic? GetUserByNameSafe(this object? userManager, string name)
    {
        if (userManager == null || string.IsNullOrWhiteSpace(name)) return null;
        try
        {
            var method = userManager.GetType().GetMethod("GetUserByName", new[] { typeof(string) });
            if (method != null)
            {
                return method.Invoke(userManager, new object[] { name });
            }
        }
        catch { }
        return null;
    }

    public static async Task DeleteUserAsyncSafe(this object? userManager, Guid id)
    {
        if (userManager == null || id == Guid.Empty) return;
        try
        {
            var method = userManager.GetType().GetMethod("DeleteUserAsync", new[] { typeof(Guid) });
            if (method != null)
            {
                var task = method.Invoke(userManager, new object[] { id }) as Task;
                if (task != null) await task.ConfigureAwait(false);
            }
        }
        catch { }
    }

    public static async Task UpdatePolicyAsyncSafe(this object? userManager, Guid id, object policy)
    {
        if (userManager == null || policy == null || id == Guid.Empty) return;
        try
        {
            var method = userManager.GetType().GetMethod("UpdatePolicyAsync", new[] { typeof(Guid), policy.GetType() })
                      ?? userManager.GetType().GetMethod("UpdatePolicyAsync", new[] { typeof(Guid), typeof(MediaBrowser.Model.Users.UserPolicy) });
            if (method != null)
            {
                var task = method.Invoke(userManager, new object[] { id, policy }) as Task;
                if (task != null) await task.ConfigureAwait(false);
            }
        }
        catch { }
    }

    public static MediaBrowser.Model.Users.UserPolicy? GetUserPolicySafe(this object? userManager, object? user)
    {
        if (userManager == null || user == null) return null;
        try
        {
            var prop = user.GetType().GetProperty("Policy");
            if (prop != null)
            {
                var pol = prop.GetValue(user, null) as MediaBrowser.Model.Users.UserPolicy;
                if (pol != null) return pol;
            }

            var method = userManager.GetType().GetMethod("GetUserPolicy", new[] { user.GetType() });
            if (method != null)
            {
                var pol = method.Invoke(userManager, new[] { user }) as MediaBrowser.Model.Users.UserPolicy;
                if (pol != null) return pol;
            }

            var dtoMethod = userManager.GetType().GetMethod("GetUserDto");
            if (dtoMethod != null)
            {
                var dto = dtoMethod.Invoke(userManager, new object[] { user, "" });
                if (dto != null)
                {
                    var dtoPolicyProp = dto.GetType().GetProperty("Policy");
                    var pol = dtoPolicyProp?.GetValue(dto, null) as MediaBrowser.Model.Users.UserPolicy;
                    if (pol != null) return pol;
                }
            }
        }
        catch { }
        return null;
    }

    public static bool IsAdminSafe(this object? userManager, object? user)
    {
        var pol = userManager.GetUserPolicySafe(user);
        return pol?.IsAdministrator ?? false;
    }

    public static bool IsDisabledSafe(this object? userManager, object? user)
    {
        var pol = userManager.GetUserPolicySafe(user);
        return pol?.IsDisabled ?? false;
    }

    public static MediaBrowser.Model.Configuration.UserConfiguration? GetUserConfigurationSafe(this object? userManager, object? user)
    {
        if (userManager == null || user == null) return null;
        try
        {
            var prop = user.GetType().GetProperty("Configuration");
            if (prop != null)
            {
                var cfg = prop.GetValue(user, null) as MediaBrowser.Model.Configuration.UserConfiguration;
                if (cfg != null) return cfg;
            }

            var method = userManager.GetType().GetMethod("GetUserConfiguration", new[] { user.GetType() });
            if (method != null)
            {
                var cfg = method.Invoke(userManager, new[] { user }) as MediaBrowser.Model.Configuration.UserConfiguration;
                if (cfg != null) return cfg;
            }
        }
        catch { }
        return null;
    }

    public static async Task<object?> CreateUserAsyncSafe(this object? userManager, string name)
    {
        if (userManager == null || string.IsNullOrWhiteSpace(name)) return null;
        try
        {
            var method = userManager.GetType().GetMethod("CreateUserAsync", new[] { typeof(string) });
            if (method != null)
            {
                var task = method.Invoke(userManager, new object[] { name }) as dynamic;
                if (task != null)
                {
                    await task;
                    return (object)task.Result;
                }
            }
        }
        catch (Exception ex)
        {
            PluginLog.Error(ex, "[CreateUserAsyncSafe] Error creating user");
        }
        return null;
    }

    public static async Task UpdateUserAsyncSafe(this object? userManager, object? user)
    {
        if (userManager == null || user == null) return;
        try
        {
            var method = userManager.GetType().GetMethod("UpdateUserAsync", new[] { user.GetType() });
            if (method != null)
            {
                var task = method.Invoke(userManager, new[] { user }) as Task;
                if (task != null) await task.ConfigureAwait(false);
            }
        }
        catch (Exception ex)
        {
            PluginLog.Error(ex, "[UpdateUserAsyncSafe] Error updating user");
        }
    }

    public static async Task UpdateConfigurationAsyncSafe(this object? userManager, Guid id, object config)
    {
        if (userManager == null || config == null || id == Guid.Empty) return;
        try
        {
            var method = userManager.GetType().GetMethod("UpdateConfigurationAsync", new[] { typeof(Guid), config.GetType() })
                      ?? userManager.GetType().GetMethod("UpdateConfigurationAsync", new[] { typeof(Guid), typeof(MediaBrowser.Model.Configuration.UserConfiguration) });
            if (method != null)
            {
                var task = method.Invoke(userManager, new object[] { id, config }) as Task;
                if (task != null) await task.ConfigureAwait(false);
            }
        }
        catch { }
    }
}
