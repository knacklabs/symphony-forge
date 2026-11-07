import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { ChatOpenAI } from '@langchain/openai';

@Injectable()
export class AssistantModel {
  readonly client: ChatOpenAI;

  constructor(config: ConfigService) {
    const apiKey = config.get<string>('ASSISTANT_AI_KEY')?.trim();
    const model = config.get<string>('ASSISTANT_MODEL')?.trim();
    if (!apiKey) throw new Error('Set ASSISTANT_AI_KEY before you start the assistant.');
    if (!model) throw new Error('Set ASSISTANT_MODEL before you start the assistant.');
    const baseURL = config.get<string>('ASSISTANT_AI_URL')?.trim();
    if (baseURL) {
      let url: URL;
      try { url = new URL(baseURL); } catch {
        throw new Error('Set ASSISTANT_AI_URL to an HTTP or HTTPS address.');
      }
      if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) {
        throw new Error('Set ASSISTANT_AI_URL to an HTTP or HTTPS address without a password.');
      }
    }
    this.client = new ChatOpenAI({
      apiKey, model, timeout: 20_000, maxRetries: 1,
      ...(baseURL ? { configuration: { baseURL } } : {}),
    });
  }
}
