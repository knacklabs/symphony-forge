import { ApiProperty } from '@nestjs/swagger';

export class CredentialsDto {
  @ApiProperty({ description: 'The account email address.', example: 'ada@example.com', maxLength: 254 })
  email!: string;

  @ApiProperty({ description: 'The account password.', example: 'correct-horse-battery-staple', minLength: 12, maxLength: 128 })
  password!: string;
}

export class ForgotPasswordDto {
  @ApiProperty({ description: 'The email address for the account.', example: 'ada@example.com', maxLength: 254 })
  email!: string;
}

export class ResetPasswordDto {
  @ApiProperty({ description: 'The single-use token from the reset link.', example: 'a-43-character-token-value', minLength: 32, maxLength: 256 })
  token!: string;

  @ApiProperty({ description: 'The new account password.', example: 'new-correct-horse-battery-staple', minLength: 12, maxLength: 128 })
  password!: string;
}

export class AccountResponseDto {
  @ApiProperty({ description: 'The account identifier.', example: 'b3e1d349-1d8e-481c-8c69-99ea576f94c7' })
  id!: string;

  @ApiProperty({ description: 'The account email address.', example: 'ada@example.com' })
  email!: string;
}

export class MessageResponseDto {
  @ApiProperty({ description: 'The result message.', example: 'If an account exists, a reset link has been sent.' })
  message!: string;
}
