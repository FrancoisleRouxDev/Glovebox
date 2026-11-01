/**
 * Root layout: opens the SQLite database (running migrations first) and sets
 * up a simple stack navigator. Every file in src/app/ is a screen.
 */
import { Stack } from 'expo-router';
import { SQLiteProvider } from 'expo-sqlite';
import { StatusBar } from 'expo-status-bar';

import { DATABASE_NAME, migrateDbIfNeeded } from '@/db/cars';

export default function RootLayout() {
  return (
    <SQLiteProvider databaseName={DATABASE_NAME} onInit={migrateDbIfNeeded}>
      <StatusBar style="dark" />
      <Stack>
        <Stack.Screen name="index" options={{ title: 'Scan a car' }} />
        <Stack.Screen name="result" options={{ title: 'Result' }} />
        <Stack.Screen name="collection" options={{ title: 'My collection' }} />
        <Stack.Screen name="car/[id]" options={{ title: 'Car' }} />
      </Stack>
    </SQLiteProvider>
  );
}
