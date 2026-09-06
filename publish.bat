@echo off
REM Rebuild, verify, publish. Run from anywhere:  publish
REM
REM Each step only runs if the one before it succeeded, so a broken build or a
REM failed check never reaches the live site. That guard matters more than the
REM convenience: the failure you want to catch is the one you would not notice.
REM
REM   publish            rebuild from files already on disk, then deploy
REM   publish YOURKEY    full refresh including the video index, then deploy
REM   publish --check    rebuild and verify, but do NOT deploy

setlocal
cd /d "%~dp0"

set PROJECT=graniterecord
set BASE=https://graniterecord.org

if "%1"=="--check" goto :build_local
if "%1"=="" goto :build_local

echo.
echo === Full rebuild, including the video index ===
python3 build_all.py --key %1
if errorlevel 1 goto :failed
goto :verify

:build_local
echo.
echo === Rebuild from local files ===
python3 build_all.py --local
if errorlevel 1 goto :failed

:verify
echo.
echo === Checking the site before publishing ===
python3 check_site.py --site site --base %BASE%
if errorlevel 1 goto :failed

if "%1"=="--check" (
  echo.
  echo Checks passed. Nothing deployed, because --check was given.
  goto :done
)

echo.
echo === Publishing ===
npx wrangler pages deploy site --project-name=%PROJECT% --commit-dirty=true
if errorlevel 1 goto :failed

echo.
echo === Live at %BASE% ===
echo A previous version can be restored from the Deployments tab in Cloudflare.
goto :done

:failed
echo.
echo *** Stopped. Nothing was published. ***
echo Fix the error above and run publish again; the steps before it are cached,
echo so a rerun is quick.
exit /b 1

:done
endlocal
