import { Body, Controller, Post } from '@nestjs/common';
import { ApiCookieAuth, ApiOperation, ApiTags } from '@nestjs/swagger';
import { AdminOnly, ApiEnvelope, ApiErrors, ApiZodBody, CurrentAccount, ZodValidationPipe, type AccountPrincipal } from '@app/core-server';
import { addAgentSchema, type AddAgentInput, type Member } from '@app/organisations-contracts';
import { AuthService } from './auth.service';
import { AgentResponseDto } from './auth.dto';

// In auth, because it makes the account, as sign-up and invites do.
@ApiTags('Organisations')
@ApiCookieAuth('session')
@Controller('agents')
export class AgentsController {
  constructor(private readonly auth: AuthService) {}

  @Post()
  @AdminOnly()
  @ApiZodBody(addAgentSchema)
  @ApiOperation({ summary: 'Add an agent account to your organisation.', description: 'Only admins can add agent accounts. The account’s email is the name with six random characters at agents.invalid, and it has no password. Create its key next.' })
  @ApiEnvelope(AgentResponseDto, 201)
  @ApiErrors(400, 401, 403, 409)
  add(@CurrentAccount() account: AccountPrincipal, @Body(new ZodValidationPipe(addAgentSchema)) input: AddAgentInput): Promise<Member> {
    return this.auth.addAgent(input, account);
  }
}
