/** A small JSON-schema checker for the subset FastAPI emits. Used by the mock tests only. */
type Schema = {
  $ref?: string;
  type?: string;
  enum?: unknown[];
  anyOf?: Schema[];
  items?: Schema;
  properties?: Record<string, Schema>;
  required?: string[];
  additionalProperties?: boolean | Schema;
};

export function validate(doc: unknown, schema: Schema, value: unknown, path = "$"): string[] {
  if (schema.$ref) {
    const target = schema.$ref
      .replace(/^#\//, "")
      .split("/")
      .reduce<unknown>((node, key) => (node as Record<string, unknown>)[key], doc);
    return validate(doc, target as Schema, value, path);
  }
  if (schema.anyOf) {
    const attempts = schema.anyOf.map((s) => validate(doc, s, value, path));
    return attempts.some((a) => a.length === 0) ? [] : [`${path}: matches none of anyOf`];
  }
  if (schema.enum && !schema.enum.includes(value)) return [`${path}: ${String(value)} not in enum`];
  switch (schema.type) {
    case "null":
      return value === null ? [] : [`${path}: expected null`];
    case "string":
      return typeof value === "string" ? [] : [`${path}: expected string`];
    case "boolean":
      return typeof value === "boolean" ? [] : [`${path}: expected boolean`];
    case "number":
      return typeof value === "number" ? [] : [`${path}: expected number`];
    case "integer":
      return Number.isInteger(value) ? [] : [`${path}: expected integer`];
    case "array": {
      if (!Array.isArray(value)) return [`${path}: expected array`];
      return value.flatMap((v, i) =>
        schema.items ? validate(doc, schema.items, v, `${path}[${i}]`) : [],
      );
    }
    case "object": {
      if (typeof value !== "object" || value === null || Array.isArray(value)) {
        return [`${path}: expected object`];
      }
      const obj = value as Record<string, unknown>;
      const errors = (schema.required ?? [])
        .filter((k) => !(k in obj))
        .map((k) => `${path}.${k}: missing`);
      for (const [k, v] of Object.entries(obj)) {
        const sub = schema.properties?.[k];
        if (sub) errors.push(...validate(doc, sub, v, `${path}.${k}`));
        else if (schema.additionalProperties === false) errors.push(`${path}.${k}: unexpected`);
      }
      return errors;
    }
    default:
      return [];
  }
}
