# workers/night-timer/

Starts the nightly on time. GitHub's scheduler began starting `nightly.yml`
five to seven hours after its 08:17 UTC cron line on 19 October 2026, which
put the night's publish in the afternoon and its General Court requests
outside `refusal.NIGHT_WINDOWS`. This Worker's own cron, at the same 08:17
UTC, asks GitHub to run `nightly.yml` on `main` with the scheduled night's
boxes (not a dry run, take the day's data, deploy the preview, no new term)
and `timer` ticked, so the run is named "nightly (scheduled, by the timer)".

GitHub's cron stays, as the fallback. A scheduled run's first job, `started`,
asks whether the timer has already started tonight's night and stands the
night down if it has. The Worker asks the same in reverse before it starts
one, so the two never both run a night. Healthchecks, pinged by the night
itself, still says so when no night starts at all.

`index.js` is the whole of it. It holds one secret and stores nothing.

## Deploying it (the person, once)

1. **Make the token.** On GitHub: Settings → Developer settings → Personal
   access tokens → Fine-grained tokens → Generate new token.
   - Name: `graniterecord-night-timer`.
   - Expiration: a year (and a calendar note to renew it; an expired token
     means the fallback runs late again, and Healthchecks will say so).
   - Resource owner: `granite-record`. Repository access: Only select
     repositories → `granite-record/granite-record`.
   - Permissions → Repository permissions → **Actions: Read and write**.
     Nothing else (Metadata: Read-only is added by GitHub itself).
   - Generate, and copy the token. It is shown once.
2. **Give it to the Worker**, in PowerShell from the repository folder:

   ```
   npx.cmd wrangler secret put GITHUB_TOKEN --config workers/night-timer/wrangler.toml
   ```

   and paste the token when asked. It is stored by Cloudflare, encrypted,
   and never in this repository.
3. **Deploy it** -- after the workflow change that reads `timer` is on
   `main`, so that the first run it starts is named and stood down for:

   ```
   npx.cmd wrangler deploy --config workers/night-timer/wrangler.toml
   ```

The next 08:17 UTC is its first night. In the Actions tab it reads "nightly
(scheduled, by the timer)", and GitHub's own scheduled run, whenever it comes,
stops after its first job with "the timer started tonight's night".

## Checked by

`node --test tests/night-timer.test.js`, which preflight runs: the boxes it
sends, that it starts nothing when tonight's night has already started, that
a refused token is not asked again, and the cron held to the workflow's.
