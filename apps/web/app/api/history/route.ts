import { NextResponse } from "next/server";
import { auth } from "@/core/lib/auth";
import { db } from "@/core/lib/db";
import { watchHistory } from "@/core/lib/schema";
import { eq, desc } from "drizzle-orm";

export const runtime = 'edge';

export async function GET(req: Request) {
  const session = await auth.api.getSession({
    headers: req.headers,
  });

  if (!session || !session.user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const history = await db.select()
      .from(watchHistory)
      .where(eq(watchHistory.userId, session.user.id))
      .orderBy(desc(watchHistory.updatedAt))
      .limit(100);

    return NextResponse.json({ success: true, history });
  } catch (error) {
    console.error("Failed to fetch history:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}

export async function POST(req: Request) {
  const session = await auth.api.getSession({
    headers: req.headers,
  });

  if (!session || !session.user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const body = await req.json();
    const { animeSlug, episode, timestampSec, durationSec, completed } = body;

    if (!animeSlug || episode === undefined) {
      return NextResponse.json({ error: "Missing required fields" }, { status: 400 });
    }

    const newRecord = await db.insert(watchHistory).values({
      userId: session.user.id,
      animeSlug,
      episode,
      timestampSec: timestampSec || 0,
      durationSec: durationSec || 0,
      completed: completed || false,
      updatedAt: new Date()
    }).onConflictDoUpdate({
      target: [watchHistory.userId, watchHistory.animeSlug, watchHistory.episode],
      set: {
        timestampSec: timestampSec || 0,
        durationSec: durationSec || 0,
        completed: completed || false,
        updatedAt: new Date()
      }
    }).returning();

    return NextResponse.json({ success: true, record: newRecord[0] });
  } catch (error) {
    console.error("Failed to sync history:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}