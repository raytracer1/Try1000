const { pgTable, serial, varchar, integer, doublePrecision, timestamp, json } = require("drizzle-orm/pg-core");

const users = pgTable("users", {
  id: serial("id").primaryKey(),
  email: varchar("email", { length: 255 }).notNull().unique(),
  username: varchar("username", { length: 100 }),
  googleId: varchar("google_id", { length: 255 }).unique(),
  hashedPassword: varchar("hashed_password", { length: 255 }),
  llmProvider: varchar("llm_provider", { length: 20 }),
  llmApiKey: varchar("llm_api_key", { length: 255 }),
  llmModel: varchar("llm_model", { length: 100 }),
  createdAt: timestamp("created_at").defaultNow(),
});

const teams = pgTable("teams", {
  id: serial("id").primaryKey(),
  userId: integer("user_id").notNull().references(() => users.id),
  name: varchar("name", { length: 200 }).notNull(),
  playerIds: json("player_ids").notNull().default([]),
  createdAt: timestamp("created_at").defaultNow(),
});

const players = pgTable("players", {
  id: serial("id").primaryKey(),
  userId: integer("user_id").notNull().references(() => users.id),
  name: varchar("name", { length: 200 }).notNull(),
  number: integer("number").notNull(),
  position: varchar("position", { length: 10 }).notNull(),
  attributes: json("attributes").notNull().default({}),
  createdAt: timestamp("created_at").defaultNow(),
});

const tactics = pgTable("tactics", {
  id: serial("id").primaryKey(),
  userId: integer("user_id").notNull().references(() => users.id),
  teamId: integer("team_id").notNull().references(() => teams.id),
  name: varchar("name", { length: 200 }).notNull(),
  formation: varchar("formation", { length: 10 }).notNull().default("4-3-3"),
  playerPositions: json("player_positions").notNull().default({}),
  pressingLevel: integer("pressing_level").default(5),
  defensiveLine: integer("defensive_line").default(5),
  attackingWidth: integer("attacking_width").default(5),
  tempo: integer("tempo").default(5),
  passingStyle: varchar("passing_style", { length: 20 }).default("mixed"),
  buildUpStyle: varchar("build_up_style", { length: 20 }).default("balanced"),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
});

const simulationJobs = pgTable("simulation_jobs", {
  id: serial("id").primaryKey(),
  userId: integer("user_id").notNull().references(() => users.id),
  homeTeamId: integer("home_team_id").notNull().references(() => teams.id),
  awayTeamId: integer("away_team_id").notNull().references(() => teams.id),
  homeTacticId: integer("home_tactic_id").notNull().references(() => tactics.id),
  awayTacticId: integer("away_tactic_id").notNull().references(() => tactics.id),
  matchCount: integer("match_count").notNull().default(10),
  status: varchar("status", { length: 20 }).default("pending"),
  progress: integer("progress").default(0),
  seedBase: integer("seed_base").default(42),
  engineVersion: varchar("engine_version", { length: 20 }).default("rule-based-v1"),
  homeTacticalDocument: varchar("home_tactical_document", { length: 5000 }).default(""),
  awayTacticalDocument: varchar("away_tactical_document", { length: 5000 }).default(""),
  createdAt: timestamp("created_at").defaultNow(),
  completedAt: timestamp("completed_at"),
});

const simulationResults = pgTable("simulation_results", {
  id: serial("id").primaryKey(),
  jobId: integer("job_id").notNull().references(() => simulationJobs.id),
  matchIndex: integer("match_index").notNull(),
  homeScore: integer("home_score").default(0),
  awayScore: integer("away_score").default(0),
  homeXg: doublePrecision("home_xg").default(0),
  awayXg: doublePrecision("away_xg").default(0),
  homePossession: doublePrecision("home_possession").default(50),
  awayPossession: doublePrecision("away_possession").default(50),
  stats: json("stats").notNull().default({}),
  replayPath: varchar("replay_path", { length: 500 }),
  createdAt: timestamp("created_at").defaultNow(),
});

const agentResults = pgTable("agent_results", {
  id: serial("id").primaryKey(),
  userId: integer("user_id").notNull().references(() => users.id),
  taskType: varchar("task_type", { length: 30 }).notNull(),
  tacticId: integer("tactic_id"),
  jobId: integer("job_id"),
  result: json("result").notNull(),
  createdAt: timestamp("created_at").defaultNow(),
});

module.exports = {
  users, teams, players, tactics,
  simulationJobs, simulationResults, agentResults,
};
