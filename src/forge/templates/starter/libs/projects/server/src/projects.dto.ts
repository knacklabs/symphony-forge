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
}

export class ProjectPaginationDto {
  @ApiProperty({ description: 'The one-based page number.', example: 1 })
  page!: number;

  @ApiProperty({ description: 'The number of projects per page.', example: 20 })
  limit!: number;

  @ApiProperty({ description: 'The number of matching projects.', example: 4 })
  totalItems!: number;

  @ApiProperty({ description: 'The number of available pages.', example: 1 })
  totalPages!: number;
}

export class ProjectListResponseDto {
  @ApiProperty({ description: 'The projects on this page.', type: [ProjectResponseDto] })
  items!: ProjectResponseDto[];

  @ApiProperty({ description: 'The page details.', type: ProjectPaginationDto })
  pagination!: ProjectPaginationDto;
}
