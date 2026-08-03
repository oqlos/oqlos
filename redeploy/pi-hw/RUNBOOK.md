# Legacy pi-hw directory

This directory no longer owns a deployment profile or migration. The only
BoardNet migration is `redeploy/122/migration.md`; its bare-metal instructions
are in `redeploy/122/RUNBOOK.md`.

Always invoke it from c2004 so the current network identity, SSH options and
source paths are rendered from `../update/env.d/21-boardnet-redeploy.env`:

```bash
../update/scripts/redeploy/deploy-fleet.sh --only 122
```

`push-hw-node-code.sh` remains only as a code-only maintenance shortcut and
reads the same c2004 profile. It is not a provisioning path.
