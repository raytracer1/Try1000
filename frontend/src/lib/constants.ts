// Formation presets and role definitions.

export const FORMATIONS = ["4-3-3", "4-4-2", "3-5-2", "4-2-3-1", "3-4-3", "4-1-4-1"];

export const ROLES = ["GK", "CB", "LB", "RB", "CDM", "CM", "CAM", "LM", "RM", "LW", "RW", "ST"];

export const PASSING_STYLES = ["short", "mixed", "direct"];
export const BUILD_UP_STYLES = ["slow", "balanced", "fast"];

export const DEFAULT_TACTIC = {
  formation: "4-3-3",
  pressing_level: 5,
  defensive_line: 5,
  attacking_width: 5,
  tempo: 5,
  passing_style: "mixed",
  build_up_style: "balanced",
};

export const TACTIC_PRESETS = {
  "Gegenpress": { pressing_level: 9, defensive_line: 8, attacking_width: 7, tempo: 8, passing_style: "mixed", build_up_style: "fast" },
  "Tiki-Taka": { pressing_level: 7, defensive_line: 7, attacking_width: 9, tempo: 7, passing_style: "short", build_up_style: "slow" },
  "Park the Bus": { pressing_level: 2, defensive_line: 2, attacking_width: 4, tempo: 3, passing_style: "direct", build_up_style: "slow" },
  "Counter Attack": { pressing_level: 4, defensive_line: 4, attacking_width: 6, tempo: 9, passing_style: "direct", build_up_style: "fast" },
};
