# Technical social drafts

The initial introduction is in `posts/social/intro-linkedin.txt`. An existing workflow, `social-drafts.yml`, supports manual previews and Buffer drafts.

A second workflow creates a LinkedIn draft after a pull request is merged into `main`, only when the PR has the label `social-ready`. No post is sent to LinkedIn automatically.

## How to opt in

Add these four headings to the PR description, with short factual text under each:

```
### Social Problem
During a failed rollout, I needed to understand if the service stayed available.

### Social Change
I added HTTP sampling during a controlled Flux recovery.

### Social Evidence
The saved run captured 1,194 HTTP 200 responses and six timeouts.

### Social Limits
The cause of the six timeouts is unknown. Successful version updates are not yet tested under continuous traffic.
```

Include direct links to evidence in the normal PR description, then apply the `social-ready` label. Only label substantive technical updates. Do not label styling, refactors without measured impact, or corrections to other social posts.

After merging, check GitHub Actions > Technical social drafts and then review the new item under Buffer > LinkedIn > Drafts. Edit tone, factual claims and citations before scheduling it.

## Design and limits

- Uses only the GitHub event, Python standard library and the existing Buffer API integration. No paid text-generation API.
- The writer uses a factual template. It does not infer outcomes or evaluate change quality by itself. The reviewer decides whether a PR is worth sharing.
- Requires all four sections, including explicit limits, so it cannot imply unmeasured success.
- Creates drafts only. Nothing is automatically published or scheduled.
- A rerun or duplicate event might create another draft. Check Buffer before manually rerunning.
- GitHub Actions is the only trigger. It does not check real-time cluster health.
- To disable automation, remove `social-ready` from future PRs or disable the workflow.
