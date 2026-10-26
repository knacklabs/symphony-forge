import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { APP_FILTER, APP_GUARD, APP_INTERCEPTOR } from '@nestjs/core';
import { ThrottlerGuard, ThrottlerModule } from '@nestjs/throttler';
import { AllExceptionsFilter, CommonModule, CsrfGuard, EnvelopeInterceptor, PrismaModule, validateEnvironment } from '@app/core-server';
import { AuthModule, SessionGuard } from '@app/auth-server';
import { HealthModule } from './health/health.module';
import { ProjectsModule } from '@app/projects-server';
import { HistoryModule } from '@app/history-server';
import { OrganisationsModule } from '@app/organisations-server';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true, validate: validateEnvironment }),
    ThrottlerModule.forRoot([{ ttl: 60_000, limit: 120 }]),
    CommonModule,
    PrismaModule,
    AuthModule,
    ProjectsModule,
    OrganisationsModule,
    HistoryModule,
    HealthModule,
  ],
  providers: [
    { provide: APP_GUARD, useClass: ThrottlerGuard },
    { provide: APP_GUARD, useClass: SessionGuard },
    { provide: APP_GUARD, useClass: CsrfGuard },
    { provide: APP_FILTER, useClass: AllExceptionsFilter },
    { provide: APP_INTERCEPTOR, useClass: EnvelopeInterceptor },
  ],
})
export class AppModule {}
