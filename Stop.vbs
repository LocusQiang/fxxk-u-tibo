Option Explicit
Dim shell, fso, root, entry, powershell, command, code, detail
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
entry = fso.BuildPath(root, "scripts\vbs-entry.ps1")
powershell = shell.ExpandEnvironmentStrings("%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe")
If Not fso.FileExists(entry) Then
    shell.Popup "Missing scripts\vbs-entry.ps1. Extract the complete release before using Stop.vbs.", 15, "fxxk u tibo", 16
    WScript.Quit 1
End If
command = Chr(34) & powershell & Chr(34) & " -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy RemoteSigned -File " & Chr(34) & entry & Chr(34) & " -Action Stop"
On Error Resume Next
code = shell.Run(command, 0, True)
If Err.Number <> 0 Then
    detail = Err.Description
    On Error GoTo 0
    shell.Popup "Could not run Stop: " & detail, 15, "fxxk u tibo", 16
    WScript.Quit 1
End If
On Error GoTo 0
If code <> 0 Then
    ' The PowerShell entry reports application errors. This also covers policy blocks.
    shell.Popup "Stop did not complete. Run scripts\vbs-entry.ps1 -Action Stop in PowerShell to see the error. If Windows blocked downloaded files, review the release and use file Properties > Unblock before extracting again.", 15, "fxxk u tibo", 16
End If
WScript.Quit code
