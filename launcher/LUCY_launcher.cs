using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

namespace LucyLauncher
{
    static class Program
    {
        [STAThread]
        static void Main()
        {
            try
            {
                string baseDir = AppDomain.CurrentDomain.BaseDirectory;
                string pythonwExe = Path.Combine(baseDir, "runtime", "pythonw.exe");
                string pythonExe = Path.Combine(baseDir, "runtime", "python.exe");
                string mainPy = Path.Combine(baseDir, "main.py");
                string setupBat = Path.Combine(baseDir, "setup.bat");

                if (!File.Exists(mainPy))
                {
                    MessageBox.Show(
                        "LUCY application files (main.py) were not found in this folder.\nPlease make sure all files from the ZIP are extracted together.",
                        "LUCY - Missing Files",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Error
                    );
                    return;
                }

                string exeToUse = File.Exists(pythonwExe) ? pythonwExe : (File.Exists(pythonExe) ? pythonExe : null);

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

                ProcessStartInfo psi = new ProcessStartInfo
                {
                    FileName = exeToUse,
                    Arguments = "\"" + mainPy + "\"",
                    WorkingDirectory = baseDir,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };

                Process.Start(psi);
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
    }
}
