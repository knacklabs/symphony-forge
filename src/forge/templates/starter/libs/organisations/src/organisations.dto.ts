import { ApiProperty } from '@nestjs/swagger';

export class MemberResponseDto {
  @ApiProperty({ description: 'The membership identifier.', example: 'b3e1d349-1d8e-481c-8c69-99ea576f94c7' })
  id!: string;
  @ApiProperty({ description: 'The account identifier.', example: 'a3e1d349-1d8e-481c-8c69-99ea576f94c7' })
  accountId!: string;
  @ApiProperty({ description: 'The member email address.', example: 'ada@example.com' })
  email!: string;
  @ApiProperty({ description: 'The member role.', enum: ['admin', 'member'], example: 'admin' })
  role!: 'admin' | 'member';
  @ApiProperty({ description: 'When the member joined, in UTC.', example: '2026-10-24T11:30:00.000Z' })
  createdAtUtc!: string;
}

class MemberPaginationDto {
  @ApiProperty({ description: 'The one-based page number.', example: 1 })
  page!: number;
  @ApiProperty({ description: 'The number of members per page.', example: 20 })
  limit!: number;
  @ApiProperty({ description: 'The number of members.', example: 1 })
  totalItems!: number;
  @ApiProperty({ description: 'The number of available pages.', example: 1 })
  totalPages!: number;
}

export class MemberListResponseDto {
  @ApiProperty({ description: 'The members on this page.', type: [MemberResponseDto] })
  items!: MemberResponseDto[];
  @ApiProperty({ description: 'The page details.', type: MemberPaginationDto })
  pagination!: MemberPaginationDto;
}
