Option Explicit
Dim shell, fso, root, entry, powershell, command, code, detail
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
entry = fso.BuildPath(root, "scripts\vbs-entry.ps1")
powershell = shell.ExpandEnvironmentStrings("%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe")
If Not fso.FileExists(entry) Then
    shell.Popup "Missing scripts\vbs-entry.ps1. Extract the complete release before using Preview.vbs.", 15, "Codex Auto Retry Kitchen", 16
    WScript.Quit 1
End If
command = Chr(34) & powershell & Chr(34) & " -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy RemoteSigned -File " & Chr(34) & entry & Chr(34) & " -Action Preview"
On Error Resume Next
code = shell.Run(command, 0, True)
If Err.Number <> 0 Then
    detail = Err.Description
    On Error GoTo 0
    shell.Popup "Could not run Preview: " & detail, 15, "Codex Auto Retry Kitchen", 16
    WScript.Quit 1
End If
On Error GoTo 0
If code <> 0 Then
    ' The PowerShell entry reports application errors. This also covers policy blocks.
    shell.Popup "Preview did not complete. Run scripts\vbs-entry.ps1 -Action Preview in PowerShell to see the error. If Windows blocked downloaded files, review the release and use file Properties > Unblock before extracting again.", 15, "Codex Auto Retry Kitchen", 16
End If
WScript.Quit code
