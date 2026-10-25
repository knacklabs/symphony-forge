import 'reflect-metadata';
import { HttpException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { NestFactory } from '@nestjs/core';
import { AuthService } from '@app/auth';
import { signUpSchema } from '@app/shared';
import { AppModule } from './app.module';

async function setupCompany(): Promise<void> {
  const app = await NestFactory.createApplicationContext(AppModule, { logger: false, abortOnError: false });
  try {
    const config = app.get(ConfigService);
    const input = signUpSchema.safeParse({ email: config.get('ADMIN_EMAIL'), password: config.get('ADMIN_PASSWORD') });
    if (!input.success) {
      for (const issue of input.error.issues) process.stderr.write(`${issue.message}\n`);
      process.exitCode = 1;
      return;
    }
    await app.get(AuthService).setUpCompany(input.data.email, input.data.password);
    process.stdout.write('The company and its first admin are ready.\n');
  } finally {
    await app.close();
  }
}

void setupCompany().catch((error: unknown) => {
  const response = error instanceof HttpException ? error.getResponse() : null;
  const message = response && typeof response === 'object' && 'message' in response
    ? String(response.message)
    : 'Company setup failed. Check the app settings and database, then try again.';
  process.stderr.write(`${message}\n`);
  process.exitCode = 1;
});
