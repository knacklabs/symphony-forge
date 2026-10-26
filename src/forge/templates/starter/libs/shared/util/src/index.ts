import { z } from 'zod';

export { formatDate, formatDateTime, formatMoney, formatNumber, formatTime } from './format';
export { csvField } from './csv-field';
export type { ApiEnvelope } from './envelope';

export const errorReportSchema = z.object({
  name: z.string().max(200).meta({ description: 'The class name of the error.', example: 'TypeError' }),
  path: z.string().max(2000).meta({ description: 'The page path where the error happened, without its query.', example: '/projects' }),
}).strict();

export type ErrorReportInput = z.infer<typeof errorReportSchema>;
