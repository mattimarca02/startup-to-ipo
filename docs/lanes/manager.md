# Lanes manager log

Only the lanes manager (a scheduled Claude run) edits this file. One line per action: "<UTC time> <lane> started: <reason>" or "<UTC time> notified owner: <what>". Runs that start nothing leave one "no action" line.

2026-10-17 17:42 no action: PRs #35 (ux), #36 (building), #37 (world), #38 (gameplay), #40 (interiors) open with no verdict; quality started reviewing them at 16:45 (under 3 h), so no lane started and no owner notice.
2026-10-17 21:50 building started: PR #36 verdict MERGE at head 57085b7 but 11 behind main, asked to rebase.
2026-10-17 21:50 gameplay started: PR #38 verdict MERGE at head 094476a but 18 behind main, asked to rebase.
2026-10-17 21:50 interiors start FAILED (permission denied by the run classifier): PR #40 verdict MERGE at 1696f9c, 14 behind main, needs a rebase/merge of main.
2026-10-17 21:50 quality start FAILED (permission denied by the run classifier): #35 (head 0d6be20) and #37 (head ef1a50d) changed head and have no verdict.
2026-10-17 21:51 notified owner: interiors and quality starts failed (permission), #41 and #16 still waiting for him.
2026-10-17 22:43 interiors start FAILED (permission denied by the run classifier, second time): PR #40 verdict MERGE at 1696f9c, 28 behind main, needs a rebase.
2026-10-17 22:43 building started: PR #36 merged, continue with the backlog (the cinematic). Ran cloud-only: no signed approval for the owner's Mac, so no Blender previews.
2026-10-17 22:43 ux started: PR #35 merged, continue with the backlog.
2026-10-17 22:43 quality start FAILED (permission denied by the run classifier, second time): #37 (head ef1a50d), #42 and #43 have no verdict.
2026-10-17 22:44 notified owner: interiors and quality starts denied again; #41 merged at 22:4x (STUDIO_SYNC_BATCH.md now on main); #16 still to close; building has no Mac approval.
2026-10-17 23:44 interiors start FAILED (permission denied by the run classifier, third time): PR #40 verdict MERGE at 1696f9c, 42 behind main, needs a rebase.
2026-10-17 23:44 building not started: started by the manager at 22:43 (under 3 h), no branch pushed yet, treated as still running.
2026-10-17 23:44 world started: PR #37 merged, no open PR, continue with the backlog (cloud only, no Mac approval).
2026-10-17 23:44 gameplay not started: PR #43 head d702c93 has no verdict (the last was for b01d07c), sent to quality.
2026-10-17 23:44 ux not started: PR #44 (head d960956) has no verdict, sent to quality; ux started 22:43 (under 3 h).
2026-10-17 23:44 quality started: review #43 (new head d702c93) and #44 (no verdict).
2026-10-17 23:45 notified owner: interiors denied a third time (#40 needs a merge of main, he can do it himself); #45 (Batch 1) waits for his merge; world and quality ran cloud-only.
2026-10-18 00:45 interiors start FAILED (permission denied by the run classifier, fourth time): PR #40 verdict MERGE at 1696f9c, 45 behind main with a CONTRIBUTING.md conflict.
2026-10-18 00:45 building not started: started by the manager at 22:43 (under 3 h).
2026-10-18 00:45 world not started: started by the manager at 23:44 (under 3 h).
2026-10-18 00:45 gameplay not started: PR #43 MERGE at d702c93; 5 behind main but only lane-file commits (docs/lanes/*.md) and the merge is clean, so no rebase (it would only reset the verdict); sent to the owner.
2026-10-18 00:45 ux not started: PR #44 MERGE at d960956; 5 behind main, only lane-file commits, clean merge; sent to the owner.
2026-10-18 00:45 quality not started: no open lane PR without a verdict for its head (#45 is quality's own, waiting for the owner).
2026-10-18 00:46 notified owner: #43 and #44 ready to merge; #45 (Batch 1) waits for him; interiors denied a fourth time, he can merge main into #40 himself.
2026-10-18 01:45 interiors start FAILED (permission denied by the run classifier, fifth time): PR #40 verdict MERGE at 1696f9c, 47 behind main, CONTRIBUTING.md conflict (dirty).
2026-10-18 01:45 building not started: started by the manager at 22:43 (under 3 h), no branch on GitHub yet.
2026-10-18 01:45 world not started: started by the manager at 23:44 (under 3 h).
2026-10-18 01:45 gameplay not started: PR #43 MERGE at d702c93; 7 behind main, only lane files and claim rows, clean merge; sent to the owner.
2026-10-18 01:45 ux not started: PR #44 MERGE at d960956; 7 behind main, only lane files and claim rows, clean merge; sent to the owner.
2026-10-18 01:45 quality not started: no open lane PR without a verdict for its head (#45 is quality's own, waiting for the owner).
2026-10-18 01:46 notified owner: #43, #44, #45 ready to merge; interiors denied a fifth time, he can merge main into #40 himself.
2026-10-18 02:42 interiors start FAILED (permission denied by the run classifier, sixth time): PR #40 verdict MERGE at 1696f9c, 48 behind main, CONTRIBUTING.md conflict.
2026-10-18 02:42 building started: manager start of 22:43 left no branch or PR (lane file still idle after ~4 h), so the run stopped; restarted with the "previous run stopped" text. Cloud only (no Mac approval).
2026-10-18 02:42 world not started: started by the manager at 23:44 (under 3 h).
2026-10-18 02:42 gameplay not started: PR #43 MERGE at d702c93; 8 behind main, only lane files and claim rows, clean merge; sent to the owner.
2026-10-18 02:42 ux not started: PR #44 MERGE at d960956; 8 behind main, only lane files and claim rows, clean merge; sent to the owner.
2026-10-18 02:42 quality not started: no open lane PR without a verdict for its head (#45 is quality's own, waiting for the owner).
2026-10-18 02:43 notified owner: #43, #44, #45 ready to merge; interiors denied a sixth time, he can merge main into #40 himself.
