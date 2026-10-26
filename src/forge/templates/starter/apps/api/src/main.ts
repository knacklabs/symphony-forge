import { RequestMethod } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { NestFactory } from '@nestjs/core';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';
import cookieParser from 'cookie-parser';
import express, { type Express } from 'express';
import helmet from 'helmet';
import { join } from 'node:path';
import { AppModule } from './app.module';
import { correlationMiddleware, JsonLogger } from '@app/core-server';

async function bootstrap(): Promise<void> {
  const logger = new JsonLogger();
  const app = await NestFactory.create(AppModule, { logger });
  const config = app.get(ConfigService);
  app.use(helmet());
  app.enableCors({
    origin: config.getOrThrow<string>('APP_ORIGIN'),
    credentials: true,
    allowedHeaders: ['Content-Type', 'X-CSRF-Token', 'X-Correlation-Id'],
  });
  app.use(cookieParser());
  app.use(correlationMiddleware);
  const webRoot = join(process.cwd(), 'apps/web/dist');
  const expressApp: Express = app.getHttpAdapter().getInstance();
  expressApp.use(express.static(webRoot));
  expressApp.get(/^(?!\/api(?:\/|$)|\/health(?:\/|$)).*/, (request, response, next) => {
    if (request.method !== 'GET' || !request.accepts('html')) return next();
    return response.sendFile(join(webRoot, 'index.html'));
  });
  app.setGlobalPrefix('api/v1', { exclude: [{ path: 'health', method: RequestMethod.GET }] });
  const swaggerConfig = new DocumentBuilder()
    .setTitle('Starter API')
    .setDescription('Account sign-in and project management API.')
    .setVersion('1.0.0')
    .addCookieAuth('starter_session', { type: 'apiKey', in: 'cookie', name: 'starter_session' }, 'session')
    .build();
  SwaggerModule.setup('api/docs', app, SwaggerModule.createDocument(app, swaggerConfig));
  app.enableShutdownHooks();
  await app.listen(config.getOrThrow<number>('PORT'), '0.0.0.0');
}

void bootstrap();
