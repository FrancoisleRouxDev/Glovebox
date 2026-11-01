/**
 * Small shared UI pieces: a button and the loading / error / message states
 * every backend-calling screen needs.
 */
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, spacing } from '@/theme';

interface ButtonProps {
  title: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'danger';
  disabled?: boolean;
}

export function Button({ title, onPress, variant = 'primary', disabled }: ButtonProps) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.button,
        variant === 'primary' && styles.primary,
        variant === 'secondary' && styles.secondary,
        variant === 'danger' && styles.danger,
        (pressed || disabled) && { opacity: disabled ? 0.4 : 0.7 },
      ]}
    >
      <Text style={[styles.buttonText, variant === 'secondary' && { color: colors.text }]}>{title}</Text>
    </Pressable>
  );
}

export function LoadingView({ message }: { message: string }) {
  return (
    <View style={styles.center}>
      <ActivityIndicator size="large" color={colors.primary} />
      <Text style={styles.message}>{message}</Text>
    </View>
  );
}

export function ErrorView({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <View style={styles.center}>
      <Text style={styles.title}>Something went wrong</Text>
      <Text style={styles.message}>{message}</Text>
      {onRetry && <Button title="Try again" onPress={onRetry} />}
    </View>
  );
}

interface MessageViewProps {
  title: string;
  message?: string;
  actionTitle?: string;
  onAction?: () => void;
}

/** Neutral full-screen message, e.g. "Not a car" or "Collection is empty". */
export function MessageView({ title, message, actionTitle, onAction }: MessageViewProps) {
  return (
    <View style={styles.center}>
      <Text style={styles.title}>{title}</Text>
      {message ? <Text style={styles.message}>{message}</Text> : null}
      {actionTitle && onAction && <Button title={actionTitle} onPress={onAction} />}
    </View>
  );
}

const styles = StyleSheet.create({
  button: {
    paddingVertical: 12,
    paddingHorizontal: spacing.md,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: spacing.sm,
  },
  primary: { backgroundColor: colors.primary },
  secondary: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border },
  danger: { backgroundColor: colors.danger },
  buttonText: { color: colors.primaryText, fontSize: 16, fontWeight: '600' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.lg, gap: spacing.sm },
  title: { fontSize: 20, fontWeight: '600', color: colors.text, textAlign: 'center' },
  message: { fontSize: 15, color: colors.muted, textAlign: 'center' },
});
