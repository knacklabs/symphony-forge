import { Module } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { JsonLogger } from '../common/json-logger';
import { LogMailProvider, MAIL_PROVIDER, type MailProvider } from './mail.provider';

@Module({
  providers: [
    {
      provide: MAIL_PROVIDER,
      useFactory: (config: ConfigService, logger: JsonLogger): MailProvider | null => {
        const environment = config.getOrThrow<string>('APP_ENV');
        return environment === 'development' || environment === 'test' ? new LogMailProvider(logger) : null;
      },
      inject: [ConfigService, JsonLogger],
    },
  ],
  exports: [MAIL_PROVIDER],
})
export class MailModule {}
