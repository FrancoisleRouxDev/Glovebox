/**
 * One-line backend connection indicator. It catches the most common setup
 * mistake (a wrong EXPO_PUBLIC_API_URL) before you take a photo.
 */
import { Pressable, StyleSheet, Text } from 'react-native';

import { ApiError, getApiUrl, getHealth } from '@/api/client';
import { useRequest } from '@/lib/useRequest';
import { colors, spacing } from '@/theme';

export function BackendStatus() {
  const [state, retry] = useRequest(getHealth);

  let text: string;
  let color = colors.muted;
  if (state.status === 'loading') {
    text = `Checking backend at ${getApiUrl() ?? '(not set)'}…`;
  } else if (state.status === 'success') {
    const providers = state.data.providers;
    text = providers.length
      ? `Backend connected · ${providers.join(' → ')}`
      : 'Backend connected, but no AI provider keys are set';
    color = providers.length ? colors.success : colors.danger;
  } else {
    const message = state.error instanceof ApiError ? state.error.message : String(state.error);
    text = `${message} (tap to retry)`;
    color = colors.danger;
  }

  return (
    <Pressable onPress={retry} disabled={state.status === 'loading'} style={styles.bar}>
      <Text style={[styles.text, { color }]} numberOfLines={3}>
        {text}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  bar: { paddingHorizontal: spacing.md, paddingVertical: spacing.sm, backgroundColor: colors.surface },
  text: { fontSize: 13 },
});
