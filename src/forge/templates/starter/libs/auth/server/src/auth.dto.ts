import { ApiProperty } from '@nestjs/swagger';
import type { AuthOptions } from '@app/auth-contracts';

export class AuthOptionsResponseDto implements AuthOptions {
  @ApiProperty({ description: 'Whether anyone can create an account.', example: true })
  signUpOpen!: boolean;
}

export class AccountResponseDto {
  @ApiProperty({ description: 'The account identifier.', example: 'b3e1d349-1d8e-481c-8c69-99ea576f94c7' })
  id!: string;

  @ApiProperty({ description: 'The account email address.', example: 'ada@example.com' })
  email!: string;

  @ApiProperty({ description: 'The role in the account’s organisation.', enum: ['admin', 'member'], example: 'admin' })
  role!: 'admin' | 'member';

  @ApiProperty({ description: 'What the account may do, as <feature>.<action>.', type: [String], example: ['projects.view', 'projects.create', 'projects.edit'] })
  permissions!: string[];
}

export class MessageResponseDto {
  @ApiProperty({ description: 'The result message.', example: 'If an account exists, a reset link has been sent.' })
  message!: string;
}
