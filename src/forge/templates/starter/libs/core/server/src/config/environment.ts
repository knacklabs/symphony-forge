export type AppEnvironment = string;
export type Environment = {
  APP_ENV: AppEnvironment;
  APP_COMPANIES: 'one' | 'many';
  DATABASE_URL: string;
  APP_ORIGIN: string;
  PORT: number;
  /** Requests a minute from one address to each sign-in, sign-up and other account route. */
  AUTH_RATE_LIMIT_PER_MINUTE: number;
  /** Requests a minute from one address to each other route. */
  RATE_LIMIT_PER_MINUTE: number;
  // Only setup:company requires and validates these with the shared sign-up schema.
  ADMIN_EMAIL?: unknown;
  ADMIN_PASSWORD?: unknown;
};

let activeEnvironment: AppEnvironment = 'development';
// Today's limits until the environment says otherwise; only the test stack raises them.
let activeRateLimits = { auth: 30, other: 120 };

export function getAppEnvironment(): AppEnvironment {
  return activeEnvironment;
}

/** The rate limits a minute, read by the throttle decorators, which cannot inject config. */
export function getRateLimits(): { auth: number; other: number } {
  return activeRateLimits;
}

function rateLimit(name: string, value: unknown, fallback: number): number {
  const limit = value === undefined || value === '' ? fallback : Number(value);
  if (!Number.isInteger(limit) || limit < 1) throw new Error(`${name} must be a whole number of 1 or more.`);
  return limit;
}

export function validateEnvironment(values: Record<string, unknown>): Environment {
  const companies = values.APP_COMPANIES ?? 'many';
  if (companies !== 'one' && companies !== 'many') {
    throw new Error('APP_COMPANIES must be one or many.');
  }
  const appEnvironment = values.APP_ENV;
  if (typeof appEnvironment !== 'string' || appEnvironment.length === 0) {
    throw new Error('APP_ENV must be set.');
  }

  const databaseUrl = values.DATABASE_URL;
  if (typeof databaseUrl !== 'string' || databaseUrl.length === 0) {
    throw new Error('DATABASE_URL must contain a PostgreSQL connection URL.');
  }
  try {
    if (!['postgres:', 'postgresql:'].includes(new URL(databaseUrl).protocol)) throw new Error();
  } catch {
    throw new Error('DATABASE_URL must contain a PostgreSQL connection URL.');
  }

  const appOrigin = values.APP_ORIGIN;
  if (typeof appOrigin !== 'string') throw new Error('APP_ORIGIN must be set.');
  let origin: URL;
  try {
    origin = new URL(appOrigin);
  } catch {
    throw new Error('APP_ORIGIN must be a valid origin URL.');
  }
  if (origin.protocol !== 'http:' && origin.protocol !== 'https:') {
    throw new Error('APP_ORIGIN must use HTTP or HTTPS.');
  }
  if (origin.origin !== appOrigin) throw new Error('APP_ORIGIN must not include a path or query.');

  const portValue = values.PORT ?? 3000;
  const port = typeof portValue === 'number' ? portValue : Number(portValue);
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('PORT must be a valid TCP port.');

  const authLimit = rateLimit('AUTH_RATE_LIMIT_PER_MINUTE', values.AUTH_RATE_LIMIT_PER_MINUTE, 30);
  const otherLimit = rateLimit('RATE_LIMIT_PER_MINUTE', values.RATE_LIMIT_PER_MINUTE, 120);

  activeEnvironment = appEnvironment;
  activeRateLimits = { auth: authLimit, other: otherLimit };
  return {
    APP_ENV: appEnvironment, APP_COMPANIES: companies, DATABASE_URL: databaseUrl, APP_ORIGIN: appOrigin, PORT: port,
    AUTH_RATE_LIMIT_PER_MINUTE: authLimit, RATE_LIMIT_PER_MINUTE: otherLimit,
    ADMIN_EMAIL: values.ADMIN_EMAIL, ADMIN_PASSWORD: values.ADMIN_PASSWORD,
  };
}
