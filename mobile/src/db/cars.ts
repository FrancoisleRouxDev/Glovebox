/**
 * Local collection of confirmed cars, stored on the device with expo-sqlite.
 *
 * Migrations use SQLite's built-in `PRAGMA user_version` counter: each
 * numbered block runs once, in order, and then bumps the version.
 */
import type { SQLiteDatabase } from 'expo-sqlite';

import type { CarCandidate } from '@/api/types';

export const DATABASE_NAME = 'carspotter.db';
const DATABASE_VERSION = 1;

/** A row in the `cars` table. Field names match the API's snake_case style. */
export interface SavedCar {
  id: number;
  /** file:// URI of our own copy of the photo in the app's document directory. */
  photo_uri: string;
  make: string;
  model: string;
  generation_or_years: string | null;
  body_type: string | null;
  confidence: number;
  provider: string;
  visible_clues: string;
  /** ISO 8601 timestamp. */
  created_at: string;
}

export interface NewCar {
  photoUri: string;
  candidate: CarCandidate;
  provider: string;
  visibleClues: string;
}

/** Passed to <SQLiteProvider onInit>. Runs before any screen renders. */
export async function migrateDbIfNeeded(db: SQLiteDatabase): Promise<void> {
  const row = await db.getFirstAsync<{ user_version: number }>('PRAGMA user_version');
  let version = row?.user_version ?? 0;
  if (version >= DATABASE_VERSION) return;

  if (version === 0) {
    await db.execAsync(`
      PRAGMA journal_mode = 'wal';
      CREATE TABLE IF NOT EXISTS cars (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        photo_uri TEXT NOT NULL,
        make TEXT NOT NULL,
        model TEXT NOT NULL,
        generation_or_years TEXT,
        body_type TEXT,
        confidence REAL NOT NULL,
        provider TEXT NOT NULL,
        visible_clues TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
      );
    `);
    version = 1;
  }
  // Future schema changes go here as `if (version === 1) { ...; version = 2; }`.

  await db.execAsync(`PRAGMA user_version = ${DATABASE_VERSION}`);
}

/** Save a confirmed car and return its new id. */
export async function insertCar(db: SQLiteDatabase, car: NewCar): Promise<number> {
  const c = car.candidate;
  // `?` placeholders let SQLite escape values safely (never build SQL with string concatenation).
  const result = await db.runAsync(
    `INSERT INTO cars
       (photo_uri, make, model, generation_or_years, body_type, confidence, provider, visible_clues, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    car.photoUri,
    c.make,
    c.model,
    c.generation_or_years,
    c.body_type,
    c.confidence,
    car.provider,
    car.visibleClues,
    new Date().toISOString(),
  );
  return result.lastInsertRowId;
}

export function listCars(db: SQLiteDatabase): Promise<SavedCar[]> {
  return db.getAllAsync<SavedCar>('SELECT * FROM cars ORDER BY created_at DESC');
}

export function getCar(db: SQLiteDatabase, id: number): Promise<SavedCar | null> {
  return db.getFirstAsync<SavedCar>('SELECT * FROM cars WHERE id = ?', id);
}

export async function deleteCar(db: SQLiteDatabase, id: number): Promise<void> {
  await db.runAsync('DELETE FROM cars WHERE id = ?', id);
}
