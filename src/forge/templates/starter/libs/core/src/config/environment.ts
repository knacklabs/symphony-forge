export type AppEnvironment = string;
export type Environment = {
  APP_ENV: AppEnvironment;
  APP_COMPANIES: 'one' | 'many';
  DATABASE_URL: string;
  APP_ORIGIN: string;
  PORT: number;
};

let activeEnvironment: AppEnvironment = 'development';

export function getAppEnvironment(): AppEnvironment {
  return activeEnvironment;
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

  activeEnvironment = appEnvironment;
  return { APP_ENV: appEnvironment, APP_COMPANIES: companies, DATABASE_URL: databaseUrl, APP_ORIGIN: appOrigin, PORT: port };
}
