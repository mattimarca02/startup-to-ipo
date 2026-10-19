# Startup to IPO: home

La pagina di partenza di Mattia (vault Obsidian = il repo). Si aggiorna da sola con il plugin Git (auto pull ogni 10 minuti).
Regola: da qui modifichi solo [[docs/lanes/owner|owner.md]] e le tue note, mai i file `.lua`.

## Ogni giorno, in 2 minuti
1. **PR da mergiare:** [lista su GitHub](https://github.com/mattimarca02/startup-to-ipo/pulls). Mergia solo quelle con verdetto **MERGE** in [[docs/lanes/quality|quality.md]] (sezione "Verdicts").
2. **Cosa fanno le lane:** apri il file della lane e leggi "Doing now" e "Last report".
3. **Cosa vuole il manager da te:** le ultime righe di [[docs/lanes/manager|manager.md]].
4. **Studio:** se c'è un batch nuovo in [[docs/STUDIO_SYNC_BATCH|STUDIO_SYNC_BATCH]], lo fai girare (con la sessione di VS Code) e poi File > Save to Roblox. Mai Publish senza deciderlo.

## Le lane
| Lane | Cosa fa | File |
|---|---|---|
| interiors | arredamento delle stanze per stadio | [[docs/lanes/interiors|interiors]] |
| building | esterno dei cinque edifici | [[docs/lanes/building|building]] |
| world | piazza, alberi, percorsi, VIP Lounge | [[docs/lanes/world|world]] |
| gameplay | economia, compiti, progressione | [[docs/lanes/gameplay|gameplay]] |
| ux | schermate, HUD, telefono | [[docs/lanes/ux|ux]] |
| quality | revisioni, batch di Studio, documenti | [[docs/lanes/quality|quality]] |

Chi possiede quale file: [[docs/lanes/claims|claims]]. Come funzionano le lane: [[docs/LANES|LANES]].

## Chiedere qualcosa alle lane
Scrivi in fondo a [[docs/lanes/owner|owner.md]] una sezione così, poi Cmd+P > "Git: Commit and push":

```
### <lane>: <cosa vuoi> (<data>)
Cosa vuoi, perché, ed eventuali decisioni già prese.
```

La lane la legge al suo prossimo giro (il manager gira ogni 3 ore).

## Idee (scrivi qui, poi le trasformiamo in richieste)
- 

## Dove sono le cose
- Il piano e lo stato: [[ROADMAP]], [[docs/OVERHAUL_REPORT|OVERHAUL_REPORT]], [[docs/OVERHAUL_PLAN|OVERHAUL_PLAN]]
- Le regole del codice: [[CLAUDE]], [[CONTRIBUTING]], [[README]]
- Pubblicare senza rompere i salvataggi: [[docs/PUBLISH_RULES|PUBLISH_RULES]]
- Economia e gameplay: [[docs/ECONOMY|ECONOMY]], [[docs/GAMEPLAY_FIRST_HOUR_PROPOSAL|GAMEPLAY_FIRST_HOUR_PROPOSAL]], [[docs/LONG_GAME_PROPOSAL|LONG_GAME_PROPOSAL]]
- Grafica: [[docs/PLOT_VISUALS|PLOT_VISUALS]], [[docs/KIT_MODELS|KIT_MODELS]], le anteprime in `docs/previews/`
- Pagina dello store: [[docs/STORE_PAGE|STORE_PAGE]]
