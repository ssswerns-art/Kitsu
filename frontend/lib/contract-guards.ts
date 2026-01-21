/**
 * API Contract Validation Guards
 * 
 * This module provides fail-fast contract validation for API responses.
 * All guards:
 * - Throw ContractError on contract violation
 * - Are synchronous and deterministic
 * - Have no side effects
 * - Do NOT use optional chaining
 * - Do NOT provide fallback values
 */

/**
 * ContractError - unified error type for all contract violations
 * Format: [ContractError] path: expected type, got actual
 */
export class ContractError extends Error {
  constructor(path: string, expected: string, actual: string) {
    super(`[ContractError] ${path}: expected ${expected}, got ${actual}`);
    this.name = 'ContractError';
  }
}

/**
 * Helper to get type name for error messages
 */
function getTypeName(value: unknown): string {
  if (value === null) return 'null';
  if (value === undefined) return 'undefined';
  if (Array.isArray(value)) return 'array';
  return typeof value;
}

/**
 * Asserts that value is an object (not null, not array)
 * @throws ContractError if value is not an object
 */
export function assertObject(value: unknown, path: string): asserts value is Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new ContractError(path, 'object', getTypeName(value));
  }
}

/**
 * Asserts that value is a string
 * @throws ContractError if value is not a string
 */
export function assertString(value: unknown, path: string): asserts value is string {
  if (typeof value !== 'string') {
    throw new ContractError(path, 'string', getTypeName(value));
  }
}

/**
 * Asserts that value is a number
 * @throws ContractError if value is not a number
 */
export function assertNumber(value: unknown, path: string): asserts value is number {
  if (typeof value !== 'number' || isNaN(value)) {
    throw new ContractError(path, 'number', getTypeName(value));
  }
}

/**
 * Asserts that value is an array
 * @throws ContractError if value is not an array
 */
export function assertArray(value: unknown, path: string): asserts value is unknown[] {
  if (!Array.isArray(value)) {
    throw new ContractError(path, 'array', getTypeName(value));
  }
}

/**
 * Validates optional fields with proper type narrowing
 * @param value - The value to validate
 * @param guard - Type guard function to validate the value if present
 * @param path - Field path for error messages
 * @returns T | undefined - the validated value or undefined if null/undefined
 * @throws ContractError if value is present but invalid
 */
export function assertOptional<T>(
  value: unknown,
  guard: (value: unknown, path: string) => asserts value is T,
  path: string
): T | undefined {
  if (value === null || value === undefined) {
    return undefined;
  }
  guard(value, path);
  return value;
}

/**
 * Asserts internal API success response envelope (Kitsu backend)
 * Validates that data is an object and not null/undefined
 * @throws ContractError if response is not a valid success envelope
 */
export function assertInternalApiResponse(data: unknown, path: string = 'ApiResponse'): asserts data is Record<string, unknown> {
  if (data === null || data === undefined) {
    throw new ContractError(path, 'object', getTypeName(data));
  }
  assertObject(data, path);
}

/**
 * Asserts internal API array response (Kitsu backend)
 * Validates that data is an array and not null/undefined
 * @throws ContractError if response is not a valid array
 */
export function assertInternalArrayResponse(data: unknown, path: string = 'ApiResponse'): asserts data is unknown[] {
  if (data === null || data === undefined) {
    throw new ContractError(path, 'array', getTypeName(data));
  }
  assertArray(data, path);
}

/**
 * Asserts external API response shape (proxy/third-party APIs)
 * Minimal validation - only checks data is an object, not null/undefined
 * Does NOT enforce strict schema as external APIs are not guaranteed by backend
 * @throws ContractError if response is not an object
 */
export function assertExternalApiShape(data: unknown, path: string = 'ExternalApiResponse'): asserts data is Record<string, unknown> {
  if (data === null || data === undefined) {
    throw new ContractError(path, 'object', getTypeName(data));
  }
  assertObject(data, path);
}

/**
 * Asserts that a field exists in an object
 * Used for external API responses where we only validate presence, not type
 * @throws ContractError if field does not exist
 */
export function assertFieldExists<T extends Record<string, unknown>>(
  obj: T,
  field: string,
  path: string
): void {
  if (!(field in obj)) {
    throw new ContractError(`${path}.${field}`, 'field to exist', 'missing');
  }
}
