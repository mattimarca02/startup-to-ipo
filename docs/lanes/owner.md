# Owner requests

Only the owner (or Claude on his behalf) edits this file. Each lane reads it at the start of every run, like the other lane files, and adds the requests addressed to it to its backlog. When a request is done, the lane says so in its own lane file (this file is not edited by lanes).

## Requests to lanes

### building: a cinematic when the company moves to a bigger building (2026-10-17)

When a garage's building changes to the next funding stage (Garage to Small Office, and so on up to Big Corporate), the owner of that garage sees a short cinematic: a crane arrives, its wrecking ball knocks down the old building, then the new building rises out of the ground and settles into place. Put it in your backlog as a high-priority item, right after the item you are doing now.

Rules for it:
- **Client only, looks only** (CLAUDE.md "Client-only visuals"): the server swaps the building exactly as today; the cinematic only animates what the client shows. Nothing is saved, nothing goes through a remote except what already tells the client the stage changed, nothing waits on the client.
- **Short and skippable**: about 5 to 7 seconds, a tap or click skips it, it never plays while a window is open (PlayerGui "OpenPanel") and plays at most once per stage change. Camera control returns to normal at the end, also if the player resets or leaves during it.
- **Never traps anyone**: solid boxes stay the server's; players inside are handled by the existing unstick rule. Other players near the garage see only a simple rise of the new building, not the camera move.
- **Phone first**: smooth on a phone, no lights, a small part budget for the crane (Parts, anchored, no collision), removed at the end.
- **Not after an IPO**: an IPO resets the building to the Garage; that reset does not play the demolition cinematic (a short "fresh start" rise at most).
- Preview it in Blender (frames of the key moments) and put the frames in docs/previews/building/ in the PR. If the crane would look better as a kit model, write it as a request in your lane file; do not add assets yourself.
