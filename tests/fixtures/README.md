# Test fixtures

`synthetic/` holds four **synthetic** games: made up, but shaped like Riot's documented match-v5
`/matches/{id}` and `/matches/{id}/timeline` responses. They exist so code and tests can run before
any Riot key does. Nothing in them is real game data; item recipes, bounties and positions are
approximations.

| Match | What it is |
|---|---|
| `NA1_9000000001` | ~31 min blue win; first blood, grubs, herald, 4 dragons + soul, baron, towers, plates, inhibitor. "Me#NA1" is participant 4, MIDDLE, Ahri |
| `NA1_9000000002` | red wins by surrender at 24:30; "Me#NA1" is participant 9, BOTTOM, Jinx |
| `NA1_9000000003` | ~38 min blue win; Elder dragon, Atakhan, inhibitors respawning; Wukong (`MonkeyKing`) and Fiddlesticks (`FiddleSticks`) |
| `NA1_9000000004` | remake at 3:10 |

## Regenerate

```
.venv/bin/python tests/fixtures/make_synthetic.py
```

The generator is deterministic (fixed seeds, standard library only) and runs the rules in
`consistency.py` on every game before writing, so the committed JSON always passes them. A test
regenerates the games in memory and compares them to the committed files.

## Real fixtures

Step 3 of `Plan.md` adds real games under `tests/fixtures/real/`. Any field the synthetic games got
wrong is fixed in the generator and the code, and tests then run on both sets.
