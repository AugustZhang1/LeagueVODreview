# Real data report

Games: 20

## Event types

### BUILDING_KILL (250)

Fields: assistingParticipantIds, bounty, buildingType, killerId, laneType, position, teamId, timestamp, towerType, type

Example: `{"bounty": 0, "buildingType": "TOWER_BUILDING", "killerId": 3, "laneType": "MID_LANE", "position": {"x": 8955, "y": 8510}, "teamId": 200, "timestamp": 583408, "towerType": "OUTER_TURRET", "type": "BUILDING_KILL"}`

### CHAMPION_KILL (986)

Fields: assistingParticipantIds, bounty, killStreakLength, killerId, position, shutdownBounty, timestamp, type, victimDamageDealt, victimDamageReceived, victimId, victimTeamfightDamageDealt, victimTeamfightDamageReceived

Example: `{"bounty": 400, "killStreakLength": 0, "killerId": 3, "position": {"x": 9169, "y": 8772}, "shutdownBounty": 0, "timestamp": 100766, "type": "CHAMPION_KILL", "victimDamageDealt": [{"basic": false, "magicDamage": 0, "name": "LeeSin", "participantId": 3, "physicalDamage": 0, "spellName": "summonerdot", "spellSlot": 4, "trueDamage": 36, "type": "OTHER"}, {"basic": true, "magicDamage": 0, "name": "LeeSin", "participantId": 3, "physicalDamage": 139, "spellName": "leesinbasicattack", "spellSlot": 64, "trueDamage": 0, "type": "OTHER"}], "victimDamageReceived": [{"basic": true, "magicDamage": 0, "name": "Tryndamere", "participantId": 3, "physicalDamage": 68, "spellName": "tryndamerebasicattack", "spellSlot": 64, "trueDamage": 0, "type": "OTHER"}, {"basic": false, "magicDamage": 0, "name": "Tryndamere", "participantId": 3, "physicalDamage": 0, "spellName": "", "spellSlot": 7, "trueDamage": 12, "type": "OTHER"}, {"basic": false, "magicDamage": 0, "name": "Tryndamere", "participantId": 3, "physicalDamage": 0, "spellName": "", "spellSlot": -1, "trueDamage": 23, "type": "OTHER"}, {"basic": false, "magicDamage": 0, "name": "Tryndamere", "participantId": 3, "physicalDamage": 74, "spellName": "tryndameree", "spellSlot": 2, "trueDamage": 0, "type": "OTHER"}, {"basic": false, "magicDamage": 0, "name": "Tryndamere", "participantId": 3, "physicalDamage": 0, "spellName": "summonerdot", "spellSlot": 4, "trueDamage": 54, "type": "OTHER"}, {"basic": true, "magicDamage": 0, "name": "Tryndamere", "participantId": 3, "physicalDamage": 133, "spellName": "tryndamerecritattack", "spellSlot": 73, "trueDamage": 0, "type": "OTHER"}, {"basic": true, "magicDamage": 0, "name": "SRU_OrderMinionRanged", "participantId": 0, "physicalDamage": 8, "spellName": "sru_orderminionrangedbasicattack2", "spellSlot": 65, "trueDamage": 0, "type": "MINION"}, {"basic": true, "magicDamage": 0, "name": "SRU_OrderMinionRanged", "participantId": 0, "physicalDamage": 8, "spellName": "sru_orderminionrangedbasicattack", "spellSlot": 64, "trueDamage": 0, "type": "MINION"}], "victimId": 8, "victimTeamfightDamageDealt": [{"basic": false, "magicDamage": 0, "name": "LeeSin", "participantId": 3, "physicalDamage": 0, "spellName": "summonerdot", "spellSlot": 4, "trueDamage": 36, "type": "OTHER"}, {"basic": true, "magicDamage": 0, "name": "LeeSin", "participantId": 3, "physicalDamage": 139, "spellName": "leesinbasicattack", "spellSlot": 64, "trueDamage": 0, "type": "OTHER"}], "victimTeamfightDamageReceived": [{"basic": true, "magicDamage": 0, "name": "Tryndamere", "participantId": 3, "physicalDamage": 68, "spellName": "tryndamerebasicattack", "spellSlot": 64, "trueDamage": 0, "type": "OTHER"}, {"basic": false, "magicDamage": 0, "name": "Tryndamere", "participantId": 3, "physicalDamage": 0, "spellName": "", "spellSlot": 7, "trueDamage": 12, "type": "OTHER"}, {"basic": false, "magicDamage": 0, "name": "Tryndamere", "participantId": 3, "physicalDamage": 0, "spellName": "", "spellSlot": -1, "trueDamage": 23, "type": "OTHER"}, {"basic": false, "magicDamage": 0, "name": "Tryndamere", "participantId": 3, "physicalDamage": 74, "spellName": "tryndameree", "spellSlot": 2, "trueDamage": 0, "type": "OTHER"}, {"basic": false, "magicDamage": 0, "name": "Tryndamere", "participantId": 3, "physicalDamage": 0, "spellName": "summonerdot", "spellSlot": 4, "trueDamage": 54, "type": "OTHER"}, {"basic": true, "magicDamage": 0, "name": "Tryndamere", "participantId": 3, "physicalDamage": 133, "spellName": "tryndamerecritattack", "spellSlot": 73, "trueDamage": 0, "type": "OTHER"}, {"basic": true, "magicDamage": 0, "name": "SRU_OrderMinionRanged", "participantId": 0, "physicalDamage": 8, "spellName": "sru_orderminionrangedbasicattack2", "spellSlot": 65, "trueDamage": 0, "type": "MINION"}, {"basic": true, "magicDamage": 0, "name": "SRU_OrderMinionRanged", "participantId": 0, "physicalDamage": 8, "spellName": "sru_orderminionrangedbasicattack", "spellSlot": 64, "trueDamage": 0, "type": "MINION"}]}`

### CHAMPION_SPECIAL_KILL (150)

Fields: killType, killerId, multiKillLength, position, timestamp, type

Example: `{"killType": "KILL_FIRST_BLOOD", "killerId": 3, "position": {"x": 8216, "y": 8309}, "timestamp": 100766, "type": "CHAMPION_SPECIAL_KILL"}`

### CHAMPION_TRANSFORM (1)

Fields: participantId, timestamp, transformType, type

Example: `{"participantId": 2, "timestamp": 797362, "transformType": "SLAYER", "type": "CHAMPION_TRANSFORM"}`

### DRAGON_SOUL_GIVEN (24)

Fields: name, teamId, timestamp, type

Example: `{"name": "Infernal", "teamId": 0, "timestamp": 1149255, "type": "DRAGON_SOUL_GIVEN"}`

### ELITE_MONSTER_KILL (167)

Fields: assistingParticipantIds, bounty, killerId, killerTeamId, monsterSubType, monsterType, position, timestamp, type

Example: `{"assistingParticipantIds": [5], "bounty": 0, "killerId": 2, "killerTeamId": 100, "monsterType": "HORDE", "position": {"x": 4618, "y": 9946}, "timestamp": 497047, "type": "ELITE_MONSTER_KILL"}`

### GAME_END (20)

Fields: gameId, realTimestamp, timestamp, type, winningTeam

Example: `{"gameId": 5652804827, "realTimestamp": 1790916797188, "timestamp": 686583, "type": "GAME_END", "winningTeam": 100}`

### ITEM_DESTROYED (4280)

Fields: itemId, participantId, timestamp, type

Example: `{"itemId": 2003, "participantId": 3, "timestamp": 52225, "type": "ITEM_DESTROYED"}`

### ITEM_PURCHASED (4405)

Fields: itemId, participantId, timestamp, type

Example: `{"itemId": 3865, "participantId": 0, "timestamp": 0, "type": "ITEM_PURCHASED"}`

### ITEM_SOLD (166)

Fields: itemId, participantId, timestamp, type

Example: `{"itemId": 2003, "participantId": 4, "timestamp": 589655, "type": "ITEM_SOLD"}`

### ITEM_UNDO (159)

Fields: afterId, beforeId, goldGain, participantId, timestamp, type

Example: `{"afterId": 0, "beforeId": 2031, "goldGain": 150, "participantId": 6, "timestamp": 241742, "type": "ITEM_UNDO"}`

### LEVEL_UP (2623)

Fields: level, participantId, timestamp, type

Example: `{"level": 2, "participantId": 2, "timestamp": 70494, "type": "LEVEL_UP"}`

### OBJECTIVE_BOUNTY_FINISH (9)

Fields: teamId, timestamp, type

Example: `{"teamId": 100, "timestamp": 1110421, "type": "OBJECTIVE_BOUNTY_FINISH"}`

### OBJECTIVE_BOUNTY_PRESTART (23)

Fields: actualStartTime, teamId, timestamp, type

Example: `{"actualStartTime": 950000, "teamId": 100, "timestamp": 935335, "type": "OBJECTIVE_BOUNTY_PRESTART"}`

### PAUSE_END (20)

Fields: realTimestamp, timestamp, type

Example: `{"realTimestamp": 1790916110569, "timestamp": 0, "type": "PAUSE_END"}`

### SKILL_LEVEL_UP (2856)

Fields: levelUpType, participantId, skillSlot, timestamp, type

Example: `{"levelUpType": "NORMAL", "participantId": 0, "skillSlot": 4, "timestamp": 0, "type": "SKILL_LEVEL_UP"}`

### TURRET_PLATE_DESTROYED (1033)

Fields: killerId, laneType, position, teamId, timestamp, type

Example: `{"killerId": 3, "laneType": "MID_LANE", "position": {"x": 8955, "y": 8510}, "teamId": 200, "timestamp": 287110, "type": "TURRET_PLATE_DESTROYED"}`

### WARD_KILL (854)

Fields: killerId, timestamp, type, wardType

Example: `{"killerId": 4, "timestamp": 44008, "type": "WARD_KILL", "wardType": "YELLOW_TRINKET"}`

### WARD_PLACED (4795)

Fields: creatorId, timestamp, type, wardType

Example: `{"creatorId": 10, "timestamp": 31516, "type": "WARD_PLACED", "wardType": "YELLOW_TRINKET"}`

## Monsters

monsterType: BARON_NASHOR, DRAGON, HORDE, RIFTHERALD

monsterSubType: AIR_DRAGON, CHEMTECH_DRAGON, EARTH_DRAGON, FIRE_DRAGON, HEXTECH_DRAGON, WATER_DRAGON

## BUILDING_KILL teamId

- 5652804827 9:43: `TOWER_BUILDING` teamId=200, killerId=3 (killer team 100)
- 5652762926 12:21: `TOWER_BUILDING` teamId=200, killerId=3 (killer team 100)
- 5652762926 13:17: `TOWER_BUILDING` teamId=100, killerId=6 (killer team 200)

teamId differs from the killer's team in 236 of 250 events (all of them means teamId is the team that lost the building).

## Presence

- DRAGON_SOUL_GIVEN: yes
- GAME_END: yes
- Rift Herald: yes
- Atakhan: no
- Unknown event types: CHAMPION_TRANSFORM, OBJECTIVE_BOUNTY_PRESTART

## gameVersion

16.19.821.7343, 16.19.823.722

## Position bounds

x: 130 to 14621, y: 135 to 14679

## Earliest objective kill

- BARON_NASHOR: 20:20 (1220 s)
- DRAGON/AIR_DRAGON: 5:58 (358 s)
- DRAGON/CHEMTECH_DRAGON: 5:22 (322 s)
- DRAGON/EARTH_DRAGON: 7:57 (477 s)
- DRAGON/FIRE_DRAGON: 13:21 (801 s)
- DRAGON/HEXTECH_DRAGON: 5:52 (352 s)
- DRAGON/WATER_DRAGON: 5:57 (357 s)
- HORDE: 8:10 (490 s)
- RIFTHERALD: 15:21 (921 s)

## Baron / Elder buff hints

None.
