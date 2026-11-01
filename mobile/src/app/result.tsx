/**
 * Result screen: uploads the photo, shows up to 3 guesses, and lets the user
 * confirm one (saved to the collection) or reject them all ("None of these").
 */
import { router, useLocalSearchParams } from 'expo-router';
import { useSQLiteContext } from 'expo-sqlite';
import { useCallback, useState } from 'react';
import { Image, ScrollView, StyleSheet, Text } from 'react-native';

import { ApiError, identifyCar } from '@/api/client';
import type { IdentifyResponse } from '@/api/types';
import { CandidateCard } from '@/components/CandidateCard';
import { Button, ErrorView, LoadingView, MessageView } from '@/components/ui';
import { insertCar } from '@/db/cars';
import { savePhotoPermanently } from '@/lib/photos';
import { useRequest } from '@/lib/useRequest';
import { colors, spacing } from '@/theme';

export default function ResultScreen() {
  const { uri } = useLocalSearchParams<{ uri: string }>();
  const db = useSQLiteContext();
  // Upload runs on mount and is cancelled if the user leaves before it finishes.
  const [state, retry] = useRequest(useCallback((signal: AbortSignal) => identifyCar(uri, signal), [uri]));
  const [selected, setSelected] = useState(0); // index into candidates; 0 = most likely
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  async function confirm(result: IdentifyResponse) {
    setSaving(true);
    setSaveError(null);
    try {
      const photoUri = await savePhotoPermanently(uri);
      await insertCar(db, {
        photoUri,
        candidate: result.candidates[selected],
        provider: result.provider,
        visibleClues: result.visible_clues,
      });
      // Replace this screen so "back" from the collection returns to Scan.
      router.replace('/collection');
    } catch (err) {
      console.warn('Saving car failed', err);
      setSaveError('Could not save this car. Please try again.');
      setSaving(false);
    }
  }

  if (!uri) return <ErrorView message="No photo was provided." />;
  if (state.status === 'loading') return <LoadingView message="Identifying car… this can take a few seconds." />;
  if (state.status === 'error') {
    const message = state.error instanceof ApiError ? state.error.message : 'Unexpected error. Please try again.';
    return <ErrorView message={message} onRetry={retry} />;
  }

  const result = state.data;
  if (!result.is_car || result.candidates.length === 0) {
    return (
      <ScrollView contentContainerStyle={styles.container}>
        <Image source={{ uri }} style={styles.photo} resizeMode="cover" />
        <MessageView
          title={result.is_car ? "Couldn't identify this car" : "That doesn't look like a car"}
          message={
            (result.visible_clues ? `What the AI saw: ${result.visible_clues}\n\n` : '') +
            'Try a clearer photo that shows the whole car, ideally from the front or side.'
          }
          actionTitle="Try another photo"
          onAction={() => router.back()}
        />
      </ScrollView>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Image source={{ uri }} style={styles.photo} resizeMode="cover" />

      <Text style={styles.heading}>Which one is it?</Text>
      {result.candidates.map((candidate, i) => (
        <CandidateCard
          key={`${candidate.make}-${candidate.model}-${i}`}
          candidate={candidate}
          rank={i + 1}
          selected={selected === i}
          onSelect={() => setSelected(i)}
        />
      ))}

      {result.visible_clues ? <Text style={styles.clues}>Clues: {result.visible_clues}</Text> : null}
      <Text style={styles.meta}>
        Answered by {result.provider} in {(result.latency_ms / 1000).toFixed(1)}s
      </Text>

      {saveError && <Text style={styles.error}>{saveError}</Text>}
      <Button title={saving ? 'Saving…' : 'Save to collection'} onPress={() => confirm(result)} disabled={saving} />
      <Button title="None of these" variant="secondary" onPress={() => router.back()} disabled={saving} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: spacing.md, paddingBottom: spacing.lg * 2, flexGrow: 1 },
  photo: { width: '100%', aspectRatio: 4 / 3, borderRadius: 10, backgroundColor: colors.surface },
  heading: { fontSize: 20, fontWeight: '600', color: colors.text, marginVertical: spacing.md },
  clues: { color: colors.text, marginTop: spacing.sm },
  meta: { color: colors.muted, fontSize: 13, marginTop: spacing.xs, marginBottom: spacing.sm },
  error: { color: colors.danger, marginTop: spacing.sm },
});
