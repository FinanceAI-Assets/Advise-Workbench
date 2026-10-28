@echo off
rem Windows launcher for run_agent.sh. Works from cmd.exe, PowerShell and a double-click.
rem
rem   scripts\run_agent.cmd             checks, then starts everything (Ctrl+C stops it all)
rem   scripts\run_agent.cmd --check     checks only
rem   scripts\run_agent.cmd --fix       checks, repairs what is safe to repair, then starts
rem
rem It runs the script with Git Bash. It deliberately avoids C:\Windows\System32\bash.exe,
rem which is the WSL launcher and would run the script in a different (Linux) environment.
setlocal

set "GITBASH="
if exist "%ProgramFiles%\Git\bin\bash.exe" set "GITBASH=%ProgramFiles%\Git\bin\bash.exe"
if not defined GITBASH if exist "%LocalAppData%\Programs\Git\bin\bash.exe" set "GITBASH=%LocalAppData%\Programs\Git\bin\bash.exe"
if not defined GITBASH if exist "%ProgramFiles(x86)%\Git\bin\bash.exe" set "GITBASH=%ProgramFiles(x86)%\Git\bin\bash.exe"

if not defined GITBASH (
  echo Git for Windows ^(Git Bash^) was not found, and run_agent.sh needs it.
  echo Install it with:  winget install --exact Git.Git
  echo then open a new terminal and run this again.
  exit /b 1
)

rem -o igncr: tolerate Windows line endings in the .sh files if a checkout converted them. It is passed on
rem the command line on purpose: exporting SHELLOPTS would leak bash options (nounset) into npm's own
rem shell wrapper and break the frontend start ("IS_WSL: unbound variable").
"%GITBASH%" -o igncr "%~dp0run_agent.sh" %*
exit /b %ERRORLEVEL%
