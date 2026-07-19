const { pgTable, serial, uuid, varchar, integer, doublePrecision, timestamp, json } = require("drizzle-orm/pg-core");

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

const simulationJobs = pgTable("simulation_jobs", {
  id: uuid("id").defaultRandom().primaryKey(),
  userId: integer("user_id").notNull().references(() => users.id),
  homePlayers: json("home_players").notNull().default([]),
  awayPlayers: json("away_players").notNull().default([]),
  homeTactic: json("home_tactic").notNull().default({}),
  awayTactic: json("away_tactic").notNull().default({}),
  matchCount: integer("match_count").notNull().default(10),
  status: varchar("status", { length: 20 }).default("pending"),
  progress: integer("progress").default(0),
  engineVersion: varchar("engine_version", { length: 20 }).default("rule-based-v1"),
  createdAt: timestamp("created_at").defaultNow(),
  completedAt: timestamp("completed_at"),
});

const simulationResults = pgTable("simulation_results", {
  id: serial("id").primaryKey(),
  jobId: uuid("job_id").notNull().references(() => simulationJobs.id),
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
  jobId: uuid("job_id"),
  result: json("result").notNull(),
  createdAt: timestamp("created_at").defaultNow(),
});

module.exports = {
  users,
  simulationJobs, simulationResults, agentResults,
};
