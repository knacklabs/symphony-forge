import { ApiProperty } from '@nestjs/swagger';

export class ProjectResponseDto {
  @ApiProperty({ description: 'The project identifier.', example: 'b3e1d349-1d8e-481c-8c69-99ea576f94c7' })
  id!: string;

  @ApiProperty({ description: 'The project name.', example: 'Migration plan' })
  name!: string;

  @ApiProperty({ description: 'The project status.', enum: ['active', 'archived'], example: 'active' })
  status!: 'active' | 'archived';

  @ApiProperty({ description: 'The UTC creation time.', example: '2026-10-22T11:30:00.000Z' })
  createdAtUtc!: string;

  @ApiProperty({ description: 'The UTC last update time.', example: '2026-10-22T11:30:00.000Z' })
  updatedAtUtc!: string;

  @ApiProperty({ description: 'The account that created the project.', example: 'a3e1d349-1d8e-481c-8c69-99ea576f94c7' })
  createdByAccountId!: string;

  @ApiProperty({ description: 'The account that last changed the project.', example: 'a3e1d349-1d8e-481c-8c69-99ea576f94c7' })
  modifiedByAccountId!: string;

  @ApiProperty({ description: 'The email of the account that created the project.', example: 'ada@example.com' })
  createdByEmail!: string;

  @ApiProperty({ description: 'The email of the account that last changed the project.', example: 'grace@example.com' })
  modifiedByEmail!: string;

  @ApiProperty({ description: 'The UTC time the project was deleted, or null when it is not deleted.', type: String, nullable: true, example: null })
  deletedAtUtc!: string | null;

  @ApiProperty({ description: 'The email of the account that deleted the project, or null when it is not deleted.', type: String, nullable: true, example: null })
  deletedByEmail!: string | null;
}

export class ProjectChangeResponseDto {
  @ApiProperty({ description: 'The change identifier.', example: 'b3e1d349-1d8e-481c-8c69-99ea576f94c7' })
  id!: string;

  @ApiProperty({ description: 'The email of the person who made the change.', example: 'grace@example.com' })
  actorEmail!: string;

  @ApiProperty({ description: 'What changed.', example: 'Status changed from active to archived' })
  summary!: string;

  @ApiProperty({ description: 'When the change happened, in UTC.', example: '2026-10-24T16:42:00.000Z' })
  createdAtUtc!: string;
}

export class ProjectPagingDto {
  @ApiProperty({ description: 'The number of projects per page.', example: 20 })
  limit!: number;

  @ApiProperty({ description: 'The cursor for the next page, or null on the last page.', type: String, nullable: true, example: 'WyJuYW1lIiwiQSJd' })
  nextCursor!: string | null;

  @ApiProperty({ description: 'The cursor for the previous page, or null on the first page.', type: String, nullable: true, example: null })
  previousCursor!: string | null;

  @ApiProperty({ description: 'The number of matching projects, counted up to 10,000.', example: 4 })
  total!: number;

  @ApiProperty({ description: 'True when more than 10,000 projects match.', example: false })
  totalCapped!: boolean;
}

export class ProjectListResponseDto {
  @ApiProperty({ description: 'The projects on this page.', type: [ProjectResponseDto] })
  items!: ProjectResponseDto[];

  @ApiProperty({ description: 'The cursors and the total for this page.', type: ProjectPagingDto })
  paging!: ProjectPagingDto;
}
