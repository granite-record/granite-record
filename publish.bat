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
REM The Pages project's production branch, as the dashboard has it. Named
REM rather than left to wrangler, which takes the branch from git: on
REM 6 September the production branch was main while this repo was on master,
REM and every deploy went to a preview while wrangler printed "Deployment
REM complete". Every production deployment since has come from master
REM (wrangler pages deployment list, 12 September). Named here, a deploy lands
REM on production whichever branch the working tree happens to be on.
set PRODUCTION_BRANCH=master

REM THE BRANCH THIS FOLDER MUST BE ON, which since 17 September is NOT the same
REM name as the one above. The repository was renamed master -> main for the
REM open-source release; the Pages project's production branch was not, and
REM still answers to master -- every Production deployment in
REM `wrangler pages deployment list` comes from it, including today's.
REM
REM So the two names below mean two different things and must not be merged
REM again. PRODUCTION_BRANCH is what --branch sends Cloudflare, and renaming it
REM to main would publish to a PREVIEW while wrangler printed "Deployment
REM complete" -- the exact failure of 6 September, in mirror image. REPO_BRANCH
REM is only the guard that stops a deploy from an experiment or a triage
REM branch. Until the rename the two happened to coincide, which is why one
REM variable did both jobs.
set REPO_BRANCH=main

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
REM CALL, because npx is npx.cmd: a batch file that runs another batch file
REM without CALL hands over to it and never comes back. Until 11 September
REM every publish ended at wrangler's "Deployment complete!" with npx's exit
REM code, and the check_live gate below never ran once.
REM FOUR ATTEMPTS, because the failure this hits is a timeout and not a
REM refusal. wrangler packs assets into buckets of up to 40 MB and posts
REM each as one body; the fat files here -- index.json at 21.5 MB and
REM fifteen vote exports of 9 to 20 MB -- make bodies that take longer to
REM send than undici waits for a response header, and five such failures
REM anywhere abort the whole deploy. Pages assets are content-addressed,
REM so every attempt begins with what the last one managed: on
REM 12 September a run reported 34,887 files uploaded and 20,465 already
REM there, which was the previous attempt's work being skipped.
REM
REM THE BRANCH THIS FOLDER IS ON, before anything is uploaded. --branch below
REM sends the deploy to production whatever git says, so a branch checked out
REM here -- a report-triage branch, an experiment -- would be published as the
REM site. The deploy happens only from REPO_BRANCH.
set BRANCH=
for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set BRANCH=%%b
if not "%BRANCH%"=="%REPO_BRANCH%" goto :wrongbranch
set ATTEMPT=0

:upload
set /a ATTEMPT+=1
call npx wrangler pages deploy site --project-name=%PROJECT% --branch=%PRODUCTION_BRANCH% --commit-dirty=true
if not errorlevel 1 goto :uploaded
if %ATTEMPT% GEQ 4 goto :failed
echo.
echo *** Upload attempt %ATTEMPT% of 4 failed. Trying again -- the files
echo *** that did upload are kept, so this starts where that one stopped.
goto :upload

:uploaded

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

:wrongbranch
echo.
echo *** Not published: this folder is on branch "%BRANCH%", not %REPO_BRANCH%. ***
echo A deploy publishes whatever this folder holds. Switch back with
echo   git checkout %REPO_BRANCH%
echo and work on other branches in a separate worktree.
exit /b 1

:failed
echo.
echo *** Stopped. Nothing was published. ***
echo Fix the error above and run publish again; the steps before it are cached,
echo so a rerun is quick.
exit /b 1

:done
endlocal
