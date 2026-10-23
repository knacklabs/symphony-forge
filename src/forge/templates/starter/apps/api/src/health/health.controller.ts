import { Controller, Get } from '@nestjs/common';
import { ApiOperation, ApiTags } from '@nestjs/swagger';
import { SkipThrottle } from '@nestjs/throttler';
import { Public } from '../common/public.decorator';

@ApiTags('Health')
@SkipThrottle()
@Controller('health')
export class HealthController {
  @Public()
  @Get()
  @ApiOperation({ summary: 'Check whether the API is ready.' })
  health(): { status: 'ok' } {
    return { status: 'ok' };
  }
}
