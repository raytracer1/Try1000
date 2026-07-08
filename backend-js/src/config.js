const config = {
  port: process.env.PORT || 8000,
  databaseUrl: process.env.DATABASE_URL || "postgres://localhost:5432/try1000",
  jwtSecret: process.env.TRY1000_JWT_SECRET_KEY || "change-me",
  jwtExpireMinutes: 1440,
  googleClientId: process.env.TRY1000_GOOGLE_CLIENT_ID || "",
  supabaseUrl: process.env.SUPABASE_URL || "",
  supabaseServiceKey: process.env.SUPABASE_SERVICE_KEY || "",
  ablyApiKey: process.env.TRY1000_ABLY_API_KEY || "",
};

module.exports = { config };
