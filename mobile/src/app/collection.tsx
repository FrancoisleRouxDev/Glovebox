/** Collection screen: every car the user has confirmed, newest first. */
import { router, useFocusEffect } from 'expo-router';
import { useSQLiteContext } from 'expo-sqlite';
import { useCallback, useState } from 'react';
import { FlatList, Image, Pressable, StyleSheet, Text, View } from 'react-native';

import { ErrorView, LoadingView, MessageView } from '@/components/ui';
import { listCars, type SavedCar } from '@/db/cars';
import { carName, formatConfidence, formatDate } from '@/lib/format';
import { colors, spacing } from '@/theme';

export default function CollectionScreen() {
  const db = useSQLiteContext();
  const [cars, setCars] = useState<SavedCar[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    listCars(db)
      .then(setCars)
      .catch((err: unknown) => {
        console.warn('Loading collection failed', err);
        setError('Could not load your collection.');
      });
  }, [db]);

  // Reload whenever the screen comes into view (e.g. after deleting a car).
  useFocusEffect(load);

  if (error) return <ErrorView message={error} onRetry={load} />;
  if (!cars) return <LoadingView message="Loading collection…" />;
  if (cars.length === 0) {
    return (
      <MessageView
        title="No cars yet"
        message="Snap a car and confirm a guess to start your collection."
        actionTitle="Scan a car"
        onAction={() => router.back()}
      />
    );
  }

  return (
    <FlatList
      data={cars}
      keyExtractor={(car) => String(car.id)}
      contentContainerStyle={styles.list}
      ItemSeparatorComponent={() => <View style={styles.separator} />}
      renderItem={({ item }) => (
        <Pressable
          style={({ pressed }) => [styles.row, pressed && { opacity: 0.6 }]}
          onPress={() => router.push({ pathname: '/car/[id]', params: { id: String(item.id) } })}
        >
          <Image source={{ uri: item.photo_uri }} style={styles.thumb} />
          <View style={styles.info}>
            <Text style={styles.name}>{carName(item)}</Text>
            {item.generation_or_years ? <Text style={styles.sub}>{item.generation_or_years}</Text> : null}
            <Text style={styles.sub}>
              {formatDate(item.created_at)} · {formatConfidence(item.confidence)} · {item.provider}
            </Text>
          </View>
        </Pressable>
      )}
    />
  );
}

const styles = StyleSheet.create({
  list: { padding: spacing.md },
  separator: { height: 1, backgroundColor: colors.border, marginVertical: spacing.sm },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  thumb: { width: 80, height: 60, borderRadius: 6, backgroundColor: colors.surface },
  info: { flex: 1 },
  name: { fontSize: 17, fontWeight: '600', color: colors.text },
  sub: { color: colors.muted, fontSize: 13, marginTop: 2 },
});
