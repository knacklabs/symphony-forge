import { ApiProperty } from '@nestjs/swagger';

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
