# Profile charts

The profile displays Artificial Analysis' native **Intelligence Index vs. Cost per
Task** and **Capability Index Comparison** image exports. The first retains its
logarithmic USD task-cost axis and Pareto line. The second compares ranks among
the selected models across all six capability indexes. Both retain the source's
default model selection, reasoning settings, and attribution. We do not
recalculate scores or substitute token pricing for task cost.

Source: <https://artificialanalysis.ai/#intelligence-index-vs-cost-per-task-chart>.
Capability source: <https://artificialanalysis.ai/#capability-index-comparison-chart>.
Chart sharing guidance: <https://artificialanalysis.ai/brand-kit>.

## Daily refresh

The `Refresh AI charts` GitHub Actions workflow runs daily at 22:17 UTC
(06:17 Singapore time). GitHub may delay scheduled jobs. You can also run it from
the repository's Actions tab using **Run workflow** on `main`.

It uses `agent-browser` 0.26.0 to click each chart's **Download chart as image**
button in a fresh browser session. It checks for plotted models, the dotted
Pareto path, logarithmic task-cost labels, all six capability columns, loaded
fonts, and complete PNGs of the expected size. The browser session closes on
success or failure. A failed capture leaves both published images and their date
unchanged; failures appear in Actions. The date below the charts lets visitors
judge freshness.

The workflow allows up to three attempts, each with a fresh session, for transient
source-page loading failures. Exhausted attempts fail the job without publishing.
Timeout logs include font, plotted-model, Pareto-path, and axis readiness details.

`assets/captured.json` records the actual capture time, the Intelligence Index
version read from the source page, and both image checksums. Publication validates
the entire bundle before updating anything. Retrying publication of an old
artifact retains its actual capture date instead of falsely reporting a new one.
Publication also skips bundles older than the currently published capture, so an
old job retry cannot roll the profile back after a newer refresh succeeds.

The capture job has read-only repository permissions and no stored checkout
credentials. A separate publishing job downloads only the generated chart bundle,
validates it again, and commits those images, metadata, and the README's capture
date. The index version remains in `assets/captured.json`. It
checks out the latest `main` and uses a normal push, so concurrent changes cannot
be overwritten. Pull request runs verify and capture a preview artifact; they
never publish.

Dois explicitly authorized daily generated chart and capture-metadata updates
without a PR for this task. This exception applies only to those generated
updates. Changes to the script, workflow, profile copy, or other files still go
through reviewed PRs. No API key or extra service is required.

GitHub can disable scheduled workflows in public repositories after 60 days of
inactivity. Check Actions if the displayed capture date falls behind; re-enable
the workflow if needed.

## Local work

Use a dedicated git worktree. Install Python 3.12+, `uv`, `actionlint` 1.7.12, Node
24, and `agent-browser` 0.26.0. Load the browser guide before using it:

```sh
agent-browser skills get core --full
agent-browser install
make check
make refresh
```

`make check` runs Ruff lint and formatting, mypy in strict mode, unit tests, and
workflow validation. `make refresh` performs the real browser capture. Inspect
both PNGs in `assets/` before opening a PR. If the site changes its
chart markup, labels, export dimensions, or default display settings, fix and
review the capture checks instead of publishing an unverified replacement.
