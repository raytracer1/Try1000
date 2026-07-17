// Encode special characters in DATABASE_URL (password may contain ?, ! etc)
function parseDatabaseUrl(raw) {
  if (!raw) return null;
  try {
    // Try to fix unencoded special chars in password
    const m = raw.match(/^postgres(?:ql)?:\/\/([^:]+):([^@]+)@(.+)$/);
    if (m) {
      const [, user, pass, rest] = m;
      return `postgresql://${user}:${encodeURIComponent(pass)}@${rest}`;
    }
  } catch {}
  return raw;
}

const config = {
  port: process.env.PORT || 8000,
  databaseUrl: parseDatabaseUrl(process.env.DATABASE_URL) || "postgres://localhost:5432/try1000",
  jwtSecret: process.env.TRY1000_JWT_SECRET_KEY || "change-me",
  jwtExpireMinutes: 1440,
  googleClientId: process.env.TRY1000_GOOGLE_CLIENT_ID || "",
  googleClientSecret: process.env.TRY1000_GOOGLE_CLIENT_SECRET || "",
  supabaseUrl: process.env.SUPABASE_URL || "",
  supabaseServiceKey: process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_SERVICE_KEY || "",
  ablyApiKey: process.env.TRY1000_ABLY_API_KEY || "",
};

module.exports = { config };
