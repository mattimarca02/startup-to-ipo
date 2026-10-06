-- SectorConfig: the sectors a company can be founded in (customize PR 1, docs/CUSTOMIZE_PROPOSAL.md sections 1.3 and 2).
-- Put this ModuleScript in ReplicatedStorage (CompanyConfig, CompanyServer and, later, the picker read it).
--
-- A company is one run of one sector's ladder. Four sector keys exist from day one, so the saved
-- Pokedex (the `pokedex` save section) never needs a new field when a sector is added: Software
-- (today's game) is the only one that can be picked now; Gaming, Fintech and Biotech are listed
-- but not enabled. Never rename or reuse a sector key: saves refer to it.
-- PickerEnabled = false until both launch sectors (Software and Gaming) exist: nobody sees a picker,
-- and every company is a Software company.
-- No text here may claim odds or chance (D9).

local SectorConfig = {}

SectorConfig.PickerEnabled = false

-- The four keys, in display order. Never renamed, never reused.
SectorConfig.Order = { "Software", "Gaming", "Fintech", "Biotech" }

SectorConfig.Default = "Software" -- a new founding, while the picker is off

-- enabled: the sector can be picked (CompanyAction "PickSector", a later PR checks it). A sector that
-- is listed but not enabled is kept in saves and counts for no goal and no board.
-- names: the fixed list a company's name comes from (no free text; the first one is the default).
-- The company names are placeholders (the content bible has no list yet): rename them freely until they ship.
SectorConfig.Sectors = {
	Software = {
		name = "Software",
		icon = "💻",
		enabled = true,
		summary = "Steady income from your upgrades and your team.",
		names = {
			"Garage Labs", "Paperclip Software", "Pixel Pioneers", "Brightbyte", "Bytebridge", "Cloudnine Apps",
			"Tidy Tech", "Open Door Systems", "Lemonade Code", "Sunrise Soft", "Nimble Networks", "Pocket Rocket",
		},
	},
	Gaming = { name = "Gaming", icon = "🎮", enabled = false, summary = "Build, polish and launch your own games.", names = {} },
	Fintech = { name = "Fintech", icon = "💳", enabled = false, summary = "Coming soon.", names = {} },
	Biotech = { name = "Biotech", icon = "🧬", enabled = false, summary = "Coming soon.", names = {} },
}

-- Goals of the Hall of Fame (saved in pokedex.hall as goalKey -> os.time()). A goal is reached when every
-- sector in its list is enabled and done. A shipped list never changes: a later sector gets a new goal key.
SectorConfig.Goals = {
	Launch = { sectors = { "Software", "Gaming" } },
}

function SectorConfig.get(key)
	return typeof(key) == "string" and SectorConfig.Sectors[key] or nil
end

-- Known = one of the four keys (enabled or not)
function SectorConfig.isKnown(key)
	return SectorConfig.get(key) ~= nil
end

-- The sector can be picked
function SectorConfig.isEnabled(key)
	local sector = SectorConfig.get(key)
	return sector ~= nil and sector.enabled == true
end

-- A company's default name in that sector: the first of its fixed list
function SectorConfig.defaultName(key)
	local sector = SectorConfig.get(key)
	return sector and sector.names[1] or nil
end

function SectorConfig.getGoal(key)
	return typeof(key) == "string" and SectorConfig.Goals[key] or nil
end

return SectorConfig
