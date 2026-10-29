import { Global, Module } from '@nestjs/common';
import { RetryKeys } from '../common/retry-keys';
import { PrismaService } from './prisma.service';

@Global()
@Module({ providers: [PrismaService, RetryKeys], exports: [PrismaService, RetryKeys] })
export class PrismaModule {}
