# ClipForge cloud growth research

A small daily research job for YouTube Shorts and TikTok editorial guidance. The job runs on
GitHub's hosted runner at approximately 06:17 UTC and can also be started manually. Host this
standalone helper in a **public repository** to use free standard GitHub-hosted runners. Publish
only this generic helper and its public-source research reports; no ClipForge project files,
private analytics, credentials, or other private data belong in the repository. GitHub may
delay scheduled jobs. It makes no posting calls, uses no AI/API keys, and never fetches media.
The Mac only needs to read the resulting small strategy file through ClipForge's integration.

The research reads four official guidance pages, two recent-news RSS searches scoped to official
platform publishers, and an optional public YouTube channel feed. News and channel feeds supply
text metadata only. It does not scrape competing videos, invent analytics, or infer success from
the channel's tiny sample. TikTok's creative guidance is for ads: corresponding advice is explicitly
marked as a hypothesis for organic clips, not proof it will increase views.

The output is `reports/strategy.json` plus a human-readable `reports/REPORT.md` with citations,
availability, and limitations. Only a fixed local catalogue of editorial tactic IDs can be emitted.
Remote page text is never copied into a model prompt. Guidance expires after seven days. No
successful report is written unless at least one official guidance page succeeds for each
platform; the workflow fails and the previous report remains in place. Partial/optional source
failures are visible in the report. Relevant titles from verified official news publishers may
select additional fixed editorial hypotheses, but no retrieved text becomes model instructions.

No credentials from ClipForge belong here. The workflow uses only GitHub's built-in repository
token to commit the two reports. It cannot change ClipForge's posting schedule, TikTok consent,
license rules, content safety checks, or publishing limits. No paid APIs or paid AI are enabled.
Free standard hosted runners for public repositories are subject to GitHub's current terms;
no larger runners or paid overages are enabled. This is not a lifetime-free guarantee.

## Local verification

```sh
python3 -m unittest -v test_research
```

The tests mock all fetches. To run live text research intentionally:

```sh
python3 research.py
```

Only generated reports should be consumed by the running ClipForge service. This directory is
a standalone helper, not another ClipForge instance, and contains no video renderer, database,
service launcher, or credentials.
