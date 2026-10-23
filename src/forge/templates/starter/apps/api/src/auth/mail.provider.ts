import { Inject, Injectable } from '@nestjs/common';
import { JsonLogger } from '../common/json-logger';

export const MAIL_PROVIDER = Symbol('MAIL_PROVIDER');

export interface MailProvider {
  sendPasswordReset(email: string, resetUrl: string): Promise<void>;
}

@Injectable()
export class LogMailProvider implements MailProvider {
  constructor(@Inject(JsonLogger) private readonly logger: JsonLogger) {}

  async sendPasswordReset(_email: string, resetUrl: string): Promise<void> {
    this.logger.log('Password reset link created for local mail', 'LogMailProvider', { resetUrl });
  }
}
