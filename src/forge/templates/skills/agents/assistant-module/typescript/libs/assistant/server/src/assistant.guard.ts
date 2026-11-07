export function containsSecret(text: string): boolean {
  if (/\b(?:password|passcode|pin|one[ -]time[ -](?:code|password)|otp)["']?\s*(?:is\b|:|=)\s*\S+/i.test(text)) return true;
  for (const match of text.matchAll(/\d(?:[\d -]*\d)?/g)) {
    const groups = match[0].match(/\d+/g) ?? [];
    // A space can separate card groups or two cards. Check each group boundary
    // without taking a substring from a longer, unbroken number.
    for (let start = 0; start < groups.length; start++) {
      let digits = '';
      for (let end = start; end < groups.length; end++) {
        digits += groups[end];
        if (digits.length > 19) break;
        if (digits.length >= 13 && passesLuhn(digits)) return true;
      }
    }
  }
  return false;
}

function passesLuhn(digits: string): boolean {
  let sum = 0;
  for (let i = digits.length - 1, offset = 0; i >= 0; i--, offset++) {
    let digit = Number(digits[i]);
    if (offset % 2 === 1) { digit *= 2; if (digit > 9) digit -= 9; }
    sum += digit;
  }
  return sum % 10 === 0;
}
