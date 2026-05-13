# Meta-Agent Directory

- `proposals/` — pending prompt improvement proposals (review before applying)
- `routing/`   — pending model routing change proposals
- `applied-proposals.log` — history of auto-applied changes

## Reviewing proposals

Each proposal in `proposals/` contains:
- The problem observed (with evidence)
- Current prompt text vs proposed replacement
- Confidence score

To apply a proposal manually:
  Read the proposal, verify the reasoning, then apply the edit to the agent .md file.
  Log it: `echo "Manually applied: <file>" >> applied-proposals.log`

## Reverting a change

All agent .md files are git-tracked. To revert:
  `git log .opencode/agent/<agent>.md` — find the commit before the change
  `git checkout <commit> -- .opencode/agent/<agent>.md`
