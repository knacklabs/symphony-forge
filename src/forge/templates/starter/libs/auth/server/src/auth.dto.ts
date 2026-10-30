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

export class AgentResponseDto {
  @ApiProperty({ description: 'The membership identifier.', example: 'b3e1d349-1d8e-481c-8c69-99ea576f94c7' })
  id!: string;
  @ApiProperty({ description: 'The agent account identifier.', example: 'a3e1d349-1d8e-481c-8c69-99ea576f94c7' })
  accountId!: string;
  @ApiProperty({ description: 'The agent account email address.', example: 'gantry-k3x9p2@agents.invalid' })
  email!: string;
  @ApiProperty({ description: 'The agent account role.', enum: ['admin', 'member'], example: 'member' })
  role!: 'admin' | 'member';
  @ApiProperty({ description: 'Always true for an agent account.', example: true })
  isAgent!: boolean;
  @ApiProperty({ description: 'Whether the agent account has a working key; false until you create one.', example: false })
  hasKey!: boolean;
  @ApiProperty({ description: 'When the agent account was added, in UTC.', example: '2026-10-27T11:30:00.000Z' })
  createdAtUtc!: string;
}
