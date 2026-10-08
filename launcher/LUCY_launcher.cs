using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

namespace LucyLauncher
{
    static class Program
    {
        // Exit code returned by python.exe when a code-integrity policy (Smart App
        // Control / WDAC) blocks loading python311.dll -> status 0xc0e90002.
        const int STATUS_BAD_IMAGE_POLICY = -1058471934;

        [STAThread]
        static void Main()
        {
            try
            {
                // All paths derive from the launcher's own folder, so startup is
                // independent of the current working directory (Search, Start Menu,
                // Desktop shortcut, direct launch all behave identically).
                string baseDir = AppDomain.CurrentDomain.BaseDirectory;
                string mainPy = Path.Combine(baseDir, "main.py");

                if (!File.Exists(mainPy))
                {
                    string localAppDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "LUCY");
                    if (File.Exists(Path.Combine(localAppDir, "main.py")))
                    {
                        baseDir = localAppDir;
                        mainPy = Path.Combine(baseDir, "main.py");
                    }
                }

                string pythonwExe = Path.Combine(baseDir, "runtime", "pythonw.exe");
                string pythonExe = Path.Combine(baseDir, "runtime", "python.exe");
                string setupBat = Path.Combine(baseDir, "setup.bat");

                if (!File.Exists(mainPy))
                {
                    MessageBox.Show(
                        "LUCY application files (main.py) were not found.\nPlease run setup.bat to install or initialize LUCY.",
                        "LUCY - Missing Files",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Error
                    );
                    return;
                }

                string exeToUse = File.Exists(pythonExe) ? pythonExe : (File.Exists(pythonwExe) ? pythonwExe : null);

                if (exeToUse == null)
                {
                    if (File.Exists(setupBat))
                    {
                        var res = MessageBox.Show(
                            "LUCY runtime environment is not initialized yet.\nWould you like to run setup.bat now?",
                            "LUCY - First Run Setup",
                            MessageBoxButtons.YesNo,
                            MessageBoxIcon.Information
                        );
                        if (res == DialogResult.Yes)
                        {
                            ProcessStartInfo setupPsi = new ProcessStartInfo
                            {
                                FileName = "cmd.exe",
                                Arguments = "/c \"" + setupBat + "\"",
                                WorkingDirectory = baseDir,
                                UseShellExecute = true
                            };
                            Process.Start(setupPsi);
                        }
                    }
                    else
                    {
                        MessageBox.Show(
                            "LUCY runtime not found. Please run setup.bat first.",
                            "LUCY - Error",
                            MessageBoxButtons.OK,
                            MessageBoxIcon.Error
                        );
                    }
                    return;
                }

                // Validate the bundled runtime before starting the app so a blocked
                // or broken python311.dll produces a clear message instead of the
                // cryptic Windows "Bad Image" popup.
                if (!RuntimeOk(exeToUse))
                {
                    MessageBox.Show(
                        "LUCY's bundled Python runtime could not start.\n\n" +
                        "This is almost always caused by Windows Smart App Control blocking\n" +
                        "the unsigned runtime DLLs (python311.dll, \"Bad Image\" 0xc0e90002).\n\n" +
                        "Fix: Windows Security > App & browser control > Smart App Control\n" +
                        "settings > Off, then restart Windows and launch LUCY again.",
                        "LUCY - Runtime Blocked by Windows",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Warning
                    );
                    return;
                }

                ProcessStartInfo psi = new ProcessStartInfo
                {
                    FileName = exeToUse,
                    Arguments = "\"" + mainPy + "\"",
                    WorkingDirectory = baseDir,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };

                try
                {
                    Process.Start(psi);
                }
                catch (System.ComponentModel.Win32Exception)
                {
                    if (exeToUse != pythonExe && File.Exists(pythonExe))
                    {
                        psi.FileName = pythonExe;
                        Process.Start(psi);
                    }
                    else
                    {
                        throw;
                    }
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    "Failed to start LUCY:\n" + ex.Message,
                    "LUCY - Error",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
            }
        }

        // Runs "python -c import sys" with a short timeout; returns false when the
        // interpreter cannot load its core DLL (e.g. blocked by code integrity).
        static bool RuntimeOk(string pythonExe)
        {
            try
            {
                ProcessStartInfo probe = new ProcessStartInfo
                {
                    FileName = pythonExe,
                    Arguments = "-c \"import sys\"",
                    WorkingDirectory = Path.GetDirectoryName(pythonExe),
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true
                };
                using (Process p = Process.Start(probe))
                {
                    string err = p.StandardError.ReadToEnd();
                    if (!p.WaitForExit(15000))
                    {
                        try { p.Kill(); } catch { }
                        return false;
                    }
                    if (p.ExitCode == 0) return true;
                    if (p.ExitCode == STATUS_BAD_IMAGE_POLICY || err.IndexOf("0xc0e90002", StringComparison.OrdinalIgnoreCase) >= 0)
                    {
                        return false; // code-integrity block (Smart App Control)
                    }
                    return false; // any other startup failure: let the message show
                }
            }
            catch
            {
                return false;
            }
        }
    }
}
