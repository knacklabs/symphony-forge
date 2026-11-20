import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PrismaService } from '@app/core-server';

const MICROS_PER_USD = 1_000_000n;
const TOKENS_PER_MILLION = 1_000_000n;

function usdMicros(config: ConfigService, name: string): bigint {
  const value = config.get<string>(name)?.trim();
  if (!value || !/^\d+(?:\.\d{1,6})?$/.test(value)) {
    throw new Error(`Set ${name} to a non-negative US dollar amount with at most six decimal places.`);
  }
  const [whole, fraction = ''] = value.split('.');
  return BigInt(whole) * MICROS_PER_USD + BigInt(fraction.padEnd(6, '0'));
}

@Injectable()
export class AssistantUsage {
  private readonly capMicros: bigint;
  private readonly inputPriceMicros: bigint;
  private readonly outputPriceMicros: bigint;

  constructor(private readonly prisma: PrismaService, config: ConfigService) {
    this.capMicros = usdMicros(config, 'ASSISTANT_SPEND_CAP_USD');
    this.inputPriceMicros = usdMicros(config, 'ASSISTANT_PRICE_INPUT_USD_PER_MTOK');
    this.outputPriceMicros = usdMicros(config, 'ASSISTANT_PRICE_OUTPUT_USD_PER_MTOK');
  }

  async canStart(now = new Date()): Promise<boolean> {
    const start = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
    const end = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 1));
    // The approved cap covers the whole app, rather than one organisation.
    const usage = await this.prisma.assistantUsage.aggregate({
      where: { createdAtUtc: { gte: start, lt: end } }, _sum: { costMicros: true },
    });
    return (usage._sum.costMicros ?? 0n) < this.capMicros;
  }

  cost(inputTokens: number, outputTokens: number): bigint {
    if (![inputTokens, outputTokens].every(value => Number.isSafeInteger(value) && value >= 0)) {
      throw new Error('The model must return non-negative whole token counts.');
    }
    const cost = BigInt(inputTokens) * this.inputPriceMicros + BigInt(outputTokens) * this.outputPriceMicros;
    // Round up once per turn so fractional micro-dollars never disappear.
    return (cost + TOKENS_PER_MILLION - 1n) / TOKENS_PER_MILLION;
  }

  async record(accountId: string, chatId: string, inputTokens: number, outputTokens: number): Promise<void> {
    await this.prisma.assistantUsage.create({ data: {
      accountId, chatId, kind: 'llm', inputTokens, outputTokens,
      costMicros: this.cost(inputTokens, outputTokens),
    } });
  }
}
