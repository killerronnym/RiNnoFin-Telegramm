using MediaBrowser.Controller.Entities;
using System.Linq;
using MediaBrowser.Controller.Library;

class Program
{
    static void Main(BaseItem item, ILibraryManager lib)
    {
        var p = item.GetParents().LastOrDefault();
        var f = lib.GetLibraryOptions(item);
    }
}
