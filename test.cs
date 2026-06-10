using System;
using System.Reflection;
using System.Linq;

class Program
{
    static void Main()
    {
        var asm = Assembly.LoadFrom(@"C:\Users\Ronny M PC\.nuget\packages\jellyfin.controller\10.11.3\lib\net9.0\MediaBrowser.Controller.dll");
        var type = asm.GetType("MediaBrowser.Controller.Authentication.IAuthenticationProvider");
        var method = type.GetMethod("HasPassword");
        Console.WriteLine(method.GetParameters()[0].ParameterType.FullName);
    }
}
