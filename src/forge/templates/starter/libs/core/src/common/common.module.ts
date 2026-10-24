import { Global, Module } from '@nestjs/common';
import { JsonLogger } from './json-logger';

@Global()
@Module({ providers: [JsonLogger], exports: [JsonLogger] })
export class CommonModule {}
