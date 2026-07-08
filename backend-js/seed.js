const { Pool } = require("pg");
const { config } = require("./src/config");

const PLAYER_TEMPLATES = {
  GK:  { pace: 50, shooting: 20, passing: 60, dribbling: 30, defending: 80, physicality: 70, stamina: 95, awareness: 80, composure: 75 },
  CB:  { pace: 70, shooting: 30, passing: 65, dribbling: 40, defending: 82, physicality: 78, stamina: 85, awareness: 75, composure: 70 },
  LB:  { pace: 80, shooting: 40, passing: 70, dribbling: 55, defending: 75, physicality: 65, stamina: 85, awareness: 70, composure: 70 },
  RB:  { pace: 80, shooting: 40, passing: 70, dribbling: 55, defending: 75, physicality: 65, stamina: 85, awareness: 70, composure: 70 },
  CDM: { pace: 65, shooting: 55, passing: 78, dribbling: 60, defending: 78, physicality: 75, stamina: 85, awareness: 78, composure: 75 },
  CM:  { pace: 70, shooting: 65, passing: 82, dribbling: 70, defending: 60, physicality: 65, stamina: 82, awareness: 78, composure: 78 },
  CAM: { pace: 75, shooting: 75, passing: 85, dribbling: 82, defending: 35, physicality: 55, stamina: 78, awareness: 82, composure: 82 },
  LW:  { pace: 90, shooting: 72, passing: 72, dribbling: 88, defending: 30, physicality: 52, stamina: 78, awareness: 72, composure: 70 },
  RW:  { pace: 90, shooting: 72, passing: 72, dribbling: 88, defending: 30, physicality: 52, stamina: 78, awareness: 72, composure: 70 },
  ST:  { pace: 82, shooting: 85, passing: 65, dribbling: 78, defending: 25, physicality: 68, stamina: 80, awareness: 75, composure: 82 },
};

const FORMATION = ["GK", "CB", "CB", "LB", "RB", "CDM", "CM", "CM", "LW", "RW", "ST"];
const NAMES = { GK: "Keeper", CB: "Defender", LB: "Fullback", RB: "Fullback", CDM: "Midfielder", CM: "Midfielder", CAM: "Playmaker", LW: "Winger", RW: "Winger", ST: "Striker" };

async function seed() {
  const pool = new Pool({ connectionString: config.databaseUrl });
  const client = await pool.connect();
  try {
    const { rows: [existing] } = await client.query("SELECT id FROM users WHERE email = $1", ["demo@try1000.io"]);
    if (existing) { console.log("Already seeded"); return; }

    const { rows: [user] } = await client.query("INSERT INTO users (email, username) VALUES ($1, $2) RETURNING id", ["demo@try1000.io", "demo"]);

    const teams = [];
    for (const name of ["FC Barcelona", "Manchester City"]) {
      const { rows: [t] } = await client.query("INSERT INTO teams (user_id, name) VALUES ($1, $2) RETURNING id", [user.id, name]);
      teams.push(t);
    }

    for (const team of teams) {
      for (let i = 0; i < FORMATION.length; i++) {
        const role = FORMATION[i];
        let attrs = { ...PLAYER_TEMPLATES[role] };
        if (team === teams[0]) { attrs.passing = Math.min(99, attrs.passing + 5); attrs.dribbling = Math.min(99, attrs.dribbling + 3); }
        else { attrs.defending = Math.min(99, attrs.defending + 5); attrs.physicality = Math.min(99, attrs.physicality + 3); }
        await client.query("INSERT INTO players (team_id, name, number, position, attributes) VALUES ($1,$2,$3,$4,$5)",
          [team.id, `${NAMES[role]} ${i + 1}`, i + 1, role, JSON.stringify(attrs)]);
      }
    }

    const styles = [
      { teamId: teams[0].id, name: "Barça 4-3-3", pressing: 7, line: 7, width: 8, tempo: 6, passing: "short", buildup: "slow" },
      { teamId: teams[1].id, name: "City 4-3-3",  pressing: 8, line: 8, width: 7, tempo: 8, passing: "mixed", buildup: "balanced" },
    ];
    for (const s of styles) {
      await client.query("INSERT INTO tactics (user_id, team_id, name, formation, pressing_level, defensive_line, attacking_width, tempo, passing_style, build_up_style) VALUES ($1,$2,$3,'4-3-3',$4,$5,$6,$7,$8,$9)",
        [user.id, s.teamId, s.name, s.pressing, s.line, s.width, s.tempo, s.passing, s.buildup]);
    }

    console.log("Seeded: demo@try1000.io | FC Barcelona, Manchester City");
  } finally {
    client.release();
    await pool.end();
  }
}

seed().catch(console.error);
