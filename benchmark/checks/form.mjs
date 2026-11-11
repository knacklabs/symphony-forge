import { addOrder, check, signIn } from './lib.mjs';

await check(async (page) => {
  await signIn(page);
  await addOrder(page, 'Corner Shop', '2099-01-01');
});
