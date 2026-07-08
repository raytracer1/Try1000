const { Pool } = require("pg");
const { drizzle } = require("drizzle-orm/node-postgres");
const { config } = require("./config");

let db;

function getDb() {
  if (!db) {
    const pool = new Pool({ connectionString: config.databaseUrl, max: 10 });
    db = drizzle(pool);
  }
  return db;
}

module.exports = { getDb };
