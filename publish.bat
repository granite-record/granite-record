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
echo === Confirming the world is getting what was just built ===
REM wrangler reporting success is not the same as the deploy landing. On
REM 6 September it printed "Deployment complete" twice for deployments the
REM production domain never took, because the project's production branch
REM was main while this repo is on master. --gate fails only when what is
REM served is not what was built; dashboard settings are reported but do
REM not fail the publish.
python3 check_live.py --gate --base %BASE% --site site
if errorlevel 1 goto :notlanded

echo.
echo === Live at %BASE% ===
echo A previous version can be restored from the Deployments tab in Cloudflare.
goto :done

:notlanded
echo.
echo *** Uploaded, but the site is still serving the previous build. ***
echo Check the Pages project's production branch, or promote the newest
echo deployment from the Deployments tab, then run publish again.
exit /b 1

:failed
echo.
echo *** Stopped. Nothing was published. ***
echo Fix the error above and run publish again; the steps before it are cached,
echo so a rerun is quick.
exit /b 1

:done
endlocal
