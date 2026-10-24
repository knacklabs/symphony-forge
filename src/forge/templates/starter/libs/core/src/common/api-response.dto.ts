import { ApiProperty } from '@nestjs/swagger';

export class ApiErrorDto {
  @ApiProperty({ description: 'The stable error code.', example: 'PROJECT_NOT_FOUND' })
  code!: string;

  @ApiProperty({ description: 'What happened and what to do next.', example: 'The project was not found.' })
  message!: string;

  @ApiProperty({ description: 'Field errors or other safe error details.', type: 'object', additionalProperties: true, nullable: true, example: null })
  details!: Record<string, unknown> | null;

  @ApiProperty({ description: 'The identifier for this failed request.', example: 'd49fe9c4-a93b-4e3d-a20a-1afc37f4d1c0' })
  errorId!: string;
}

export class ApiErrorResponseDto {
  @ApiProperty({ description: 'Whether the request succeeded.', example: false })
  success!: false;

  @ApiProperty({ description: 'Failed responses have no data.', type: 'object', properties: {}, nullable: true, example: null })
  data!: null;

  @ApiProperty({ description: 'The error details.', type: ApiErrorDto })
  error!: ApiErrorDto;
}
