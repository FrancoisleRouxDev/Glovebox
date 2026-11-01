import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { CarCandidate } from '@/api/types';
import { carName, formatConfidence } from '@/lib/format';
import { colors, spacing } from '@/theme';

interface Props {
  candidate: CarCandidate;
  rank: number;
  selected: boolean;
  onSelect: () => void;
}

/** One guess on the Result screen. Tap to select it. */
export function CandidateCard({ candidate, rank, selected, onSelect }: Props) {
  const details = [candidate.generation_or_years, candidate.body_type].filter(Boolean).join(' · ');
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityState={{ selected }}
      onPress={onSelect}
      style={[styles.card, selected && styles.selected]}
    >
      <View style={styles.row}>
        <Text style={styles.name}>
          {rank}. {carName(candidate)}
        </Text>
        <Text style={styles.confidence}>{formatConfidence(candidate.confidence)}</Text>
      </View>
      {details ? <Text style={styles.details}>{details}</Text> : null}
      {/* Simple confidence bar. */}
      <View style={styles.barTrack}>
        <View style={[styles.barFill, { width: `${Math.round(candidate.confidence * 100)}%` }]} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    borderWidth: 2,
    borderColor: colors.border,
    borderRadius: 10,
    padding: spacing.md,
    marginBottom: spacing.sm,
    backgroundColor: colors.background,
  },
  selected: { borderColor: colors.primary, backgroundColor: '#eff6ff' },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  name: { fontSize: 17, fontWeight: '600', color: colors.text, flexShrink: 1 },
  confidence: { fontSize: 15, fontWeight: '600', color: colors.primary, marginLeft: spacing.sm },
  details: { color: colors.muted, marginTop: spacing.xs },
  barTrack: { height: 4, backgroundColor: colors.surface, borderRadius: 2, marginTop: spacing.sm },
  barFill: { height: 4, backgroundColor: colors.primary, borderRadius: 2 },
});
