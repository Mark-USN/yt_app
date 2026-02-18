Get-CimInstance Win32_Process |
  Where-Object {
    $_.Name -like "python*.exe" -and
    $_.CommandLine -match "aldale_yt_app.py"
  } |
  Select-Object ProcessId, Name, CommandLine
