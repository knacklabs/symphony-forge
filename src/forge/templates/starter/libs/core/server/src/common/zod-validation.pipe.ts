import { BadRequestException, type PipeTransform } from '@nestjs/common';
import { z } from 'zod';

export class ZodValidationPipe<Schema extends z.ZodType> implements PipeTransform<unknown, z.output<Schema>> {
  constructor(private readonly schema: Schema, private readonly rootField = 'body') {}

  transform(value: unknown): z.output<Schema> {
    const result = this.schema.safeParse(value);
    if (result.success) return result.data;

    const fieldErrors = result.error.issues.flatMap((issue) =>
      issue.code === 'unrecognized_keys'
        ? issue.keys.map((field) => ({ field, reason: 'Remove this field.' }))
        : [{ field: issue.path.join('.') || this.rootField, reason: issue.message }],
    );
    throw new BadRequestException({
      code: 'VALIDATION_ERROR',
      message: 'Check the fields and try again.',
      details: { fieldErrors },
    });
  }
}
