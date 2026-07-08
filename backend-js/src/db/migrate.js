const { Pool } = require("pg");
const { config } = require("../config");

async function createTables() {
  const pool = new Pool({ connectionString: config.databaseUrl, max: 1 });
  const client = await pool.connect();
  try {
    await client.query(`
      CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email VARCHAR(255) UNIQUE NOT NULL,
        username VARCHAR(100),
        google_id VARCHAR(255) UNIQUE,
        hashed_password VARCHAR(255),
        llm_provider VARCHAR(20),
        llm_api_key VARCHAR(255),
        llm_model VARCHAR(100),
        created_at TIMESTAMP DEFAULT NOW()
      );
      CREATE TABLE IF NOT EXISTS teams (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        name VARCHAR(200) NOT NULL,
        created_at TIMESTAMP DEFAULT NOW()
      );
      CREATE TABLE IF NOT EXISTS players (
        id SERIAL PRIMARY KEY,
        team_id INTEGER NOT NULL REFERENCES teams(id),
        name VARCHAR(200) NOT NULL,
        number INTEGER NOT NULL,
        position VARCHAR(10) NOT NULL,
        attributes JSONB NOT NULL DEFAULT '{}',
        created_at TIMESTAMP DEFAULT NOW()
      );
      CREATE TABLE IF NOT EXISTS tactics (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        team_id INTEGER NOT NULL REFERENCES teams(id),
        name VARCHAR(200) NOT NULL,
        formation VARCHAR(10) NOT NULL DEFAULT '4-3-3',
        player_positions JSONB NOT NULL DEFAULT '{}',
        pressing_level INTEGER DEFAULT 5,
        defensive_line INTEGER DEFAULT 5,
        attacking_width INTEGER DEFAULT 5,
        tempo INTEGER DEFAULT 5,
        passing_style VARCHAR(20) DEFAULT 'mixed',
        build_up_style VARCHAR(20) DEFAULT 'balanced',
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
      );
      CREATE TABLE IF NOT EXISTS simulation_jobs (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        home_team_id INTEGER NOT NULL REFERENCES teams(id),
        away_team_id INTEGER NOT NULL REFERENCES teams(id),
        home_tactic_id INTEGER NOT NULL REFERENCES tactics(id),
        away_tactic_id INTEGER NOT NULL REFERENCES tactics(id),
        match_count INTEGER NOT NULL DEFAULT 10,
        status VARCHAR(20) DEFAULT 'pending',
        progress INTEGER DEFAULT 0,
        seed_base INTEGER DEFAULT 42,
        engine_version VARCHAR(20) DEFAULT 'rule-based-v1',
        created_at TIMESTAMP DEFAULT NOW(),
        completed_at TIMESTAMP
      );
      CREATE TABLE IF NOT EXISTS simulation_results (
        id SERIAL PRIMARY KEY,
        job_id INTEGER NOT NULL REFERENCES simulation_jobs(id),
        match_index INTEGER NOT NULL,
        home_score INTEGER DEFAULT 0,
        away_score INTEGER DEFAULT 0,
        home_xg REAL DEFAULT 0,
        away_xg REAL DEFAULT 0,
        home_possession REAL DEFAULT 50,
        away_possession REAL DEFAULT 50,
        stats JSONB NOT NULL DEFAULT '{}',
        replay_path VARCHAR(500),
        created_at TIMESTAMP DEFAULT NOW()
      );
      CREATE TABLE IF NOT EXISTS agent_results (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        task_type VARCHAR(30) NOT NULL,
        tactic_id INTEGER,
        job_id INTEGER,
        result JSONB NOT NULL,
        created_at TIMESTAMP DEFAULT NOW()
      );
    `);
    console.log("Tables created");
  } finally {
    client.release();
    await pool.end();
  }
}

module.exports = { createTables };
