import { db } from '@/db';
import { sql } from 'drizzle-orm';
import Journal from './journal';
export const dynamic = 'force-dynamic';
export default async function HomePage() {
  await db.execute(sql`select 1`);
  return <Journal />;
}
