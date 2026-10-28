import { HttpException } from '@nestjs/common';
import { ErrorCode, McpError, type ReadResourceResult, type Resource, type ResourceTemplate } from '@modelcontextprotocol/sdk/types.js';
import { z } from 'zod';
import { hasPermission } from './permissions';
import type { ToolContext } from './tools';

type FeatureResources = {
  feature: string; one: string; permission: string; input: z.ZodObject<Record<string, z.ZodType>>;
  read: (id: string, context: ToolContext) => Promise<Record<string, unknown>>;
};
const FEATURES: FeatureResources[] = [];
const JSON_TYPE = 'application/json';
const snake = (value: string) => value.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`).replace(/-/g, '_');
const label = (value: unknown) => String(value).charAt(0).toUpperCase() + String(value).slice(1).replace(/[-_]/g, ' ');

/** The feature's tools file registers resources from its own input schema and detailed reader. */
export function defineFeatureResources(config: FeatureResources): void {
  if (FEATURES.some(({ feature }) => feature === config.feature)) throw new Error(`Duplicate resources: ${config.feature}`);
  FEATURES.push(config);
}

function fieldGuide(feature: FeatureResources) {
  const document = z.toJSONSchema(feature.input, { io: 'input' });
  return Object.entries(feature.input.shape).map(([name, schema]) => {
    const field = z.toJSONSchema(schema);
    return {
      name: snake(name), kind: field.type, ...(field.format ? { format: field.format } : {}),
      required: document.required?.includes(name) ?? false,
      description: field.description, example: schema.meta()?.example,
      ...(field.enum ? { allowed_values: field.enum, values_uri: `app://${feature.feature}/fields/${snake(name)}/values` } : {}),
    };
  });
}

function resources(feature: FeatureResources): Resource[] {
  return [{ name: `${feature.feature} fields`, uri: `app://${feature.feature}/fields`,
    description: `Read the fields, examples and allowed values for ${feature.feature}.`, mimeType: JSON_TYPE },
  ...fieldGuide(feature).filter((field) => field.values_uri).map((field) => ({
    name: `${feature.feature} ${field.name} values`, uri: field.values_uri!,
    description: `Read the allowed ${field.name} values and their labels for ${feature.feature}.`, mimeType: JSON_TYPE,
  }))];
}

export function listResources(context: ToolContext): Resource[] {
  return FEATURES.filter((feature) => hasPermission(context.account, feature.permission)).flatMap(resources);
}

export function listResourceTemplates(context: ToolContext): ResourceTemplate[] {
  return FEATURES.filter((feature) => hasPermission(context.account, feature.permission)).map((feature) => ({
    name: `${feature.feature} item`, uriTemplate: `app://${feature.feature}/{${snake(feature.one)}_id}`,
    description: `Read every field of one ${feature.one} in your organisation.`, mimeType: JSON_TYPE,
  }));
}

export async function readResource(uri: string, context: ToolContext): Promise<ReadResourceResult> {
  const feature = FEATURES.find((entry) => uri.startsWith(`app://${entry.feature}/`));
  if (!feature) throw new McpError(ErrorCode.InvalidParams, 'Unknown resource. Use resources/list to find a resource.');
  if (!hasPermission(context.account, feature.permission)) {
    const message = "Your agent account's role cannot view this feature. An admin can change its role on the Members screen.";
    throw new McpError(-32002, message, { kind: 'not_allowed', message, retryable: false });
  }
  const path = uri.slice(`app://${feature.feature}/`.length);
  let data: unknown;
  if (path === 'fields') data = { fields: fieldGuide(feature) };
  else if (path.startsWith('fields/')) {
    const field = fieldGuide(feature).find((entry) => entry.values_uri === uri);
    if (!field) throw new McpError(ErrorCode.InvalidParams, 'Unknown field values. Read the field guide to find the address.');
    data = { values: field.allowed_values!.map((value) => ({ value, label: label(value) })) };
  } else {
    const id = z.string().uuid().safeParse(path);
    if (!id.success) throw new McpError(ErrorCode.InvalidParams, 'Use a valid item id from the feature search tool.');
    try {
      data = await feature.read(id.data, context);
    } catch (error) {
      if (error instanceof HttpException && error.getStatus() < 500) {
        const kind = error.getStatus() === 404 ? 'not_found' : error.getStatus() === 403 ? 'not_allowed' : 'invalid_input';
        const message = error.getStatus() === 404
          ? 'No item has this id in your organisation. Use the feature search tool to find it.'
          : 'Your account cannot read this item. Check its permissions and try again.';
        throw new McpError(-32002, message, { kind, message, retryable: false });
      }
      context.reportError?.(error);
      const message = 'The app could not read this item. Wait 5 seconds and try again.';
      throw new McpError(-32002, message, { kind: 'unavailable', message, retryable: true });
    }
  }
  return { contents: [{ uri, mimeType: JSON_TYPE, text: JSON.stringify(data) }] };
}
