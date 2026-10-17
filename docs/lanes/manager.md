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
2026-10-17 22:44 notified owner: interiors and quality starts denied again; #41 and #16 still waiting for him; building has no Mac approval.
