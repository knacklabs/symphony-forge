export function containsSecret(text: string): boolean {
  if (/\b(?:password|passcode|pin|one[ -]time[ -](?:code|password)|otp)\s*(?:is\b|:|=)\s*\S+/i.test(text)) return true;
  for (const match of text.matchAll(/(?<!\d)\d(?:[ -]?\d){12,}(?!\d)/g)) {
    const digits = match[0].replace(/\D/g, '');
    if (digits.length > 19) continue;
    let sum = 0;
    for (let i = digits.length - 1, offset = 0; i >= 0; i--, offset++) {
      let digit = Number(digits[i]);
      if (offset % 2 === 1) { digit *= 2; if (digit > 9) digit -= 9; }
      sum += digit;
    }
    if (sum % 10 === 0) return true;
  }
  return false;
}
