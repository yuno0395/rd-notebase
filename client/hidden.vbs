' Runs workspace\notebase.cmd without showing a window (used by the scheduled task)
Set fso = CreateObject("Scripting.FileSystemObject")
ws = fso.GetParentFolderName(fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName)))
arg = ""
If WScript.Arguments.Count > 0 Then arg = WScript.Arguments(0)
CreateObject("WScript.Shell").Run """" & ws & "\notebase.cmd"" " & arg, 0, True
