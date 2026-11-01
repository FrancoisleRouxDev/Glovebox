/**
 * Car detail screen: the saved photo and specs come from the local database.
 * The Wikipedia summary comes from the backend's /facts endpoint.
 */
import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useSQLiteContext } from 'expo-sqlite';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Alert, Image, Linking, ScrollView, StyleSheet, Text, View } from 'react-native';

import { ApiError, getFacts } from '@/api/client';
import { Button, ErrorView, LoadingView, MessageView } from '@/components/ui';
import { deleteCar, getCar, type SavedCar } from '@/db/cars';
import { carName, formatConfidence, formatDate } from '@/lib/format';
import { deletePhoto } from '@/lib/photos';
import { useRequest } from '@/lib/useRequest';
import { colors, spacing } from '@/theme';

type CarState = { status: 'loading' } | { status: 'missing' } | { status: 'error' } | { status: 'ok'; car: SavedCar };

export default function CarDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const db = useSQLiteContext();
  const [carState, setCarState] = useState<CarState>({ status: 'loading' });

  useEffect(() => {
    getCar(db, Number(id))
      .then((car) => setCarState(car ? { status: 'ok', car } : { status: 'missing' }))
      .catch((err: unknown) => {
        console.warn('Loading car failed', err);
        setCarState({ status: 'error' });
      });
  }, [db, id]);

  if (carState.status === 'loading') return <LoadingView message="Loading…" />;
  if (carState.status === 'error') return <ErrorView message="Could not load this car." />;
  if (carState.status === 'missing') {
    return <MessageView title="Car not found" actionTitle="Back" onAction={() => router.back()} />;
  }

  const { car } = carState;

  function confirmDelete() {
    Alert.alert('Remove car?', `${carName(car)} will be removed from your collection.`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Remove',
        style: 'destructive',
        onPress: async () => {
          await deleteCar(db, car.id);
          deletePhoto(car.photo_uri);
          router.back();
        },
      },
    ]);
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Stack.Screen options={{ title: carName(car) }} />
      <Image source={{ uri: car.photo_uri }} style={styles.photo} resizeMode="cover" />

      <Text style={styles.title}>{carName(car)}</Text>
      <View style={styles.specs}>
        <Spec label="Generation / years" value={car.generation_or_years ?? 'Unknown'} />
        <Spec label="Body type" value={car.body_type ?? 'Unknown'} />
        <Spec label="AI confidence" value={formatConfidence(car.confidence)} />
        <Spec label="Identified by" value={car.provider} />
        <Spec label="Spotted on" value={formatDate(car.created_at)} />
      </View>
      {car.visible_clues ? <Text style={styles.clues}>Clues: {car.visible_clues}</Text> : null}

      <Text style={styles.sectionTitle}>About this model</Text>
      <FactsSection make={car.make} model={car.model} />

      <Button title="Remove from collection" variant="danger" onPress={confirmDelete} />
    </ScrollView>
  );
}

function Spec({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.specRow}>
      <Text style={styles.specLabel}>{label}</Text>
      <Text style={styles.specValue}>{value}</Text>
    </View>
  );
}

/** Wikipedia summary with its own loading / error / not-found states. */
function FactsSection({ make, model }: { make: string; model: string }) {
  const [state, retry] = useRequest(
    useCallback((signal: AbortSignal) => getFacts(make, model, signal), [make, model]),
  );

  if (state.status === 'loading') {
    return <ActivityIndicator style={{ marginVertical: spacing.md }} color={colors.primary} />;
  }
  if (state.status === 'error') {
    const err = state.error;
    if (err instanceof ApiError && err.code === 'facts_not_found') {
      return <Text style={styles.muted}>No Wikipedia article found for this model.</Text>;
    }
    return (
      <View>
        <Text style={styles.muted}>{err instanceof ApiError ? err.message : String(err)}</Text>
        <Button title="Retry" variant="secondary" onPress={retry} />
      </View>
    );
  }
  const facts = state.data;
  return (
    <View>
      <Text style={styles.summary}>{facts.summary}</Text>
      <Text style={styles.link} onPress={() => Linking.openURL(facts.source_url)}>
        Source: Wikipedia – {facts.title}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: spacing.md, paddingBottom: spacing.lg * 2 },
  photo: { width: '100%', aspectRatio: 4 / 3, borderRadius: 10, backgroundColor: colors.surface },
  title: { fontSize: 24, fontWeight: '700', color: colors.text, marginTop: spacing.md },
  specs: { marginTop: spacing.sm },
  specRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: spacing.xs + 2,
    borderBottomWidth: 1,
    borderBottomColor: colors.surface,
  },
  specLabel: { color: colors.muted },
  specValue: { color: colors.text, fontWeight: '500', flexShrink: 1, textAlign: 'right', marginLeft: spacing.md },
  clues: { color: colors.text, marginTop: spacing.sm },
  sectionTitle: { fontSize: 18, fontWeight: '600', color: colors.text, marginTop: spacing.lg, marginBottom: spacing.sm },
  summary: { fontSize: 15, lineHeight: 22, color: colors.text },
  link: { color: colors.primary, marginTop: spacing.sm, marginBottom: spacing.md, textDecorationLine: 'underline' },
  muted: { color: colors.muted, marginBottom: spacing.sm },
});
