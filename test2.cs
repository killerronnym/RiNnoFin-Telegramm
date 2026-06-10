using System;
using System.Reflection;

class Program {
    static void Main() {
        try {
        var asm = Assembly.LoadFrom(@"C:\Users\Ronny M PC\.nuget\packages\jellyfin.controller\10.11.3\lib\net9.0\MediaBrowser.Controller.dll");
        var type = asm.GetType("MediaBrowser.Controller.Authentication.IAuthenticationProvider");
        var m = type.GetMethod("HasPassword");
        Console.WriteLine(m.GetParameters()[0].ParameterType.FullName);
        } catch(Exception ex) { Console.WriteLine(ex.ToString()); }
    }
}
