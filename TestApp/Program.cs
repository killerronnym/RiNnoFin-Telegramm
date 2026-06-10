using System;
using System.Reflection;

class Program {
    static void Main() {
        var asm = typeof(MediaBrowser.Controller.Authentication.IAuthenticationProvider).Assembly;
        var type = asm.GetType("MediaBrowser.Controller.Authentication.IAuthenticationProvider");
        var m = type.GetMethod("HasPassword");
        Console.WriteLine(m.GetParameters()[0].ParameterType.FullName);
    }
}
