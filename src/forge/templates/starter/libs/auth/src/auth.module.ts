import { Module } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { JsonLogger } from '@app/core';
import { AuthController } from './auth.controller';
import { AuthService } from './auth.service';
import { LogMailProvider, MAIL_PROVIDER, type MailProvider } from './mail.provider';

@Module({
  controllers: [AuthController],
  providers: [
    AuthService,
    {
      provide: MAIL_PROVIDER,
      useFactory: (config: ConfigService, logger: JsonLogger): MailProvider | null => {
        const environment = config.getOrThrow<string>('APP_ENV');
        return environment === 'development' || environment === 'test' ? new LogMailProvider(logger) : null;
      },
      inject: [ConfigService, JsonLogger],
    },
  ],
})
export class AuthModule {}
