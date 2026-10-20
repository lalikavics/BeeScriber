// BeeScriber.exe: starts the app without a console window.
//   installed:   <folder>\python\pythonw.exe  (the Python bundled by the installer)
//   development: <folder>\tools\venv\Scripts\pythonw.exe  (created by devtest\bee_test.py setup)
// Build: csc /target:winexe /win32icon:app\beescriber\ui\logo.ico ...   (the C# compiler that comes with Windows)
using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Windows.Forms;

[assembly: System.Reflection.AssemblyTitle("BeeScriber")]
[assembly: System.Reflection.AssemblyProduct("BeeScriber")]
[assembly: System.Reflection.AssemblyCompany("Lalikavics")]
[assembly: System.Reflection.AssemblyVersion("0.1.0.0")]

static class BeeScriberLauncher
{
    [STAThread]
    static int Main(string[] args)
    {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string py = Path.Combine(root, @"python\pythonw.exe");
        if (!File.Exists(py)) py = Path.Combine(root, @"tools\venv\Scripts\pythonw.exe");
        string app = Path.Combine(root, "app");
        if (!File.Exists(py) || !Directory.Exists(Path.Combine(app, "beescriber")))
        {
            MessageBox.Show("BeeScriber could not start: its Python or the app folder is missing next to BeeScriber.exe.\n\n" +
                            "Please reinstall BeeScriber.", "BeeScriber", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
        var psi = new ProcessStartInfo(py)
        {
            Arguments = "-m beescriber " + string.Join(" ", args.Select(a => "\"" + a.Replace("\"", "\\\"") + "\"")),
            WorkingDirectory = app,
            UseShellExecute = false,
        };
        try { Process.Start(psi); }
        catch (Exception ex)
        {
            MessageBox.Show("BeeScriber could not start:\n" + ex.Message, "BeeScriber", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 2;
        }
        return 0;
    }
}
