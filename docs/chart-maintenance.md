# Profile chart

The profile displays Artificial Analysis' native **Intelligence Index vs. Cost per
Task** image export. The chart retains its model selection, reasoning settings,
logarithmic USD task-cost axis, Pareto line, and source attribution. We do not
recalculate scores or substitute token pricing for task cost.

Source: <https://artificialanalysis.ai/#intelligence-index-vs-cost-per-task-chart>.
Chart sharing guidance: <https://artificialanalysis.ai/brand-kit>.

## Daily refresh

The `Refresh intelligence chart` GitHub Actions workflow runs daily at 22:17 UTC
(06:17 Singapore time). GitHub may delay scheduled jobs. You can also run it from
the repository's Actions tab using **Run workflow** on `main`.

It uses `agent-browser` 0.26.0 to click the source chart's **Download chart as
image** button in a fresh browser session. It checks for plotted models, the
dotted Pareto path, logarithmic task-cost labels, loaded fonts, and a complete PNG
of the expected size. The browser session closes on success or failure. A failed
capture leaves the last published image and its date unchanged; failures appear
in Actions. The date under the chart lets visitors judge freshness.

The capture job has read-only repository permissions and no stored checkout
credentials. A separate publishing job downloads only the generated image,
validates it again, and commits that image and the README's capture date. It
checks out the latest `main` and uses a normal push, so concurrent changes cannot
be overwritten. Pull request runs verify and capture a preview artifact; they
never publish.

Dois explicitly authorized daily generated chart and capture-date updates
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
`assets/intelligence-vs-cost.png` before opening a PR. If the site changes its
chart markup, labels, export dimensions, or default display settings, fix and
review the capture checks instead of publishing an unverified replacement.
